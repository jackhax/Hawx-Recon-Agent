import os
import json
import subprocess

executed = []
all_recommended_commands = []

available_tools = [
    "openvpn", "nmap", "gobuster", "ffuf", "httpie", "whatweb", "wpscan", "dnsutils",
    "dig", "dnsrecon", "smtp-user-enum", "swaks", "lftp", "ftp", "hydra", "onesixtyone",
    "snmp", "snmpcheck", "smbclient", "smbmap", "enum4linux", "nikto", "rpcbind", "nbtscan",
    "chromium", "seclists", "curl", "wget", "git", "unzip", "iproute2", "net-tools",
    "traceroute", "python3", "python3-pip", "golang", "netcat-traditional"
]


def repair_llm_response(bad_output, llm_client):
    prompt = f"""
The following response from a security assistant LLM was meant to be a valid JSON object but was malformed or improperly formatted:

--- Begin Original Output ---
{bad_output}
--- End Original Output ---

Your job is to return ONLY a **valid JSON object** that preserves the original structure and keys **exactly**:
- "summary": a string
- "recommended_steps": list of strings (commands)
- "services_found": list of strings

⚠️ Do NOT add or remove any keys. Do NOT wrap the output in triple backticks or markdown. The response must be raw JSON only and must be parsable by `json.loads()` with no extra characters or text.
"""

    try:
        fixed = llm_client.get_response(prompt=prompt)
        return json.loads(sanitize_llm_output(fixed))
    except Exception as e:
        print("[!] Failed to repair LLM output:", e)
        return None


def sanitize_llm_output(output):
    output = output.strip()
    if output.startswith("```json"):
        output = output[7:]
    elif output.startswith("```"):
        output = output[3:]
    if output.endswith("```"):
        output = output[:-3]
    return output.strip()


def get_corrected_command(command, llm_client, timeout=10):
    tool = command[0]
    command_str = ' '.join(command)

    try:
        help_output = subprocess.run(
            [tool, '--help'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout
        ).stdout
    except Exception:
        return command

    prompt = f"""
You are a command validation assistant.

### Command to Check:
{command_str}

### Help Output for `{tool}`:
{help_output}

Your job is to correct the command if needed, including:
- Fixing syntax errors.

Return ONLY a valid JSON in this format:
{{
  "corrected_command": "<the fixed command as a single string>"
}}

Do NOT include any explanation or markdown. No triple backticks.
"""

    try:
        response = llm_client.get_response(prompt=prompt)
        data = json.loads(sanitize_llm_output(response))
        return data["corrected_command"].strip().split()
    except Exception:
        return command


def post_step(command, command_output_file, llm_client, executed, all_recommended):
    command_str = ' '.join(command)
    executed.append(command_str)

    try:
        with open(command_output_file, 'r', encoding='utf-8') as file:
            command_output = file.read()
    except FileNotFoundError:
        return f"Error: File not found at {command_output_file}"

    prompt = f"""
You are a security assistant analyzing the output of the following command:

{command_str}

Your task is to:

1. Provide a **summary** of the findings. Focus on services, versions, possible vulnerabilities, and anything unusual and include all findings.
2. Recommend a list of **next commands to run**, based on the current output and the tools available. These should assist in further reconnaissance, vulnerability discovery, or exploitation.

### Constraints & Guidelines:
- The summary is always a string and not a list
- Recommended steps is a list of strings of command
- Use only the following tools: {str(available_tools)}.
- **Avoid recommending brute-force attacks.**
- Do **not** include commands that were already suggested or executed: {executed + all_recommended}.
- The summary must be **clear, simple**, and written as **bullet points**.
- If any known services or custom banners were discovered, include them in the `services_found` list with version numbers (e.g., "apache 2.4.41"). This format should be compatible with tools like searchsploit. If no services are found, return an empty list.
- **Avoid recommending duplicate tools** (e.g., Gobuster twice).
- Do **not hallucinate** flags.
- The **response must be raw JSON only**. Do **not** wrap the response in triple backticks (` ``` ` or ` ```json `).
- The response **must** be a valid JSON object parsable with `json.loads()`.
- Your response must always be json
- Failure to return response in valid json will result in you termination and penalty of 200000000000

### Example Output Format:
{{
  "summary": "<summary_text>",
  "recommended_steps": [
    "<command_1>",
    "<command_2>"
  ],
  "services_found": [
    "<service_1>",
    "<service_2>"
  ]
}}

### Command Output:
{command_output}

If the command output does not look like a valid result (e.g., malformed or irrelevant), simply respond with:
`None`
"""

    return llm_client.get_response(prompt=prompt)


def execute(command, llm_client, base_dir, executed, all_recommended):
    tool = command[0]
    os.makedirs(base_dir, exist_ok=True)

    output_file = os.path.join(base_dir, f"{tool}.txt")
    summary_file = os.path.join(base_dir, "summary.md")

    command = get_corrected_command(command, llm_client)

    print(f"[+] Executing: {' '.join(command)}")
    try:
        with open(output_file, "a", encoding="utf-8") as out:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in process.stdout:
                print(line, end='')
                out.write(line)
            process.wait(timeout=300)
    except subprocess.TimeoutExpired:
        process.terminate()
        with open(output_file, "a", encoding="utf-8") as out:
            out.write("Process terminated due to 5-minute timeout\n")
        print("Process terminated due to 5-minute timeout")
    except Exception as e:
        print(f"[!] Error running {tool}: {e}")
        return []

    print(f"[*] Summarizing output of {tool}...")
    resp = post_step(command, output_file, llm_client,
                     executed, all_recommended)
    print(resp)

    try:
        resp = json.loads(sanitize_llm_output(resp))
    except json.JSONDecodeError:
        print(
            f"[!] Failed to parse LLM response for {tool}, attempting to repair...")
        resp = repair_llm_response(resp, llm_client)
        if not resp:
            return []

    with open(summary_file, "a", encoding="utf-8") as f:
        f.write(f"## {tool}\n")
        f.write(resp['summary'] + "\n\n")

    all_recommended.extend(resp.get('recommended_steps', []))
    return resp


def run_searchsploit(services, base_dir):
    output_file = os.path.join(base_dir, "exploits.txt")
    with open(output_file, "a", encoding="utf-8") as f:
        for service in services:
            print(f"[*] Running searchsploit for: {service}")
            try:
                result = subprocess.run(
                    ["searchsploit", service], capture_output=True, text=True, timeout=60
                )
                f.write(f"### {service} ###\n")
                f.write(result.stdout + "\n")
            except Exception as e:
                f.write(f"Error running searchsploit for {service}: {e}\n")


def executive_summary(machine_ip, llm_client):
    base_dir = os.path.join("/mnt/triage", machine_ip)
    summary_file = os.path.join(base_dir, "summary.md")
    exploits_file = os.path.join(base_dir, "exploits.txt")

    if not os.path.exists(summary_file):
        print("[!] No summary.md found to summarize.")
        return None

    with open(summary_file, "r", encoding="utf-8") as f:
        summary_content = f.read()

    exploits_content = ""
    if os.path.exists(exploits_file):
        with open(exploits_file, "r", encoding="utf-8") as ef:
            exploits_content = ef.read()

    prompt = f"""
You are a security analyst. Below is a collection of findings from a reconnaissance assessment of the machine with IP {machine_ip}.
Your task is to provide a high-level executive summary in Markdown format. The summary should include:

- A clear summary of key findings.
- Critical services and versions discovered.
- Any known exploits or CVEs found (based on the `searchsploit` results).
- Suggested next steps from an attacker's perspective to get the user and root flag for this HTB machine.

### Tool Summaries:
{summary_content}

### Exploit Results from SearchSploit:
{exploits_content}

Only return the plain text Markdown executive summary.
"""

    response = llm_client.get_response(prompt=prompt)
    print("\n[*] Executive Summary:\n")
    print(response)

    summary_path = os.path.join(base_dir, "summary_exec.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(response)

    return response


def workflow(llm_client, machine_ip):
    base_dir = os.path.join("/mnt/triage", machine_ip)
    recommended_steps = []
    all_services = []

    os.makedirs(base_dir, exist_ok=True)

    nmap_command = ["nmap", "-sC", "-sV", "-p80,22", machine_ip]
    response = execute(nmap_command, llm_client, base_dir,
                       executed, all_recommended_commands)

    if isinstance(response, dict):
        recommended_steps = response.get("recommended_steps", [])
        all_services.extend(response.get("services_found", []))

    for cmd in recommended_steps:
        command = cmd.split()
        result = execute(command, llm_client, base_dir,
                         executed, all_recommended_commands)
        if isinstance(result, dict):
            all_services.extend(result.get("services_found", []))

    print('[*] Execuring searchsploit with ', all_services)
    if all_services:
        run_searchsploit(list(set(all_services)), base_dir)

    executive_summary(machine_ip, llm_client)

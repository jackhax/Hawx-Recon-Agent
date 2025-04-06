import os
import json
import subprocess

executed = []
available_tools = ["openvpn", "nmap", "gobuster", "nikto", "ffuf", "httpie", "whatweb", "wpscan", "dnsutils", "dig", "dnsrecon", "smtp-user-enum", "swaks", "lftp", "ftp", "hydra", "onesixtyone", "snmp", "snmpcheck",
                   "smbclient", "smbmap", "enum4linux", "rpcbind", "nbtscan", "chromium", "seclists", "curl", "wget", "git", "unzip", "iproute2", "net-tools", "traceroute", "python3", "python3-pip", "golang", "netcat-traditional"]


def post_step(command, command_output_file, llm_client, executed):
    command_str = ' '.join(command)
    executed.append(command_str)

    try:
        with open(command_output_file, 'r') as file:
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
- Use only the following tools: {str(available_tools)}.
- **Avoid recommending brute-force attacks.**
- Do **not** include commands that were already executed: {executed}.
- The summary must be **clear, simple**, and written as **bullet points**.
- If any known services or custom banners were discovered, include them in the `services_found` list with version numbers (e.g., "apache 2.4.41"). This format should be compatible with tools like searchsploit. If no services are found, return an empty list.
- **Avoid recommending duplicate tools** (e.g., Gobuster twice).
- Use flags to **suppress debug or verbose output**, but **only if the tool supports it**.
  - Examples:
    - ffuf: use `-s` or `-silent`
    - httpx: use `-silent`
    - nikto: use `-nointeractive`
    - wpscan: use `--no-banner`
    - whatweb: use `--quiet`
  - Do **not hallucinate** flags. Only include flags that are officially supported by the tool.
- The **response must be raw JSON only**. Do **not** wrap the response in triple backticks (``` or ```json).
  - ❌ Incorrect:
    ```json
    {{
      "summary": "...",
      ...
    }}
    ```
  - ✅ Correct:
    {{
      "summary": "...",
      ...
    }}
- The response **must** be a valid JSON object parsable with `json.loads()`.

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
None
"""

    return llm_client.get_response(prompt=prompt)


def execute(command, llm_client, base_dir, executed):
    tool = command[0]
    os.makedirs(base_dir, exist_ok=True)

    output_file = os.path.join(base_dir, f"{tool}.txt")
    summary_file = os.path.join(base_dir, "summary.md")

    print(f"[+] Executing: {' '.join(command)}")
    try:
        with open(output_file, "w") as out:
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

            for line in process.stdout:
                print(line, end='')
                out.write(line)

            process.wait(timeout=300)
    except subprocess.TimeoutExpired:
        process.terminate()
        with open(output_file, "a") as out:
            out.write("Process terminated due to 5-minute timeout\n")
        print("Process terminated due to 5-minute timeout")
    except Exception as e:
        print(f"[!] Error running {tool}: {e}")
        return [], []

    print(f"[*] Summarizing output of {tool}...")
    resp = post_step(command, output_file, llm_client, executed)
    print(resp)

    try:
        parsed = json.loads(resp)
    except json.JSONDecodeError:
        print(f"[!] Failed to parse LLM response for {tool}")
        return [], []

    with open(summary_file, "a") as f:
        f.write(f"## {tool}\n")
        f.write(parsed['summary'] + "\n\n")

    return parsed.get('recommended_steps', []), parsed.get('services_found', [])


def executive_summary(machine_ip, llm_client):
    base_dir = os.path.join("/mnt/triage", machine_ip)
    summary_file = os.path.join(base_dir, "summary.md")

    if not os.path.exists(summary_file):
        print("[!] No summary.md found to summarize.")
        return None

    with open(summary_file, "r") as f:
        content = f.read()

    prompt = f"""
You are a security analyst. Below is a collection of tool-based summaries from a recon test against the machine with IP {machine_ip}.
Your task is to provide a high-level executive summary that highlights the most critical findings, affected services, and possible next actions from a decision-maker's point of view.

### Tool Summaries:
{content}

Only return the plain text executive summary.
"""
    response = llm_client.get_response(prompt=prompt)
    print("\n[*] Executive Summary:\n")
    print(response)
    summary_path = os.path.join(base_dir, "summary_exec.md")
    with open(summary_path, "w") as f:
        f.write(response)
    return response


def run_searchsploit(services, base_dir):
    output_file = os.path.join(base_dir, "exploits.txt")
    with open(output_file, "w") as f:
        for service in services:
            print(f"[*] Running searchsploit for: {service}")
            try:
                result = subprocess.run(
                    ["searchsploit", service], capture_output=True, text=True, timeout=60)
                f.write(f"### {service} ###\n")
                f.write(result.stdout + "\n")
            except Exception as e:
                f.write(f"Error running searchsploit for {service}: {e}\n")


def workflow(llm_client, machine_ip):
    base_dir = os.path.join("/mnt/triage", machine_ip)
    recommended_steps = []
    all_services = []

    # Step 1: Run Nmap scan
    nmap_command = ["nmap", "-sC", "-sV", "-p80,22", machine_ip]
    steps, services = execute(nmap_command, llm_client, base_dir, executed)
    recommended_steps.extend(steps)
    all_services.extend(services)

    # Step 2: Execute each recommended step from LLM
    for command_str in recommended_steps:
        command = command_str.split()
        try:
            steps, services = execute(command, llm_client, base_dir, executed)
            recommended_steps.extend(steps)
            all_services.extend(services)
        except Exception as e:
            print(f"[*] Failed to execute command: {command} -> {e}")

    # Step 3: Run searchsploit on discovered services
    if all_services:
        run_searchsploit(list(set(all_services)), base_dir)

    # Step 4: Generate Executive Summary
    executive_summary(machine_ip, llm_client)

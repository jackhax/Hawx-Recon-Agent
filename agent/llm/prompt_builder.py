"""
Prompt builder utilities for Hawx Recon.

Provides functions to construct prompts for LLM-based summarization, command recommendation,
JSON repair, deduplication, and executive summary generation.
"""


def _build_prompt_post_step(
    available_tools,
    command_str,
    command_output,
    previous_commands=None,
    similar_context=None,
):
    previous_commands = previous_commands or []
    previous_commands_str = "\n".join(previous_commands)
    similar_context_str = (
        f"\n\n# Similar Previous Commands and Summaries:\n{similar_context}"
        if similar_context
        else ""
    )
    return f"""
You are a cybersecurity assistant analyzing the result of the following recon command:

{command_str}
{similar_context_str}

---

### 🛠️ Pentesting Workflow Template:

1. **Initial Reconnaissance**
   - Identify live hosts, open ports, and running services (e.g., nmap full scan, ping sweep).
   - Detect service versions and banners (e.g., nmap -sV, whatweb, banner grabbing).
   - Map the attack surface: enumerate domains, subdomains, and virtual hosts (vhosts).

2. **Service Enumeration**
   - For each discovered service/port, enumerate in depth:
     - **Web**: Directory/file brute-forcing (gobuster, feroxbuster), virtual host discovery (gobuster vhost mode), tech fingerprinting (whatweb, wappalyzer), robots.txt, .git, config files, admin panels, login pages, and custom endpoints.
     - **FTP/SMB/NFS**: Anonymous login, share listing, file download, version checks, user enumeration, null sessions.
     - **SSH/Telnet**: Banner grabbing, weak/default credentials, version checks.
     - **Mail (SMTP/POP3/IMAP)**: VRFY/EXPN/RCPT enumeration, open relay, user enumeration, version checks.
     - **DNS**: Zone transfers, subdomain brute-forcing, record enumeration.
     - **SNMP**: Public community string, version, walk, user enumeration.
     - **Other**: Enumerate all detected services with appropriate tools and techniques.

3. **Vulnerability Identification**
   - For each service/version, search for known vulnerabilities (e.g., searchsploit, CVE databases).
   - Check for default/weak credentials, misconfigurations, outdated software, and exposed sensitive files.
   - Correlate banners and version info with public exploits.
   - Identify potential attack vectors (e.g., file upload, command injection, LFI/RFI, SQLi, XSS, SSRF, etc.).

4. **Exploitation (if in scope)**
   - Attempt exploitation only if a clear vulnerability is identified and exploitation is permitted.
   - Use public exploits, default creds, or misconfigurations to gain access.
   - Always show proof/evidence of exploitation attempts.

5. **Post-Exploitation (if applicable)**
   - Enumerate further for privilege escalation, lateral movement, or data exfiltration.
   - Gather additional information from compromised services.

6. **Reporting**
   - Summarize all findings, evidence, and recommended next steps.
   - Clearly link each finding to supporting output and tool results.

---

**Special Guidance:**
- If the server header or banner indicates nginx, and the root response appears empty, default, or forbidden — strongly consider recommending virtual host enumeration.
- Use: `gobuster vhost -u http://<ip> -w /usr/share/seclists/Discovery/DNS/namelist.txt`

---

### 🎯 Tasks:

1. **Summarize the output**: Provide a concise, accurate summary of the findings — include services, endpoints, versions, banners, subdomains, exposed files, misconfigs, or anything notable.
2. **Show proof**: For each finding, include supporting output like banners, credentials, hashes, file paths, or IPs. Do not make vague statements without quoting evidence from the output.
3. **Recommend next steps**: Based only on the current output, suggest further recon or exploit commands. Each must yield meaningful new output.
4. **Extract services for searchsploit**: From the output, extract valid 'name version' pairs (e.g., 'apache 2.4.41', 'phpmyadmin 5.1.0'). Generic terms or tool banners must be excluded.

---

### 🔒 Constraints:

- The summary must be a plain string.
- `recommended_steps` must be a list of valid shell commands.
- Use only from these tools: {str(available_tools)}.
- Do not suggest:
  - Any previously executed command:
{previous_commands_str}
  - Commands that clone, download, or save output without displaying it.
  - Another nmap scan unless it uses `-sC -sV -p-`.
  - Brute-force attacks or password spraying.
  - Tools or flags not clearly applicable to the findings.

- All commands must print output to the terminal.
  - If a command writes to a file (e.g., using `-o`, `>`, or `tee`), it must be followed by `&& cat <file>`, `&& head <file>`, or `&& ls -lah <file>` to show results in stdout.
  - If a command performs a background task or has no output, omit it.

- If a tool requires a wordlist, it must come from:
    - /usr/share/seclists/Discovery/Web-Content/big.txt
    - /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt
    - /usr/share/seclists/Discovery/DNS/namelist.txt
    - /usr/share/seclists/Usernames/top-usernames-shortlist.txt
    - /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt

---

### 🧠 Intelligence Rules:

- Do not recommend commands that offer no additional insight beyond previous output.
- Retain tools with different probing styles **only if** they extract new information.
- Always keep commands that probe new paths, subdomains, or resources.
- Treat `.git`, `robots.txt`, `config.zip`, and `/server-status` as high-priority targets unless fully downloaded and printed.

---

### 📤 Output Format (strict):

Respond with this **raw JSON object** only:

{{
        "summary": "<string>",
  "recommended_steps": ["<command1>", "<command2>", "..."],
  "services_found": ["apache 2.4.41", "phpmyadmin 5.1.0"]
}}

- Do not include markdown, code blocks, or triple backticks.
- Output must be directly parseable by `json.loads()`.
- Do not include generic services like `http`, `ftp`, or `ssh` unless version numbers or banners are present.

---

### 📦 Command Output:
{command_output}
"""


def _build_prompt_exec_summary(machine_ip, summary_content, exploits_content):
    """Build prompt for executive summary generation."""
    return f"""
    You are a security analyst. Below is a collection of findings from a reconnaissance assessment of the machine with IP {machine_ip}.
    Your task is to provide a very detailed executive summary in Markdown format. The summary should include:

    - A clear summary of key findings.
        - Include direct evidence from tool outputs for each finding
        - Quote specific banners, headers, response data, or other proof
    - Critical services and versions discovered.
        - Include the exact version strings, banners, and where they were found
        - Quote the specific tool output that revealed each service
    - Any known exploits or CVEs found (based on the `searchsploit` results).
        - Include the exploit titles and IDs
        - Quote the relevant searchsploit output
    - Suggested next steps from an attacker's perspective to get the user and root flag for this HTB machine.
        - Do not suggest repeated steps
        - Base suggestions on concrete evidence from the reconnaissance
    - Support all findings with relevant evidence and quotes from the tool outputs

    ### Tool Summaries:
    {summary_content}

    ### Exploit Results from SearchSploit:
    {exploits_content}

    Only return the plain text Markdown executive summary.
    If any service found, mention where it was found and how it was used if possible.
    """


def _build_prompt_json_repair(bad_output):
    """Build prompt to repair malformed JSON output from LLM."""
    return f"""
    The following response from a security assistant LLM was meant to be a valid JSON object but was malformed or improperly formatted:

    --- Begin Original Output ---
    {bad_output}
    --- End Original Output ---

    Your job is to return ONLY a **valid JSON object** that preserves the original structure and keys **exactly**

    Do NOT add or remove any keys. Do NOT wrap the output in triple backticks or markdown. The response must be raw JSON only and must be parsable by `json.loads()` with no extra characters or text.
    """


def _build_prompt_deduplication(current_layer, prior_layers):
    return f"""
You are an LLM assistant optimizing reconnaissance workflows.

---

### 🎯 Objective:
From the list of **Current Layer Commands**, return only the most **informative, distinct, and useful commands** that have **not already been functionally covered** by any commands in **Prior Layers**.

---

### 🧠 Deduplication Strategy:

1. **Functional Redundancy Check (Critical):**
   - Discard commands that probe the same underlying resource, service, or functionality as any command in prior layers.
   - Consider functional overlap across different input formats (IP vs domain), different tools (e.g., scanner A vs B), or minor flag variations.
   - Two commands using different tools or syntax are still considered redundant if they are expected to produce equivalent output.

2. **Usefulness Filtering:**
   - Discard commands known to repeatedly fail, produce no output, or yield non-actionable results for this target class.
   - Discard commands that over-enumerate (e.g., repeating exhaustive scans over hosts already thoroughly probed).
   - Only retain commands likely to return **new, relevant, or deeper** information.

3. **Value Contribution:**
   - Each retained command must provide **new intelligence** not covered earlier — such as targeting new protocols, new services, new sub-resources, or more advanced discovery methods.
   - Avoid repeating commands across layers unless the context or intent clearly changes the expected outcome.

---

### Inputs:
- **Current Layer Commands:**  
{current_layer}  
\nBREAK
- **Prior Layer Commands:**  
{prior_layers}  
\nBREAK

---

### ✅ Output Format:
Return a **valid JSON** object as follows:

{{
  "deduplicated_commands": ["<command_1>", "<command_2>", "..."]
}}

⚠️ Constraints:
- Return only raw JSON — no markdown, explanation, or comments.
- Ensure output is strictly valid for `json.loads()` with no surrounding text.
- Limit to **a maximum of 32 commands**.
- Any command writing to a file must include a `&& cat <file>` suffix to show results
- Do not include commands that show no stdout output
"""


def _build_prompt_post_step_chunked(available_tools, command_str, chunk, prev_summary):
    """Build prompt for chunked post-step LLM summarization."""
    return f"""
You are a security assistant helping analyze the output of the command: {command_str}

This is a continuation of a multi-part output. Your job is to update the existing summary using the new chunk of command output provided below.

### Previous Summary:
{prev_summary or "[None yet]"}

### New Output Chunk:
{chunk}

---

    ### Constraints & Guidelines:
    - The summary is always a string and not a list
    - Recommended steps is a list of strings of command
    - Use only the following tools: {str(available_tools)}.
    - **Avoid recommending brute-force attacks.**
    - The summary must be **clear and simple**.
    - If any known services or custom banners were discovered, include them in the `services_found` list with version numbers (e.g., "apache 2.4.41"). This format should be compatible with tools like searchsploit. If no services are found, return an empty list.
    - **Avoid recommending duplicate tools** (e.g., Gobuster twice).
    - Do **not hallucinate** flags.
    - The **response must be raw JSON only**. Do **not** wrap the response in triple backticks (` ``` ` or ` ```json `).
    - The response **must** be a valid JSON object parsable with `json.loads()`.
    - Your response must always be json
    - Failure to return response in valid json will result in you termination and penalty of 200000000000
    - The recommended commands should be executable
    - Do not recommend nmap scans unless they are completely exhaustive of nmap -sC -sV -p- target
    If any tools require worldlist, do not hallucinate wordlists and use only from the following:
    Seclists path: /usr/share/seclists"
    #                Big.txt: /usr/share/seclists/Discovery/Web-Content/big.txt"
    #                FTP: /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt" 
    #                DNS: /usr/share/seclists/Discovery/DNS/namelist.txt"
    #                Usernames: /usr/share/seclists/Usernames/top-usernames-shortlist.txt"
    #                Passwords: /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt"


You must return a valid JSON object with the following structure:
    ### Example Output Format:
    {{
    "summary": "<summary_text>",
    "recommended_steps": [
        "<command_1> --flag --flag --flag -f",
        "<command_2> --flag --flag --flag -f",
        "command_3 --flag --flag --flag -f"
        ...
    ],
    "services_found": [
        "<service_1>",
        "<service_2>"
    ]
    }}

⚠️ Constraints:
- Only return the raw JSON, no explanations, no markdown.
- The response must be compatible with `json.loads()`.
- The output must preserve the structure and key names exactly.
"""


def _build_prompt_exec_summary_chunked(machine_ip, chunk, prev_summary):
    """Build prompt for chunked executive summary generation."""
    return f"""
You are a cybersecurity analyst working on an executive summary for the recon of machine {machine_ip}.

Below is a new chunk of tool output or exploit results. Update and refine the executive summary based on it.

### Current Executive Summary So Far:
{prev_summary or '[None yet]'}

### New Chunk to Incorporate:
{chunk}

---

Your updated output must be a complete, detailed but crisp Markdown executive summary.
Only return the Markdown summary. Do not include any additional commentary or formatting.
Try to intelligently identify false positives and remove them from the summary. Ex: searchsploit results for apache and ssh are often false positives and should be removed from the summary.
Return only the plain text Markdown executive summary.
    - A clear summary of key findings.
    - Critical services and versions discovered.
    - Any known exploits or CVEs found (based on the `searchsploit` results).
    - Suggested next steps from an attacker's perspective to get the user and root flag for this HTB machine.
        - Do not suggest repeated steps
    - Anything else you see fit to include

"""

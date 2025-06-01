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
    """Build prompt for post-step LLM summarization and recommendation, with DRY logic, proof, searchsploit service extraction, and similar context."""
    previous_commands = previous_commands or []
    previous_commands_str = "\n".join(previous_commands)
    similar_context_str = (
        f"\n\n# Similar Previous Commands and Summaries (for context):\n{similar_context}"
        if similar_context
        else ""
    )
    return f"""
You are a security assistant analyzing the output of the following command:

{command_str}
{similar_context_str}

Your task is to:

1. Provide a **detailed, accurate summary** of all findings — including visible services, endpoints, versions, banners, and any unusual behavior or hints toward vulnerabilities.
2. **Include proof or evidence for each key finding in the summary.** This could be an IOC (Indicator of Compromise), a concrete value, a banner, a file path, a subdomain, a hash, a credential, or any other direct indicator from the command output. The summary should not just state what was found, but also show a snippet or value from the output as proof.
3. Recommend a list of **next actionable commands** that further reconnaissance, vulnerability discovery, or exploitation — strictly based on this output.
4. **Extract and output service names and versions in a format suitable for use with searchsploit.** Do NOT output random strings, generic names, or tool banners. Only output real software/service names (e.g., 'apache 2.4.41', 'nginx 1.18.0', 'phpmyadmin 5.1.0', 'vsftpd 3.0.3'). If no valid service is found, leave the list empty.

---

### Constraints & Guidelines:

- The summary must be a **plain string**, not a list.
- `recommended_steps` must be a **list of executable commands**, each string a valid shell command.
- Use only from these tools: {str(available_tools)}.
- Do **not** suggest brute-force attacks.
- Do **not** hallucinate or fabricate flags or tool features.
- Do **not** suggest commands unless directly supported by current findings.
- If **multiple tools probe the same service differently**, recommend all **if each yields new insights** (e.g., `dirb` and `ffuf` can coexist).
- Prefer **breadth and depth over tool uniqueness** — retain diverse tools **unless exact redundancy is confirmed**.
- All commands must **print useful output directly to the console**. Do **not** recommend commands that only download files, save output to files, or require manual file inspection. If a command saves output to a file, it must include a follow-up command (like `cat` or `grep`) to print the result to the console.
- Do **not** recommend commands like `wget`, `curl -O`, or `git clone` unless the output is printed to the console.
- Do not suggest another `nmap` scan unless it covers **full TCP port + service/version detection** (`-sC -sV -p-`).
- If a tool requires a wordlist, use only from:
    - `/usr/share/seclists/Discovery/Web-Content/big.txt`
    - `/usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt`
    - `/usr/share/seclists/Discovery/DNS/namelist.txt`
    - `/usr/share/seclists/Usernames/top-usernames-shortlist.txt`
    - `/usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt`
- **Do not suggest any command that has already been executed.** Here is a list of previously executed commands (do not repeat any of these):
{previous_commands_str}
---

### Critical Logic:

- Do **not remove** any command that contributes **unique coverage or intelligence** — even if it's similar in purpose.
- Treat **targeted probes** (like `.git`, `robots.txt`, `config.zip`, `/server-status`, etc.) as **high-signal** unless already fully retrieved.
- **Never drop commands that scan new paths, test specific endpoints, or involve targeted enumeration**.

---

### Output Requirements:

- Respond with a single, valid JSON object. Must include:
    - `"summary"`: short string summarizing findings, with proof/evidence for each key finding
    - `"recommended_steps"`: list of command strings
    - `"services_found"`: list of service names and versions suitable for searchsploit (e.g., 'apache 2.4.41', 'nginx 1.18.0'). Do NOT include random strings, generic names, or tool banners.
- Do **not** include markdown, comments, or explanations.
- Response **must be parseable by `json.loads()`**.
- Failure to follow format results in termination and a penalty of `200000000000`.
- Do **not** provide common services like https, ssh, ftp, or http unless they have specific version numbers or banners.
---

### Command Output:
{command_output}
"""


def _build_prompt_exec_summary(machine_ip, summary_content, exploits_content):
    """Build prompt for executive summary generation."""
    return f"""
    You are a security analyst. Below is a collection of findings from a reconnaissance assessment of the machine with IP {machine_ip}.
    Your task is to provide a very detailed executive summary in Markdown format. The summary should include:

    - A clear summary of key findings.
    - Critical services and versions discovered.
    - Any known exploits or CVEs found (based on the `searchsploit` results).
    - Suggested next steps from an attacker's perspective to get the user and root flag for this HTB machine.
        - Do not suggest repeated steps
    - Anything else you see fit to include

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

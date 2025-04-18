def _build_prompt_post_step(available_tools, command_str, command_output):
    return f"""
    You are a security assistant analyzing the output of the following command:

    {command_str}

    Your task is to:

    1. Provide a **Detailed summary** of the findings. Focus on services, versions, possible vulnerabilities, and anything unusual and include all findings.
    2. Recommend a list of **next commands to run**, based on the current output and the tools available. These should assist in further reconnaissance, vulnerability discovery, or exploitation.

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
    - Every command you recommend should be directly related to a service discovered in nmap's scan. Do not make assumptions

    If any tools require worldlist, do not hallucinate wordlists and use only from the following:
        Seclists path: /usr/share/seclists"
    #                Big.txt: /usr/share/seclists/Discovery/Web-Content/big.txt"
    #                FTP: /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt"
    #                DNS: /usr/share/seclists/Discovery/DNS/namelist.txt"
    #                Usernames: /usr/share/seclists/Usernames/top-usernames-shortlist.txt"
    #                Passwords: /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt"

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

    ### Command Output:
    {command_output}
    """


def _build_prompt_exec_summary(machine_ip, summary_content, exploits_content):
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
    You are a cybersecurity assistant tasked with deduplicating and normalizing a list of command-line recon commands.

    ### Current Layer Commands:
    {current_layer}

    ### Previously Executed or Recommended Commands:
    {prior_layers}

    ---

    ### Your Responsibilities:
        1. Treat the current list of commands as a draft. Your job is to trim it down to only the most useful and non-redundant entries.
        2. Exclude any command that has already appeared in a previous layer, even if modified slightly. Prior usage disqualifies it from this layer unless explicitly requested.
        3. Identify commands that achieve similar outcomes using different tools or parameters. Keep only one — the most capable, general, or reliable version — and remove the rest.
        4. If multiple commands target the same protocol, port, or endpoint, discard the ones with narrower scope or redundant intent.
        5. Commands should not repeat the same type of enumeration in every layer. Prioritize novelty and eliminate repetition of generic scans.
        6. Scanning commands that differ only in output format, verbosity, or timing options are not considered unique. Filter them out.
        7. Ensure that every command in the final list contributes something distinct. If a command does not expand overall coverage in a meaningful way, it should be removed.
    ---

    ### Output Format (must be valid JSON):
    {{
    "deduplicated_commands": ["<command_1 --some_flag value>", "<command_2 --some_flag value>", "..."]
    }}

    ⚠️ Constraints:
    - Do **not** wrap the JSON output in triple backticks or markdown.
    - Do **not** include any explanatory text.
    - The response **must** be valid JSON and parsable by `json.loads()` with **no extra characters or formatting**.
    - Any failure to comply will result in termination and a penalty of 200000000000.
    - Avoid malformed commands like curlhttp127.0.0.1

    Additional information:
    #       For tools that use wordlists, do not hallucinate wordlists, ony use one from below
    #             Seclists path: /usr/share/seclists"
    #                Big.txt: /usr/share/seclists/Discovery/Web-Content/big.txt"
    #                FTP: /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt"
    #                DNS: /usr/share/seclists/Discovery/DNS/namelist.txt"
    #                Usernames: /usr/share/seclists/Usernames/top-usernames-shortlist.txt"
    #                Passwords: /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt"

    Return only the final deduplicated current commands list in JSON format.
    """


def _build_prompt_post_step_chunked(available_tools, command_str, chunk, prev_summary):
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

"""

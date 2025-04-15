import json
import os
import re
import requests
from records import Records


class LLMClient:
    def __init__(
        self, api_key=None, provider=None, model=None, base_url=None, ollama_host=None, context_length=8192
    ):
        if not provider or not model:
            raise ValueError("Both provider and model must be specified.")

        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.host = ollama_host

        self.context_length = context_length or 8192

        records = Records()
        self.available_tools = records.available_tools

    # ========== Utility Methods ==========

    def _sanitize_llm_output(self, output):
        output = output.strip()
        if output.startswith("```json"):
            output = output[7:]
        elif output.startswith("```"):
            output = output[3:]
        if output.endswith("```"):
            output = output[:-3]
        return output.strip()

    def truncate_to_tokens(self, text, max_tokens):
        tokens = re.findall(r"\w+|\S", text)
        return "".join(tokens[:max_tokens])

    def _build_chat_payload(self, prompt):
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _build_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ========== Prompt Builders ==========

    # def _build_prompt_command_correction(self, command_str, help_output):
    #     return f"""
    # You are a command validation assistant.

    # ### Command to Check:
    # {command_str}

    # ### Help Output:
    # {help_output}

    # Your job is to correct the command if needed, with:
    # - Proper spacing for each flag and argument.

    # Return **only** JSON:
    # {{
    # "corrected_command": "<ccorected command>"
    # }}
    # """

    def _build_prompt_post_step(self, command_str, command_output):
        return f"""
    You are a security assistant analyzing the output of the following command:

    {command_str}

    Your task is to:

    1. Provide a **Detailed summary** of the findings. Focus on services, versions, possible vulnerabilities, and anything unusual and include all findings.
    2. Recommend a list of **next commands to run**, based on the current output and the tools available. These should assist in further reconnaissance, vulnerability discovery, or exploitation.

    ### Constraints & Guidelines:
    - The summary is always a string and not a list
    - Recommended steps is a list of strings of command
    - Use only the following tools: {str(self.available_tools)}.
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

    def _build_prompt_exec_summary(self, machine_ip, summary_content, exploits_content):
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

    def _build_prompt_json_repair(self, bad_output):
        return f"""
    The following response from a security assistant LLM was meant to be a valid JSON object but was malformed or improperly formatted:

    --- Begin Original Output ---
    {bad_output}
    --- End Original Output ---

    Your job is to return ONLY a **valid JSON object** that preserves the original structure and keys **exactly**

    Do NOT add or remove any keys. Do NOT wrap the output in triple backticks or markdown. The response must be raw JSON only and must be parsable by `json.loads()` with no extra characters or text.
    """

    def _build_prompt_deduplication(self, current_layer, prior_layers):
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

    # ========== LLM Query Methods ==========

    def get_response(self, prompt):
        prompt = self.truncate_to_tokens(prompt, self.context_length)
        if self.provider == "groq":
            return self._query_groq(prompt)
        elif self.provider == "openai":
            return self._query_openai(prompt)
        elif self.provider == "ollama":
            return self._query_ollama(prompt)
        else:
            raise NotImplementedError(f"Unsupported provider: {self.provider}")

    def _query_groq(self, prompt):
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=self._build_headers(),
                json=self._build_chat_payload(prompt),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Groq request failed: {e}")

    def _query_openai(self, prompt):
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            resp = requests.post(
                url,
                headers=self._build_headers(),
                json=self._build_chat_payload(prompt),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"OpenAI request failed: {e}")

    def _query_ollama(self, prompt):
        try:
            resp = requests.post(
                f"{self.host.rstrip('/')}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    # ========== Repair & Correction ==========

    def repair_llm_response(self, bad_output):
        prompt = self._build_prompt_json_repair(bad_output)
        try:
            fixed = self.get_response(prompt)
            return json.loads(self._sanitize_llm_output(fixed))
        except Exception as e:
            print("[!] Failed to repair LLM output:", e)
            return None

    # def get_corrected_command(self, command, timeout=10):
    #   Causing more problems than it's solving
    #     tool = command[0]
    #     command_str = " ".join(command)

    #     try:
    #         help_output = subprocess.run(
    #             [tool, "--help"],
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.STDOUT,
    #             text=True,
    #             timeout=timeout,
    #         ).stdout

    #         if tool.lower() in ("gobuster", "ffuf"):
    #             help_output += "\n\nSeclists path: /usr/share/seclists"
    #             help_output += "\n Big.txt: /usr/share/seclists/Discovery/Web-Content/big.txt"
    #             help_output += "\n FTP: /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt"
    #             help_output += "\n DNS: /usr/share/seclists/Discovery/DNS/namelist.txt"
    #             help_output += "\n Usernames: /usr/share/seclists/Usernames/top-usernames-shortlist.txt"
    #             help_output += "\n Passwords: /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt"
    #     except Exception:
    #         return command

    #     prompt = self._build_prompt_command_correction(
    #         command_str, help_output)

    #     try:
    #         response = self.get_response(prompt)
    #         corrected = json.loads(self._sanitize_llm_output(response))
    #         return corrected["corrected_command"].strip().split()
    #     except Exception:
    #         return command

    def post_step(self, command, command_output_file):
        command_str = " ".join(command)

        try:
            with open(command_output_file, "r", encoding="utf-8") as file:
                command_output = file.read()
        except FileNotFoundError:
            return f"Error: File not found at {command_output_file}"

        prompt = self._build_prompt_post_step(command_str, command_output)

        response = self.get_response(prompt)
        response = self._sanitize_llm_output(response)
        try:
            return json.loads(response)
        except Exception:
            return self.repair_llm_response(response)

    def executive_summary(self, machine_ip):
        base_dir = os.path.join("/mnt/triage", machine_ip)
        summary_file = os.path.join(base_dir, "summary.md")
        exploits_file = os.path.join(base_dir, "exploits.txt")

        if not os.path.exists(summary_file):
            print("[!] No summary.md found.")
            return None

        with open(summary_file, "r", encoding="utf-8") as f:
            summary_content = f.read()

        exploits_content = ""
        if os.path.exists(exploits_file):
            with open(exploits_file, "r", encoding="utf-8") as ef:
                exploits_content = ef.read()

        prompt = self._build_prompt_exec_summary(
            machine_ip, summary_content, exploits_content
        )

        response = self.get_response(prompt)
        print("\n[*] Executive Summary:\n")
        print(response)

        with open(
            os.path.join(base_dir, "summary_exec.md"), "w", encoding="utf-8"
        ) as f:
            f.write(response)

        return response

    def deduplicate_commands(self, commands, layer):
        current_layer = commands[layer]
        prior_layers = commands[:layer]

        prompt = self._build_prompt_deduplication(current_layer, prior_layers)
        response = self.get_response(prompt)
        response = self._sanitize_llm_output(response)

        try:
            return json.loads(response)
        except Exception:
            return self.repair_llm_response(response)

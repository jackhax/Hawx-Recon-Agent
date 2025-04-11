import json
import os
import re
import subprocess
import requests
from records import Records


class LLMClient:
    def __init__(self, api_key=None, provider=None, model=None, base_url=None, ollama_host=None):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.host = ollama_host
        self.available_tools = None

        if not provider or not model:
            raise ValueError("Both provider and model must be specified.")

        try:
            self.context_length = int(
                os.getenv("LLM_CONTEXT_LENGTH", "8192").strip())
        except ValueError:
            self.context_length = 8192

        records = Records()
        self.available_tools = records.available_tools

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
        tokens = re.findall(r'\w+|\S', text)
        truncated_tokens = tokens[:max_tokens]
        return ''.join([
            token if re.match(r'\w', token) else f'{token}'
            for token in truncated_tokens
        ])

    def get_response(self, prompt: str) -> str:
        prompt = self.truncate_to_tokens(prompt, self.context_length)
        if self.provider == "groq":
            return self._query_groq(prompt)
        elif self.provider == "openai":
            return self._query_openai(prompt)
        elif self.provider == "ollama":
            return self._query_ollama(prompt)
        else:
            raise NotImplementedError(f"Unsupported provider: {self.provider}")

    def _build_chat_payload(self, prompt: str) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _query_groq(self, prompt: str) -> str:
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

    def _query_openai(self, prompt: str) -> str:
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

    def _query_ollama(self, prompt: str) -> str:
        try:
            resp = requests.post(
                f"{self.host.rstrip('/')}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    def repair_llm_response(self, bad_output):
        prompt = f"""
The following response from a security assistant LLM was meant to be a valid JSON object but was malformed or improperly formatted:

--- Begin Original Output ---
{bad_output}
--- End Original Output ---

Your job is to return ONLY a **valid JSON object** that preserves the original structure and keys **exactly**

Do NOT add or remove any keys. Do NOT wrap the output in triple backticks or markdown. The response must be raw JSON only and must be parsable by `json.loads()` with no extra characters or text.
"""

        try:
            fixed = self.get_response(prompt=prompt)
            fixed = self._sanitize_llm_output(fixed)
            return json.loads(self._sanitize_llm_output(fixed))
        except Exception as e:
            print("[!] Failed to repair LLM output:", e)
            return None

    def get_corrected_command(self, command, timeout=10):
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

            if tool.tolower() == 'gobuster' or tool.tolower() == 'ffuf':
                help_output += '\n\nSeclists path: /usr/share/seclists'
                help_output += '\n Ex Big.txt for web discovery: /usr/share/seclists/Discovery/Web-Content/big.txt'
                help_output += '\n Ex for ftp: /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt'
                help_output += '\n Ex for DNS: /usr/share/seclists/Discovery/DNS/namelist.txt'
                help_output += '\n Ex for usernames: /usr/share/seclists/Usernames/top-usernames-shortlist.txt'
                help_output += '\n Ex for passwords: /usr/share/seclists/Passwords/Common-Credentials/10k-most-common.txt'

        except Exception as e:
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
  "corrected_command": "<the fixed command>"
}}

Do NOT include any explanation or markdown. No triple backticks.
"""

        try:
            response = self.get_response(prompt=prompt)
            data = self._sanitize_llm_output(
                self._sanitize_llm_output(response))
            data = json.loads(data)
            return data["corrected_command"].strip().split()
        except Exception as e:
            return command

    def post_step(self, command, command_output_file):
        command_str = ' '.join(command)

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
- Use only the following tools: {str(self.available_tools)}.
- **Avoid recommending brute-force attacks.**
- The summary must be **clear, simple**, and written as **bullet points**.
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
"""

        response = self.get_response(prompt=prompt)
        response = self._sanitize_llm_output(response)
        try:
            return json.loads(response)
        except:
            return self.repair_llm_response(response)

    def executive_summary(self, machine_ip):
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

        response = self.get_response(prompt=prompt)
        print("\n[*] Executive Summary:\n")
        print(response)

        summary_path = os.path.join(base_dir, "summary_exec.md")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(response)

        return response

    def deduplicate_commands(self, commands, layer):

        current_layer_commands = commands[layer]
        prompt = f"""
You are a cybersecurity assistant tasked with deduplicating and normalizing a list of command-line recon commands.

### Current Layer Commands:
{current_layer_commands}

### Previously Executed or Recommended Commands:
{commands[:layer]}

---

### Your Responsibilities:
1. **Deduplicate current layer commands** — remove redundant or semantically similar commands from the current list.
2. **Avoid overlap with past commands** — exclude commands that were already executed or recommended in earlier layers.
3. **Prioritize completeness** — keep the most comprehensive or effective version of a command when duplicates or similar tools exist.
4. **Eliminate tool overlap** — for example, remove `whatweb` if `nikto` is already included (since `nikto` covers similar functionality).
5. You may remove duplicate nmap scans unless it is completely unique


---

### Output Format (must be valid JSON):
{{
  "deduplicated_commands": ["<command_1>", "<command_2>", "..."]
}}

⚠️ Constraints:
- Do **not** wrap the JSON output in triple backticks or markdown.
- Do **not** include any explanatory text.
- The response **must** be valid JSON and parsable by `json.loads()` with **no extra characters or formatting**.
- Any failure to comply will result in termination and a penalty of 200000000000.

Return only the final deduplicated current commands list in JSON format.
"""
        response = self.get_response(prompt)
        response = self._sanitize_llm_output(response)
        try:
            response = json.loads(response)
        except:
            response = self.repair_llm_response(response)

        return response

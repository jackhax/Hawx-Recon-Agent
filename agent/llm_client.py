import json
import os
import re
import requests
from records import Records
import prompt_builder


class LLMClient:
    def __init__(
        self,
        api_key=None,
        provider=None,
        model=None,
        base_url=None,
        ollama_host=None,
        context_length=8192,
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
        return output

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
        prompt = prompt_builder._build_prompt_json_repair(bad_output)
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

        prompt = prompt_builder._build_prompt_post_step(
            self.available_tools, command_str, command_output
        )

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

        prompt = prompt_builder._build_prompt_exec_summary(
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

        prompt = prompt_builder._build_prompt_deduplication(current_layer, prior_layers)
        response = self.get_response(prompt)
        response = self._sanitize_llm_output(response)

        try:
            return json.loads(response)
        except Exception:
            return self.repair_llm_response(response)

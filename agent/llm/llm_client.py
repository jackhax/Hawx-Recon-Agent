"""
LLM client for Hawx Recon Agent.

Handles communication with LLM providers (Groq, OpenAI, Ollama), response post-processing,
command deduplication, and executive summary generation.
"""

import json
import os
import re
import requests
from agent.utils.records import Records
from agent.llm import prompt_builder


class LLMClient:
    """
    Client for interacting with a Large Language Model (LLM) provider.

    Supports Groq, OpenAI, OpenRouter and Ollama APIs. Provides methods for querying the LLM,
    repairing malformed responses, deduplicating commands, and generating executive summaries.
    """

    def __init__(
        self,
        api_key=None,
        provider=None,
        model=None,
        base_url=None,
        ollama_host=None,
        context_length=8192,
    ):
        # Validate required LLM provider and model
        if not provider or not model:
            raise ValueError("Both provider and model must be specified.")

        self.provider = provider
        self.api_key = api_key
        self.model = model
        # Always use default base_url for known providers
        if provider == "groq":
            self.base_url = "https://api.groq.com/openai/v1"
        elif provider == "openai":
            self.base_url = "https://api.openai.com/v1"
        elif provider == "openrouter":
            self.base_url = "https://openrouter.ai/api/v1"
        else:
            self.base_url = base_url  # Only use config for unknown/custom providers
        self.host = ollama_host
        self.context_length = context_length or 8192

        # Load available tools for prompt context
        records = Records()
        self.available_tools = records.available_tools

    # ========== Utility Methods ==========
    def _chunk_text_by_tokens(self, text, max_tokens):
        """Split text into chunks based on token count for LLM context limits."""
        tokens = re.findall(r"\w+|\S", text)
        chunks = []
        for i in range(0, len(tokens), max_tokens):
            chunk = "".join(tokens[i : i + max_tokens])
            chunks.append(chunk)
        return chunks

    def _sanitize_llm_output(self, output):
        """Remove markdown/code block wrappers from LLM output."""
        output = output.strip()
        if output.startswith("```json"):
            output = output[7:]
        elif output.startswith("```"):
            output = output[3:]
        if output.endswith("```"):
            output = output[:-3]
        return output

    def _build_chat_payload(self, prompt):
        """Build the payload for chat-based LLM APIs."""
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _build_headers(self):
        """Build HTTP headers for LLM API requests."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            # OpenRouter requires Referer and X-Title headers
            # Change to your app/site if needed
            headers["HTTP-Referer"] = "https://hawx.local"
            headers["X-Title"] = "Hawx Recon Agent"
        return headers

    # ========== LLM Query Methods ==========

    def get_response(self, prompt):
        """Query the configured LLM provider with the given prompt."""
        if self.provider in ("groq", "openai", "openrouter"):
            return self._query_openai(prompt)
        elif self.provider == "ollama":
            return self._query_ollama(prompt)
        else:
            raise NotImplementedError(f"Unsupported provider: {self.provider}")

    def _query_openai(self, prompt):
        """Send a prompt to the OpenAI-compatible API."""
        try:
            url = f"{self.base_url.rstrip('/')}/chat/completions"
            resp = requests.post(
                url,
                headers=self._build_headers(),
                json=self._build_chat_payload(prompt),
            )
            resp.raise_for_status()
            if resp.status_code == 429:
                raise RuntimeError("Rate limit exceeded")
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"OpenAI request failed: {exc}")

    def _query_ollama(self, prompt):
        """Send a prompt to the Ollama API."""
        try:
            resp = requests.post(
                f"{self.host.rstrip('/')}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as exc:
            raise RuntimeError(f"Ollama request failed: {exc}")

    # ========== Repair & Correction ==========

    def repair_llm_response(self, bad_output):
        """Attempt to repair malformed LLM output by prompting the LLM to fix its own response."""
        prompt = prompt_builder._build_prompt_json_repair(bad_output)
        try:
            fixed = self.get_response(prompt)
            return json.loads(self._sanitize_llm_output(fixed))
        except Exception as exc:
            print("[!] Failed to repair LLM output:", exc)
            return None

    def post_step(
        self,
        command,
        command_output_file,
        previous_commands=None,
        command_output_override=None,
        similar_context=None,
    ):
        """Summarize and recommend next steps after running a command, considering previous commands and similar context."""
        command_str = " ".join(command)
        previous_commands = previous_commands or []

        if command_output_override is not None:
            command_output = command_output_override
        else:
            try:
                with open(command_output_file, "r", encoding="utf-8") as f:
                    command_output = f.read()
            except FileNotFoundError:
                return f"Error: File not found at {command_output_file}"

        tokens = re.findall(r"\w+|\S", command_output)
        # Use chunked prompt if output is too large for LLM context
        if len(tokens) < self.context_length - 1000:
            prompt = prompt_builder._build_prompt_post_step(
                self.available_tools,
                command_str,
                command_output,
                previous_commands,
                similar_context,
            )
            response = self.get_response(prompt)
        else:
            chunks = self._chunk_text_by_tokens(
                command_output, self.context_length - 1000
            )
            summary_so_far = ""
            for chunk in chunks:
                prompt = prompt_builder._build_prompt_post_step_chunked(
                    self.available_tools, command_str, chunk, summary_so_far
                )
                summary_so_far = self.get_response(prompt)
            response = summary_so_far

        try:
            return json.loads(self._sanitize_llm_output(response))
        except Exception as exc:
            print("[!] LLM output parse error:", exc)
            # Attempt to repair if JSON parsing fails
            return self.repair_llm_response(response)

    def executive_summary(self, base_dir):
        """Generate a detailed executive summary for the recon session."""
        print("\n\033[94m[*] Preparing Executive Summary...\033[0m\n")
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

        full_input = summary_content + "\n\n" + exploits_content
        tokens = re.findall(r"\w+|\S", full_input)

        # Use chunked prompt if summary is too large
        if len(tokens) < self.context_length - 1000:
            prompt = prompt_builder._build_prompt_exec_summary(
                os.path.basename(base_dir), summary_content, exploits_content
            )
            response = self.get_response(prompt)
        else:
            chunks = self._chunk_text_by_tokens(full_input, self.context_length - 1000)
            summary_so_far = ""
            for chunk in chunks:
                prompt = prompt_builder._build_prompt_exec_summary_chunked(
                    os.path.basename(base_dir), chunk, summary_so_far
                )
                summary_so_far = self.get_response(prompt)
            response = summary_so_far

        print("\n[*] Executive Summary:\n")
        print(response)

        # Save the executive summary to a markdown file
        with open(
            os.path.join(base_dir, "summary_exec.md"), "w", encoding="utf-8"
        ) as f:
            f.write(response)

        return response

    def deduplicate_commands(self, commands, layer):
        """Deduplicate and normalize a list of command-line reconnaissance commands."""
        if not commands or not isinstance(commands, list):
            return {"deduplicated_commands": []}
        current_layer = commands[layer] if layer < len(commands) else []
        prior_layers = [
            cmd
            for i, layer_cmds in enumerate(commands)
            if i != layer
            for cmd in layer_cmds
        ]
        prompt = prompt_builder._build_prompt_deduplication(current_layer, prior_layers)
        resp = self.get_response(prompt)
        try:
            return json.loads(self._sanitize_llm_output(resp))
        except Exception as exc:
            print("[!] Deduplication LLM output parse error:", exc)
            return self.repair_llm_response(resp)

import requests
import os


class LLMClient:
    def __init__(self, api_key=None, provider=None, ollama_model=None, ollama_host=None, model=None, base_url=None):
        self.api_key = api_key
        self.provider = provider
        self.ollama_model = ollama_model
        self.ollama_host = ollama_host
        self.model = model
        self.base_url = base_url
        try:
            self.context_length = int(
                os.getenv("LLM_CONTEXT_LENGTH", "8192").strip())
        except ValueError:
            self.context_length = 8192

    def get_response(self, prompt):
        if self.provider == "groq":
            return self._query_grok(prompt)
        elif self.provider == "ollama":
            return self._query_ollama(prompt)
        elif self.provider == "openai":
            return self._query_openai(prompt)
        else:
            raise NotImplementedError(
                f"LLM provider '{self.provider}' is not implemented.")

    def _query_grok(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        json_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions", headers=headers, json=json_payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _query_ollama(self, prompt):
        json_payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False
        }
        try:
            resp = requests.post(
                f"{self.ollama_host}/api/generate", json=json_payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    def _query_openai(self, prompt):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        json_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = requests.post(
            f"{self.base_url}/chat/completions", headers=headers, json=json_payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

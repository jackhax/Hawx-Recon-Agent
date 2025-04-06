import requests
import openai
import os


class LLMClient:
    def __init__(self, api_key, provider="grok"):
        self.api_key = api_key
        self.provider = provider
        self.model = None
        self.groq_api = 'https://api.groq.com/openai/v1/chat/completions'

    def get_response(self, prompt):
        """Get response from LLM based on the provider."""
        if self.provider == "grok":
            self.model = os.getenv("GROK_MODEL")
            return self._ask_grok(prompt)
        elif self.provider == "openai":
            self.model = os.getenv("GROK_MODEL")
            return self._ask_openai(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _ask_grok(self, prompt):
        """
        Call Grok API and get the response.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,  # Using the model defined in the class
            "messages": [
                {"role": "system", "content": "You are an expert recon assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        try:
            response = requests.post(
                self.groq_api, headers=headers, json=payload
            )
            response.raise_for_status()  # Will raise an HTTPError if the response is an error
            return response.json().get("choices")[0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            print(f"[!] Error making API call: {e}")
            return None

    def _ask_openai(self, prompt):
        """Call OpenAI API and get the response."""
        openai.api_key = self.api_key

        response = openai.Completion.create(
            model="gpt-3.5-turbo",  # Replace with appropriate model
            messages=[
                {"role": "system", "content": "You are an expert recon assistant."},
                {"role": "user", "content": prompt},
            ]
        )

        return response['choices'][0]['message']['content']

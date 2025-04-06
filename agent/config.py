import os


def load_env_vars():
    """Load only required environment variables based on the selected LLM provider."""
    provider_raw = os.getenv("LLM_PROVIDER", "").strip().lower()

    if provider_raw not in ["groq", "ollama", "openai"]:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: {provider_raw}. Supported values are: groq, ollama, openai.")

    if provider_raw == "groq":
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY is required for Groq provider.")
        return {
            "provider": "groq",
            "api_key": api_key,
            "model": os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        }

    elif provider_raw == "ollama":
        return {
            "provider": "ollama",
            "model": os.getenv("OLLAMA_MODEL", "llama3"),
            "host": os.getenv("OLLAMA_HOST", "http://localhost:11434")
        }

    elif provider_raw == "openai":
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY is required for OpenAI provider.")
        return {
            "provider": "openai",
            "api_key": api_key,
            "model": os.getenv("OPENAI_MODEL", "gpt-4"),
            "base_url": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        }

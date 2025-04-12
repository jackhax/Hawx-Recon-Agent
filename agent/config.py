import os


def load_env_vars():
    """Load only required environment variables based on the selected LLM provider."""
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    model = os.getenv("MODEL")

    if provider not in ["groq", "ollama", "openai"]:
        raise ValueError(
            f"Unsupported LLM_PROVIDER: {provider}. Supported values are: groq, ollama, openai."
        )

    if not model:
        raise ValueError("MODEL must be explicitly set in the environment.")

    config = {"provider": provider, "model": model}

    if provider in ["groq", "openai"]:
        api_key = os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("LLM_API_KEY is required for Groq/OpenAI provider.")
        config["api_key"] = api_key

    if provider == "ollama":
        config["host"] = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    if provider == "openai":
        config["base_url"] = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    return config

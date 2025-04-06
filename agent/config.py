import os


def load_env_vars():
    """Load essential environment variables."""
    llm_api_key = os.getenv("LLM_API_KEY")
    llm_provider = os.getenv("LLM_PROVIDER", "grok")

    if not llm_api_key:
        raise ValueError("LLM_API_KEY is not set in the environment.")
    if not llm_provider:
        raise ValueError("LLM_PROVIDER is not set in the environment.")

    return llm_api_key, llm_provider

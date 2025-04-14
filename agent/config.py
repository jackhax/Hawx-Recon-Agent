import os
import yaml
from dotenv import load_dotenv


def load_config(config_path="/mnt/config.yaml"):
    """Load config.yaml and .env (for API key only)"""
    load_dotenv()

    # Load sensitive values
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise ValueError("LLM_API_KEY must be set in the .env file.")

    # Load structured config
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"config.yaml not found at {config_path}")

    with open(config_path, "r") as f:
        raw = yaml.safe_load(f)

    config = {
        "api_key": api_key,
        "provider": raw["llm"]["provider"],
        "model": raw["llm"]["model"],
        "base_url": raw["llm"].get("base_url"),
        "host": raw.get("ollama", {}).get("host"),
        "context_length": raw["llm"].get("context_length", 8192),
    }

    return config

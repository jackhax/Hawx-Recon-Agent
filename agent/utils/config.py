"""
Configuration loader for Hawx Recon Agent.

Loads sensitive values from .env and structured configuration from config.yaml.
"""

import os
import yaml
from dotenv import load_dotenv


def load_config(config_path=None):
    """Load config.yaml and .env (for API key only)"""
    load_dotenv()  # Load environment variables from .env file

    # Load sensitive values (API key)
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        # Fail fast if API key is missing
        raise ValueError("LLM_API_KEY must be set in the .env file.")

    # Load structured config from YAML file
    # Try default locations
    if config_path is None:
        if os.path.exists("/opt/agent/configs/config.yaml"):
            config_path = "/opt/agent/configs/config.yaml"
        else:
            raise FileNotFoundError("config.yaml not found in known locations")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Compose config dictionary from loaded values
    config = {
        "api_key": api_key,
        "provider": raw["llm"]["provider"],
        "model": raw["llm"]["model"],
        "base_url": raw["llm"].get("base_url"),
        "host": raw.get("ollama", {}).get("host"),
        "context_length": raw["llm"].get("context_length", 8192),
    }

    return config

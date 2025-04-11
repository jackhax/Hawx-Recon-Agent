from workflow import ReconExecutor
from config import load_env_vars
from llm_client import LLMClient
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: main.py <machine_ip> [steps]")
        exit(1)

    config = load_env_vars()
    machine_ip = sys.argv[1]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    llm_client = LLMClient(
        api_key=config.get("api_key"),
        provider=config["provider"],
        ollama_host=config.get("host"),
        model=config.get("model"),
        base_url=config.get("base_url")
    )

    executor = ReconExecutor(llm_client, machine_ip)
    executor.workflow(llm_client, machine_ip, steps)


if __name__ == "__main__":
    main()

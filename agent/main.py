import sys
from workflow.executor import ReconExecutor
from llm_client import LLMClient
from config import load_config


def print_banner():
    print(
        r"""
██╗  ██╗ █████╗ ██╗    ██╗██╗  ██╗
██║  ██║██╔══██╗██║    ██║╚██╗██╔╝
███████║███████║██║ █╗ ██║ ╚███╔╝ 
██╔══██║██╔══██║██║███╗██║ ██╔██╗ 
██║  ██║██║  ██║╚███╔███╔╝██╔╝ ██╗
╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ ╚═╝  ╚═╝

 H A W X | LLM-based Autonomous Recon Agent ⚡
    """
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: main.py <machine_ip> [steps] [interactive]")
        exit(1)

    config = load_config()
    machine_ip = sys.argv[1]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    interactive = sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False

    llm_client = LLMClient(
        api_key=config["api_key"],
        provider=config["provider"],
        model=config["model"],
        base_url=config.get("base_url"),
        ollama_host=config.get("host"),
        context_length=config.get("context_length", 8192),
    )

    executor = ReconExecutor(llm_client, machine_ip, interactive)
    executor.workflow(steps)


if __name__ == "__main__":
    print_banner()
    main()

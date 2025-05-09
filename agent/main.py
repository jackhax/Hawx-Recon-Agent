"""
Main entry point for the Hawx Recon Agent.

This script initializes the LLM client, loads configuration, and starts the reconnaissance workflow
for a given target machine IP. It is intended to be run inside the Docker container as the main process.
"""

import sys
from workflow.executor import ReconExecutor
from llm_client import LLMClient
from config import load_config


def print_banner():
    # Print the ASCII art banner for branding and user feedback
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
    # Ensure the script is called with at least the target machine IP
    if len(sys.argv) < 2:
        print("Usage: main.py <machine_ip> [steps] [interactive]")
        exit(1)

    # Load configuration from config.yaml and .env
    config = load_config()
    machine_ip = sys.argv[1]  # Target machine IP address
    # Number of workflow steps/layers
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    interactive = (
        sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False
    )  # Interactive mode flag

    # Initialize the LLM client with config values
    llm_client = LLMClient(
        api_key=config["api_key"],
        provider=config["provider"],
        model=config["model"],
        ollama_host=config.get("host"),
        context_length=config.get("context_length", 8192),
    )

    # Create the workflow executor and start the recon workflow
    executor = ReconExecutor(llm_client, machine_ip, interactive)
    executor.workflow(steps)


if __name__ == "__main__":
    print_banner()  # Show banner at startup
    main()  # Start the main workflow

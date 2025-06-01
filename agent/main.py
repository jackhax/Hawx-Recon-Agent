"""
Main entry point for the Hawx Recon Agent.

This script initializes the LLM client, loads configuration, and starts the reconnaissance workflow
for a given target machine IP. It is intended to be run inside the Docker container as the main process.
"""

from agent.utils.config import load_config
from agent.llm.llm_client import LLMClient
from agent.workflow.executor import ReconExecutor
import sys
import os


def print_banner():
    """Print the ASCII art banner for branding and user feedback."""
    os.system("clear" if os.name == "posix" else "cls")  # Clears terminal
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
    """Main entry point for the Hawx Recon Agent."""
    # Ensure the script is called with at least the target and mode
    if len(sys.argv) < 4:
        print("Usage: main.py <target> <steps> <interactive> <target_mode>")
        print("  <target>: IP/domain (for host) or full URL (for website)")
        print("  <target_mode>: 'host' or 'website'")
        sys.exit(1)

    # Load configuration from config.yaml and .env
    config = load_config()
    target = sys.argv[1]  # Target machine IP or domain
    # Number of workflow steps/layers
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    interactive = (
        sys.argv[3].lower() == "true" if len(sys.argv) > 3 else False
    )  # Interactive mode flag
    target_mode = sys.argv[4] if len(sys.argv) > 4 else "host"  # Target mode

    # Initialize the LLM client with config values
    llm_client = LLMClient(
        api_key=config["api_key"],
        provider=config["provider"],
        model=config["model"],
        ollama_host=config.get("host"),
        context_length=config.get("context_length", 8192),
    )

    # Create the workflow executor and start the recon workflow
    executor = ReconExecutor(llm_client, target, interactive, target_mode)
    executor.workflow(steps)


if __name__ == "__main__":
    print_banner()  # Show banner at startup
    main()  # Start the main workflow

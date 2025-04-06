from workflow import workflow
from config import load_env_vars
from llm_client import LLMClient
import sys


def main():

    args = sys.argv
    if len(args) < 2:
        print('Usage: main.py <machine_ip>')
        exit(0)

    api_key, provider = load_env_vars()
    machine_ip = args[1]

    llm_client = LLMClient(api_key, provider)
    workflow(llm_client, machine_ip)


if __name__ == "__main__":
    main()

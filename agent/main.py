from config import load_env_vars
from llm_client import LLMClient
import sys
from recon_tasks import nmap_scan
import ask_llm
import os


def main():

    args = sys.argv
    if len(args) < 2:
        print('Usage: main.py <machine_ip>')
        exit(0)

    machine_ip = args[1]
    default_file_name = machine_ip.replace('.', '_')

    # Load environment variables
    api_key, provider = load_env_vars()

    # Initialize the LLM client
    llm_client = LLMClient(api_key, provider)

    # Perform nmap scan:
    nmap_scan(machine_ip=machine_ip)

    file_path = os.path.join('/', 'mnt', 'nmap_reports',
                             f'nmap_scan_{default_file_name}.xml')
    print(ask_llm.post_nmap(file_path, llm_client))

    # # Test with a simple "ping" or "hello" query to the LLM
    # prompt = "Hello, how are you today?"

    # try:
    #     # Send the query to the LLM and get a response
    #     response = llm_client.get_response(prompt)
    #     print(f"LLM Response: {response}")
    # except Exception as e:
    #     print(f"[!] Error: {e}")
    #     exit(1)


if __name__ == "__main__":
    main()

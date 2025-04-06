from llm_client import LLMClient


def post_nmap(nmap_result_file, llm_client):
    nmap_results = None
    try:
        with open(nmap_result_file, 'r') as file:
            nmap_results = file.read()
    except FileNotFoundError:
        return f"Error: File not found at {nmap_result_file}"

    prompt = '''
    You are analyzing the results of an Nmap scan. Below is the Nmap scan output for a target machine. 

    Please provide:
    1. A concise summary of the services and open ports detected on the machine.
    2. A list of **recommended steps** to continue the investigation, specifically in the form of commands to run next. Include commands that may help in further reconnaissance, vulnerability analysis, or exploitation.

    The available tools are:
    - Nmap
    - Gobuster
    - Nikto
    - Gobuster
    - HTTPX
    - FFUF
    - Enum4Linux
    - Seclists

    Here is the Nmap scan output:\n\n
    ''' + nmap_results + '''\n\n
    Your response should be in the following format:
    {
    "summary": "<summary_text>",
    "recommended_steps": [
        "<command_1>",
        "<command_2>",
        ...
    ]
    }

    If the nmap result doesn't look like a valid nmap scan result just reply with None nothing else
    '''
    return llm_client.get_response(prompt=prompt)


# post_nmap('nmap_reports/nmap_scan_10_10_11_58_log.txt')

import os
import pytest
from config import load_config
from llm_client import LLMClient


@pytest.mark.parametrize("commands, expected_retained", [
    (
        # Test 1: unique_tools_same_function
        [
            ["nmap -p- 10.10.11.58", "nmap -sV 10.10.11.58"],
            ["whatweb 10.10.11.58",
             "dirb http://10.10.11.58 /usr/share/seclists/Discovery/Web-Content/big.txt",
             "ffuf -u http://10.10.11.58/FUZZ -w /usr/share/seclists/Discovery/Web-Content/big.txt"]
        ],
        ["whatweb 10.10.11.58",
            "dirb http://10.10.11.58 /usr/share/seclists/Discovery/Web-Content/big.txt"]
    ),
    (
        # Test 2: keep_targeted_probes
        [
            ["nmap -sC -sV -p- 10.10.11.58"],
            ["curl http://10.10.11.58/.git/config",
             "curl http://10.10.11.58/robots.txt",
             "curl http://10.10.11.58/.htaccess"]
        ],
        ["curl http://10.10.11.58/.git/config",
         "curl http://10.10.11.58/robots.txt",
         "curl http://10.10.11.58/.htaccess"]
    ),
    (
        # Test 3: exclude_duplicate_ffuf
        [
            ["ffuf -u http://10.10.11.58/FUZZ -w /usr/share/seclists/Discovery/Web-Content/big.txt"],
            ["ffuf -u http://10.10.11.58/FUZZ -w /usr/share/seclists/Discovery/Web-Content/big.txt"]
        ],
        []
    ),
    (
        # Test 4: keep_deeper_scan
        [
            ["nmap -p- 10.10.11.58"],
            ["nmap -sC -sV -p- 10.10.11.58"]
        ],
        ["nmap -sC -sV -p- 10.10.11.58"]
    ),
    (
        # Test 5: mixed_static_and_duplicate
        [
            ["nmap -p 80 10.10.11.58"],
            ["nmap -p 80 10.10.11.58", "curl http://10.10.11.58/robots.txt"]
        ],
        ["curl http://10.10.11.58/robots.txt"]
    )
])
def test_deduplication_variants(commands, expected_retained):
    config = load_config()
    client = LLMClient(
        provider=config["provider"],
        model=config["model"],
        api_key=os.environ["LLM_API_KEY"],
        base_url=config.get("base_url"),
        ollama_host=config.get("host"),
        context_length=config.get("context_length", 8192)
    )

    result = client.deduplicate_commands(commands, layer=1)
    actual = result["deduplicated_commands"]

    print("\n--- Original ---")
    for layer in commands:
        for cmd in layer:
            print(cmd)

    print("\n--- Expected ---")
    for cmd in expected_retained:
        print(cmd)

    print("\n--- Actual ---")
    for cmd in actual:
        print(cmd)

    assert sorted(actual) == sorted(expected_retained)

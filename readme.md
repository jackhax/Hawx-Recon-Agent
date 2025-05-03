# Hawx Recon Agent

## Overview

**Hawx Recon Agent** is an intelligent, autonomous reconnaissance system powered by a Large Language Model (LLM). Designed for offensive security workflows, it automates initial triage and guided follow-up based on live service data. The agent runs in a Dockerized environment and can optionally tunnel through OpenVPN. Output is structured, actionable, and neatly organized per target.

---

## Features

- 📡 Autonomous recon workflow
- 🤖 LLM-guided command planning and triage
- 🔍 CVE and exploit discovery using SearchSploit
- 🌐 Optional OpenVPN integration
- 🧠 Markdown summaries of recon
- 📂 Clean directory structure per target
- 🧹 Output filtering via filter.yaml (custom regex-based noise reduction)
- 🌐 Hosts file injection for domain-based targeting

---

## Architecture

```text
[Host]
└── hawx.sh
    ├── Parses flags (IP, --ovpn, --steps, --hosts, etc.)
    ├── Launches Docker container
    │   ├── Mounts current directory to /mnt
    │   └── Passes env vars
    ↓

[Inside Docker Container]
└── entrypoint.sh
    ├── Starts OpenVPN if provided
    ├── Verifies target connectivity
    ├── Injects custom hosts file to /etc/hosts
    └── Resolves domain from hosts file and launches agent.py

[agent.py]
├── Runs nmap on target
├── Parses and summarizes output
├── Picks follow-up tools
├── Stores all logs and recon data
└── Summarizes recon using LLM
```

---

## Agent Workflow

### 🔎 Initial Enumeration
- Nmap (`-sC -sV -p-`)
- Stores raw and structured output

### 🧠 Analysis + Planning
- LLM decides follow-up tools:
  - Web → `httpx`, `gobuster`, `nikto`
  - FTP/SSH/SMB → enumeration tools
- Deduplicates tools across layers

### 🧰 Follow-Up Tools
| Service | Toolset |
|---------|---------|
| HTTP    | httpx, gobuster, nikto |
| FTP     | ftp-anon, manual login |
| SMB     | enum4linux, smbclient |
| SSH     | Banner grab |
| SQL     | Basic login logic |
| Custom  | LLM-based tool picks |

### 🛡️ CVE Discovery
- SearchSploit per service/version
- LLM-based CVE summaries
- Output written to `exploits.txt`

### 📋 Executive Summary
- Clear Markdown (`summary.md`)
- Includes:
  - Ports/services
  - CVEs
  - Attack paths
  - Recommended tools

---

## Output Filtering with filter.yaml

You can reduce noise in tool outputs by specifying regex patterns in a `filter.yaml` file at the project root. For each supported tool (e.g., ffuf, gobuster, nikto), add a list of regex patterns to filter out unwanted lines before logs and summaries are generated.

**Example filter.yaml:**
```yaml
ffuf:
  - .*:: Progress:      # Filters all ffuf progress lines
gobuster:
  - ^Progress:          # Filters gobuster progress lines
nikto:
  - OSVDB               # Filters Nikto OSVDB noise
```

Patterns are applied per line, and only lines not matching any pattern are written to logs and used for summarization. This keeps your recon output clean and focused on actionable results.

---

## Directory Structure

```
triage/192.168.1.10/
├── nmap_output.txt
├── httpx_output.txt
├── gobuster.txt
├── exploits.txt
├── summary.md
└── summary_exec.md
```

---

## Setup

### 1. Install Docker
Ensure you have Docker installed and running:
```bash
sudo apt install docker.io
```

### 2. Create `.env` file with your API key
Create a `.env` file in the root of the repo:
```env
LLM_API_KEY=your_llm_api_key_here
```
> Only the API key is read from `.env`. All other config is in `config.yaml`

### 3. Create `config.yaml`
Create a `config.yaml` in the root directory (or mountable from outside):
```yaml
llm:
  provider: groq           # or openai, ollama
  model: qwen-2.5-coder-32b
  context_length: 8192

ollama:
  host: http://host.docker.internal:11434
```

---

## Usage

```bash
./hawx.sh [--steps N] [--ovpn file.ovpn] [--hosts file.txt] [--interactive] <target_ip>
```

### Examples:
```bash
./hawx.sh 192.168.1.10
./hawx.sh --steps 2 --ovpn vpn.ovpn --hosts hosts.txt --interactive 10.10.11.58
```

> You can specify a hosts file like:
> ```
> 10.10.11.58 dog.htb
> ```
> The agent will resolve and use `dog.htb` instead of the raw IP wherever possible.

---

## Flags

| Flag            | Description                                                  |
|-----------------|--------------------------------------------------------------|
| `--steps`       | Number of recon layers (default: 1, max: 3)                  |
| `--ovpn`        | OpenVPN config file                                          |
| `--hosts`       | File to append to `/etc/hosts` inside container              |
| `--force-build` | Rebuild Docker image before execution                        |
| `--interactive` | Ask user's confirmation before executing recommended commands|
| `--help`        | Show usage help                                              |

---

## Roadmap

- 🔬 Add `nuclei`, `wpscan`, and brute-force modules
- 🧾 PDF export via Pandoc
- 📊 JSON + HTML output formats
- 🕵️ Passive recon plugin support

---

## License

MIT License – use freely, responsibly, and at your own risk.

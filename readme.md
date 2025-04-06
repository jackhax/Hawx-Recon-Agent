# HTB Autonomous Recon Agent Proposal

## Overview

This proposal outlines a system for an autonomous Hack The Box (HTB) recon agent that uses a Large Language Model (LLM) to perform intelligent initial triage on a target IP. The system is Dockerized, includes automatic OpenVPN setup, and performs both static and LLM-assisted follow-up recon including CVE identification.

---

## Architecture

### High-Level Flow

```text
[Host]
└── start_agent.sh
    ├── Builds Docker image (if needed)
    ├── Launches Docker container
    │   ├── Mounts current directory to /mnt
    │   ├── Passes OVPN file and IP
    │   └── Runs entrypoint (Python-based agent)
    ↓

[Inside Docker Container]
└── agent.py (LLM-enabled)
    ├── Starts OpenVPN
    ├── Verifies connection (tun0 + IP)
    ├── Runs nmap on target IP
    ├── Parses output
    ├── Takes follow-up actions (web tools, host updates, etc.)
    └── Calls LLM for triage summary
        └── Saves results in /mnt/triage/10.10.10.X/
```

---

## Agent Responsibilities

### 1. Initial Enumeration
- Run: `nmap -sC -sV -oX`
- Store XML output
- Extract open ports and services

### 2. Parse and Plan
- Use LLM or rules to plan next tools:
  - Web → `httpx`, `gobuster`, `nikto`
  - FTP → `ftp-anon`, login attempts
  - SMB → `enum4linux-ng`, `smbclient`
  - SSH → banner grab, check weak creds
  - SQL → login test

### 3. Follow-Up Recon

| Port | Follow-Up |
|------|-----------|
| 21 (FTP) | `ftp-anon`, login |
| 22 (SSH) | Banner grab |
| 80/443 | `httpx`, `gobuster`, `nikto`, screenshots |
| 139/445 | `enum4linux-ng`, `nmap smb-*` |
| 3306 | MySQL test |
| Others | Banner grab |

### 4. CVE Checking
- `searchsploit "service version"`
- `vulners.nse` (Nmap script)
- Optional Vulners API query
- LLM mapping versions → CVEs

### 5. LLM Summary Generation
- Markdown report
- Include:
  - Open ports/services
  - Potential CVEs
  - Suggested attack paths
  - Follow-up tool suggestions

---

## Directory Structure (per IP)

```
triage/10.10.10.5/
├── nmap.xml
├── httpx_output.txt
├── gobuster.txt
├── nikto.txt
├── screenshots/
├── exploits.txt
├── cve_suggestions.json
└── summary.md
```

---

## Automation Script (Host)

### `start_agent.sh`
- Builds Docker image
- Validates `.ovpn` and IP
- Mounts CWD to container
- Passes env vars (IP, OVPN)
- Starts `agent.py` inside container

---

## Future Add-ons

- Nuclei for fast vuln scans
- CMS scanners (wpscan, joomscan)
- Brute-force via Hydra/Medusa
- Export reports to PDF
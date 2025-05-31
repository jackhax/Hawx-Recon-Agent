FROM kalilinux/kali-rolling

LABEL maintainer="jackhax <adnanjackady@gmail.com>"
LABEL version="1.0"
LABEL description="Recon Agent for automated offensive security assessments"

ENV DEBIAN_FRONTEND=noninteractive
ENV GO_VERSION=1.22.0
ENV PATH="/usr/local/go/bin:$PATH"

# Install system dependencies and Python 3.10 with required modules
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openvpn nmap gobuster nikto ffuf dnsutils dnsrecon \
        smtp-user-enum lftp ftp hydra onesixtyone snmp snmpd snmpcheck \
        smbclient enum4linux rpcbind nbtscan seclists curl wget git unzip \
        iproute2 net-tools traceroute exploitdb python3 python3-pip golang \
        netcat-traditional && \
    rm -rf /var/lib/apt/lists/*

# Install Go
RUN curl -OL https://golang.org/dl/go${GO_VERSION}.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go${GO_VERSION}.linux-amd64.tar.gz && \
    rm go${GO_VERSION}.linux-amd64.tar.gz

# Set working directory
WORKDIR /opt/agent

# Install Python dependencies and run setup
COPY requirements.txt setup.py tools.yaml /tmp/
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt pytest && \
    rm /tmp/requirements.txt && \
    python3 /tmp/setup.py

# Copy agent code and configs
COPY agent/ /opt/agent/
COPY tests/ /opt/agent/tests/
COPY tools.yaml /opt/agent/
COPY filter.yaml /opt/agent/
COPY config.yaml /opt/agent/config.yaml

# Copy entrypoint and make executable
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

# Use the custom entrypoint that appends CUSTOM_HOSTS_FILE to /etc/hosts
ENTRYPOINT ["/opt/entrypoint.sh"]

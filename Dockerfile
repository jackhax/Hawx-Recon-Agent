# Dockerfile.base
FROM kalilinux/kali-rolling

LABEL maintainer="jackhax <adnanjackady@gmail.com>"
LABEL version="1.0"
LABEL description="Recon Agent base image with all tools pre-installed"

ENV DEBIAN_FRONTEND=noninteractive
ENV GO_VERSION=1.24.0
ENV PATH="/usr/local/go/bin:$PATH"

# Use a reliable Kali mirror and force IPv4 for apt
RUN sed -i 's|http://http.kali.org/kali|http://kali.download/kali|g' /etc/apt/sources.list && \
    echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

# Install core utilities (layered, max 5 per RUN)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl wget git unzip --fix-missing && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends iproute2 net-tools traceroute --fix-missing && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential pkg-config --fix-missing && \
    rm -rf /var/lib/apt/lists/*

# Install recon and pentest tools (layered, max 5 per RUN, each with apt-get update)
RUN apt-get update && \
    apt-get install -y --no-install-recommends openvpn nmap gobuster nikto ffuf --fix-missing && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends dnsutils dnsrecon smtp-user-enum lftp ftp --fix-missing && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends hydra onesixtyone snmp snmpd snmpcheck --fix-missing && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends smbclient enum4linux rpcbind nbtscan seclists --fix-missing && \
    rm -rf /var/lib/apt/lists/*
RUN apt-get update && \
    apt-get install -y --no-install-recommends exploitdb netcat-traditional --fix-missing && \
    rm -rf /var/lib/apt/lists/*

# Install network libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpcap-dev \
    libpcap0.8 \
    --fix-missing \
    && rm -rf /var/lib/apt/lists/*

# Install Python and Go
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    --fix-missing \
    && rm -rf /var/lib/apt/lists/*

# Install necessary heavy Python packages
RUN pip3 install --break-system-packages --no-cache-dir numpy sentence-transformers

# Set working directory
WORKDIR /opt/agent

# Copy and install core requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt

# Copy and install runtime requirements
COPY requirements_runtime.txt /tmp/requirements_runtime.txt
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements_runtime.txt

# Copy and run apt and custom install scripts
COPY apt_install.sh /tmp/apt_install.sh
RUN bash /tmp/apt_install.sh

RUN pip3 install --no-cache-dir --break-system-packages golang
ENV PATH="/root/go/bin:${PATH}"

COPY custom_install.sh /tmp/custom_install.sh
RUN bash /tmp/custom_install.sh

# Copy configuration files and agent code
COPY configs/filter.yaml /opt/agent/filter.yaml
COPY configs/config.yaml /opt/agent/config.yaml
COPY configs/tools.yaml /opt/agent/tools.yaml
COPY agent/* /opt/agent/
COPY agent/llm /opt/agent/llm/
COPY agent/utils /opt/agent/utils/
COPY agent/workflow /opt/agent/workflow/
COPY tests/ /opt/agent/tests/

# Copy entrypoint and make executable
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

# Use the custom entrypoint that appends CUSTOM_HOSTS_FILE to /etc/hosts
ENTRYPOINT ["/opt/entrypoint.sh"]

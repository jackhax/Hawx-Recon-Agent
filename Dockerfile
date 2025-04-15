FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive
ENV GO_VERSION=1.22.0
ENV PATH="/root/go/bin:$PATH"

# Install system dependencies and Python 3.10 with required modules
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openvpn \
        nmap \
        gobuster \
        nikto \
        ffuf \
        whatweb \
        dnsutils \
        dnsrecon \
        smtp-user-enum \
        lftp \
        ftp \
        hydra \
        onesixtyone \
        snmp \
        snmpd \
        snmpcheck \
        smbclient \
        enum4linux \
        rpcbind \
        nbtscan \
        seclists \
        curl \
        wget \
        git \
        unzip \
        iproute2 \
        net-tools \
        traceroute \
        exploitdb \
        python3 \
        python3-pip \
        golang \
        wpscan \
        netcat-traditional && \
    apt-get clean


# Install Go
RUN curl -OL https://golang.org/dl/go${GO_VERSION}.linux-amd64.tar.gz && \
    tar -C /root -xzf go${GO_VERSION}.linux-amd64.tar.gz && \
    rm go${GO_VERSION}.linux-amd64.tar.gz

# Set working directory
WORKDIR /opt/agent

# Install Python dependencies and run setup
COPY requirements.txt setup.py tools.yaml /tmp/
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt
RUN python3 /tmp/setup.py

# Copy agent code and entrypoint
COPY agent/ /opt/agent/
COPY tools.yaml /opt/agent/
COPY config.yaml /opt/agent/config.yaml
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh

ENTRYPOINT ["/opt/entrypoint.sh"]

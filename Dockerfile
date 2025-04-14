FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive
ENV GO_VERSION=1.22.0
ENV PATH="/root/go/bin:$PATH"

# Update and install base tools
# need to add more tools
# Update the package list and install packages available via apt
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

# Install HTTPie using pip
RUN pip3 install --break-system-packages --no-cache-dir httpie

# Install WPScan using gem
# RUN apt-get install -y ruby ruby-dev && \
#     gem install wpscan

# Install Swaks by downloading the standalone script
RUN curl -o /usr/local/bin/swaks https://jetmore.org/john/code/swaks/files/swaks && \
    chmod +x /usr/local/bin/swaks

# Install smbmap from GitHub
RUN git clone https://github.com/ShawnDEvans/smbmap.git /opt/smbmap && \
    ln -s /opt/smbmap/smbmap.py /usr/local/bin/smbmap

# Install Chromium using snap
# RUN apt-get install -y snapd && \
#     snap install chromium

# Install httpx (projectdiscovery)
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Set working directory
WORKDIR /opt/agent

# Copy agent and entrypoint
COPY agent/ /opt/agent/
COPY config.yaml /opt/agent/config.yaml
COPY entrypoint.sh /opt/entrypoint.sh

# Ensure entrypoint is executable
RUN chmod +x /opt/entrypoint.sh

# Start from the entrypoint
ENTRYPOINT ["/opt/entrypoint.sh"]
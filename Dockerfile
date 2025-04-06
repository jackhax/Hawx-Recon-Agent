FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive
ENV GO_VERSION=1.22.0
ENV PATH="/root/go/bin:$PATH"

# Update and install base tools
RUN apt update && apt install -y \
    openvpn \
    nmap \
    gobuster \
    python3 \
    python3-pip \
    curl \
    iproute2 \
    net-tools \
    git \
    unzip \
    wget \
    ffuf \
    chromium \
    seclists \
    enum4linux \
    golang \
    netcat-traditional \
    dnsutils \
    traceroute \
    && apt clean

# Install httpx (projectdiscovery)
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Set working directory
WORKDIR /opt/agent

# Copy agent and entrypoint
COPY agent/ /opt/agent/
COPY entrypoint.sh /opt/entrypoint.sh

# Ensure entrypoint is executable
RUN chmod +x /opt/entrypoint.sh

# Start from the entrypoint
ENTRYPOINT ["/opt/entrypoint.sh"]
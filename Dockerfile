# Dockerfile
FROM jackhax/recon-agent-base:latest
#base can be built locally with `docker build -f Dockerfile.base -t jackhax/recon-agent-base:1.0 .`

LABEL maintainer="jackhax <mj3184@nyu.edu>"
LABEL version="2.0"
LABEL description="Recon Agent runtime image with final code and configs"
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

COPY configs/ /opt/agent/configs/
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

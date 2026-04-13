FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install all required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    nginx \
    supervisor \
    iputils-ping \
    traceroute \
    nmap \
    tcpdump \
    curl \
    wget \
    dnsutils \
    iproute2 \
    netcat-openbsd \
    iptables \
    net-tools \
    vim \
    nano \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Install ttyd 1.7.7 (x86_64 binary — target platform is VPS/amd64)
ADD https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 /usr/local/bin/ttyd
RUN chmod +x /usr/local/bin/ttyd

# Create non-root student user
RUN useradd -m -s /bin/bash student

# Copy configuration files
COPY supervisord.conf /etc/supervisord.conf
COPY default_index.html /var/www/html/index.html
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Allow student to edit web content
RUN chown -R student:student /var/www/html

EXPOSE 22 80 7681

ENTRYPOINT ["/entrypoint.sh"]

#!/bin/bash
set -e

STUDENT_PASSWORD="${STUDENT_PASSWORD:-changeme}"

# Set password for student user
echo "student:${STUDENT_PASSWORD}" | chpasswd

# Ensure sshd runtime directory exists (tmpfs, wiped on restart)
mkdir -p /run/sshd

# Configure SSH
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config

# Ensure log directory exists
mkdir -p /var/log/supervisor

# Start supervisord (replaces this process)
exec /usr/bin/supervisord -c /etc/supervisord.conf

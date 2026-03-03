#!/usr/bin/env bash
# VPS Infrastructure Setup Script
# Idempotent script to install and configure Nginx for the dual-environment setup.
# Run this once on the VPS as root.

set -e

echo "=========================================================="
echo "          VPS Infrastructure Setup - TreeJar              "
echo "=========================================================="

echo "[1/4] Checking and installing Nginx..."
if ! command -v nginx &> /dev/null; then
    echo "Nginx not found. Installing..."
    apt-get update
    apt-get install -y nginx
    echo "Nginx installed successfully."
else
    echo "Nginx is already installed. Skipping installation."
fi

# Ensure Nginx is enabled on boot
systemctl enable nginx

echo "[2/4] Setting up Nginx Virtual Hosts..."
REPO_DIR="/root/treejar"

if [ ! -d "$REPO_DIR/scripts" ]; then
    echo "Error: Could not find the repository at $REPO_DIR."
    echo "Please clone the repo first: cd /root && git clone https://github.com/maslennikov-ig/treejar.git"
    exit 1
fi

# Copy Nginx configs to sites-available
cp "$REPO_DIR/scripts/treejar-prod.conf" /etc/nginx/sites-available/treejar-prod
cp "$REPO_DIR/scripts/treejar-dev.conf" /etc/nginx/sites-available/treejar-dev

# Enable the sites by creating symlinks
ln -sf /etc/nginx/sites-available/treejar-prod /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/treejar-dev /etc/nginx/sites-enabled/

# Remove default nginx site if it exists to avoid port 80 conflicts
if [ -f /etc/nginx/sites-enabled/default ]; then
    echo "Removing default nginx site..."
    rm /etc/nginx/sites-enabled/default
fi

echo "[3/4] Testing Nginx configuration..."
nginx -t

echo "[4/4] Reloading Nginx to apply changes..."
systemctl reload nginx

echo "=========================================================="
echo "                      SETUP COMPLETE                      "
echo "=========================================================="
echo "Traffic for chat.megacampus.com -> routes to port 8000"
echo "Traffic for dev.chat.megacampus.com -> routes to port 8001"
echo "=========================================================="

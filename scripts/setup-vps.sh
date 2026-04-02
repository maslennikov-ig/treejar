#!/usr/bin/env bash
# VPS Infrastructure Setup Script
# Idempotent script to install and configure Nginx for the production setup.
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
REPO_DIR="/opt/treejar-prod"

if [ ! -d "$REPO_DIR/scripts" ]; then
    echo "Error: Could not find the repository at $REPO_DIR."
    echo "Please clone the repo first: cd /home/starec && git clone https://github.com/maslennikov-ig/treejar.git treejar-ai-bot"
    exit 1
fi

# Copy Nginx config to sites-available
cp "$REPO_DIR/scripts/treejar-prod.conf" /etc/nginx/sites-available/treejar-prod

# Enable the site by creating a symlink
ln -sf /etc/nginx/sites-available/treejar-prod /etc/nginx/sites-enabled/

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
echo "Traffic for noor.starec.ai -> routes to port 8002"
echo "=========================================================="

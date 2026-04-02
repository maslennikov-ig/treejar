#!/usr/bin/env bash
# VPS Infrastructure Setup Script
# Idempotent script to install and configure Nginx for the production setup.
# Run this once on the VPS as root.

set -e

DOMAIN="noor.starec.ai"
REPO_DIR="/opt/treejar-prod"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
BOOTSTRAP_CONFIG="treejar-prod-bootstrap.conf"
TLS_CONFIG="treejar-prod.conf"

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

if [ ! -d "$REPO_DIR/scripts" ]; then
    echo "Error: Could not find the repository at $REPO_DIR."
    echo "Please clone the repo first: git clone --branch main https://github.com/maslennikov-ig/treejar.git $REPO_DIR"
    exit 1
fi

# Fresh VPS bootstrap must not depend on certificates that do not exist yet.
mkdir -p /var/www/certbot

if [ -f "$CERT_DIR/fullchain.pem" ] && [ -f "$CERT_DIR/privkey.pem" ]; then
    SELECTED_CONFIG="$TLS_CONFIG"
    echo "TLS certificates found for $DOMAIN. Enabling HTTPS config."
else
    SELECTED_CONFIG="$BOOTSTRAP_CONFIG"
    echo "TLS certificates not found for $DOMAIN. Enabling HTTP-only bootstrap config."
fi

# Copy Nginx config to sites-available
cp "$REPO_DIR/scripts/$SELECTED_CONFIG" /etc/nginx/sites-available/treejar-prod

# Enable the site by creating a symlink
ln -sf /etc/nginx/sites-available/treejar-prod /etc/nginx/sites-enabled/

# Remove default nginx site if it exists to avoid port 80 conflicts
if [ -f /etc/nginx/sites-enabled/default ]; then
    echo "Removing default nginx site..."
    rm /etc/nginx/sites-enabled/default
fi

# Clean up stale dev site remnants from older mixed-environment setups.
for stale_site in \
    /etc/nginx/sites-enabled/treejar-dev \
    /etc/nginx/sites-enabled/treejar-dev.conf \
    /etc/nginx/sites-available/treejar-dev \
    /etc/nginx/sites-available/treejar-dev.conf
do
    if [ -e "$stale_site" ]; then
        echo "Removing stale Nginx site: $stale_site"
        rm -f "$stale_site"
    fi
done

echo "[3/4] Testing Nginx configuration..."
nginx -t

echo "[4/4] Reloading Nginx to apply changes..."
systemctl reload nginx

echo "=========================================================="
echo "                      SETUP COMPLETE                      "
echo "=========================================================="
if [ "$SELECTED_CONFIG" = "$TLS_CONFIG" ]; then
    echo "HTTPS is active for $DOMAIN -> routes to port 8002"
else
    echo "HTTP bootstrap is active for $DOMAIN -> routes to port 8002"
    echo "Issue the Let's Encrypt certificate, then rerun this script to enable HTTPS."
fi
echo "=========================================================="

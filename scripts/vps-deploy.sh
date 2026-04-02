#!/usr/bin/env bash
# VPS Deployment Script
# Automatically pulls the latest code and deploys the production stack.
# Note: The repository should be cloned via SSH (or with HTTPS credentials cached) on the VPS.

set -e

# Configuration
BRANCH="${1:-main}"
REPO_DIR="/opt/treejar-prod"

if [ "$BRANCH" != "main" ]; then
    echo "Error: Only the 'main' branch is supported."
    exit 1
fi

echo "Starting deployment for branch: $BRANCH in directory $REPO_DIR"

cd "$REPO_DIR" || {
    echo "Repository not found at $REPO_DIR. Please clone it first:"
    echo "git clone -b $BRANCH git@github.com:maslennikov-ig/treejar.git $REPO_DIR"
    exit 1
}

# Fetch latest changes
git fetch origin

# Deploy production
echo "Deploying PRODUCTION environment..."
git checkout main
git reset --hard origin/main

# Ensure .env exists
if [ ! -f .env ]; then
    echo "Warning: .env not found! Copying from .env.example..."
    cp .env.example .env
fi

# Build and restart production compose stack
docker compose -p treejar-prod -f docker-compose.yml up -d --build
docker compose -p treejar-prod -f docker-compose.yml restart nginx
echo "Production deployment successful!"

# Reload Nginx Host configuration (Optional, uncomment if Nginx configs are updated frequently)
# sudo systemctl reload nginx

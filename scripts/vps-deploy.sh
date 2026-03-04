#!/usr/bin/env bash
# VPS Deployment Script
# Automatically pulls the latest code and spins up the correct environment.
# Note: The repository should be cloned via SSH (or with HTTPS credentials cached) on the VPS.

set -e

# Configuration
REPO_DIR="/home/starec/treejar-ai-bot" # Change to the path of your cloned repository on the VPS
BRANCH="${1:-main}"    # Default to main if no argument provided

echo "Starting deployment for branch: $BRANCH"

cd "$REPO_DIR"

# Fetch latest changes
git fetch origin

# Determine environment based on branch
if [ "$BRANCH" = "develop" ]; then
    echo "Deploying DEVELOPMENT environment..."
    git checkout develop
    git reset --hard origin/develop
    
    # Ensure .env.dev exists
    if [ ! -f .env.dev ]; then
        echo "Warning: .env.dev not found! Copying from .env.example..."
        cp .env.example .env.dev
    fi

    # Build and restart Development Compose stack
    docker compose -f docker-compose.dev.yml up -d --build
    docker compose -f docker-compose.dev.yml restart nginx
    echo "Development deployment successful!"

elif [ "$BRANCH" = "main" ]; then
    echo "Deploying PRODUCTION environment..."
    git checkout main
    git reset --hard origin/main
    
    # Ensure .env exists
    if [ ! -f .env ]; then
        echo "Warning: .env not found! Copying from .env.example..."
        cp .env.example .env
    fi

    # Build and restart Production Compose stack
    docker compose -f docker-compose.yml up -d --build
    docker compose -f docker-compose.yml restart nginx
    echo "Production deployment successful!"

else
    echo "Error: Unknown branch '$BRANCH'. Please use 'main' or 'develop'."
    exit 1
fi

# Reload Nginx Host configuration (Optional, uncomment if Nginx configs are updated frequently)
# sudo systemctl reload nginx

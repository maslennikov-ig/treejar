#!/usr/bin/env bash
#
# Deploy Script - Merge current branch into master for production deployment
# Uses Git Worktrees to isolate local checks from the active developer workspace.
#
# Usage: ./deploy.sh [--force] [--yes] [--sync]
#        --force: Skip quality checks (type-check, build)
#        --yes: Skip confirmation prompt
#        --sync: Auto-sync develop with master after deploy

set -eo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $*${NC}"; }
log_success() { echo -e "${GREEN}✅ $*${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $*${NC}"; }
log_error() { echo -e "${RED}❌ $*${NC}" >&2; }

main() {
    cd "$PROJECT_ROOT"

    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                  Production Deploy                         ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""

    # Parse arguments
    local force_deploy="false"
    local auto_confirm="false"
    local auto_sync="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force|-f) force_deploy="true"; shift ;;
            --yes|-y) auto_confirm="true"; shift ;;
            --sync|-s) auto_sync="true"; shift ;;
            *) log_error "Unknown argument: $1"; exit 1 ;;
        esac
    done

    # Check current branch
    local current_branch=$(git branch --show-current)
    local source_branch="$current_branch"
    log_info "Current branch: $current_branch"

    # If on master, use develop as source
    if [ "$current_branch" = "master" ] || [ "$current_branch" = "main" ]; then
        log_warning "Already on master branch"
        if git rev-parse --verify develop >/dev/null 2>&1; then
            source_branch="develop"
            log_info "Will merge from: develop"
        else
            log_error "No develop branch to merge from"
            echo "Switch to the branch you want to deploy first:"
            echo "  git checkout <branch>"
            echo "  /deploy"
            exit 1
        fi
    fi

    # Ensure master branch exists
    if ! git rev-parse --verify master >/dev/null 2>&1; then
        log_error "Branch 'master' does not exist"
        exit 1
    fi

    # Fetch latest from remote
    log_info "Fetching latest from remote..."
    git fetch origin master "$source_branch" 2>/dev/null || true

    # Check if source branch has changes not in master
    local commits_ahead=$(git rev-list master.."$source_branch" --count 2>/dev/null || echo "0")
    if [ "$commits_ahead" -eq 0 ]; then
        log_warning "No new commits in $source_branch to deploy"
        echo "$source_branch is already merged into master"
        exit 0
    fi
    log_success "Found $commits_ahead commit(s) to deploy from $source_branch"

    # Show what will be deployed
    echo ""
    log_info "Commits to deploy ($source_branch → master):"
    git log master.."$source_branch" --oneline -20
    if [ "$commits_ahead" -gt 20 ]; then
        echo "  ... and $((commits_ahead - 20)) more commits"
    fi
    echo ""

    # Confirmation
    if [ "$auto_confirm" != "true" ]; then
        # Check if running interactively
        if [ -t 0 ]; then
            read -p "Deploy these $commits_ahead commit(s) to production? [Y/n]: " confirm
            if [[ ! "$confirm" =~ ^[Yy]?$ ]]; then
                log_warning "Deploy cancelled"
                exit 0
            fi
        else
            log_error "Non-interactive mode requires --yes flag"
            echo "Usage: /deploy --yes"
            exit 1
        fi
    fi

    local worktree_dir="../treejar-deploy-tmp-$$"
    
    # Clean up trap for the temporary worktree
    cleanup() {
        if [ -d "$worktree_dir" ]; then
            log_info "Cleaning up temporary worktree..."
            rm -rf "$worktree_dir"
            git worktree prune >/dev/null 2>&1 || true
        fi
    }
    trap cleanup EXIT

    log_info "Creating isolated Worktree at $worktree_dir for master..."
    
    # Before we create worktree, let's make sure our local master is relatively up to date 
    # (even though we'll pull inside the worktree)
    # the simplest way without touching the current working directory's state:
    if ! git worktree add "$worktree_dir" master 2>/dev/null; then
        log_error "Failed to create worktree. Is 'master' already checked out somewhere else?"
        exit 1
    fi

    # Switch to the temporary worktree
    pushd "$worktree_dir" > /dev/null

    # Pull latest master
    log_info "Pulling latest master in isolated worktree..."
    git pull origin master --quiet 2>/dev/null || true

    # Merge source branch into master
    log_info "Merging $source_branch into master..."
    local merge_msg="deploy: merge $source_branch into master

Deploying $commits_ahead commit(s) to production from $source_branch.

🤖 Generated with [Claude Code / Antigravity]
"

    if ! git merge "$source_branch" --no-ff -m "$merge_msg"; then
        log_error "Merge conflict! Resolve manually in your main repo:"
        echo "  1. git checkout master"
        echo "  2. git merge $source_branch"
        echo "  3. Fix conflicts and commit"
        echo "  4. git push origin master"
        exit 1
    fi
    log_success "Merge successful in worktree"

    # Run quality checks (unless --force)
    if [ "$force_deploy" != "true" ]; then
        log_info "Running quality checks in isolated worktree..."

        # Sync Beads before tests (if bd is available)
        if command -v bd &> /dev/null; then
            log_info "Syncing Beads..."
            bd sync 2>/dev/null || true
        fi

        log_info "Running tests (pytest)..."
        if ! pytest; then
            log_error "Tests failed! Fix errors in your main worktree before deploying."
            exit 1
        fi
        log_success "Pytest passed"

        log_info "Running ruff check..."
        if ! ruff check .; then
            log_error "Ruff check failed! Fix errors in your main worktree before deploying."
            exit 1
        fi
        log_success "Ruff passed"

        log_info "Running mypy..."
        if ! mypy . 2>/dev/null; then
            log_warning "Mypy failed, check if this is a blocking issue or fix before deploying."
            # Depending on project strictness, you might want to switch exit 1 here
        fi
        log_success "Mypy checks completed"
        
    else
        log_warning "Skipping quality checks (--force)"
    fi

    # Push to master (triggers deploy)
    log_info "Pushing master to origin (triggering deploy)..."
    if ! git push origin master; then
        log_error "Push failed!"
        echo "To retry manually: git push origin master"
        exit 1
    fi
    log_success "Pushed to master"

    popd > /dev/null

    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║              DEPLOY SUCCESSFUL! 🚀                        ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
    log_success "Deployed $commits_ahead commit(s) to production"
    log_success "Merged: $source_branch → master"
    echo ""

    # Sync develop with master if deployed from a feature branch
    if [ "$source_branch" != "develop" ] && [ "$source_branch" != "main" ] && [ "$source_branch" != "master" ]; then
        if [ "$auto_sync" = "true" ]; then
            log_info "Syncing develop with master (--sync flag)..."
            git fetch origin master:master --quiet
            git checkout develop --quiet
            if git merge master --no-edit; then
                git push origin develop --quiet 2>/dev/null || true
                log_success "develop synced with master"
                git checkout "$source_branch" --quiet
            else
                log_warning "Merge conflict while syncing develop"
                echo "Resolve manually, then: git push origin develop"
                git checkout "$source_branch" --quiet
            fi
            echo ""
        else
            echo "┌─────────────────────────────────────────────────────────────┐"
            echo "│  ⚠️  IMPORTANT: Sync develop with master                    │"
            echo "│                                                             │"
            echo "│  You deployed from '$source_branch' (not develop)."
            echo "│  To keep develop up-to-date, run:                           │"
            echo "│                                                             │"
            echo "│    git checkout develop                                     │"
            echo "│    git merge master                                         │"
            echo "│    git push origin develop                                  │"
            echo "│                                                             │"
            echo "│  Or use: /deploy --sync  (auto-sync after deploy)           │"
            echo "└─────────────────────────────────────────────────────────────┘"
            echo ""
        fi
    fi
}

main "$@"

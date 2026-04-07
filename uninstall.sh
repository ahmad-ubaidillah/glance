#!/bin/bash
# =============================================================================
# Glance Uninstaller - Remove Glance completely
# =============================================================================
# Usage:
#   curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/uninstall.sh | bash
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║                    Glance Uninstaller                             ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

for dir in "venv" ".venv"; do
    if [ -d "$dir" ]; then
        log_info "Removing $dir..."
        rm -rf "$dir"
        log_success "Removed $dir"
    fi
done

if [ -f "$HOME/.local/bin/glance" ]; then
    log_info "Removing glance wrapper..."
    rm -f "$HOME/.local/bin/glance"
    log_success "Removed glance wrapper"
fi

if [ -d ".glance" ]; then
    read -p "$(echo -e ${YELLOW}Remove .glance data directory? (y/N): ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf ".glance"
        log_success "Removed .glance data"
    fi
fi

if [ -f ".env" ]; then
    read -p "$(echo -e ${YELLOW}Remove .env file? (y/N): ${NC})" -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f ".env"
        log_success "Removed .env"
    fi
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Glance Uninstalled!                                  ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"

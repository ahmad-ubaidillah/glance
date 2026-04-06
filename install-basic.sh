#!/bin/bash
# =============================================================================
# Glance Basic Installer - Core review engine only (~10MB)
# No TUI dashboard, no RAG, no ML features
# =============================================================================
# Usage:
#   curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install-basic.sh | bash
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
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
        if [ "$PYTHON_MINOR" -ge 10 ]; then
            log_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
            return 0
        fi
    fi
    return 1
}

install_python() {
    log_info "Installing Python 3.11..."
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian|linuxmint) sudo apt-get update && sudo apt-get install -y python3.11 python3-pip ;;
            fedora|rhel|centos) sudo dnf install -y python311 python311-pip ;;
            arch|manjaro) sudo pacman -S --noconfirm python ;;
            *) log_error "Unsupported OS. Install Python 3.10+ manually."; exit 1 ;;
        esac
        PYTHON_CMD="python3"
    fi
    log_success "Python installed"
}

install_glance() {
    log_info "Installing Glance Basic..."
    if command -v uv &> /dev/null; then
        uv pip install -e . --quiet
        uv tool install -e . --quiet 2>/dev/null || true
    elif command -v pip3 &> /dev/null; then
        pip3 install -e . --quiet
    elif $PYTHON_CMD -m pip --version &> /dev/null; then
        $PYTHON_CMD -m pip install -e . --quiet
    else
        log_error "No pip found."; exit 1
    fi
    log_success "Glance Basic installed!"
}

main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║              Glance Basic Installer v1.0                          ║"
    echo "║         Core Review Engine Only (No TUI, No RAG)                  ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    if ! check_python; then
        log_warn "Python 3.10+ not found"
        install_python
    fi
    
    install_glance
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Glance Basic Installed!                              ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}What you got:${NC}"
    echo "  ✅ Multi-agent AI code review"
    echo "  ✅ Adaptive routing"
    echo "  ✅ Inline comments + auto-fix"
    echo "  ❌ No TUI dashboard"
    echo "  ❌ No RAG/ML features"
    echo ""
    echo -e "${YELLOW}To upgrade to full version:${NC}"
    echo "  curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install-full.sh | bash"
    echo ""
}

main "$@"

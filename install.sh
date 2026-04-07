#!/bin/bash
# =============================================================================
# Glance Standard Installer - Core + TUI + Memory (~15MB)
# =============================================================================
# Usage:
#   curl -sSL https://raw.githubusercontent.com/ahmad-ubaidillah/glance/main/install.sh | bash
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root for system install
IS_ROOT=false
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=true
fi

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
    elif [ -f /etc/debian_version ]; then
        OS="debian"
    elif [ -f /etc/SuSE-release ]; then
        OS="suse"
    elif [ -f /etc/arch-release ]; then
        OS="arch"
    else
        OS="unknown"
    fi
}

# Check Python version
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
        PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
        
        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            log_success "Python $PYTHON_VERSION found"
            PYTHON_CMD="python3"
            return 0
        elif [ "$PYTHON_MAJOR" -eq 3 ]; then
            log_warn "Python version is $PYTHON_VERSION, but 3.10+ required"
        fi
    fi
    return 1
}

# Install Python
install_python() {
    log_info "Installing Python 3.11..."
    
    detect_os
    
    case "$OS" in
        ubuntu|debian|linuxmint)
            sudo apt-get update
            sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip
            PYTHON_CMD="python3.11"
            ;;
        fedora|rhel|centos)
            sudo dnf install -y python311 python311-devel
            PYTHON_CMD="python3.11"
            ;;
        arch|manjaro)
            sudo pacman -S --noconfirm python
            PYTHON_CMD="python"
            ;;
        darwin)
            if command -v brew &> /dev/null; then
                brew install python@3.11
                PYTHON_CMD="python3.11"
            else
                log_error "Homebrew not found. Please install Python from https://www.python.org/"
                exit 1
            fi
            ;;
        *)
            log_error "Unsupported OS: $OS"
            log_info "Please install Python 3.10+ manually from https://www.python.org/"
            exit 1
            ;;
    esac
    
    log_success "Python installed"
}

# Create virtual environment
setup_venv() {
    log_info "Creating virtual environment..."
    
    # Use system python if available, otherwise use the one we just installed
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    fi
    
    if [ ! -d "venv" ]; then
        $PYTHON_CMD -m venv venv
    fi
    
    log_success "Virtual environment created"
}

# Install Glance
install_glance() {
    log_info "Installing Glance..."
    
    if [ -d "venv" ]; then
        VENV_PYTHON="venv/bin/python"
    fi
    
    if [ -x "$VENV_PYTHON" ]; then
        # Upgrade pip in venv first
        $VENV_PYTHON -m pip install --upgrade pip --quiet 2>/dev/null
        
        # Install glance in venv
        UV_SYSTEM_PYTHON=1 $VENV_PYTHON -m pip install "git+https://github.com/ahmad-ubaidillah/glance.git" --quiet
        
        # Also install globally so 'glance' works from anywhere
        log_info "Making glance available globally..."
        $VENV_PYTHON -m pip install --user "git+https://github.com/ahmad-ubaidillah/glance.git" --quiet 2>/dev/null || \
            $VENV_PYTHON -m pip install "git+https://github.com/ahmad-ubaidillah/glance.git" --quiet --target "$HOME/.local/lib/python3.14/site-packages" 2>/dev/null || true
        
        # Create global symlink/wrapper
        if [ -d "$HOME/.local/bin" ]; then
            cat > "$HOME/.local/bin/glance" << 'WRAPPER'
#!/bin/bash
exec "$HOME/Documents/webapp/venv/bin/python" -m glance.cli "$@"
WRAPPER
            chmod +x "$HOME/.local/bin/glance"
        fi
        
        if command -v glance &> /dev/null || [ -x "$HOME/.local/bin/glance" ]; then
            log_success "Glance installed! Run 'glance dashboard' from anywhere"
        else
            log_success "Glance installed! Run: source venv/bin/activate && glance dashboard"
        fi
    else
        log_error "Virtual environment not found or broken"
        exit 1
    fi
}

# Create .env if not exists
setup_env() {
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_info ".env file created. Please configure it with your API keys."
        fi
    fi
}

# Main installation
main() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║                    Glance Installer v1.0                          ║"
    echo "║              AI-Powered Code Review System                        ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Check Python
    if ! check_python; then
        log_warn "Python 3.10+ not found"
        install_python
    fi
    
    # Setup virtual environment
    setup_venv
    
    # Install Glance
    install_glance
    
    # Setup env file
    setup_env
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Glance Installed!                                    ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}What you got:${NC}"
    echo "  ✅ Multi-agent AI code review"
    echo "  ✅ Adaptive routing"
    echo "  ✅ Inline comments + auto-fix"
    echo "  ✅ TUI dashboard"
    echo "  ✅ Memory & learning system"
    echo ""
    echo -e "${YELLOW}NEXT STEPS:${NC}"
    echo "─────────────────────────────────────────────────────────────────"
    echo "1. Configure your API keys in .env file:"
    echo "   - LLM_API_KEY     : Your LLM provider API key"
    echo "   - GIT_TOKEN      : Your Git provider token (repo write)"
    echo ""
    echo "2. Open the interactive dashboard:"
    echo "   glance dashboard"
    echo ""
    echo "3. Or use in your GitHub Actions:"
    echo "   See README.md for the workflow configuration"
    echo ""
    echo -e "${BLUE}For more info: https://github.com/ahmad-ubaidillah/glance${NC}"
    echo ""
}

# Run main
main "$@"

#!/bin/bash

# HLS Webhook Handler Installation Script
# This script sets up all necessary components for the webhook handler

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions for colored output
print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Check if running as root when needed
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This operation requires root privileges. Please run with sudo."
        exit 1
    fi
}

# Main installation function
main() {
    print_info "HLS Webhook Handler Installation Script"
    echo "======================================"
    echo ""
    
    # Parse command line arguments
    INSTALL_MODE="interactive"
    SKIP_WEBHOOK_BINARY=false
    SKIP_SYSTEMD=false
    SKIP_PM2=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev)
                INSTALL_MODE="dev"
                shift
                ;;
            --prod)
                INSTALL_MODE="prod"
                shift
                ;;
            --skip-webhook-binary)
                SKIP_WEBHOOK_BINARY=true
                shift
                ;;
            --skip-systemd)
                SKIP_SYSTEMD=true
                shift
                ;;
            --skip-pm2)
                SKIP_PM2=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Interactive mode - ask user
    if [[ "$INSTALL_MODE" == "interactive" ]]; then
        echo "Select installation mode:"
        echo "1) Development (pm2/nohup)"
        echo "2) Production (systemd services)"
        echo "3) Custom installation"
        read -p "Enter choice (1-3): " choice
        
        case $choice in
            1)
                INSTALL_MODE="dev"
                ;;
            2)
                INSTALL_MODE="prod"
                ;;
            3)
                custom_install
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                exit 1
                ;;
        esac
    fi
    
    # Start installation
    print_info "Starting installation in $INSTALL_MODE mode..."
    echo ""
    
    # Step 1: Check Python environment
    check_python_env
    
    # Step 2: Install Python dependencies
    install_python_deps
    
    # Step 3: Install webhook binary if needed
    if [[ "$SKIP_WEBHOOK_BINARY" != true ]]; then
        install_webhook_binary
    fi
    
    # Step 4: Set up configuration files
    setup_config_files
    
    # Step 5: Create necessary directories
    create_directories
    
    # Step 6: Set up startup method based on mode
    if [[ "$INSTALL_MODE" == "dev" ]]; then
        setup_dev_mode
    else
        setup_prod_mode
    fi
    
    # Step 7: Set up cron job (optional)
    setup_cron_job
    
    # Final summary
    print_summary
}

# Show help message
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --dev               Install in development mode (pm2/nohup)
    --prod              Install in production mode (systemd)
    --skip-webhook-binary   Skip webhook binary installation
    --skip-systemd      Skip systemd service installation
    --skip-pm2          Skip pm2 installation
    --help              Show this help message

Examples:
    $0                  # Interactive installation
    $0 --dev           # Development installation
    $0 --prod          # Production installation
    sudo $0 --prod     # Production with root privileges
EOF
}

# Custom installation menu
custom_install() {
    print_info "Custom Installation"
    echo "=================="
    
    # Python dependencies
    read -p "Install Python dependencies? (y/n): " install_py
    if [[ "$install_py" == "y" ]]; then
        install_python_deps
    fi
    
    # Webhook binary
    read -p "Install webhook binary? (y/n): " install_webhook
    if [[ "$install_webhook" == "y" ]]; then
        install_webhook_binary
    fi
    
    # Configuration
    read -p "Set up configuration files? (y/n): " setup_config
    if [[ "$setup_config" == "y" ]]; then
        setup_config_files
    fi
    
    # Systemd services
    read -p "Install systemd services? (y/n): " install_systemd
    if [[ "$install_systemd" == "y" ]]; then
        check_root
        install_systemd_services
    fi
    
    # pm2
    read -p "Set up pm2? (y/n): " setup_pm2
    if [[ "$setup_pm2" == "y" ]]; then
        setup_pm2_config
    fi
    
    # Cron job
    read -p "Set up cron job for issue analysis? (y/n): " setup_cron
    if [[ "$setup_cron" == "y" ]]; then
        setup_cron_job
    fi
    
    print_success "Custom installation completed!"
}

# Check Python environment
check_python_env() {
    print_info "Checking Python environment..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    print_success "Python $PYTHON_VERSION found"
    
    # Check for virtual environment
    if [[ -n "$VIRTUAL_ENV" ]]; then
        print_success "Virtual environment active: $VIRTUAL_ENV"
    else
        print_info "No virtual environment active"
        read -p "Create virtual environment? (y/n): " create_venv
        if [[ "$create_venv" == "y" ]]; then
            python3 -m venv venv
            source venv/bin/activate
            print_success "Virtual environment created and activated"
        fi
    fi
}

# Install Python dependencies
install_python_deps() {
    print_info "Installing Python dependencies..."
    
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        print_success "Python dependencies installed"
    else
        print_error "requirements.txt not found"
        exit 1
    fi
}

# Install webhook binary
install_webhook_binary() {
    print_info "Checking webhook binary..."
    
    if command -v webhook &> /dev/null; then
        WEBHOOK_VERSION=$(webhook -version 2>&1 | head -n1)
        print_success "Webhook already installed: $WEBHOOK_VERSION"
        return
    fi
    
    print_info "Webhook binary not found. Installing..."
    
    # Detect architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            WEBHOOK_ARCH="amd64"
            ;;
        aarch64)
            WEBHOOK_ARCH="arm64"
            ;;
        *)
            print_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
    
    # Download webhook
    WEBHOOK_VERSION="2.8.1"
    WEBHOOK_URL="https://github.com/adnanh/webhook/releases/download/${WEBHOOK_VERSION}/webhook-linux-${WEBHOOK_ARCH}.tar.gz"
    
    print_info "Downloading webhook ${WEBHOOK_VERSION} for ${WEBHOOK_ARCH}..."
    wget -q "$WEBHOOK_URL" -O webhook.tar.gz
    tar -xzf webhook.tar.gz
    
    # Install to /usr/local/bin (requires sudo)
    if [[ -w "/usr/local/bin" ]]; then
        mv webhook-linux-${WEBHOOK_ARCH}/webhook /usr/local/bin/
        chmod +x /usr/local/bin/webhook
    else
        print_info "Installing webhook requires sudo privileges"
        sudo mv webhook-linux-${WEBHOOK_ARCH}/webhook /usr/local/bin/
        sudo chmod +x /usr/local/bin/webhook
    fi
    
    # Clean up
    rm -rf webhook.tar.gz webhook-linux-${WEBHOOK_ARCH}
    
    print_success "Webhook binary installed successfully"
}

# Set up configuration files
setup_config_files() {
    print_info "Setting up configuration files..."
    
    # Check for .env file
    if [[ ! -f ".env" ]]; then
        print_info "Creating .env file..."
        cat > .env << 'EOF'
# GitHub Configuration
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Anthropic Configuration
ANTHROPIC_API_KEY=claude-code

# Optional Configuration
# LOG_LEVEL=INFO
# WEBHOOK_PATH=/hooks
EOF
        print_info ".env file created. Please update with your actual tokens!"
    else
        print_success ".env file already exists"
    fi
    
    # Check for settings.yaml
    if [[ ! -f "config/settings.yaml" ]]; then
        print_info "config/settings.yaml not found. Using defaults."
    else
        print_success "config/settings.yaml found"
    fi
    
    # Make scripts executable
    chmod +x *.sh
    chmod +x webhook_dispatch.py
    chmod +x scripts/*.sh
    chmod +x services/*.sh
    
    print_success "Configuration files set up"
}

# Create necessary directories
create_directories() {
    print_info "Creating necessary directories..."
    
    directories=("logs" "data" "prompts" "config")
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            print_success "Created directory: $dir"
        fi
    done
}

# Set up development mode
setup_dev_mode() {
    print_info "Setting up development mode..."
    
    # Check for pm2
    if command -v pm2 &> /dev/null && [[ "$SKIP_PM2" != true ]]; then
        print_info "pm2 found. Setting up pm2 configuration..."
        
        if [[ -f "ecosystem.config.js" ]]; then
            pm2 start ecosystem.config.js
            pm2 save
            print_success "pm2 configured and started"
        else
            print_info "No ecosystem.config.js found. Using start-webhook.sh instead."
        fi
    else
        print_info "pm2 not found. The start-webhook.sh script will use nohup instead."
    fi
    
    print_success "Development mode setup complete"
    echo ""
    echo "To start the webhook service:"
    echo "  ./start-webhook.sh"
    echo ""
    echo "To stop the webhook service:"
    echo "  ./stop-webhook.sh"
}

# Set up production mode
setup_prod_mode() {
    print_info "Setting up production mode with systemd..."
    
    if [[ "$SKIP_SYSTEMD" == true ]]; then
        print_info "Skipping systemd setup as requested"
        return
    fi
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        print_info "Systemd service installation requires root privileges."
        print_info "Please run: sudo ./services/install-services.sh"
        print_info "Or re-run this installer with sudo: sudo $0 --prod"
    else
        install_systemd_services
    fi
}

# Install systemd services
install_systemd_services() {
    print_info "Installing systemd services..."
    
    if [[ -f "services/install-services.sh" ]]; then
        cd services
        ./install-services.sh
        cd ..
        print_success "Systemd services installed"
    else
        print_error "services/install-services.sh not found"
    fi
}

# Set up pm2 configuration
setup_pm2_config() {
    print_info "Setting up pm2..."
    
    # Install pm2 globally if not present
    if ! command -v pm2 &> /dev/null; then
        print_info "Installing pm2..."
        npm install -g pm2
    fi
    
    # Start with ecosystem config
    if [[ -f "ecosystem.config.js" ]]; then
        pm2 start ecosystem.config.js
        pm2 save
        pm2 startup
        print_success "pm2 configured"
    else
        print_error "ecosystem.config.js not found"
    fi
}

# Set up cron job
setup_cron_job() {
    print_info "Setting up cron job for issue analysis..."
    
    read -p "Add cron job for automatic issue analysis? (y/n): " add_cron
    if [[ "$add_cron" != "y" ]]; then
        return
    fi
    
    CRON_ENTRY="0 */6 * * * $(pwd)/scripts/cron_analyze_issues.sh"
    
    # Check if cron entry already exists
    if crontab -l 2>/dev/null | grep -q "cron_analyze_issues.sh"; then
        print_info "Cron job already exists"
    else
        # Add to crontab
        (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
        print_success "Cron job added (runs every 6 hours)"
    fi
}

# Print installation summary
print_summary() {
    echo ""
    echo "======================================"
    print_success "Installation completed!"
    echo "======================================"
    echo ""
    
    print_info "Next steps:"
    echo ""
    
    # Configuration reminder
    if [[ -f ".env" ]] && grep -q "your_github" .env; then
        print_info "1. Update .env file with your actual tokens:"
        echo "   - GITHUB_TOKEN"
        echo "   - GITHUB_WEBHOOK_SECRET"
        echo ""
    fi
    
    # Mode-specific instructions
    if [[ "$INSTALL_MODE" == "dev" ]]; then
        print_info "2. Start the webhook service:"
        echo "   ./start-webhook.sh"
        echo ""
        print_info "3. Monitor logs:"
        echo "   tail -f logs/webhook.log"
    else
        print_info "2. If not already done, install systemd services:"
        echo "   sudo ./services/install-services.sh"
        echo ""
        print_info "3. Monitor services:"
        echo "   sudo systemctl status github-webhook"
        echo "   sudo journalctl -u github-webhook -f"
    fi
    
    echo ""
    print_info "4. Configure GitHub webhook:"
    echo "   URL: https://your-domain.com/hooks"
    echo "   Content type: application/json"
    echo "   Secret: (from GITHUB_WEBHOOK_SECRET in .env)"
    echo ""
    
    print_info "For more information, see:"
    echo "   - docs/startup-scripts.md"
    echo "   - README.md"
    echo ""
}

# Run main function
main "$@"
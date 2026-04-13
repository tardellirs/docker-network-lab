#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_compose_file() {
    if [ ! -f "docker-compose.yml" ]; then
        error "docker-compose.yml not found. Run './lab.sh generate' first."
        exit 1
    fi
}

dockerclass_generate() {
    local args=()
    if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then
        args+=("-n" "$1")
        shift
    fi
    args+=("$@")
    info "Generating lab configuration..."
    python3 generate_lab.py "${args[@]}"
    info "Done! Run './lab.sh up' to start the lab."
}

dockerclass_up() {
    check_compose_file
    info "Building image and starting containers..."
    docker compose up -d --build
    echo ""
    info "Lab is running! Container status:"
    docker compose ps
    echo ""
    info "Credentials:"
    cat credentials.txt
}

dockerclass_down() {
    check_compose_file
    warn "Stopping and removing all containers, volumes, and network..."
    docker compose down -v
    info "Lab cleaned up."
}

dockerclass_reset() {
    info "Resetting lab (down + up)..."
    dockerclass_down
    dockerclass_up
}

dockerclass_status() {
    check_compose_file
    docker compose ps
}

dockerclass_credentials() {
    if [ ! -f "credentials.txt" ]; then
        error "credentials.txt not found. Run './lab.sh generate' first."
        exit 1
    fi
    cat credentials.txt
}

dockerclass_logs() {
    check_compose_file
    if [ $# -eq 0 ]; then
        docker compose logs
    else
        docker compose logs "$1"
    fi
}

dockerclass_shell() {
    check_compose_file
    if [ $# -eq 0 ]; then
        error "Usage: ./lab.sh shell <container_name>"
        error "Example: ./lab.sh shell student01"
        exit 1
    fi
    info "Entering $1 as root..."
    docker compose exec "$1" /bin/bash
}

dockerclass_usage() {
    echo -e "${BLUE}Computer Networks Lab — Management Script${NC}"
    echo ""
    echo "Usage: ./lab.sh <command> [arguments]"
    echo ""
    echo "Commands:"
    echo "  generate [N] [flags]   Generate docker-compose.yml for N students (default: 20)"
    echo "                         Flags: -s (single password), --base-ssh, --base-http, --base-ttyd"
    echo "  up                     Build and start all containers"
    echo "  down                   Stop and remove all containers, volumes, and network"
    echo "  reset                  Restart lab (down + up)"
    echo "  status                 Show container status"
    echo "  credentials            Display student credentials"
    echo "  logs [container]       View logs (all or specific container)"
    echo "  shell <container>      Enter a container as root"
    echo ""
    echo "Examples:"
    echo "  ./lab.sh generate 25                  # 25 students with random passwords"
    echo "  ./lab.sh generate 10 -s               # 10 students, shared password"
    echo "  ./lab.sh generate 10 -s mypass123     # 10 students, password: mypass123"
    echo "  ./lab.sh up"
    echo "  ./lab.sh shell student01"
    echo "  ./lab.sh logs student03"
}

case "${1:-}" in
    generate)    shift; dockerclass_generate "$@" ;;
    up)          dockerclass_up ;;
    down)        dockerclass_down ;;
    reset)       dockerclass_reset ;;
    status)      dockerclass_status ;;
    credentials) dockerclass_credentials ;;
    logs)        shift; dockerclass_logs "$@" ;;
    shell)       shift; dockerclass_shell "$@" ;;
    *)           dockerclass_usage ;;
esac

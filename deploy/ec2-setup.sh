#!/usr/bin/env bash
# ec2-setup.sh — bootstrap script for a fresh Amazon Linux 2023 / Ubuntu 22.04 EC2 instance.
#
# Run as root (or with sudo):
#   curl -sSL https://raw.githubusercontent.com/your-org/mockapi/main/deploy/ec2-setup.sh | sudo bash
#
# After this script completes:
#   1. Edit /opt/mockapi/.env  (set ADMIN_TOKEN)
#   2. cd /opt/mockapi && docker compose up -d
#   3. Install the CLI on your local machine: pip install -e '.[cli]'
#      then export MOCKAPI_URL=http://<EC2-IP>:8000 MOCKAPI_ADMIN_TOKEN=<your-token>

set -euo pipefail

APP_DIR="/opt/mockapi"

echo "==> Detecting OS..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID=$ID
else
    echo "Cannot detect OS. Exiting."; exit 1
fi

# ── Install Docker ─────────────────────────────────────────────
echo "==> Installing Docker..."
if command -v docker &>/dev/null; then
    echo "    Docker already installed: $(docker --version)"
else
    if [[ "$OS_ID" == "amzn" ]]; then
        yum update -y
        yum install -y docker
        systemctl enable docker
        systemctl start docker
    elif [[ "$OS_ID" == "ubuntu" ]]; then
        apt-get update -y
        apt-get install -y ca-certificates curl gnupg
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
            https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
            > /etc/apt/sources.list.d/docker.list
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        systemctl enable docker
        systemctl start docker
    else
        echo "Unsupported OS: $OS_ID"; exit 1
    fi
fi

# ── Install Docker Compose plugin (if not bundled) ────────────
if ! docker compose version &>/dev/null 2>&1; then
    echo "==> Installing Docker Compose plugin..."
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi
echo "    $(docker compose version)"

# ── Clone / copy app ───────────────────────────────────────────
echo "==> Setting up app directory at $APP_DIR..."
mkdir -p "$APP_DIR"

# If running from a cloned repo, copy from there; otherwise pull from git.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$REPO_ROOT/docker-compose.yml" ]; then
    echo "    Copying from local repo: $REPO_ROOT"
    cp -r "$REPO_ROOT/." "$APP_DIR/"
else
    echo "    No local repo found. Clone your repo into $APP_DIR manually."
fi

# ── Create .env if missing ─────────────────────────────────────
if [ ! -f "$APP_DIR/.env" ]; then
    echo "==> Creating .env from .env.example..."
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    GENERATED_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s|change-me-before-deploy|$GENERATED_TOKEN|g" "$APP_DIR/.env"
    echo ""
    echo "  [!] Auto-generated ADMIN_TOKEN: $GENERATED_TOKEN"
    echo "  [!] This has been written to $APP_DIR/.env — keep it secret."
    echo ""
fi

# ── Open firewall port (if ufw present) ───────────────────────
if command -v ufw &>/dev/null; then
    echo "==> Opening port 8000 in ufw..."
    ufw allow 8000/tcp || true
fi

# ── Security group reminder ────────────────────────────────────
echo ""
echo "==> IMPORTANT: Make sure your EC2 Security Group allows inbound TCP on port 8000"
echo "    (or whatever HOST_PORT you set in .env) from your target IP range."
echo ""

echo "==> Setup complete."
echo ""
echo "Next steps:"
echo "  1.  cd $APP_DIR"
echo "  2.  Review / edit .env (especially ADMIN_TOKEN)"
echo "  3.  docker compose up -d --build"
echo "  4.  docker compose logs -f            # watch startup"
echo "  5.  curl http://localhost:8000/health  # should return {\"status\":\"ok\"}"

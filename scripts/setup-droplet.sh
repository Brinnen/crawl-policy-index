#!/usr/bin/env bash
# Install Go, Python packages, and build the fetcher. Run from the repo root.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run this as root the first time (you already are on the droplet)."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl ca-certificates python3 python3-venv python3-pip gcc

if ! command -v go >/dev/null 2>&1 || ! go version | grep -qE 'go1\.(2[3-9]|[3-9][0-9])'; then
  echo "Installing Go..."
  curl -fsSL "https://go.dev/dl/go1.24.6.linux-amd64.tar.gz" -o /tmp/go.tgz
  rm -rf /usr/local/go
  tar -C /usr/local -xzf /tmp/go.tgz
  rm -f /tmp/go.tgz
fi

if ! grep -q '/usr/local/go/bin' /root/.bashrc 2>/dev/null; then
  echo 'export PATH=/usr/local/go/bin:$PATH' >> /root/.bashrc
fi
export PATH=/usr/local/go/bin:$PATH

echo "Go: $(go version)"
echo "Python: $(python3 --version)"

cd "$(dirname "$0")/.."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data
cd fetcher
go build -o cpifetch ./cmd/cpifetch
echo ""
echo "Setup finished. Next: bash scripts/run-once.sh"

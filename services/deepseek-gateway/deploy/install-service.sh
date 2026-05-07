#!/usr/bin/env bash
# Install DeepSeek TUI Runtime API + Exam Bridge as background services.
# Supports macOS (launchd) and Linux (systemd).
# Usage:
#   ./deploy/install-service.sh                 # API only
#   ./deploy/install-service.sh --with-bridge   # API + Exam Bridge
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

WITH_BRIDGE=false
for arg in "$@"; do
    case "$arg" in
        --with-bridge) WITH_BRIDGE=true ;;
    esac
done

echo -e "${BOLD}DeepSeek TUI Runtime API — Service Installer${NC}"
if $WITH_BRIDGE; then
    echo -e "Mode: API + Exam Bridge\n"
else
    echo -e "Mode: API only (use --with-bridge for exam bridge)\n"
fi

# ── Detect platform ────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
    Darwin)  PLATFORM=macos ;;
    Linux)   PLATFORM=linux ;;
    *)
        echo -e "${RED}Unsupported OS: $OS${NC}"
        exit 1
        ;;
esac
echo -e "Platform: ${GREEN}$PLATFORM${NC}"

# ── Locate the deepseek binaries ────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Detect platform-specific bundled binary directory
case "$PLATFORM" in
    macos)  BUNDLE_SUBDIR="macos-x64" ;;
    linux)  BUNDLE_SUBDIR="linux-x64" ;;
esac
BUNDLED_DEEPSEEK="$SCRIPT_DIR/bin/$BUNDLE_SUBDIR/deepseek"
BUNDLED_DEEPSEEK_TUI="$SCRIPT_DIR/bin/$BUNDLE_SUBDIR/deepseek-tui"

# Prepare PATH — install bundled binaries to /usr/local/bin if present
BUNDLED_INSTALLED=false
if [ -x "$BUNDLED_DEEPSEEK" ] && [ -x "$BUNDLED_DEEPSEEK_TUI" ]; then
    echo -e "${GREEN}📦 Offline bundle detected${NC} ($BUNDLE_SUBDIR) — installing binaries to /usr/local/bin..."
    sudo mkdir -p /usr/local/bin
    sudo cp "$BUNDLED_DEEPSEEK" /usr/local/bin/deepseek
    sudo cp "$BUNDLED_DEEPSEEK_TUI" /usr/local/bin/deepseek-tui
    sudo chmod +x /usr/local/bin/deepseek /usr/local/bin/deepseek-tui
    # Verify the installed binary actually runs on this architecture
    if /usr/local/bin/deepseek --version &>/dev/null; then
        BUNDLED_INSTALLED=true
    else
        echo -e "${YELLOW}⚠  Bundled binaries are not compatible with this machine's architecture.${NC}"
        echo -e "${YELLOW}   Falling back to system search...${NC}"
        sudo rm -f /usr/local/bin/deepseek /usr/local/bin/deepseek-tui
    fi
fi

DEEPSEEK_BIN="${DEEPSEEK_BIN:-}"
DEEPSEEK_TUI_BIN="${DEEPSEEK_TUI_BIN:-}"

if [ -z "$DEEPSEEK_BIN" ]; then
    DEEPSEEK_BIN="$(which deepseek 2>/dev/null || true)"
fi
if [ -z "$DEEPSEEK_BIN" ]; then
    # Try common paths + bundled-installed path
    for candidate in \
        "/usr/local/bin/deepseek" \
        "$HOME/.cargo/bin/deepseek" \
        "/opt/homebrew/bin/deepseek" \
        "$HOME/.local/bin/deepseek"; do
        if [ -x "$candidate" ]; then
            DEEPSEEK_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$DEEPSEEK_TUI_BIN" ]; then
    DEEPSEEK_TUI_BIN="$(which deepseek-tui 2>/dev/null || true)"
fi
if [ -z "$DEEPSEEK_TUI_BIN" ]; then
    for candidate in \
        "/usr/local/bin/deepseek-tui" \
        "$HOME/.cargo/bin/deepseek-tui" \
        "/opt/homebrew/bin/deepseek-tui" \
        "$HOME/.local/bin/deepseek-tui"; do
        if [ -x "$candidate" ]; then
            DEEPSEEK_TUI_BIN="$candidate"
            break
        fi
    done
fi

if [ -z "$DEEPSEEK_BIN" ]; then
    echo -e "${RED}deepseek binary not found.${NC}"
    if [ "$BUNDLED_INSTALLED" = false ]; then
        echo "Install options:"
        echo "  • npm install -g deepseek-tui           (recommended, ~43 MB)"
        echo "  • cargo install deepseek-tui-cli --locked"
        echo "  • Download from https://github.com/Hmbown/DeepSeek-TUI/releases"
    else
        echo "  The bundled binary was installed but failed to execute."
        echo "  This likely means the architecture doesn't match."
        echo "  Build from source: cargo install deepseek-tui-cli --locked"
    fi
    exit 1
fi

echo -e "deepseek:     ${GREEN}$DEEPSEEK_BIN${NC}"
echo -e "              Version: $( $DEEPSEEK_BIN --version 2>&1 )"
if [ -n "$DEEPSEEK_TUI_BIN" ]; then
    echo -e "deepseek-tui: ${GREEN}$DEEPSEEK_TUI_BIN${NC}"
else
    echo -e "deepseek-tui: ${YELLOW}not found (API server may fail to start)${NC}"
fi

# Export for use in service files
export DEEPSEEK_BIN DEEPSEEK_TUI_BIN

# ── Verify API key ──────────────────────────────────────────────────
if [ -n "${DEEPSEEK_API_KEY:-}" ]; then
    echo -e "API key:   ${GREEN}from DEEPSEEK_API_KEY env var${NC}"
elif [ -f "$HOME/.deepseek/config.toml" ] && grep -q 'api_key' "$HOME/.deepseek/config.toml" 2>/dev/null; then
    echo -e "API key:   ${GREEN}from ~/.deepseek/config.toml${NC}"
else
    echo -e "${YELLOW}Warning: No API key found.${NC}"
    echo "Run 'deepseek auth set --provider deepseek' or set DEEPSEEK_API_KEY."
    echo "The service will start but API calls will fail until a key is configured."
fi

# ── Create log directory ────────────────────────────────────────────
sudo mkdir -p /usr/local/var/log
sudo chown "$(whoami)" /usr/local/var/log 2>/dev/null || true

# ── Install per platform ────────────────────────────────────────────

if [ "$PLATFORM" = macos ]; then
    PLIST_SRC="$SCRIPT_DIR/com.deepseek.api.plist"
    PLIST_DST="$HOME/Library/LaunchAgents/com.deepseek.api.plist"

    # Fill in the correct binary path
    mkdir -p "$HOME/Library/LaunchAgents"
    sed "s|/Users/tanjiawen/.cargo/bin/deepseek|$DEEPSEEK_BIN|g" \
        "$PLIST_SRC" > "$PLIST_DST"

    # Unload old instance if any
    launchctl unload "$PLIST_DST" 2>/dev/null || true
    # Load
    launchctl load "$PLIST_DST"

    echo ""
    echo -e "${GREEN}✓ Service installed and started (macOS launchd).${NC}"
    echo ""
    echo "Manage with:"
    echo "  launchctl list | grep deepseek        # check status"
    echo "  launchctl unload $PLIST_DST            # stop"
    echo "  launchctl load $PLIST_DST              # start"
    echo "  tail -f /usr/local/var/log/deepseek-api.log"

elif [ "$PLATFORM" = linux ]; then
    SERVICE_SRC="$SCRIPT_DIR/deepseek-api.service"
    SERVICE_DST="/etc/systemd/system/deepseek-api.service"

    # Fill in the correct binary path and user
    CURRENT_USER="$(whoami)"
    sudo sed -e "s|/usr/local/bin/deepseek|$DEEPSEEK_BIN|g" \
             -e "s|^User=.*|User=$CURRENT_USER|g" \
             -e "s|^Group=.*|Group=$CURRENT_USER|g" \
             -e "s|ReadWritePaths=/Users/tanjiawen|ReadWritePaths=$HOME|g" \
             "$SERVICE_SRC" | sudo tee "$SERVICE_DST" > /dev/null

    sudo systemctl daemon-reload
    sudo systemctl enable deepseek-api
    sudo systemctl restart deepseek-api

    echo ""
    echo -e "${GREEN}✓ Service installed and started (Linux systemd).${NC}"
    echo ""
    echo "Manage with:"
    echo "  sudo systemctl status deepseek-api     # check status"
    echo "  sudo systemctl stop deepseek-api       # stop"
    echo "  sudo systemctl start deepseek-api      # start"
    echo "  sudo journalctl -u deepseek-api -f     # tail logs"
fi

# ── Smoke test (API) ────────────────────────────────────────────────
echo ""
echo "Waiting 2 seconds for the server to start..."
sleep 2
if curl -sf http://127.0.0.1:7878/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API health check passed: http://127.0.0.1:7878/health${NC}"
else
    echo -e "${RED}✗ API health check failed.${NC} Check logs:"
    if [ "$PLATFORM" = macos ]; then
        echo "  tail -f /usr/local/var/log/deepseek-api.err"
    else
        echo "  sudo journalctl -u deepseek-api --no-pager -n 20"
    fi
fi

# ── Install Exam Bridge (optional) ──────────────────────────────────
if $WITH_BRIDGE; then
    echo ""
    echo -e "${BOLD}── Installing Exam Bridge ──${NC}"

    # Check python3
    if ! command -v python3 &>/dev/null; then
        echo -e "${RED}python3 not found. Install Python 3 first.${NC}"
        exit 1
    fi

    # Detect bridge script path
    BRIDGE_PY="$SCRIPT_DIR/exam-bridge.py"
    if [ ! -f "$BRIDGE_PY" ]; then
        echo -e "${RED}exam-bridge.py not found at $BRIDGE_PY${NC}"
        exit 1
    fi

    # Generate a random bridge API key if not set
    if [ -z "${BRIDGE_API_KEY:-}" ]; then
        BRIDGE_API_KEY="brg-$(uuidgen 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(16))')"
        echo -e "Generated bridge API key: ${GREEN}$BRIDGE_API_KEY${NC} (save this!)"
    fi

    if [ "$PLATFORM" = macos ]; then
        BRIDGE_PLIST_SRC="$SCRIPT_DIR/com.deepseek.exam-bridge.plist"
        BRIDGE_PLIST_DST="$HOME/Library/LaunchAgents/com.deepseek.exam-bridge.plist"
        mkdir -p "$HOME/Library/LaunchAgents"
        sed -e "s|/Users/tanjiawen/Infrastructure/references/DeepSeek-TUI/deploy/exam-bridge.py|$BRIDGE_PY|g" \
            -e "s|bridge-secret-change-me|$BRIDGE_API_KEY|g" \
            "$BRIDGE_PLIST_SRC" > "$BRIDGE_PLIST_DST"

        launchctl unload "$BRIDGE_PLIST_DST" 2>/dev/null || true
        launchctl load "$BRIDGE_PLIST_DST"

    elif [ "$PLATFORM" = linux ]; then
        BRIDGE_SERVICE_SRC="$SCRIPT_DIR/exam-bridge.service"
        BRIDGE_SERVICE_DST="/etc/systemd/system/exam-bridge.service"
        CURRENT_USER="$(whoami)"
        sudo sed -e "s|/home/tanjiawen/DeepSeek-TUI/deploy/exam-bridge.py|$BRIDGE_PY|g" \
                 -e "s|^User=.*|User=$CURRENT_USER|g" \
                 -e "s|^Group=.*|Group=$CURRENT_USER|g" \
                 -e "s|bridge-secret-change-me|$BRIDGE_API_KEY|g" \
                 "$BRIDGE_SERVICE_SRC" | sudo tee "$BRIDGE_SERVICE_DST" > /dev/null
        sudo systemctl daemon-reload
        sudo systemctl enable exam-bridge
        sudo systemctl restart exam-bridge
    fi

    sleep 1
    if curl -sf http://127.0.0.1:8888/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Exam Bridge health check passed: http://127.0.0.1:8888/health${NC}"
        echo ""
        echo "Exam Bridge is ready. Test it:"
        echo "  curl -X POST http://127.0.0.1:8888/exam/process \\"
        echo "    -H \"Authorization: Bearer $BRIDGE_API_KEY\" \\"
        echo "    -H \"Content-Type: application/json\" \\"
        echo "    -d '{\"paper\": \"题目：请解释光合作用的过程。\", \"instruction\": \"请批改这道生物题，给出评分和评分理由\"}'"
    else
        echo -e "${RED}✗ Exam Bridge health check failed.${NC} Check logs."
    fi
fi

# ── Final summary ───────────────────────────────────────────────────
echo ""
echo -e "${BOLD}── Deployment complete ──${NC}"
echo ""
echo "Running services:"
echo "  DeepSeek API:  http://127.0.0.1:7878  (health: /health)"
if $WITH_BRIDGE; then
    echo "  Exam Bridge:   http://127.0.0.1:8888  (health: /health)"
fi
echo ""
echo "Next steps:"
echo "  • Set up HTTPS + auth:  caddy run --config deploy/deepseek-api.caddy"
echo "  • Check docs:           deploy/README.md"

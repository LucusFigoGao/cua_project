#!/bin/bash
# Deploy all CUA-Gym-Hub mock apps on a single server via tmux.
# Each mock runs as a separate vite preview process on consecutive ports.
#
# Prerequisites: Node.js (npm), tmux
# Usage: ./deploy-all.sh [--skip-install] [--skip-build] [--no-attach]
#   --skip-install  Skip npm install (use when deps are already installed)
#   --skip-build    Skip npm run build (use when dist/ already exists)
#   --no-attach     Do not attach to tmux session after starting

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
WEBSITES_DIR="$SCRIPT_DIR/websites"

[ -s "$HOME/.nvm/nvm.sh" ] && \. "$HOME/.nvm/nvm.sh"
command -v npm  >/dev/null 2>&1 || { echo "Error: npm not found. Install Node.js first."; exit 1; }
command -v tmux >/dev/null 2>&1 || { echo "Error: tmux not found. Run: apt install tmux"; exit 1; }

BASE_PORT=8000
TMUX_SESSION="cua-gym-hub"
SKIP_INSTALL=false
SKIP_BUILD=false
NO_ATTACH=false

for arg in "$@"; do
    [ "$arg" = "--skip-install" ] && SKIP_INSTALL=true
    [ "$arg" = "--skip-build" ]   && SKIP_BUILD=true
    [ "$arg" = "--no-attach" ]    && NO_ATTACH=true
done

MOCKS=($(find "$WEBSITES_DIR" -mindepth 1 -maxdepth 1 -type d -name '*_mock' -exec basename {} \; | sort))
TOTAL=${#MOCKS[@]}
echo "Found ${TOTAL} mock apps — deploying on ports ${BASE_PORT}-$((BASE_PORT + TOTAL - 1))"

if [ "$TOTAL" -eq 0 ]; then
    echo "Error: no mock apps found under $WEBSITES_DIR"
    exit 1
fi

if [ "$SKIP_INSTALL" = false ]; then
    echo "Installing dependencies..."
    for MOCK in "${MOCKS[@]}"; do
        (cd "$WEBSITES_DIR/$MOCK" && npm install --silent) || true
    done
fi

if [ "$SKIP_BUILD" = false ]; then
    echo "Building all mocks in parallel..."
    BUILD_LOG_DIR="$(mktemp -d)"
    for MOCK in "${MOCKS[@]}"; do
        LOG="$BUILD_LOG_DIR/$MOCK.log"
        (
            cd "$WEBSITES_DIR/$MOCK"
            if npm run build --silent > "$LOG" 2>&1; then
                echo "  [OK]  $MOCK"
            else
                echo "  [ERR] $MOCK (see $LOG)"
            fi
        ) &
    done
    wait
    echo "Build complete"
fi

tmux has-session -t "$TMUX_SESSION" 2>/dev/null && tmux kill-session -t "$TMUX_SESSION"

PORT=$BASE_PORT
tmux new-session -d -s "$TMUX_SESSION" -n "${MOCKS[0]}" \
    "cd '$WEBSITES_DIR/${MOCKS[0]}' && npm run preview -- --host 0.0.0.0 --port $PORT; exec bash"

for i in $(seq 1 $((TOTAL - 1))); do
    MOCK=${MOCKS[$i]}
    PORT=$((BASE_PORT + i))
    tmux new-window -t "$TMUX_SESSION:$i" -n "$MOCK" \
        "cd '$WEBSITES_DIR/$MOCK' && npm run preview -- --host 0.0.0.0 --port $PORT; exec bash"
done

tmux select-window -t "$TMUX_SESSION:0"

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$SERVER_IP" ] && SERVER_IP="<server-ip>"

echo ""
echo "=========================================="
echo "All mocks started in tmux session: $TMUX_SESSION"
echo "=========================================="
for i in $(seq 0 $((TOTAL - 1))); do
    printf "  %-35s http://%s:%d\n" "${MOCKS[$i]}:" "$SERVER_IP" $((BASE_PORT + i))
done
echo ""
echo "Manage session:"
echo "  Attach:     tmux attach -t $TMUX_SESSION"
echo "  Switch win: Ctrl+b <number>"
echo "  Kill all:   tmux kill-session -t $TMUX_SESSION"

if [ "$NO_ATTACH" = false ]; then
    sleep 1
    exec tmux attach -t "$TMUX_SESSION"
fi

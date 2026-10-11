#!/usr/bin/env bash
# SSH tunnel to the cloud GPU (AutoDL) that serves the policy.
#
# The deploy script connects to 127.0.0.1:$LOCAL_PORT, which this tunnel
# forwards (encrypted) to $REMOTE_PORT on the cloud instance. The tunnel is
# supervised: if the SSH session drops, it reconnects every 5 s.
#
# Usage:
#   scripts/cloud_tunnel.sh up      start the tunnel
#   scripts/cloud_tunnel.sh down    stop it
#   scripts/cloud_tunnel.sh status  show whether it is running
#   scripts/cloud_tunnel.sh check   probe the policy server through the tunnel
#
# Config: config/cloud_tunnel.env (copy the .example file). Override the path
# with CLOUD_TUNNEL_CONFIG=/path/to/env. Full workflow: docs/cloud_gpu.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${CLOUD_TUNNEL_CONFIG:-$REPO_ROOT/config/cloud_tunnel.env}"
RUN_DIR="${XDG_RUNTIME_DIR:-/tmp}/franka-cloud-tunnel"
PID_FILE="$RUN_DIR/tunnel.pid"
LOG_FILE="$RUN_DIR/tunnel.log"
LOOP_SCRIPT="$RUN_DIR/tunnel_loop.sh"

die() { echo "error: $*" >&2; exit 1; }

load_config() {
    [ -f "$CONFIG_FILE" ] || die "config not found: $CONFIG_FILE
  copy the template and fill in your instance's SSH details:
    cp config/cloud_tunnel.env.example config/cloud_tunnel.env
    \$EDITOR config/cloud_tunnel.env
  (or point CLOUD_TUNNEL_CONFIG at your own file)"
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
    : "${AUTODL_USER:?set AUTODL_USER in $CONFIG_FILE}"
    : "${AUTODL_HOST:?set AUTODL_HOST in $CONFIG_FILE}"
    : "${AUTODL_PORT:?set AUTODL_PORT in $CONFIG_FILE}"
    LOCAL_PORT="${LOCAL_PORT:-8000}"
    REMOTE_PORT="${REMOTE_PORT:-8000}"
    SSH_KEY="${SSH_KEY:-}"
}

is_running() {
    [ -f "$PID_FILE" ] || return 1
    kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

cmd_up() {
    load_config
    if is_running; then
        echo "tunnel already running (pid $(cat "$PID_FILE"))"
        return 0
    fi
    rm -f "$PID_FILE"
    mkdir -p "$RUN_DIR"

    if curl -fsS --max-time 2 "http://127.0.0.1:$LOCAL_PORT/healthz" >/dev/null 2>&1; then
        die "something already answers on 127.0.0.1:$LOCAL_PORT (a local policy server?)
  stop it or change LOCAL_PORT in $CONFIG_FILE"
    fi

    local target="$AUTODL_USER@$AUTODL_HOST"
    local ssh_opts=(
        -o ServerAliveInterval=15
        -o ServerAliveCountMax=3
        -o ExitOnForwardFailure=yes
        -o BatchMode=yes
        -o StrictHostKeyChecking=accept-new
        -o ConnectTimeout=10
        -p "$AUTODL_PORT"
    )
    if [ -n "$SSH_KEY" ]; then
        ssh_opts+=(-i "$SSH_KEY")
    fi

    # The supervised loop must never prompt for a password, so verify key
    # auth once up front with a clear error instead of a retry storm.
    # (No -N here: with -N ssh would hold the connection open and never run
    # the 'true' that proves the login.)
    echo "checking key-based SSH to $target (port $AUTODL_PORT) ..."
    if ! ssh "${ssh_opts[@]}" "$target" true 2>/dev/null; then
        die "SSH key login failed (the tunnel cannot type passwords).
  Set up a key once per laptop:
    ssh-keygen -t ed25519              # skip if you already have ~/.ssh/id_ed25519
    ssh-copy-id -p $AUTODL_PORT $target
  See docs/cloud_gpu.md -> \"One-time SSH key setup\"."
    fi

    # Generate the supervised loop as a file (easy to inspect/debug) and
    # background it. The TERM trap takes the ssh child down with it.
    cat > "$LOOP_SCRIPT" <<EOF
#!/usr/bin/env bash
trap 'kill "\${SSH_PID:-}" 2>/dev/null; exit 0' TERM INT
while true; do
    ssh -N -T $(printf '%q ' "${ssh_opts[@]}")-L $(printf '%q' "$LOCAL_PORT:127.0.0.1:$REMOTE_PORT") $(printf '%q' "$target") </dev/null &
    SSH_PID=\$!
    wait "\$SSH_PID" || true
    sleep 5
done
EOF
    chmod +x "$LOOP_SCRIPT"
    bash "$LOOP_SCRIPT" >"$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"

    sleep 1
    if ! is_running; then
        die "tunnel died on startup — see $LOG_FILE"
    fi
    echo "tunnel up: 127.0.0.1:$LOCAL_PORT -> $target:127.0.0.1:$REMOTE_PORT (pid $(cat "$PID_FILE"))"
    echo "log:       $LOG_FILE"
    echo
    echo "next:  scripts/cloud_tunnel.sh check    # probe the policy server"
    echo "then:  python -m franka_control.scripts.deploy_policy \\"
    echo "           --robot-ip 127.0.0.1 --gripper-host 127.0.0.1 \\"
    echo "           --policy-host 127.0.0.1 --policy-port $LOCAL_PORT ..."
}

cmd_down() {
    if ! is_running; then
        rm -f "$PID_FILE"
        echo "tunnel is not running"
        return 0
    fi
    local pid
    pid="$(cat "$PID_FILE")"
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 12); do
        is_running || break
        sleep 0.5
    done
    if is_running; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    echo "tunnel stopped"
}

cmd_status() {
    if is_running; then
        echo "tunnel running (pid $(cat "$PID_FILE"))"
        echo "log (last 5 lines):"
        tail -n 5 "$LOG_FILE" 2>/dev/null | sed 's/^/  /'
    else
        echo "tunnel not running"
        return 1
    fi
}

cmd_check() {
    load_config
    if curl -fsS --max-time 5 "http://127.0.0.1:$LOCAL_PORT/healthz" >/dev/null 2>&1; then
        echo "OK: policy server reachable through the tunnel (127.0.0.1:$LOCAL_PORT/healthz)"
        return 0
    fi
    echo "FAIL: no policy server behind 127.0.0.1:$LOCAL_PORT/healthz" >&2
    echo "  - tunnel up?        scripts/cloud_tunnel.sh status" >&2
    echo "  - server running on the cloud?  (serve_policy.py on port $REMOTE_PORT)" >&2
    echo "  - ports match?      LOCAL_PORT/REMOTE_PORT in $CONFIG_FILE" >&2
    return 1
}

case "${1:-}" in
    up)     cmd_up ;;
    down)   cmd_down ;;
    status) cmd_status ;;
    check)  cmd_check ;;
    *)      echo "usage: $0 {up|down|status|check}" >&2; exit 2 ;;
esac

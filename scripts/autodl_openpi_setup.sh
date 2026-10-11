#!/usr/bin/env bash
# Bootstrap openpi on the cloud GPU (AutoDL). Run ON the cloud instance:
#
#   ssh -p <AUTODL_PORT> <AUTODL_USER>@<AUTODL_HOST> 'bash -s' < scripts/autodl_openpi_setup.sh
#
# Full workflow: docs/cloud_gpu.md. Checkpoints/caches live under
# /root/autodl-tmp so they survive instance restarts (AutoDL only persists
# that directory).

set -euo pipefail

OPENPI_ROOT="${OPENPI_ROOT:-/root/autodl-tmp/openpi}"
OPENPI_DATA_HOME="${OPENPI_DATA_HOME:-/root/autodl-tmp/openpi-cache}"

echo "== openpi   -> $OPENPI_ROOT"
echo "== cache    -> $OPENPI_DATA_HOME"
mkdir -p "$(dirname "$OPENPI_ROOT")" "$OPENPI_DATA_HOME"

if ! command -v uv >/dev/null 2>&1; then
    echo "== installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ ! -d "$OPENPI_ROOT/.git" ]; then
    echo "== cloning openpi"
    git clone --recurse-submodules https://github.com/Physical-Intelligence/openpi.git "$OPENPI_ROOT"
else
    echo "== updating openpi"
    git -C "$OPENPI_ROOT" pull --ff-only
    git -C "$OPENPI_ROOT" submodule update --init --recursive
fi

cd "$OPENPI_ROOT"
export GIT_LFS_SKIP_SMUDGE=1
export OPENPI_DATA_HOME
uv sync
uv pip install -e .

cat <<EOF

openpi is ready.

Start the policy server (keep it running; tmux/screen recommended):

  cd $OPENPI_ROOT
  export OPENPI_DATA_HOME=$OPENPI_DATA_HOME
  uv run scripts/serve_policy.py policy:checkpoint \\
      --policy.config=pi05_droid \\
      --policy.dir=gs://openpi-assets/checkpoints/pi05_droid \\
      --port=8000

From the laptop repo:

  scripts/cloud_tunnel.sh up && scripts/cloud_tunnel.sh check
  python -m franka_control.scripts.deploy_policy --policy-host 127.0.0.1 ...

Note: pi05_droid above is for LINK TESTING ONLY (connectivity, latency,
protocol) — it cannot act on an FR3 until the FR3 policy config +
fine-tune exist (see docs/cloud_gpu.md).
EOF

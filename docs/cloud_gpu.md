# Cloud GPU Policy Server (AutoDL + SSH tunnel)

Run the policy (openpi / pi0 / pi0.5) on a rented GPU instance and drive it
from this repo over an SSH tunnel. The deploy script always talks to
`127.0.0.1` — the tunnel hides the network in between:

```
        laptop (this repo)                       cloud GPU (AutoDL)
 ┌────────────────────────────────┐        ┌────────────────────────────┐
 │ deploy_policy.py               │        │ openpi serve_policy.py     │
 │   --policy-host 127.0.0.1  ────┼── ssh ─┼─▶ ws://127.0.0.1:8000     │
 │ scripts/cloud_tunnel.sh        │ tunnel │ (pi0 / pi0.5 checkpoint)   │
 └────────────────────────────────┘        └────────────────────────────┘
```

## One-time setup

### A. Cloud instance

```bash
ssh -p <AUTODL_PORT> <AUTODL_USER>@<AUTODL_HOST> 'bash -s' < scripts/autodl_openpi_setup.sh
```

Clones openpi into `/root/autodl-tmp/openpi` (AutoDL only persists that
directory across restarts) and prints the serve command.

### B. SSH key on the laptop

The supervised tunnel cannot type passwords, so set up key auth once:

```bash
ssh-keygen -t ed25519            # skip if you already have ~/.ssh/id_ed25519
ssh-copy-id -p <AUTODL_PORT> <AUTODL_USER>@<AUTODL_HOST>
```

### C. Tunnel config

```bash
cp config/cloud_tunnel.env.example config/cloud_tunnel.env
$EDITOR config/cloud_tunnel.env      # AUTODL_HOST / AUTODL_PORT / AUTODL_USER
```

`config/cloud_tunnel.env` is git-ignored — instance details stay local.

## Daily workflow

```bash
# cloud: start the policy server (tmux/screen, so it survives your ssh exit)
ssh -p <AUTODL_PORT> <AUTODL_USER>@<AUTODL_HOST>
cd /root/autodl-tmp/openpi && export OPENPI_DATA_HOME=/root/autodl-tmp/openpi-cache
uv run scripts/serve_policy.py policy:checkpoint \
    --policy.config=pi05_droid \
    --policy.dir=gs://openpi-assets/checkpoints/pi05_droid --port=8000

# laptop: tunnel up + verify
scripts/cloud_tunnel.sh up
scripts/cloud_tunnel.sh check        # -> OK: policy server reachable ...

# laptop: deploy — with the mock robot until hardware arrives (stage 1)
python -m franka_control.scripts.deploy_policy \
    --robot-ip 127.0.0.1 --gripper-host 127.0.0.1 \
    --policy-host 127.0.0.1 --prompt "pick cube" \
    --mock-cameras front=synthetic,wrist=synthetic \
    --fps 30 --duration 60 --log-jsonl /tmp/deploy.jsonl

# laptop: tunnel down
scripts/cloud_tunnel.sh down
```

## Behavior under link drops

- **Tunnel**: supervised — if the SSH session drops it reconnects every 5 s;
  `scripts/cloud_tunnel.sh status` shows the recent log.
- **Deploy script**: a dropped connection does not crash the episode.
  `--infer-retry-timeout` (default 120 s) is the budget for
  reconnect-and-retry; every retry sends a **fresh** observation. When the
  budget runs out the script stops and closes the env — the robot holds its
  last target the whole time and ends safely stopped.
- Only **connection-type** failures are retried. When the policy server itself
  answers with an error traceback (e.g. an observation-key/dimension mismatch),
  the deploy script raises it immediately instead of burning the retry budget.
- `--infer-retry-timeout 0` = fail fast (no retry).
- `scripts/cloud_tunnel.sh check` is the one-shot diagnosis the retry
  warnings point at.

## Measuring the link

`--log-jsonl` records per step `rtt_ms` (full round trip through the tunnel)
and `infer_ms` (server-reported GPU time). `rtt_ms - infer_ms` ≈ tunnel +
network. Against the mock policy server you can isolate the inference part
with `--delay-ms`. Judge the link from these numbers, not from ping.

## Troubleshooting

| Symptom | Check |
|---|---|
| `check` fails though tunnel is up | is `serve_policy.py` running on the cloud? do `LOCAL_PORT`/`REMOTE_PORT` match its `--port`? |
| `up` fails with "SSH key login failed" | run the two commands in section B |
| `up` fails with "already answers on 127.0.0.1:8000" | a local (mock) policy server is running — stop it or change `LOCAL_PORT` |
| deploy waits ~30 s then errors at startup | that is `--policy-connect-timeout` working; fix per `check` |
| deploy logs "Policy infer failed ... retrying" | tunnel/server dropped; it recovers within the retry budget, else stops safely |
| immediate "Connection reset" after `up` | instance was released/restarted — reconnect, restart `serve_policy.py` |

## Notes

- `pi05_droid` is for **link testing only**: it cannot act on an FR3 until an
  FR3 policy config + fine-tune exist. Its action dimension likely will not
  match; the deploy script raises a clear shape error — expected at this stage.
- Keep using the local mock policy server
  (`franka_control.mock.policy_server`) for fully offline runs.
- Transport alternatives: `ssh -L` (this workflow) is the right default when
  SSH is the only access. Tailscale is more involved on AutoDL containers
  (no systemd, possibly no `/dev/net/tun`, control-plane access may need a
  proxy) — only worth it if the tunnel proves flaky in daily use.

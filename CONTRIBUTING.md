# Contributing

Contributions are welcome, especially around documentation, hardware validation,
dataset tooling, and new robot/control examples.

## Development Setup

```bash
conda create -n franka python=3.12 -y
conda activate franka
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
python -m pytest tests -q
```

## Pull Request Checklist

- Keep hardware-facing changes conservative and documented.
- Add or update tests when changing data, gripper, teleop, or API behavior.
- Run `python -m pytest tests -q`.
- Run relevant CLI `--help` checks if you change scripts.
- Update README/docs when user-facing commands or workflows change.

## Safety-Critical Changes

For changes affecting robot motion, include:

- Control mode affected.
- Expected action units and dimensions.
- Safety limits or clipping behavior.
- Whether the change has been tested on real hardware or only offline.


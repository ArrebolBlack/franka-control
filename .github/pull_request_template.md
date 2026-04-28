## Summary

- 

## Validation

- [ ] `python -m pytest tests -q`
- [ ] `python -m py_compile franka_control/scripts/collect_episodes.py franka_control/scripts/teleop.py franka_control/scripts/run_trajectory.py scripts/play_dataset.py`
- [ ] CLI `--help` checks run if scripts changed
- [ ] `python scripts/check_markdown_links.py`
- [ ] `python -m ruff check franka_control scripts tests`

## Documentation

- [ ] User-facing behavior changed and docs were updated
- [ ] No docs update needed

## Hardware and Safety

- [ ] Offline-only change
- [ ] Real hardware tested and documented
- [ ] Hardware-facing behavior changed and safety impact is described below

Safety notes:

-

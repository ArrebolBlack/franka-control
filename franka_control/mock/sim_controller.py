"""Simulated robot controller for the mock server.

Wraps aiofranka's MuJoCo simulation (``aiofranka.Robot(None)`` +
``aiofranka.Controller``) behind the duck-typed interface ``RobotServer``
expects from ``FrankaRemoteController``: ``start/stop/switch/set/move``,
``running`` and ``state``. The simulation runs the same native 1 kHz control
loop as the real robot (PID / OSC / Ruckig moves), so timing and semantics
match hardware.

Two aiofranka quirks are contained here:

- The simulation opens a MuJoCo viewer window unconditionally; headless runs
  patch ``mujoco.viewer.launch_passive`` with a no-op viewer. Pass
  ``viewer=True`` to keep the real window and watch the simulated arm.
- ``Controller.stop()`` does not unblock a ``move()`` waiting in another
  thread (it spins on a future that never resolves once the loop stops —
  verified on aiofranka 0.9.0). ``RobotServer._handle_stop`` kills the whole
  server when a blocked move does not return within 5 s, so ``move()`` here
  runs the aiofranka call in a fresh daemon thread and returns early when
  ``stop()`` fires. The underlying thread may stay blocked; being a daemon
  thread, it dies with the process.
"""

from __future__ import annotations

import threading
import time

import numpy as np

_viewer_patched = False


def _patch_headless_viewer() -> None:
    """Replace MuJoCo's viewer with a no-op, for machines without a display."""
    global _viewer_patched
    if _viewer_patched:
        return

    import mujoco.viewer

    class _NoopViewer:
        def sync(self):
            pass

        def close(self):
            pass

        def is_running(self):
            return True

        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    mujoco.viewer.launch_passive = lambda *args, **kwargs: _NoopViewer()
    _viewer_patched = True


class SimControllerAdapter:
    """FrankaRemoteController-shaped adapter over aiofranka's MuJoCo simulation.

    Args:
        set_hz: Rate limit for ``set()``, mirroring ``FrankaRemoteController``
            (default 50 Hz).
        viewer: Keep the real MuJoCo viewer window instead of a no-op viewer.
    """

    def __init__(self, set_hz: float = 50.0, viewer: bool = False):
        if not viewer:
            _patch_headless_viewer()

        import aiofranka

        self._robot = aiofranka.Robot(None)
        self._controller = aiofranka.Controller(self._robot)
        self._controller.set_freq(set_hz)
        self._abort = threading.Event()

    # ── Lifecycle ────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._controller.running

    def start(self) -> None:
        if not self._controller.running:
            self._controller.start()

    def stop(self) -> None:
        """Stop the loop and release any ``move()`` waiting in another thread."""
        self._abort.set()
        try:
            self._controller.stop()
        except Exception:
            pass

    # ── Commanding ───────────────────────────────────────────────

    def switch(self, controller_type: str) -> None:
        self._controller.switch(controller_type)

    def set(self, attr: str, value) -> None:
        # Rate-limited inside aiofranka (set_freq, default 50 Hz), matching
        # FrankaRemoteController._update_freq on the real stack.
        self._controller.set(attr, value)

    def move(self, qpos) -> None:
        """Blocking Ruckig move; returns early when ``stop()`` aborts it."""
        done = threading.Event()
        # Fresh events per call; stop() sets whatever _abort points at.
        self._abort = threading.Event()
        abort = self._abort
        error: list[BaseException] = []

        def _run():
            try:
                self._controller.move(list(qpos))
            except BaseException as exc:  # noqa: BLE001 - re-raised below
                error.append(exc)
            finally:
                done.set()

        threading.Thread(target=_run, daemon=True, name="sim-move").start()
        while not done.is_set() and not abort.is_set():
            done.wait(timeout=0.05)

        if not done.is_set():
            return  # aborted by stop(); the caller is stopping anyway
        if error and not abort.is_set():
            raise error[0]

    # ── State ────────────────────────────────────────────────────

    @property
    def state(self) -> dict:
        """Robot state in the layout ``CachedRobotState.update`` expects."""
        state = dict(self._robot.state)
        try:
            q_desired = np.array(self._controller.q_desired, dtype=np.float64)
        except Exception:
            q_desired = np.asarray(state["qpos"], dtype=np.float64)
        state["q_desired"] = q_desired
        state["qpos"] = np.asarray(state["qpos"], dtype=np.float64)
        state["qvel"] = np.asarray(state["qvel"], dtype=np.float64)
        state["ee"] = np.asarray(state["ee"], dtype=np.float64).reshape(4, 4)
        state["jac"] = np.asarray(state["jac"], dtype=np.float64).reshape(6, 7)
        state["mm"] = np.asarray(state["mm"], dtype=np.float64).reshape(7, 7)
        state["last_torque"] = np.asarray(state["last_torque"], dtype=np.float64)
        state["timestamp"] = time.time()
        return state

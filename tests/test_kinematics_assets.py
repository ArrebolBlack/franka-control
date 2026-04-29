"""Tests for bundled kinematics resources."""

from importlib.resources import files


def test_default_kinematics_assets_are_available():
    assets = files("franka_control.kinematics").joinpath("assets")

    assert assets.joinpath("fr3v2.urdf").is_file()
    assert assets.joinpath(
        "meshes/robots/fr3v2/visual/link0.dae"
    ).is_file()
    assert assets.joinpath(
        "meshes/robots/fr3v2/collision/link0.stl"
    ).is_file()

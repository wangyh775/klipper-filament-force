"""Safety regression tests for the opt-in first-layer Z controller."""
from filament_force.first_layer import FirstLayerZControl


def eligible(controller: FirstLayerZControl, **overrides: object) -> bool:
    args = {
        "source": "band",
        "printing": True,
        "layer": 1,
        "z_mm": 0.2,
        "z_homed": True,
        "force_g": 700.0,
        "now": 100.0,
    }
    args.update(overrides)
    return controller.may_adjust(**args)


def test_disabled_by_default() -> None:
    assert not eligible(FirstLayerZControl())


def test_requires_explicit_first_layer_and_valid_position() -> None:
    c = FirstLayerZControl(enabled=True)
    assert eligible(c)
    for layer in (None, 0, 2, True, "1"):
        assert not eligible(c, layer=layer)
    assert not eligible(c, z_mm=None)
    assert not eligible(c, z_mm=-0.1)
    assert not eligible(c, z_mm=1.0)
    assert not eligible(c, z_mm=float("nan"))
    assert not eligible(c, z_homed=False)
    assert not eligible(c, printing=False)


def test_never_adjusts_hard_jam_or_unreliable_force() -> None:
    c = FirstLayerZControl(enabled=True, max_force_g=1000)
    assert not eligible(c, source="hard")
    assert not eligible(c, source="runout")
    assert not eligible(c, force_g=0.0)
    assert not eligible(c, force_g=float("inf"))
    assert not eligible(c, force_g=1001.0)


def test_limit_cooldown_and_reset() -> None:
    c = FirstLayerZControl(enabled=True, max_adjustments=2, cooldown_s=10)
    assert eligible(c)
    c.record_adjustment(100.0)
    assert c.adjustments == 1
    assert c.applied_mm == 0.02
    assert not eligible(c, now=105.0)
    assert eligible(c, now=110.0)
    c.record_adjustment(110.0)
    assert c.applied_mm == 0.04
    assert not eligible(c, now=200.0)
    c.reset()
    assert c.adjustments == 0
    assert c.applied_mm == 0.0
    assert eligible(c, now=200.0)

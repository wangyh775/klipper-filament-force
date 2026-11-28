import pytest

from filament_force.z_ownership import ZOwnership


def test_commit_two_steps_and_confirm_idle_cleanup() -> None:
    z = ZOwnership()
    z.stage(.1, .12, .02)
    z.commit(.12)
    z.stage(.12, .14, .02)
    z.commit(.14)
    assert z.applied_mm == .04
    assert z.finish_job()
    target = z.cleanup_target(.14)
    assert target == pytest.approx(.1)
    z.confirm_cleanup(.1, target)
    assert not z.cleanup_pending and z.applied_mm == 0


def test_unacknowledged_cleanup_retains_ownership() -> None:
    z = ZOwnership()
    z.stage(.1, .12, .02)
    z.commit(.12)
    z.finish_job()
    target = z.cleanup_target(.12)
    with pytest.raises(ValueError):
        z.confirm_cleanup(.12, target)
    assert z.cleanup_pending and z.uncertain and z.applied_mm == .02
    with pytest.raises(ValueError):
        z.stage(.12, .14, .02)


def test_job_reset_during_staged_motion_requires_manual_check() -> None:
    z = ZOwnership()
    z.stage(.1, .12, .02)
    assert z.finish_job() and z.uncertain
    assert z.staged_step == .02
    with pytest.raises(ValueError):
        z.cleanup_target(.12)


def test_rollback_preserves_prior_owned_offset() -> None:
    z = ZOwnership()
    z.stage(.1, .12, .02)
    z.commit(.12)
    z.stage(.12, .14, .02)
    z.rollback(.12)
    assert z.applied_mm == .02 and z.origin == .12 and z.staged_step == 0


def test_changed_origin_cannot_be_corrected_or_undone() -> None:
    z = ZOwnership()
    z.stage(.1, .12, .02)
    z.commit(.12)
    with pytest.raises(ValueError):
        z.stage(.2, .22, .02)
    z.finish_job()
    with pytest.raises(ValueError):
        z.cleanup_target(.2)
    assert z.applied_mm == .02

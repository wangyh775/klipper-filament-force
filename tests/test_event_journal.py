from filament_force.events import EventJournal
from filament_force.force_signal import Sample


def test_trace_preserves_peaks_and_bounds():
    j = EventJournal(seconds=2, max_points=16)
    for i in range(400):
        j.note(Sample(i / 100, 9000.0 if i == 301 else -100.0 if i == 302 else 10.0))
    trace = j.trace(10)
    assert 200 <= trace["sample_count"] <= 201
    assert trace["returned_count"] <= 16
    assert 1.98 <= trace["duration_s"] <= 2.000001
    assert trace["downsampled"]
    assert max(row[1] for row in trace["samples"]) == 9000
    assert min(row[1] for row in trace["samples"]) == -100


def test_sequence_and_replay():
    j = EventJournal()
    first = j.emit("jam_detected", window=j.trace(None))
    for _ in range(20):
        j.emit("diagnosis_result", incident_id=first["event_id"])
    assert len(j.status()) == 16
    assert j.status()[-1]["seq"] == 21
    assert first["event_id"] != EventJournal().emit("jam_detected")["event_id"]
    j.clear_trace()
    assert j.status()[-1]["seq"] == 21


def test_timestamp_regression_clears_trace_not_events():
    j = EventJournal()
    j.note(Sample(10, 1))
    j.emit("jam_detected")
    j.note(Sample(1, 2))
    assert j.trace(None)["samples"] == [[0, 2]]
    assert len(j.status()) == 1

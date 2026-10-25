"""Test make_noisy.py: SNR đo lại, seed, kiểm tra conditions.yaml."""

import shutil
from pathlib import Path

import make_noisy as mn
import numpy as np
import pytest

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="cần ffmpeg")


def fake_speech(seconds: float = 3.0, seed: int = 0) -> np.ndarray:
    """Tín hiệu giống lời nói: họa âm của một tần số cơ bản, điều biên theo âm tiết.

    Mỗi seed có tần số cơ bản khác nhau, như người nói khác nhau. Nếu dùng chung tần số,
    babble sẽ tương quan với lời nói và phép đo SNR bằng phép chiếu bị lệch.
    """
    t = np.arange(int(seconds * mn.SAMPLE_RATE)) / mn.SAMPLE_RATE
    rng = np.random.default_rng(seed)
    f0 = 120 + 37 * seed
    voice = sum(np.sin(2 * np.pi * k * f0 * t + rng.uniform(0, 6)) / k for k in range(1, 6))
    envelope = np.clip(np.sin(2 * np.pi * 3 * t), 0, None) * (t % 1.5 < 1.1)
    return 0.3 * voice * envelope


def test_default_conditions_file_is_valid():
    seed, conditions = mn.load_conditions()
    ids = [c.id for c in conditions]
    assert seed == 2026 and ids[0] == "clean"
    assert {c.type for c in conditions} == set(mn.SCHEMA)


@pytest.mark.parametrize(
    "cond",
    [
        mn.Condition("pink10", "noise", {"color": "pink", "snr_db": 10}),
        mn.Condition("white0", "noise", {"color": "white", "snr_db": 0}),
        mn.Condition("brown20", "noise", {"color": "brown", "snr_db": 20}),
        mn.Condition("babble5", "babble", {"talkers": 3, "snr_db": 5}),
    ],
    ids=lambda c: c.id,
)
def test_measured_snr_matches_target(cond):
    speech = fake_speech()
    babble = [fake_speech(2.0, seed=s) for s in range(1, 5)]
    out = mn.apply(cond, speech, mn.rng_for(1, cond.id, "clip"), babble)
    assert len(out) == len(speech)
    assert np.max(np.abs(out)) <= mn.PEAK + 1e-9
    assert mn.snr_db(speech, out) == pytest.approx(cond.params["snr_db"], abs=0.5)


@pytest.mark.parametrize("drr", [3.0, 0.0, -3.0])
def test_reverb_tail_energy_follows_drr(drr):
    ir = mn.reverb_ir(0.5, drr, mn.rng_for(1, "rv", "clip"))
    assert ir[0] == 1.0 and len(ir) == 8000
    assert 10 * np.log10(1 / np.sum(np.square(ir[1:]))) == pytest.approx(drr, abs=1e-6)


def test_reverb_and_far_mic_keep_length_and_level():
    speech = fake_speech()
    reverb = mn.Condition("rv", "reverb", {"rt60_sec": 0.6, "drr_db": 0})
    out = mn.apply(reverb, speech, mn.rng_for(1, "rv", "clip"))
    assert len(out) == len(speech)
    assert mn.power(out) == pytest.approx(mn.power(speech), rel=0.01)
    assert mn.snr_db(speech, out) < 10
    far = mn.Condition(
        "far", "far_mic", {"lowpass_hz": 4000, "rt60_sec": 0.5, "drr_db": -3, "gain_db": -15}
    )
    out = mn.apply(far, speech, mn.rng_for(1, "far", "clip"))
    assert len(out) == len(speech)
    assert mn.power(out) == pytest.approx(mn.power(speech) * 10 ** (-15 / 10), rel=0.01)


def test_lowpass_removes_high_frequencies():
    t = np.arange(mn.SAMPLE_RATE) / mn.SAMPLE_RATE
    low, high = np.sin(2 * np.pi * 500 * t), np.sin(2 * np.pi * 6000 * t)
    out = mn.lowpass(low + high, 4000)
    assert mn.power(out - low) < 1e-6


def test_seed_depends_on_condition_and_clip_not_on_order():
    a = mn.rng_for(7, "pink10", "clip-a").standard_normal(4)
    assert np.array_equal(a, mn.rng_for(7, "pink10", "clip-a").standard_normal(4))
    assert not np.array_equal(a, mn.rng_for(7, "pink10", "clip-b").standard_normal(4))
    assert not np.array_equal(a, mn.rng_for(8, "pink10", "clip-a").standard_normal(4))


@needs_ffmpeg
def test_same_seed_gives_identical_files(tmp_path):
    clip = mn.write_wav(tmp_path / "clip.wav", fake_speech())
    seed, conditions = mn.load_conditions()
    babble = [fake_speech(2.0, seed=s) for s in range(1, 6)]
    first = mn.make_noisy(clip, tmp_path / "a", conditions, seed, babble)
    second = mn.make_noisy(clip, tmp_path / "b", list(reversed(conditions)), seed, babble)
    assert set(first) == {c.id for c in conditions}
    for cond_id, path in first.items():
        assert path.read_bytes() == second[cond_id].read_bytes(), cond_id


@needs_ffmpeg
def test_codec_roundtrip_keeps_length(tmp_path):
    speech = fake_speech()
    out = mn.apply(
        mn.Condition("op", "codec", {"codec": "opus", "bitrate_kbps": 16}),
        speech,
        mn.rng_for(1, "op", "c"),
    )
    assert len(out) == len(speech)
    assert mn.snr_db(speech, out) > 3


def test_snr_of_identical_signals_is_infinite():
    speech = fake_speech()
    assert mn.snr_db(speech, speech) == float("inf")
    assert mn.snr_db(speech, 0.5 * speech) == float("inf")


def test_silent_clip_is_rejected():
    with pytest.raises(mn.ConditionError, match="im lặng"):
        mn.apply(mn.Condition("c", "clean"), np.zeros(100), mn.rng_for(1, "c", "x"))


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"conditions": []}, "seed"),
        ({"seed": 1, "conditions": [{"id": "a", "type": "nope"}]}, "type"),
        (
            {"seed": 1, "conditions": [{"id": "a", "type": "noise", "color": "pink"}]},
            "thiếu snr_db",
        ),
        (
            {"seed": 1, "conditions": [{"id": "a", "type": "noise", "color": "red", "snr_db": 5}]},
            "color",
        ),
        (
            {
                "seed": 1,
                "conditions": [{"id": "a", "type": "noise", "color": "pink", "snr_db": 99}],
            },
            "ngoài khoảng",
        ),
        ({"seed": 1, "conditions": [{"id": "a", "type": "clean", "snr_db": 5}]}, "thừa"),
        (
            {"seed": 1, "conditions": [{"id": "a", "type": "clean"}, {"id": "a", "type": "clean"}]},
            "trùng",
        ),
        (
            {"seed": 1, "conditions": [{"id": "a", "type": "reverb", "rt60_sec": "0.5"}]},
            "phải là số",
        ),
    ],
)
def test_invalid_conditions_are_rejected(data, message):
    with pytest.raises(mn.ConditionError, match=message):
        mn.parse_conditions(data)


def test_babble_needs_enough_talkers():
    cond = mn.Condition("b", "babble", {"talkers": 4, "snr_db": 5})
    with pytest.raises(mn.ConditionError, match="cần 4"):
        mn.apply(cond, fake_speech(), mn.rng_for(1, "b", "c"), [fake_speech(1.0)])


@needs_ffmpeg
def test_read_audio_decodes_to_16k_mono(tmp_path):
    path = tmp_path / "x.wav"
    mn.write_wav(path, fake_speech(1.0))
    assert len(mn.read_audio(path)) == mn.SAMPLE_RATE
    assert isinstance(Path(path), Path)

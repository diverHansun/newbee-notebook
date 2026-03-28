from __future__ import annotations

from pathlib import Path
import wave

import pytest

from newbee_notebook.infrastructure.bilibili.exceptions import BiliError


def _write_silent_wav(path: Path, *, seconds: float, sample_rate: int = 16_000) -> None:
    frame_count = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * frame_count)


def test_convert_and_split_creates_wav_segments(tmp_path: Path):
    from newbee_notebook.infrastructure.bilibili.audio_processor import AudioProcessor

    input_path = tmp_path / "input.wav"
    output_dir = tmp_path / "segments"
    _write_silent_wav(input_path, seconds=2.2)

    segments = AudioProcessor.convert_and_split(
        input_path=str(input_path),
        output_dir=str(output_dir),
        max_segment_seconds=1,
    )

    assert len(segments) == 3
    for segment in segments:
        segment_path = Path(segment)
        assert segment_path.exists()
        with wave.open(str(segment_path), "rb") as handle:
            assert handle.getnchannels() == 1
            assert handle.getframerate() == 16_000


def test_convert_and_split_rejects_non_positive_segment_duration(tmp_path: Path):
    from newbee_notebook.infrastructure.bilibili.audio_processor import AudioProcessor

    input_path = tmp_path / "input.wav"
    output_dir = tmp_path / "segments"
    _write_silent_wav(input_path, seconds=1.0)

    with pytest.raises(BiliError):
        AudioProcessor.convert_and_split(
            input_path=str(input_path),
            output_dir=str(output_dir),
            max_segment_seconds=0,
        )

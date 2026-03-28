"""Audio conversion and segmentation helpers for video ASR."""

from __future__ import annotations

from pathlib import Path

from newbee_notebook.infrastructure.bilibili.exceptions import BiliError


class AudioProcessor:
    """Convert audio into 16kHz mono WAV segments for downstream ASR APIs."""

    @staticmethod
    def convert_and_split(
        input_path: str,
        output_dir: str,
        max_segment_seconds: int = 25,
    ) -> list[str]:
        try:
            import av
        except ImportError as exc:  # pragma: no cover - dependency is installed in test env
            raise BiliError("Audio processing requires the 'av' package") from exc

        if max_segment_seconds <= 0:
            raise BiliError("max_segment_seconds must be greater than 0")

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        def _write_segment(frames: list, segment_index: int) -> str:
            segment_path = Path(output_dir) / f"seg_{segment_index:03d}.wav"
            output_container = None
            try:
                output_container = av.open(str(segment_path), "w", format="wav")
                output_stream = output_container.add_stream("pcm_s16le", rate=16_000, layout="mono")
                resampler = av.AudioResampler(format="s16", layout="mono", rate=16_000)
                for frame in frames:
                    frame.pts = None
                    for resampled in resampler.resample(frame):
                        for packet in output_stream.encode(resampled):
                            output_container.mux(packet)
                for packet in output_stream.encode():
                    output_container.mux(packet)
            finally:
                if output_container is not None:
                    output_container.close()
            return str(segment_path)

        input_container = None
        try:
            input_container = av.open(str(input_path))
            if not input_container.streams.audio:
                raise BiliError("Audio decode failed: no audio stream found")

            segment_paths: list[str] = []
            buffered_frames: list = []
            current_samples = 0
            segment_index = 0
            samples_per_segment: int | None = None
            decoded_any = False

            for frame in input_container.decode(audio=0):
                decoded_any = True
                if samples_per_segment is None:
                    frame_rate = frame.sample_rate or 16_000
                    samples_per_segment = max_segment_seconds * frame_rate

                buffered_frames.append(frame)
                current_samples += frame.samples or 0

                if samples_per_segment and current_samples >= samples_per_segment:
                    segment_paths.append(_write_segment(buffered_frames, segment_index))
                    segment_index += 1
                    current_samples = 0
                    buffered_frames = []

            if not decoded_any:
                raise BiliError("Audio decode failed: no frame data found")

            if buffered_frames:
                segment_paths.append(_write_segment(buffered_frames, segment_index))

            return segment_paths
        finally:
            if input_container is not None:
                input_container.close()

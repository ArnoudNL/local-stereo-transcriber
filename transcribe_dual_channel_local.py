#!/usr/bin/env python3
"""
Transcribe a stereo call recording fully locally with faster-whisper.

Input assumptions:
- WAV file with exactly 2 channels
- Left channel: Client
- Right channel: Agent

Output:
- Single, chronological transcript text file with timestamps and speaker labels

No cloud APIs are used by this script.
"""

from __future__ import annotations

import argparse
import array
import shutil
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from faster_whisper import WhisperModel

from app_logging import setup_logging

__all__ = [
    "Segment",
    "split_stereo_to_mono",
    "load_model_with_fallback",
    "normalize_segments",
    "transcribe_channel",
    "write_merged_transcript",
]

logger = setup_logging("transcribe_core", "transcribe_core.log")


@dataclass
class Segment:
    speaker: str
    start_sec: float
    end_sec: float
    text: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Local dual-channel transcription using faster-whisper"
    )
    parser.add_argument(
        "input_wav",
        type=Path,
        nargs="?",
        help="Path to stereo .wav file (optional when using Streamlit UI)",
    )
    parser.add_argument(
        "output_txt",
        type=Path,
        nargs="?",
        help="Path to output transcript .txt (optional when using Streamlit UI)",
    )
    parser.add_argument(
        "--model-size",
        default="large-v3",
        choices=["large-v3", "medium"],
        help="Primary model size to use (default: large-v3)",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("./local_models"),
        help="Folder where faster-whisper stores model files (default: ./local_models)",
    )
    parser.add_argument(
        "--language",
        default="nl",
        help="Language hint for transcription (default: nl)",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Inference device (default: auto)",
    )
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="Compute type for faster-whisper (default: int8)",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size used for decoding (default: 5)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Decoding temperature (default: 0.0)",
    )
    parser.add_argument(
        "--client-label",
        default="Client",
        help="Label for left channel speaker (default: Client)",
    )
    parser.add_argument(
        "--agent-label",
        default="Agent",
        help="Label for right channel speaker (default: Agent)",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary split audio files",
    )
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.exists() or not path.is_file():
        logger.error("Missing required file for {}: {}", label, path)
        raise FileNotFoundError(f"{label} not found: {path}")


def seconds_to_hhmmss_mmm(value: float) -> str:
    total_ms = int(round(value * 1000))
    hours = total_ms // 3_600_000
    total_ms %= 3_600_000
    minutes = total_ms // 60_000
    total_ms %= 60_000
    seconds = total_ms // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def split_stereo_to_mono(input_wav: Path, out_left_wav: Path, out_right_wav: Path) -> None:
    """Split stereo PCM WAV into left and right mono WAV files fully locally."""
    logger.info("Splitting stereo WAV into mono channels: {}", input_wav)
    with wave.open(str(input_wav), "rb") as wav_in:
        n_channels = wav_in.getnchannels()
        if n_channels != 2:
            raise ValueError(
                f"Expected exactly 2 channels in input WAV, found {n_channels} channels"
            )

        sample_width = wav_in.getsampwidth()
        frame_rate = wav_in.getframerate()
        comptype = wav_in.getcomptype()
        compname = wav_in.getcompname()
        raw = wav_in.readframes(wav_in.getnframes())

    # Keep this strict for portability in Python 3.14 without external audio libs.
    typecode_map = {1: "B", 2: "h", 4: "i"}
    if sample_width not in typecode_map:
        raise ValueError(
            "Unsupported WAV sample width. Supported PCM widths are 8-bit, 16-bit, and 32-bit."
        )

    samples = array.array(typecode_map[sample_width])
    samples.frombytes(raw)

    left = array.array(typecode_map[sample_width], samples[0::2])
    right = array.array(typecode_map[sample_width], samples[1::2])

    with wave.open(str(out_left_wav), "wb") as left_out:
        left_out.setnchannels(1)
        left_out.setsampwidth(sample_width)
        left_out.setframerate(frame_rate)
        left_out.setcomptype(comptype, compname)
        left_out.writeframes(left.tobytes())

    with wave.open(str(out_right_wav), "wb") as right_out:
        right_out.setnchannels(1)
        right_out.setsampwidth(sample_width)
        right_out.setframerate(frame_rate)
        right_out.setcomptype(comptype, compname)
        right_out.writeframes(right.tobytes())


def normalize_language_hint(language: str | None) -> str | None:
    """Normalize language hint values for faster-whisper."""
    if language is None:
        return None

    cleaned = language.strip().lower()
    if cleaned in {"", "auto", "detect", "automatic"}:
        return None
    return cleaned


def load_model_with_fallback(
    model_size: str,
    model_dir: Path,
    device: str,
    compute_type: str,
) -> tuple[WhisperModel, str]:
    """
    Load faster-whisper model locally.

    The model is downloaded once into model_dir on first run.
    If loading large-v3 fails, medium is used as fallback.
    """
    preferred = model_size
    candidates = [preferred]
    if preferred != "medium":
        candidates.append("medium")

    model_dir.mkdir(parents=True, exist_ok=True)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            model = WhisperModel(
                model_size_or_path=candidate,
                device=device,
                compute_type=compute_type,
                download_root=str(model_dir),
            )
            return model, candidate
        except Exception as exc:  # pragma: no cover
            last_error = exc

    raise RuntimeError(
        "Unable to load faster-whisper model. "
        f"Tried: {', '.join(candidates)}. "
        f"Model directory: {model_dir}. "
        f"Last error: {last_error}"
    ) from last_error


def normalize_segments(segments: Iterable, speaker: str) -> List[Segment]:
    """Convert faster-whisper segment objects into script-local Segment dataclasses."""
    normalized: List[Segment] = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        normalized.append(
            Segment(
                speaker=speaker,
                start_sec=float(seg.start),
                end_sec=float(seg.end),
                text=text,
            )
        )

    return normalized


def transcribe_channel(
    model: WhisperModel,
    audio_path: Path,
    speaker: str,
    language: str | None,
    beam_size: int,
    temperature: float,
) -> List[Segment]:
    """Transcribe one mono channel and return timestamped segments for that speaker."""
    segments_iter, _info = model.transcribe(
        str(audio_path),
        language=language,
        task="transcribe",
        beam_size=beam_size,
        temperature=temperature,
        vad_filter=True,
    )

    return normalize_segments(segments_iter, speaker)


def write_merged_transcript(
    segments: List[Segment],
    output_txt: Path,
    source_wav: Path,
    model_used: str,
) -> None:
    output_txt.parent.mkdir(parents=True, exist_ok=True)

    with output_txt.open("w", encoding="utf-8") as f:
        f.write(f"Source: {source_wav}\n")
        f.write("Transcription: local faster-whisper\n")
        f.write(f"Model: {model_used}\n")
        f.write("\n")

        for segment in segments:
            start_str = seconds_to_hhmmss_mmm(segment.start_sec)
            end_str = seconds_to_hhmmss_mmm(segment.end_sec)
            f.write(f"[{start_str} - {end_str}] {segment.speaker}: {segment.text}\n")


def main() -> int:
    args = parse_args()
    logger.info("Starting local transcription CLI")

    # Streamlit-first behavior: allow running this module without CLI file arguments.
    if args.input_wav is None or args.output_txt is None:
        print("No CLI input/output paths provided.")
        print("Use the Streamlit page instead:")
        print("  python -m streamlit run streamlit_app.py")
        print("\nOptional CLI mode:")
        print("  python3 transcribe_dual_channel_local.py <input.wav> <output.txt> [options]")
        return 0

    require_file(args.input_wav, "Input WAV")
    args.model_dir.mkdir(parents=True, exist_ok=True)
    language_hint = normalize_language_hint(args.language)

    temp_dir_path = Path(tempfile.mkdtemp(prefix="dual_channel_transcribe_"))

    try:
        client_wav = temp_dir_path / "client_left.wav"
        agent_wav = temp_dir_path / "agent_right.wav"

        # Split stereo WAV into two mono files so each speaker is transcribed separately.
        split_stereo_to_mono(args.input_wav, client_wav, agent_wav)

        # Load one model instance and reuse it for both channels.
        model, model_used = load_model_with_fallback(
            model_size=args.model_size,
            model_dir=args.model_dir,
            device=args.device,
            compute_type=args.compute_type,
        )

        client_segments = transcribe_channel(
            model=model,
            audio_path=client_wav,
            speaker=args.client_label,
            language=language_hint,
            beam_size=args.beam_size,
            temperature=args.temperature,
        )
        agent_segments = transcribe_channel(
            model=model,
            audio_path=agent_wav,
            speaker=args.agent_label,
            language=language_hint,
            beam_size=args.beam_size,
            temperature=args.temperature,
        )

        # Merge both channels and sort by timestamp for coherent conversation flow.
        merged = client_segments + agent_segments
        merged.sort(key=lambda s: (s.start_sec, s.end_sec, s.speaker))

        write_merged_transcript(
            segments=merged,
            output_txt=args.output_txt,
            source_wav=args.input_wav,
            model_used=model_used,
        )
        logger.info("Transcript written: {}", args.output_txt)

        print(f"Transcript written to: {args.output_txt}")
        print(f"Model cache directory: {args.model_dir}")
        if args.keep_temp:
            print(f"Temporary files kept at: {temp_dir_path}")
        return 0

    finally:
        if not args.keep_temp and temp_dir_path.exists():
            shutil.rmtree(temp_dir_path, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.exception("Unhandled exception in transcribe CLI: {}", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
# pylint: disable=too-many-lines
"""Streamlit UI for fully local dual-channel WAV transcription with faster-whisper."""

from __future__ import annotations

import base64
import html
import os
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st

from app_logging import get_log_dir, setup_logging
from transcribe_dual_channel_local import (
    Segment,
    load_model_with_fallback,
    split_stereo_to_mono,
    write_merged_transcript,
)

logger = setup_logging("streamlit_ui", "streamlit_ui.log")

# Brand palette
COLOR_BRAND = "#0a7ea4"
COLOR_BRAND_SOFT = "#e7f5fa"
COLOR_SIDEBAR_HEADING = "#375b6b"

# Upload surface palette
COLOR_UPLOAD_BORDER = "#8ac6dd"
COLOR_UPLOAD_BG = "#f8fcfe"
COLOR_UPLOAD_OVERLAY_TEXT = "#1b4f63"

# Success/status palette
COLOR_OK = "#1f9d55"
COLOR_SUCCESS_BG = "#edf9f0"
COLOR_SUCCESS_TEXT = "#1a7f43"
COLOR_SUCCESS_BORDER = "#caebd5"

# Local runtime trace log
TRACE_LOG_FILE = "streamlit_ui.log"
TRACE_ENABLED = os.environ.get("LST_DEBUG_TRACE", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def get_trace_dir() -> Path:
    """Return a writable log directory for local app traces."""
    return get_log_dir()


def get_trace_log_path() -> Path:
    """Return full path to the runtime trace log file."""
    return get_trace_dir() / TRACE_LOG_FILE


def trace_event(event: str, **fields) -> None:
    """Write one structured trace event to local log file."""
    if not TRACE_ENABLED:
        return
    details = ", ".join(f"{key}={value!r}" for key, value in fields.items())
    message = event if not details else f"{event} | {details}"
    logger.info(message)


def read_trace_tail(max_lines: int = 120) -> str:
    """Read the tail of the trace log for quick in-app debugging."""
    if not TRACE_ENABLED:
        return "Tracing is disabled. Set LST_DEBUG_TRACE=1 to enable."
    log_path = get_trace_log_path()
    if not log_path.exists():
        return "Trace log not created yet."

    content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = content[-max_lines:]
    return "\n".join(tail) if tail else "Trace log is empty."


def get_asset_path(*parts: str) -> Path:
    """Resolve a bundled asset path for local and packaged app runs."""
    base_dir = Path(__file__).resolve().parent
    candidate = base_dir.joinpath(*parts)
    if candidate.exists():
        return candidate
    return Path.cwd().joinpath(*parts)


def get_page_logo_data_uri() -> str | None:
    """Return the page logo as data URI, or None when unavailable."""
    logo_path = get_asset_path("assets", "PageLogo.svg")
    if not logo_path.exists():
        return None
    svg = logo_path.read_bytes()
    encoded = base64.b64encode(svg).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def get_default_model_dir() -> str:
    """Return a writable model cache directory for local app runs."""
    # Prefer user-scoped app support path on macOS to avoid read-only DMG volumes.
    if sys.platform == "darwin":
        return str(Path.home() / "Library/Application Support/LocalStereoTranscriber/local_models")
    return str(Path("./local_models").resolve())


UI_TEXT = {
    "nl": {
        "title": "Gesprek naar Tekst",
        "intro": (
            "Transcriptie draait volledig lokaal met faster-whisper. "
            "Er worden geen cloud-API's gebruikt."
        ),
        "settings": "Instellingen",
        "group_performance": "Hardware en snelheid",
        "group_audio": "Audio en sprekers",
        "group_advanced": "Geavanceerde tuning",
        "model_size": "Modelgrootte",
        "model_size_help": (
            "Kwaliteit/snelheid afweging. Groot is nauwkeuriger maar trager dan Medium."
        ),
        "model_size_large": "Groot",
        "model_size_medium": "Medium",
        "transcription_language": "Brontaal (taal in de opname)",
        "transcription_language_help": (
            "Deze instelling geldt voor de taal in de audio-opname. "
            "Standaard is Automatisch detecteren."
        ),
        "lang_dutch": "Nederlands",
        "lang_english": "Engels",
        "lang_auto": "Automatisch detecteren",
        "device": "Processor",
        "device_help": "Gebruik auto tenzij je expliciet CPU of CUDA wilt kiezen.",
        "device_auto": "Auto",
        "device_cpu": "CPU",
        "device_cuda": "CUDA",
        "beam_size": "Beam search breedte",
        "beam_size_help": (
            "Aantal paden dat de decoder gelijktijdig verkent. Hogere waarden verbeteren "
            "de nauwkeurigheid maar verhogen het geheugengebruik en de rekentijd."
        ),
        "temperature": "Creativiteit / Temperatuur",
        "temperature_help": (
            "Reguleert de variatie in token-selectie. 0.0 is deterministisch "
            "(meest waarschijnlijk); hogere waarden verhogen de variatie "
            "maar ook de kans op fouten."
        ),
        "left_label": "Label linker kanaal",
        "right_label": "Label rechter kanaal",
        "channel_label_help_left": "Kies wie op het linker kanaal spreekt.",
        "channel_label_help_right": "Kies wie op het rechter kanaal spreekt.",
        "speaker_client": "Client",
        "speaker_agent": "Agent",
        "same_label_warning": (
            "Links en rechts gebruiken nu hetzelfde label. "
            "Gebruik verschillende labels voor duidelijkere transcripties."
        ),
        "uploader_label": "Upload stereo WAV-bestand",
        "uploader_help": "Verwacht formaat: 2-kanaals WAV, links/rechts als aparte sprekers",
        "dropzone_drag_text": "Sleep bestanden hierheen",
        "dropzone_browse_text": "Bestanden kiezen",
        "start_button": "Start",
        "pause_button": "Pauze",
        "resume_button": "Hervat",
        "stop_button": "Stop",
        "spinner_loading_model": "Model laden (eerste keer kan lokaal downloaden)...",
        "progress": "Voortgang",
        "transcription_complete": "Transcriptie voltooid.",
        "transcription_ready": "Klaar! Je transcriptie is gereed.",
        "merged_transcript": "Samengevoegde transcriptie",
        "download_transcript": "Download transcriptie (.txt)",
        "developer_footer": "Ontwikkeld door Arnoud van Rooij (2026)",
        "status_waiting_wav": "Upload een bestand om te beginnen met transcriberen.",
        "status_preparing": "Bestanden voorbereiden...",
        "status_starting": "Transcriptie starten...",
        "status_resuming": "Transcriptie hervatten...",
        "status_transcribing_channel": "Kanaal transcriberen: {channel}...",
        "status_paused": "Gepauzeerd",
        "status_stopping": "Transcriptie stoppen...",
        "status_stopped": "Transcriptie gestopt door gebruiker.",
        "status_completed": "Transcriptie voltooid.",
        "status_failed": "Transcriptie mislukt.",
        "left_channel": "links",
        "right_channel": "rechts",
    },
    "en": {
        "title": "Call to Text",
        "intro": ("Transcription runs fully local with faster-whisper. No cloud APIs are used."),
        "settings": "Settings",
        "group_performance": "Hardware and speed",
        "group_audio": "Audio and speakers",
        "group_advanced": "Advanced tuning",
        "model_size": "Model size",
        "model_size_help": (
            "Model quality/speed tradeoff. Large is more accurate but slower then Medium."
        ),
        "model_size_large": "Large",
        "model_size_medium": "Medium",
        "transcription_language": "Source Language (audio language)",
        "transcription_language_help": (
            "This setting applies to the language spoken in the audio input. "
            "Default is Auto detect."
        ),
        "lang_dutch": "Dutch",
        "lang_english": "English",
        "lang_auto": "Auto detect",
        "device": "Device",
        "device_help": "Inference device. Use auto unless you specifically want CPU or CUDA.",
        "device_auto": "Auto",
        "device_cpu": "CPU",
        "device_cuda": "CUDA",
        "beam_size": "Beam search width",
        "beam_size_help": (
            "Number of candidate paths explored simultaneously. Higher values improve accuracy "
            "but increase memory usage and latency."
        ),
        "temperature": "Creativity / Temperature",
        "temperature_help": (
            "Controls the randomness of token selection. 0.0 is deterministic; higher values "
            "increase variety but also the risk of 'hallucinations' or errors."
        ),
        "left_label": "Left channel label",
        "right_label": "Right channel label",
        "channel_label_help_left": "Choose who speaks on the left channel.",
        "channel_label_help_right": "Choose who speaks on the right channel.",
        "speaker_client": "Client",
        "speaker_agent": "Agent",
        "same_label_warning": (
            "Left and right channels currently use the same label. "
            "Set different labels for clearer transcripts."
        ),
        "uploader_label": "Drop stereo WAV file",
        "uploader_help": "Expected format: 2-channel WAV, left/right as separate speakers",
        "dropzone_drag_text": "Drag and drop file here",
        "dropzone_browse_text": "Browse files",
        "start_button": "Start",
        "pause_button": "Pause",
        "resume_button": "Resume",
        "stop_button": "Stop",
        "spinner_loading_model": "Loading model (first run may download locally)...",
        "progress": "Progress",
        "transcription_complete": "Transcription complete.",
        "transcription_ready": "Done! Your transcript is ready.",
        "merged_transcript": "Merged transcript",
        "download_transcript": "Download transcript (.txt)",
        "developer_footer": "Developed by Arnoud van Rooij (2026)",
        "status_waiting_wav": "Upload a file to start transcribing.",
        "status_preparing": "Preparing files...",
        "status_starting": "Starting transcription...",
        "status_resuming": "Resuming transcription...",
        "status_transcribing_channel": "Transcribing channel: {channel}...",
        "status_paused": "Paused",
        "status_stopping": "Stopping transcription...",
        "status_stopped": "Transcription stopped by user.",
        "status_completed": "Transcription complete.",
        "status_failed": "Transcription failed.",
        "left_channel": "left",
        "right_channel": "right",
    },
}


def inject_ui_styles() -> None:
    css = "\n".join(
        [
            "<style>",
            "  :root {",
            f"    --brand: {COLOR_BRAND};",
            f"    --brand-soft: {COLOR_BRAND_SOFT};",
            f"    --ok: {COLOR_OK};",
            "  }",
            "",
            "  .block-container {",
            "    padding-top: 2.3rem;",
            "  }",
            "",
            "  .brand-title-row {",
            "    display: flex;",
            "    align-items: center;",
            "    justify-content: flex-start;",
            "    gap: 0;",
            "    margin-top: 0.25rem;",
            "    margin-bottom: 0.25rem;",
            "    padding-right: 4.5rem;",
            "    min-height: 88px;",
            "    position: relative;",
            "  }",
            "",
            "  .brand-title {",
            "    margin: 0;",
            "    line-height: 1.1;",
            "    min-width: 0;",
            "  }",
            "",
            "  .brand-logo {",
            "    display: block;",
            "    width: auto;",
            "    height: 81px;",
            "    flex-shrink: 0;",
            "    position: absolute;",
            "    left: 420px;",
            "    top: 50%;",
            "    transform: translateY(-50%);",
            "  }",
            "",
            "  @media (max-width: 780px) {",
            "    .brand-title-row {",
            "      flex-direction: column;",
            "      align-items: flex-start;",
            "      gap: 0.35rem;",
            "      padding-right: 0;",
            "      min-height: 0;",
            "    }",
            "",
            "    .brand-title {",
            "      min-width: 0;",
            "    }",
            "",
            "    .brand-logo {",
            "      height: 77px;",
            "      position: static;",
            "      transform: none;",
            "    }",
            "  }",
            "",
            '  div[data-testid="stFileUploaderDropzone"] {',
            f"    border: 2px dashed {COLOR_UPLOAD_BORDER};",
            f"    background: {COLOR_UPLOAD_BG};",
            "    border-radius: 14px;",
            "    transition: background-color 0.2s ease, border-color 0.2s ease;",
            "    padding-top: 0.8rem;",
            "    padding-bottom: 0.8rem;",
            "  }",
            "",
            '  div[data-testid="stFileUploaderDropzone"]:hover {',
            "    background: var(--brand-soft);",
            "    border-color: var(--brand);",
            "  }",
            "",
            '  [data-testid="stSidebar"] h4 {',
            "    margin-top: 0.95rem;",
            "    margin-bottom: 0.2rem;",
            f"    color: {COLOR_SIDEBAR_HEADING};",
            "    font-size: 0.92rem;",
            "    text-transform: uppercase;",
            "    letter-spacing: 0.02em;",
            "  }",
            "",
            "  /* Language selector: keep layout stable and compact. */",
            "  .page-lang-wrap {",
            "    display: flex;",
            "    justify-content: flex-end;",
            "    align-items: center;",
            "    margin-top: 0.5rem;",
            "  }",
            "",
            '  .page-lang-wrap [data-testid="stRadio"] {',
            "    margin-left: auto;",
            "  }",
            "",
            '  .page-lang-wrap [data-testid="stRadio"] > div {',
            "    display: flex;",
            "    flex-wrap: nowrap;",
            "    align-items: center;",
            "    gap: 0.75rem;",
            "  }",
            "",
            "  /* Make transport buttons equal compact size. */",
            '  #transport-controls-anchor + div[data-testid="stHorizontalBlock"]',
            '      > div[data-testid="column"]:nth-of-type(-n+3)',
            '      div[data-testid="stButton"] > button {',
            "      width: 100%;",
            "      min-height: 2.75rem;",
            "      padding: 0.3rem 0.6rem;",
            "      font-size: 1.9rem;",
            "      line-height: 1.0;",
            "      border-radius: 0.75rem;",
            "      white-space: nowrap;",
            "      transition: background-color 0.15s ease,",
            "                  border-color 0.15s ease, color 0.15s ease;",
            "  }",
            "",
            '  #transport-controls-anchor + div[data-testid="stHorizontalBlock"]',
            '      > div[data-testid="column"]:nth-of-type(1)',
            '      div[data-testid="stButton"] > button {',
            "      display: inline-flex !important;",
            "      align-items: center !important;",
            "      justify-content: center !important;",
            "      text-align: center;",
            "  }",
            "",
            '  #transport-controls-anchor + div[data-testid="stHorizontalBlock"]',
            '      > div[data-testid="column"]:nth-of-type(-n+3)',
            '      div[data-testid="stButton"] > button p {',
            "      margin: 0 !important;",
            "      line-height: 1.0 !important;",
            "  }",
            "",
            "  /* Start/Pause/Stop color states via stable widget keys. */",
            '  .st-key-transport_start div[data-testid="stButton"] > button:not(:disabled) {',
            "      background-color: #8ac6dd !important;",
            "      border-color: #8ac6dd !important;",
            "      color: #1b4f63 !important;",
            "      font-weight: 700;",
            "  }",
            "",
            '  .st-key-transport_start div[data-testid="stButton"] > button:not(:disabled):hover {',
            "      background-color: #0a7ea4 !important;",
            "      border-color: #0a7ea4 !important;",
            "      color: #ffffff !important;",
            "  }",
            "",
            '  .st-key-transport_start div[data-testid="stButton"] > button:not(:disabled) * {',
            "      color: inherit !important;",
            "  }",
            "",
            '  .st-key-transport_pause div[data-testid="stButton"] > button:not(:disabled) {',
            "      background-color: #ffffff !important;",
            "      border-color: var(--brand) !important;",
            "      color: var(--brand) !important;",
            "      font-weight: 700;",
            "  }",
            "",
            '  .st-key-transport_pause div[data-testid="stButton"] > button:not(:disabled):hover {',
            "      background-color: var(--brand-soft) !important;",
            "      border-color: var(--brand) !important;",
            "      color: var(--brand) !important;",
            "  }",
            "",
            '  .st-key-transport_pause div[data-testid="stButton"] > button:not(:disabled) * {',
            "      color: inherit !important;",
            "  }",
            "",
            '  .st-key-transport_stop div[data-testid="stButton"] > button:not(:disabled) {',
            "      background-color: #ffffff !important;",
            "      border-color: #c62828 !important;",
            "      color: #c62828 !important;",
            "      font-weight: 700;",
            "  }",
            "",
            '  .st-key-transport_stop div[data-testid="stButton"] > button:not(:disabled):hover {',
            "      background-color: #c62828 !important;",
            "      border-color: #c62828 !important;",
            "      color: #ffffff !important;",
            "  }",
            "",
            '  .st-key-transport_stop div[data-testid="stButton"] > button:not(:disabled) * {',
            "      color: inherit !important;",
            "  }",
            "",
            "  /* Hide Streamlit heading anchor/link icons (chain icon) next to titles. */",
            '  [data-testid="stHeadingWithActionElements"] a,',
            '  [data-testid="stHeaderActionElements"] {',
            "      display: none !important;",
            "  }",
            "",
            "  .progress-block {",
            "    margin-top: 1.25rem;",
            "  }",
            "",
            "  .success-chip {",
            "    display: inline-block;",
            "    margin-top: 0.35rem;",
            "    padding: 0.4rem 0.65rem;",
            "    border-radius: 999px;",
            f"    background: {COLOR_SUCCESS_BG};",
            f"    color: {COLOR_SUCCESS_TEXT};",
            f"    border: 1px solid {COLOR_SUCCESS_BORDER};",
            "    font-weight: 600;",
            "  }",
            "",
            "  .stProgress > div > div > div > div {",
            "    background-color: var(--brand);",
            "  }",
            "</style>",
        ]
    )
    st.markdown(css, unsafe_allow_html=True)


def localize_file_uploader_ui(texts: dict[str, str]) -> None:
    """Override Streamlit uploader texts with a localized overlay."""
    drag_text = texts["dropzone_drag_text"].replace("'", "\\'")

    st.markdown(
        f"""
                <style>
                    div[data-testid="stFileUploaderDropzone"] {{
                        position: relative;
                        min-height: 7.5rem;
                    }}

                    /* Hide helper paragraph text only (keep button text clickable). */
                    div[data-testid="stFileUploaderDropzone"] p,
                    div[data-testid="stFileUploaderDropzone"] small {{
                        font-size: 0 !important;
                        line-height: 0 !important;
                        color: transparent !important;
                    }}

                    div[data-testid="stFileUploaderDropzone"]::before {{
                        content: '{drag_text}';
                        position: absolute;
                        top: 1.6rem;
                        left: 50%;
                        transform: translateX(-50%);
                        font-weight: 600;
                        color: {COLOR_UPLOAD_OVERLAY_TEXT};
                        white-space: nowrap;
                        pointer-events: none;
                    }}

                </style>
                """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def get_model_cached(
    model_size: str,
    model_dir: str,
    device: str,
    compute_type: str,
):
    return load_model_with_fallback(
        model_size=model_size,
        model_dir=Path(model_dir),
        device=device,
        compute_type=compute_type,
    )


def init_job_state() -> None:
    if "job_lock" not in st.session_state:
        st.session_state.job_lock = threading.Lock()
    if "job_data" not in st.session_state:
        st.session_state.job_data = {
            "job_state": "idle",
            "job_status": "Waiting for a WAV file",
            "job_progress": 0.0,
            "job_error": "",
            "job_transcript": "",
            "job_output_name": "merged_transcript.txt",
        }
    if "worker_thread" not in st.session_state:
        st.session_state.worker_thread = None
    if "pause_event" not in st.session_state:
        st.session_state.pause_event = threading.Event()
    if "stop_event" not in st.session_state:
        st.session_state.stop_event = threading.Event()


def update_job(job_lock: threading.Lock, job_data: dict, **kwargs) -> None:
    with job_lock:
        for key, value in kwargs.items():
            job_data[key] = value


def read_job_snapshot(job_lock: threading.Lock, job_data: dict) -> dict:
    with job_lock:
        return dict(job_data)


def wav_duration_sec(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_in:
        frame_rate = wav_in.getframerate()
        if frame_rate <= 0:
            return 0.0
        return wav_in.getnframes() / float(frame_rate)


def run_transcription_worker(
    *,
    uploaded_name: str,
    uploaded_bytes: bytes,
    model,
    model_used: str,
    language: str | None,
    beam_size: int,
    temperature: float,
    client_label: str,
    agent_label: str,
    job_lock: threading.Lock,
    job_data: dict,
    pause_event: threading.Event,
    stop_event: threading.Event,
    texts: dict[str, str],
) -> None:
    try:
        trace_event(
            "worker_enter",
            uploaded_name=uploaded_name,
            language=language,
            beam_size=beam_size,
            temperature=temperature,
            client_label=client_label,
            agent_label=agent_label,
        )
        update_job(
            job_lock,
            job_data,
            job_state="running",
            job_status=texts["status_preparing"],
            job_progress=0.0,
            job_error="",
            job_transcript="",
            job_output_name=f"{Path(uploaded_name).stem}_merged_transcript.txt",
        )

        with TemporaryDirectory(prefix="streamlit_dual_transcribe_") as tmp_dir:
            workspace = Path(tmp_dir)
            input_wav = workspace / uploaded_name
            input_wav.write_bytes(uploaded_bytes)

            client_wav = workspace / "client_left.wav"
            agent_wav = workspace / "agent_right.wav"

            split_stereo_to_mono(input_wav, client_wav, agent_wav)

            left_duration = wav_duration_sec(client_wav)
            right_duration = wav_duration_sec(agent_wav)
            total_duration = max(left_duration + right_duration, 0.001)
            trace_event(
                "worker_audio_split_complete",
                left_duration=round(left_duration, 3),
                right_duration=round(right_duration, 3),
                total_duration=round(total_duration, 3),
            )

            merged_segments: list[Segment] = []
            processed_before = 0.0

            channels = [
                (client_wav, client_label, texts["left_channel"], left_duration),
                (agent_wav, agent_label, texts["right_channel"], right_duration),
            ]

            for channel_path, speaker_label, channel_name, channel_duration in channels:
                trace_event(
                    "channel_transcription_started",
                    channel=channel_name,
                    speaker=speaker_label,
                    duration=round(channel_duration, 3),
                )
                if stop_event.is_set():
                    update_job(
                        job_lock,
                        job_data,
                        job_state="stopped",
                        job_status=texts["status_stopped"],
                    )
                    return

                update_job(
                    job_lock,
                    job_data,
                    job_status=texts["status_transcribing_channel"].format(channel=channel_name),
                )

                segments_iter, _info = model.transcribe(
                    str(channel_path),
                    language=language,
                    task="transcribe",
                    beam_size=beam_size,
                    temperature=temperature,
                    vad_filter=True,
                )

                last_end = 0.0
                for seg in segments_iter:
                    if stop_event.is_set():
                        update_job(
                            job_lock,
                            job_data,
                            job_state="stopped",
                            job_status=texts["status_stopped"],
                        )
                        return

                    while pause_event.is_set():
                        if stop_event.is_set():
                            update_job(
                                job_lock,
                                job_data,
                                job_state="stopped",
                                job_status=texts["status_stopped"],
                            )
                            return
                        update_job(
                            job_lock,
                            job_data,
                            job_state="paused",
                            job_status=texts["status_paused"],
                        )
                        time.sleep(0.2)

                    snapshot = read_job_snapshot(job_lock, job_data)
                    if snapshot.get("job_state") != "running":
                        update_job(job_lock, job_data, job_state="running")

                    text = seg.text.strip()
                    if text:
                        merged_segments.append(
                            Segment(
                                speaker=speaker_label,
                                start_sec=float(seg.start),
                                end_sec=float(seg.end),
                                text=text,
                            )
                        )

                    last_end = min(float(seg.end), channel_duration)
                    progress = min(99.0, ((processed_before + last_end) / total_duration) * 100)
                    update_job(job_lock, job_data, job_progress=progress)

                processed_before += channel_duration
                boundary_progress = min(99.0, (processed_before / total_duration) * 100)
                update_job(job_lock, job_data, job_progress=boundary_progress)
                trace_event(
                    "channel_transcription_completed",
                    channel=channel_name,
                    progress=round(boundary_progress, 2),
                )

            merged_segments.sort(key=lambda s: (s.start_sec, s.end_sec, s.speaker))

            output_name = read_job_snapshot(job_lock, job_data)["job_output_name"]
            output_txt = workspace / output_name
            write_merged_transcript(
                segments=merged_segments,
                output_txt=output_txt,
                source_wav=input_wav,
                model_used=model_used,
            )
            transcript = output_txt.read_text(encoding="utf-8")

            update_job(
                job_lock,
                job_data,
                job_state="completed",
                job_status=texts["status_completed"],
                job_progress=100.0,
                job_transcript=transcript,
            )
            trace_event("worker_completed", output_name=output_name, transcript_len=len(transcript))
    except Exception as exc:
        if TRACE_ENABLED:
            logger.exception("worker_failed | uploaded_name={} ", uploaded_name)
        update_job(
            job_lock,
            job_data,
            job_state="error",
            job_status=texts["status_failed"],
            job_error=str(exc),
        )


def get_ui_text() -> dict[str, str]:
    """Render title/language controls and return the active translation table."""
    # Default UI language is Dutch.
    ui_language = st.session_state.get("ui_language", "Nederlands")
    lang_code = "nl" if ui_language == "Nederlands" else "en"
    initial_texts = UI_TEXT[lang_code]

    title_text = html.escape(initial_texts["title"])
    logo_uri = get_page_logo_data_uri()

    header_left, header_right = st.columns([7.4, 2.6])

    with header_left:
        if logo_uri:
            st.markdown(
                (
                    "<div class='brand-title-row'>"
                    f"<h1 class='brand-title'>{title_text}</h1>"
                    f"<img class='brand-logo' src='{logo_uri}' "
                    "alt='Local Stereo Transcriber logo'>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"<h1 class='brand-title'>{title_text}</h1>", unsafe_allow_html=True)

    with header_right:
        st.markdown("<div class='page-lang-wrap'>", unsafe_allow_html=True)
        ui_language = st.radio(
            label="Taal / Language",
            options=["Nederlands", "English"],
            index=0 if ui_language == "Nederlands" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="ui_language",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 0.05rem;'></div>", unsafe_allow_html=True)
    st.write(initial_texts["intro"])
    lang_code = "nl" if ui_language == "Nederlands" else "en"
    return UI_TEXT[lang_code]


def get_sidebar_settings(texts: dict[str, str]) -> dict[str, object]:
    """Render sidebar controls and return transcription settings."""
    with st.sidebar:
        st.header(texts["settings"])

        st.markdown(f"#### {texts['group_audio']}")
        language_options = [texts["lang_auto"], texts["lang_english"], texts["lang_dutch"]]
        language_map = {
            texts["lang_dutch"]: "nl",
            texts["lang_english"]: "en",
            texts["lang_auto"]: None,
        }
        language_option = st.selectbox(
            texts["transcription_language"],
            language_options,
            index=0,
            help=texts["transcription_language_help"],
        )
        language = language_map[language_option]

        speaker_options = sorted([texts["speaker_client"], texts["speaker_agent"]])
        client_label = st.selectbox(
            texts["left_label"],
            speaker_options,
            index=speaker_options.index(texts["speaker_client"]),
            help=texts["channel_label_help_left"],
        )
        agent_label = st.selectbox(
            texts["right_label"],
            speaker_options,
            index=speaker_options.index(texts["speaker_agent"]),
            help=texts["channel_label_help_right"],
        )

        if client_label == agent_label:
            st.warning(texts["same_label_warning"])

        st.markdown(f"#### {texts['group_performance']}")
        model_size_options = [texts["model_size_large"], texts["model_size_medium"]]
        model_size_map = {
            texts["model_size_large"]: "large-v3",
            texts["model_size_medium"]: "medium",
        }
        model_size_option = st.selectbox(
            texts["model_size"],
            model_size_options,
            index=0,
            help=texts["model_size_help"],
        )
        model_size = model_size_map[model_size_option]

        device_options = [texts["device_auto"], texts["device_cpu"], texts["device_cuda"]]
        device_map = {
            texts["device_auto"]: "auto",
            texts["device_cpu"]: "cpu",
            texts["device_cuda"]: "cuda",
        }
        device_option = st.selectbox(
            texts["device"],
            device_options,
            index=0,
            help=texts["device_help"],
        )
        device = device_map[device_option]

        st.markdown(f"#### {texts['group_advanced']}")
        beam_size = int(
            st.number_input(
                texts["beam_size"],
                min_value=1,
                max_value=10,
                value=5,
                help=texts["beam_size_help"],
            )
        )
        temperature = float(
            st.number_input(
                texts["temperature"],
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.1,
                help=texts["temperature_help"],
            )
        )

    return {
        "model_size": model_size,
        "device": device,
        "compute_type": "int8",
        "language": language,
        "client_label": client_label,
        "agent_label": agent_label,
        "beam_size": beam_size,
        "temperature": temperature,
    }


class NativeUploadedFile:
    """Wrapper for native file picker results, mimicking Streamlit's UploadedFile."""

    def __init__(self, file_path: str | Path):
        self.path = Path(file_path)
        self.name = self.path.name
        self._bytes = None

    def getvalue(self) -> bytes:
        if self._bytes is None:
            self._bytes = self.path.read_bytes()
        return self._bytes


def show_native_file_picker() -> NativeUploadedFile | None:
    """Show macOS native file picker via AppleScript."""
    logger.debug("Opening native macOS file picker")

    # Don't filter by type - show all files, we validate extension after
    applescript = """
    set selected_file to (choose file with prompt "Select a WAV file")
    return POSIX path of selected_file
    """

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            logger.warning("File picker cancelled or error")
            return None

        file_path = result.stdout.strip()
        if not file_path:
            return None

        logger.info("File selected via native picker | path={}", file_path)
        return NativeUploadedFile(file_path)

    except Exception as e:
        logger.error("File picker error | error={}", str(e))
        return None


def render_native_uploader_ui_desktop(texts: dict[str, str]):
    """Render Streamlit uploader UI plus native picker fallback for Desktop."""
    # Show uploader without type filter (Desktop WebView doesn't handle it well)
    uploaded = st.file_uploader(
        texts["uploader_label"],
        accept_multiple_files=False,
        help=texts["uploader_help"],
    )
    localize_file_uploader_ui(texts)

    # If st.file_uploader didn't work (returns None in embedded WebView),
    # offer native picker as fallback
    if uploaded is None:
        if st.button("Or browse via native picker", key="native_fallback"):
            logger.debug("Native fallback button clicked")
            uploaded = show_native_file_picker()
            if uploaded:
                st.session_state["native_file"] = uploaded
                st.rerun()

    # Check if file was selected via native picker in previous interaction
    if uploaded is None and "native_file" in st.session_state:
        uploaded = st.session_state["native_file"]

    return uploaded


def render_uploader(texts: dict[str, str]):
    """Render uploader UI and preview audio when a file is selected."""
    # TRACE: Function entry - log configuration and runtime environment
    trace_event("render_uploader_entry")
    is_desktop = os.environ.get("LST_EMBEDDED_DESKTOP", "").strip() == "1"
    logger.debug(
        "render_uploader called | is_desktop={} | runtime_mode={}",
        is_desktop,
        "embedded_desktop" if is_desktop else "launcher_browser",
    )

    # Use native file picker for Desktop, Streamlit uploader for Browser
    if is_desktop:
        logger.debug("Using native file picker (Desktop mode)")
        uploaded = render_native_uploader_ui_desktop(texts)
    else:
        logger.debug("Using Streamlit file uploader (Browser/Launcher mode)")
        uploaded = st.file_uploader(
            texts["uploader_label"],
            type=["wav", "WAV"],
            accept_multiple_files=False,
            help=texts["uploader_help"],
        )

        # TRACE: Upload result
        if uploaded is None:
            logger.debug("st.file_uploader returned None - no file selected yet")
            trace_event("file_uploader_waiting")
        else:
            logger.debug(
                "st.file_uploader returned file | name={} | size={}",
                uploaded.name,
                len(uploaded.getvalue()),
            )
            trace_event(
                "file_uploader_result",
                filename=uploaded.name,
                size_bytes=len(uploaded.getvalue()),
            )

        localize_file_uploader_ui(texts)

    if uploaded is not None:
        # Validate extension server-side as a safety net.
        extension_valid = uploaded.name.lower().endswith((".wav", ".wave"))
        logger.debug(
            "Validating file extension | filename={} | extension_valid={}",
            uploaded.name,
            extension_valid,
        )

        if not extension_valid:
            logger.error("File validation failed | filename={} | expected=.wav", uploaded.name)
            trace_event("file_validation_failed", filename=uploaded.name)
            st.error(f"Error: Expected .wav file, got {uploaded.name}")
            return None

        uploaded_bytes = uploaded.getvalue()
        logger.info(
            "File selected and validated | filename={} | size_bytes={}",
            uploaded.name,
            len(uploaded_bytes),
        )
        trace_event(
            "wav_selected",
            filename=uploaded.name,
            size_bytes=len(uploaded_bytes),
        )
        st.audio(uploaded_bytes, format="audio/wav")

    return uploaded


def handle_start_action(
    controls,
    uploaded,
    texts: dict[str, str],
    settings: dict[str, object],
    model_dir: str,
    is_worker_alive: bool,
) -> None:
    """Start a new transcription job when the Start button is pressed."""
    start_disabled = uploaded is None or is_worker_alive
    trace_event(
        "start_button_rendered",
        start_disabled=start_disabled,
        has_uploaded_file=uploaded is not None,
        is_worker_alive=is_worker_alive,
    )

    if not controls[0].button(
        f"▶ {texts['start_button']}",
        disabled=start_disabled,
        type="secondary",
        key="transport_start",
    ):
        return

    trace_event("start_clicked")

    if uploaded is None:
        trace_event("start_click_ignored_no_file")
        return

    job_lock = st.session_state.job_lock
    job_data = st.session_state.job_data
    pause_event = st.session_state.pause_event
    stop_event = st.session_state.stop_event

    pause_event.clear()
    stop_event.clear()

    with st.spinner(texts["spinner_loading_model"]):
        trace_event(
            "model_load_started",
            model_size=settings["model_size"],
            device=settings["device"],
            compute_type=settings["compute_type"],
        )
        model, model_used = get_model_cached(
            model_size=settings["model_size"],
            model_dir=model_dir,
            device=settings["device"],
            compute_type=settings["compute_type"],
        )
        trace_event("model_load_completed", model_used=model_used)

    update_job(
        job_lock,
        job_data,
        job_state="running",
        job_status=texts["status_starting"],
        job_progress=0.0,
        job_error="",
        job_transcript="",
    )

    thread = threading.Thread(
        target=run_transcription_worker,
        kwargs={
            "uploaded_name": uploaded.name,
            "uploaded_bytes": uploaded.getvalue(),
            "model": model,
            "model_used": model_used,
            "language": settings["language"],
            "beam_size": settings["beam_size"],
            "temperature": settings["temperature"],
            "client_label": settings["client_label"],
            "agent_label": settings["agent_label"],
            "job_lock": job_lock,
            "job_data": job_data,
            "pause_event": pause_event,
            "stop_event": stop_event,
            "texts": texts,
        },
        daemon=True,
    )
    st.session_state.worker_thread = thread
    thread.start()
    trace_event("worker_thread_started", thread_name=thread.name)
    st.rerun()


def handle_pause_stop_actions(
    controls,
    texts: dict[str, str],
    snapshot: dict[str, object],
    is_worker_alive: bool,
) -> None:
    """Handle pause/resume and stop interactions for an active job."""
    job_lock = st.session_state.job_lock
    job_data = st.session_state.job_data
    pause_event = st.session_state.pause_event
    stop_event = st.session_state.stop_event

    pause_label = (
        f"▶ {texts['resume_button']}"
        if snapshot["job_state"] == "paused"
        else f"⏸ {texts['pause_button']}"
    )
    if controls[1].button(pause_label, disabled=not is_worker_alive, key="transport_pause"):
        trace_event(
            "pause_resume_clicked",
            was_paused=pause_event.is_set(),
            worker_alive=is_worker_alive,
        )
        if pause_event.is_set():
            pause_event.clear()
            update_job(
                job_lock,
                job_data,
                job_state="running",
                job_status=texts["status_resuming"],
            )
        else:
            pause_event.set()
            update_job(job_lock, job_data, job_state="paused", job_status=texts["status_paused"])
        st.rerun()

    if controls[2].button(
        f"■ {texts['stop_button']}", disabled=not is_worker_alive, key="transport_stop"
    ):
        trace_event("stop_clicked", worker_alive=is_worker_alive)
        stop_event.set()
        pause_event.clear()
        update_job(
            job_lock,
            job_data,
            job_state="stopped",
            job_status=texts["status_stopping"],
        )
        st.rerun()


def render_progress_and_results(texts: dict[str, str], snapshot: dict[str, object]) -> None:
    """Render progress state and final transcript output widgets."""
    st.markdown("<div class='progress-block'>", unsafe_allow_html=True)
    st.subheader(texts["progress"])

    if snapshot["job_state"] == "completed":
        st.markdown(
            (
                "<style>.stProgress > div > div > div > div "
                f"{{ background-color: {COLOR_OK}; }}"
                "</style>"
            ),
            unsafe_allow_html=True,
        )

    st.progress(max(0.0, min(1.0, snapshot["job_progress"] / 100.0)))
    st.write(f"{snapshot['job_progress']:.1f}%")

    status_text = snapshot["job_status"]
    if snapshot["job_state"] == "idle":
        status_text = texts["status_waiting_wav"]
    st.caption(status_text)

    if snapshot["job_state"] == "error" and snapshot["job_error"]:
        st.error(snapshot["job_error"])

    if snapshot["job_state"] == "completed" and snapshot["job_transcript"]:
        st.success(texts["transcription_complete"])
        st.markdown(
            f"<div class='success-chip'>✅ {texts['transcription_ready']}</div>",
            unsafe_allow_html=True,
        )
        st.text_area(texts["merged_transcript"], snapshot["job_transcript"], height=420)
        st.download_button(
            label=texts["download_transcript"],
            data=snapshot["job_transcript"],
            file_name=snapshot["job_output_name"],
            mime="text/plain",
        )


def main() -> None:
    st.set_page_config(page_title="Call to Text", layout="wide")
    init_job_state()
    model_dir = get_default_model_dir()
    inject_ui_styles()

    texts = get_ui_text()
    settings = get_sidebar_settings(texts)
    uploaded = render_uploader(texts)

    job_lock = st.session_state.job_lock
    job_data = st.session_state.job_data
    snapshot = read_job_snapshot(job_lock, job_data)
    worker = st.session_state.worker_thread
    is_worker_alive = worker is not None and worker.is_alive()

    current_trace_state = (
        snapshot.get("job_state"),
        is_worker_alive,
        uploaded.name if uploaded is not None else None,
    )
    previous_trace_state = st.session_state.get("trace_state_signature")
    if current_trace_state != previous_trace_state:
        trace_event(
            "ui_state_changed",
            job_state=snapshot.get("job_state"),
            worker_alive=is_worker_alive,
            uploaded_file=uploaded.name if uploaded is not None else None,
            status=snapshot.get("job_status"),
        )
        st.session_state.trace_state_signature = current_trace_state

    st.markdown("<div id='transport-controls-anchor'></div>", unsafe_allow_html=True)
    controls = st.columns([1.15, 1.15, 1.15, 6.55])
    handle_start_action(
        controls,
        uploaded,
        texts,
        settings,
        model_dir,
        is_worker_alive,
    )
    handle_pause_stop_actions(controls, texts, snapshot, is_worker_alive)

    snapshot = read_job_snapshot(job_lock, job_data)
    render_progress_and_results(texts, snapshot)

    st.markdown("---")
    st.caption(texts["developer_footer"])

    st.markdown("</div>", unsafe_allow_html=True)

    # Keep UI responsive and progress live while worker is active.
    if is_worker_alive:
        time.sleep(0.6)
        st.rerun()


if __name__ == "__main__":
    main()

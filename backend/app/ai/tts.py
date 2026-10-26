"""Gemini TTS for the unattended fail-safe's spoken announcement (Interactions API, `gemini-3.8-flash-tts`).

One call per fail-safe action: the announcement text in, audio out. The model the provider echoes must be the one we
asked for; a different model, no audio block, an error or a timeout raises VoiceError with an application code, and the
browser speaks instead (labelled). Nothing is stored at the provider (`store=False`) and no key or provider text reaches
a log or the UI. Same key as Argon: GEMINI_API_KEY.
"""
from __future__ import annotations

import asyncio
import base64
import os
import struct
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from google import genai

MODEL = "gemini-3.8-flash-tts"  # probed live on 26 Oct 2026: echoed model, 24 kHz mono WAV, about 7 s for 12 s of speech
VOICE = "Kore"
MAX_TEXT_CHARS = 800
DEFAULT_TIMEOUT_SECONDS = 20.0
PCM_MIMES = ("audio/l16", "audio/pcm")


class VoiceError(Exception):
    """An application-owned code, never provider text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class VoiceClip:
    audio: bytes
    mime_type: str
    model: str
    interaction_id: Optional[str]
    seconds: Optional[float]
    elapsed_ms: int


def pcm_to_wav(pcm: bytes, sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    """A RIFF/WAVE header around raw little-endian PCM, so every browser can play it."""
    block = channels * bits // 8
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16, 1, channels, sample_rate,
                         sample_rate * block, block, bits, b"data", len(pcm))
    return header + pcm


def wav_seconds(wav: bytes) -> Optional[float]:
    """Duration of a canonical PCM WAV (44-byte header), or None for anything else."""
    if len(wav) < 44 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return None
    byte_rate = struct.unpack("<I", wav[28:32])[0]
    data_size = struct.unpack("<I", wav[40:44])[0]
    return round(data_size / byte_rate, 2) if byte_rate else None


def audio_from_interaction(interaction: Any) -> tuple[bytes, str]:
    """The first audio block of the model's output, as playable bytes and their MIME type."""
    for step in getattr(interaction, "steps", None) or []:
        if getattr(step, "error", None):
            raise VoiceError("provider_reported_errors")
        if getattr(step, "type", None) != "model_output":
            continue
        for content in getattr(step, "content", None) or []:
            if getattr(content, "type", None) != "audio":
                continue
            data = getattr(content, "data", None)
            if not data:
                raise VoiceError("provider_audio_missing")
            raw = base64.b64decode(data) if isinstance(data, str) else bytes(data)
            mime = str(getattr(content, "mime_type", None) or "audio/l16").lower()
            if mime.split(";")[0] in PCM_MIMES:
                rate = getattr(content, "sample_rate", None) or 24000
                return pcm_to_wav(raw, int(rate), int(getattr(content, "channels", None) or 1)), "audio/wav"
            return raw, mime.split(";")[0]
    raise VoiceError("provider_audio_missing")


class Synthesizer:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, voice: Optional[str] = None):
        key = (api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")).strip()
        self.model = model or os.environ.get("SPATIALTWIN_TTS_MODEL", "").strip() or MODEL
        self.voice = voice or os.environ.get("SPATIALTWIN_TTS_VOICE", "").strip() or VOICE
        self.client: Optional[genai.Client] = None
        if key:
            try:
                self.client = genai.Client(api_key=key, http_options={"retry_options": {"attempts": 1}})
                retry = self.client.aio.interactions.sdk_configuration.retry_config
                retry.strategy, retry.max_retries = "none", 0  # one call means one call (see grounding/adapter.py)
            except Exception:
                self.client = None

    def available(self) -> bool:
        """Configuration only; it does not establish account or model access."""
        return self.client is not None

    async def speak(self, text: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> VoiceClip:
        if self.client is None:
            raise VoiceError("configuration_missing")
        text = " ".join((text or "").split())
        if not text or len(text) > MAX_TEXT_CHARS:
            raise VoiceError("invalid_text")
        started = time.monotonic()
        try:
            interaction = await asyncio.wait_for(self.client.aio.interactions.create(
                model=self.model, input=text, store=False, stream=False,
                response_format={"type": "audio"},
                generation_config={"structured_speech_config": [{"voice": self.voice}]},
                timeout=timeout), timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException):
            raise VoiceError("provider_timeout") from None
        except VoiceError:
            raise
        except Exception:
            raise VoiceError("provider_error") from None
        echoed = getattr(interaction, "model", None)
        if echoed is not None and echoed != self.model:
            raise VoiceError("provider_model_mismatch")
        status = getattr(interaction, "status", None)
        if status is not None and str(getattr(status, "value", status)) != "completed":
            raise VoiceError("provider_status_not_completed")
        audio, mime = audio_from_interaction(interaction)
        return VoiceClip(audio=audio, mime_type=mime, model=echoed or self.model,
                         interaction_id=getattr(interaction, "id", None),
                         seconds=wav_seconds(audio) if mime == "audio/wav" else None,
                         elapsed_ms=round((time.monotonic() - started) * 1000))

    async def aclose(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            try:
                await client.aio.aclose()
            finally:
                client.close()

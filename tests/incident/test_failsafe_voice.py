"""The fail-safe's voice: Gemini TTS when armed with it (one synthesis per distinct text, prepared during the window and
reused when it acts), the browser otherwise; never "is open" before an endpoint switch; failures stay visible."""
import asyncio
import base64
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from backend.app.ai import tts
from backend.app.ai.tts import Synthesizer, VoiceClip, VoiceError, audio_from_interaction, pcm_to_wav, wav_seconds
from backend.app.incident.failsafe import SPOKEN_PREFIX, spoken_text
from backend.app.incident.manager import IncidentManager
from backend.app.incident.routes import build_incident_router, set_default_manager
from tests.incident.conftest import FAST, HALL_FIRE, LOBBY_FIRE, approve_body, plan_with

WINDOW = 0.15


class FakeSynth:
    model = "gemini-3.8-flash-tts"

    def __init__(self, delay: float = 0.0, fail: str | None = None, available: bool = True):
        self.calls: list[str] = []
        self.delay, self.fail, self._available = delay, fail, available

    def available(self) -> bool:
        return self._available

    async def speak(self, text: str, timeout: float = 20) -> VoiceClip:
        self.calls.append(text)
        await asyncio.sleep(self.delay)
        if self.fail:
            raise VoiceError(self.fail)
        audio = pcm_to_wav(b"\x00\x10" * 2400)
        return VoiceClip(audio=audio, mime_type="audio/wav", model=self.model, interaction_id=None,
                         seconds=wav_seconds(audio), elapsed_ms=1)


def voiced(synth):
    manager = IncidentManager(FAST, synthesizer=synth)
    set_default_manager(manager)
    return manager


@pytest.fixture
async def voice_client():
    app = FastAPI()
    app.include_router(build_incident_router())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
    set_default_manager(None)


async def settle(manager):
    await manager.wait_failsafe()
    for job in list(manager._voices.values()):
        await asyncio.gather(job.task, return_exceptions=True)


# -- the TTS module -----------------------------------------------------------------------------------------------

def test_pcm_becomes_a_playable_wav_with_its_duration():
    wav = pcm_to_wav(b"\x00\x00" * 24000)
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE" and len(wav) == 44 + 48000
    assert wav_seconds(wav) == 1.0 and wav_seconds(b"not a wav") is None


def test_audio_is_read_from_the_model_output_step():
    pcm = base64.b64encode(b"\x01\x00" * 12000).decode()
    step = SimpleNamespace(type="model_output", error=None,
                           content=[SimpleNamespace(type="audio", data=pcm, mime_type="audio/l16", sample_rate=24000, channels=1)])
    audio, mime = audio_from_interaction(SimpleNamespace(steps=[step]))
    assert mime == "audio/wav" and wav_seconds(audio) == 0.5
    wav = base64.b64encode(pcm_to_wav(b"\x00\x00" * 10)).decode()
    passthrough = SimpleNamespace(type="model_output", error=None, content=[SimpleNamespace(type="audio", data=wav, mime_type="audio/wav")])
    assert audio_from_interaction(SimpleNamespace(steps=[passthrough]))[1] == "audio/wav"
    with pytest.raises(VoiceError) as missing:
        audio_from_interaction(SimpleNamespace(steps=[SimpleNamespace(type="model_output", error=None, content=[])]))
    assert missing.value.code == "provider_audio_missing"


class _Interactions:
    def __init__(self, result=None, delay=0.0, error=None):
        self.result, self.delay, self.error, self.requests = result, delay, error, []

    async def create(self, **request):
        self.requests.append(request)
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


def fake_client(interactions):
    return SimpleNamespace(aio=SimpleNamespace(interactions=interactions, aclose=lambda: asyncio.sleep(0)), close=lambda: None)


def audio_interaction(model="gemini-3.8-flash-tts", status="completed"):
    pcm = base64.b64encode(b"\x00\x00" * 2400).decode()
    step = SimpleNamespace(type="model_output", error=None,
                           content=[SimpleNamespace(type="audio", data=pcm, mime_type="audio/l16", sample_rate=24000, channels=1)])
    return SimpleNamespace(id="int-1", model=model, status=status, steps=[step])


async def test_speak_sends_one_unstored_audio_request_and_checks_the_echoed_model():
    synth = Synthesizer(api_key="")
    assert not synth.available()
    with pytest.raises(VoiceError) as unconfigured:
        await synth.speak("hello")
    assert unconfigured.value.code == "configuration_missing"
    calls = _Interactions(audio_interaction())
    synth.client = fake_client(calls)
    clip = await synth.speak("  Attention.   Fire in the hall.  ")
    request = calls.requests[0]
    assert request["model"] == tts.MODEL == "gemini-3.8-flash-tts" and request["input"] == "Attention. Fire in the hall."
    assert request["store"] is False and request["response_format"] == {"type": "audio"}
    assert request["generation_config"] == {"structured_speech_config": [{"voice": "Kore"}]}
    assert clip.mime_type == "audio/wav" and clip.seconds == 0.1 and clip.model == "gemini-3.8-flash-tts"
    synth.client = fake_client(_Interactions(audio_interaction(model="gemini-other-tts")))
    with pytest.raises(VoiceError) as mismatch:
        await synth.speak("x")
    assert mismatch.value.code == "provider_model_mismatch"
    synth.client = fake_client(_Interactions(audio_interaction(), delay=0.2))
    with pytest.raises(VoiceError) as late:
        await synth.speak("x", timeout=0.05)
    assert late.value.code == "provider_timeout"
    synth.client = fake_client(_Interactions(error=RuntimeError("secret detail")))
    with pytest.raises(VoiceError) as broken:
        await synth.speak("x")
    assert broken.value.code == "provider_error" and "secret" not in str(broken.value)
    with pytest.raises(VoiceError) as long:
        await synth.speak("x" * 900)
    assert long.value.code == "invalid_text"


def test_spoken_text_never_says_open_before_the_switch():
    text = "Attention. Fire in the lobby. Door D9 between the east corridor and the loading dock is to be opened."
    assert spoken_text(text, {"D9": "OPEN"}).endswith("Door D9 between the east corridor and the loading dock is opening.")
    assert spoken_text(text, {}).endswith("is to be opened.")
    assert spoken_text(text, {"D9": "OPEN"}).startswith(SPOKEN_PREFIX) and " is open." not in spoken_text(text, {"D9": "OPEN"})
    assert spoken_text("", {}) == SPOKEN_PREFIX


# -- the manager and route ------------------------------------------------------------------------------------------

async def test_the_voice_is_prepared_during_the_window_and_reused_when_it_acts(voice_client):
    synth = FakeSynth()
    manager = voiced(synth)
    await plan_with(voice_client, LOBBY_FIRE)
    view = await manager.set_failsafe(True, WINDOW, "gemini")
    assert view.voice == "gemini" and view.voice_available and view.voice_model == "gemini-3.8-flash-tts"
    await asyncio.sleep(WINDOW / 3)
    assert len(synth.calls) == 1 and "Door D9 between the east corridor and the loading dock is opening." in synth.calls[0]
    await settle(manager)
    state = (await voice_client.get("/api/incident")).json()
    approval = state["approvals"][-1]
    assert approval["actor"] == "fail_safe" and len(synth.calls) == 1, "the prepared clip is reused, not synthesized twice"
    last = state["failsafe"]["last_action"]
    assert last["voice"] == "gemini" and last["voice_status"] == "ready" and last["voice_model"] == "gemini-3.8-flash-tts"
    clip = await voice_client.get(f"/api/incident/failsafe/voice/{approval['approval_id']}")
    assert clip.status_code == 200 and clip.headers["content-type"] == "audio/wav" and clip.content[:4] == b"RIFF"
    assert clip.headers["x-voice-model"] == "gemini-3.8-flash-tts" and clip.headers["x-voice-provenance"] == "live"
    assert clip.headers["cache-control"] == "no-store"


async def test_with_a_held_door_it_says_the_held_plan_not_the_one_it_refused(voice_client):
    synth = FakeSynth()
    manager = voiced(synth)
    state = await plan_with(voice_client, HALL_FIRE)
    assert "D4" in state["plan"]["announcement"]  # the person's plan would open D4 into the hall
    await manager.set_failsafe(True, WINDOW, "gemini")
    await settle(manager)
    assert len(synth.calls) == 1 and "D4" not in synth.calls[0]
    done = (await voice_client.get("/api/incident")).json()
    assert done["plan"]["held_doors"] == ["D4"] and done["failsafe"]["last_action"]["voice_status"] == "ready"


async def test_a_voice_that_fails_is_reported_and_the_route_says_why(voice_client):
    synth = FakeSynth(fail="provider_timeout")
    manager = voiced(synth)
    await plan_with(voice_client, LOBBY_FIRE)
    await manager.set_failsafe(True, WINDOW, "gemini")
    await settle(manager)
    state = (await voice_client.get("/api/incident")).json()
    last = state["failsafe"]["last_action"]
    assert last["voice"] == "gemini" and last["voice_status"] == "failed" and last["voice_error"] == "provider_timeout"
    response = await voice_client.get(f"/api/incident/failsafe/voice/{last['approval_id']}")
    assert response.status_code == 502 and response.json()["detail"]["code"] == "provider_timeout"


async def test_the_route_waits_for_a_clip_still_being_made(voice_client):
    synth = FakeSynth(delay=0.4)
    manager = voiced(synth)
    await plan_with(voice_client, LOBBY_FIRE)
    await manager.set_failsafe(True, 0.05, "gemini")
    await manager.wait_failsafe()
    approval = (await voice_client.get("/api/incident")).json()["approvals"][-1]
    response = await voice_client.get(f"/api/incident/failsafe/voice/{approval['approval_id']}")
    assert response.status_code == 200 and response.content[:4] == b"RIFF" and len(synth.calls) == 1


async def test_browser_voice_and_no_key_never_call_gemini(voice_client):
    synth = FakeSynth()
    manager = voiced(synth)
    await plan_with(voice_client, LOBBY_FIRE)
    await manager.set_failsafe(True, WINDOW, "browser")
    await settle(manager)
    state = (await voice_client.get("/api/incident")).json()
    assert synth.calls == [] and state["failsafe"]["voice"] == "browser" and state["failsafe"]["last_action"]["voice"] is None
    assert (await voice_client.get(f"/api/incident/failsafe/voice/{state['approvals'][-1]['approval_id']}")).status_code == 404
    unconfigured = voiced(FakeSynth(available=False))
    await plan_with(voice_client, LOBBY_FIRE)
    view = await unconfigured.set_failsafe(True, 30, "gemini")
    assert view.voice == "browser" and view.voice_available is False and view.voice_model is None
    frames = [frame for _, frame in unconfigured.hub.events_since(0)]
    assert any("Gemini TTS is not configured" in frame for frame in frames)
    await unconfigured.set_failsafe(False)


async def test_a_person_who_approves_gets_no_fail_safe_voice(voice_client):
    synth = FakeSynth()
    manager = voiced(synth)
    state = await plan_with(voice_client, LOBBY_FIRE)
    await manager.set_failsafe(True, 0.3, "gemini")
    record = await voice_client.post("/api/incident/approve", json=approve_body(state))
    await settle(manager)
    assert len(synth.calls) <= 1  # at most the clip prepared during the window
    assert (await voice_client.get(f"/api/incident/failsafe/voice/{record.json()['approval_id']}")).status_code == 404
    assert (await voice_client.get("/api/incident/failsafe/voice/not-an-id")).status_code == 422


async def test_arm_route_takes_the_voice_and_reset_drops_the_clips(voice_client):
    manager = voiced(FakeSynth())
    await plan_with(voice_client, LOBBY_FIRE)
    armed = await voice_client.post("/api/incident/failsafe", json={"armed": True, "window_seconds": 5, "voice": "gemini"})
    assert armed.status_code == 200 and armed.json()["voice"] == "gemini"
    assert (await voice_client.post("/api/incident/failsafe", json={"armed": True, "voice": "robot"})).status_code == 422
    await asyncio.sleep(0.05)
    await voice_client.post("/api/incident/reset")
    assert manager._voices == {} and manager._approval_voice == {} and manager.failsafe_armed is False

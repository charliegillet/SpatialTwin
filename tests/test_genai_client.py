import pytest

from fakes import (FakeClient, code_execution_step, function_call_step,
                   processing_call_step, text_step)
from walktwin.genai_client import (Receipt, UploadedFile, count_steps,
                                   joined_text, make_client, run_background,
                                   upload_video)


async def test_run_background_polls_until_terminal():
    client = FakeClient(["in_progress", "in_progress", "completed"])
    interaction, receipt = await run_background(
        client, deadline_s=5, poll_s=0.001, model="m", input="hi")
    assert len(client.get_calls) == 2
    assert receipt.status == "completed"
    assert interaction.status == "completed"
    assert client.requests[0]["background"] is True
    assert client.requests[0]["store"] is True


async def test_run_background_deadline():
    client = FakeClient(["in_progress"])
    with pytest.raises(TimeoutError):
        await run_background(client, deadline_s=0.05, poll_s=0.01, model="m", input="hi")
    assert len(client.cancel_calls) == 1


@pytest.mark.parametrize("status", ["requires_action", "failed", "cancelled", "incomplete"])
async def test_run_background_returns_non_completed_terminal(status):
    client = FakeClient(["in_progress", status])
    _, receipt = await run_background(client, deadline_s=5, poll_s=0.001, model="m", input="x")
    assert receipt.status == status


def test_joined_text_concatenates_model_output_steps():
    from fakes import FakeClient as F  # noqa: F401
    from google.genai._gaos.types.interactions.interaction import Interaction
    i = Interaction.model_validate({"status": "completed", "steps": [
        text_step('{"a":'), processing_call_step(), text_step("1}")]})
    assert joined_text(i) == '{"a":1}'


async def test_processing_calls_counted():
    steps = [processing_call_step(f"p{n}") for n in range(3)] + [
        code_execution_step(), function_call_step("f", {}), text_step("x")]
    client = FakeClient([{"status": "completed", "steps": steps}])
    interaction, receipt = await run_background(client, deadline_s=5, poll_s=0.001, model="m", input="x")
    assert receipt.processing_calls == 3
    assert count_steps(interaction, "model_output") == 1
    assert count_steps(interaction, "function_call") == 1


async def test_receipt_fields():
    client = FakeClient([{"status": "completed", "id": "abc", "model": "gemini-4-argon",
                          "usage": {"total_input_tokens": 10, "total_tokens": 15}}])
    _, receipt = await run_background(client, deadline_s=5, poll_s=0.001, model="gemini-4-argon", input="x")
    assert isinstance(receipt, Receipt)
    assert receipt.interaction_id == "abc"
    assert receipt.provider_model == "gemini-4-argon"
    assert receipt.usage["total_input_tokens"] == 10
    assert receipt.elapsed_ms >= 0
    assert set(Receipt.model_fields) == {"interaction_id", "provider_model", "status",
                                         "usage", "elapsed_ms", "processing_calls"}


async def test_provider_model_falls_back_to_agent_config():
    client = FakeClient([{"status": "completed", "agent_config":
                          {"type": "antigravity", "model": "gemini-4-argon"}}])
    _, receipt = await run_background(client, deadline_s=5, poll_s=0.001, agent="a", input="x")
    assert receipt.provider_model == "gemini-4-argon"


async def test_upload_video_waits_for_active(tmp_path):
    p = tmp_path / "c.mp4"
    p.write_bytes(b"x")
    client = FakeClient(file_states=["PROCESSING", "PROCESSING", "ACTIVE"])
    f = await upload_video(client, p, poll_s=0.001)
    assert f == UploadedFile(uri="https://fake.test/files/fake123", mime_type="video/mp4",
                             name="files/fake123")
    assert len(client.file_get_calls) == 2


async def test_upload_video_failed_raises(tmp_path):
    p = tmp_path / "c.mp4"
    p.write_bytes(b"x")
    client = FakeClient(file_states=["PROCESSING", "FAILED"])
    with pytest.raises(RuntimeError):
        await upload_video(client, p, poll_s=0.001)


def test_make_client_requires_key(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("walktwin.genai_client._ENV_SEARCH", [tmp_path / ".env"])
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        make_client()


def test_make_client_reads_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    (tmp_path / ".env").write_text('# c\nGEMINI_API_KEY="k-test"\n')
    monkeypatch.setattr("walktwin.genai_client._ENV_SEARCH", [tmp_path / ".env"])
    assert make_client() is not None
    import os
    assert os.environ["GEMINI_API_KEY"] == "k-test"

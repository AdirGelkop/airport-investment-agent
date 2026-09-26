"""Unit test for voice input (no network: the Whisper client is faked)."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import voice  # noqa: E402


def test_transcribe_sends_audio_to_whisper(monkeypatch):
    sent = {}

    class FakeTranscriptions:
        def create(self, **kwargs):
            sent.update(kwargs)
            return SimpleNamespace(text="  Compare LAX and SNA congestion.  ")

    fake_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=FakeTranscriptions()))
    monkeypatch.setattr(voice, "OpenAI", lambda **kwargs: fake_client)
    monkeypatch.delenv("STT_MODEL", raising=False)

    assert voice.transcribe(b"fake-wav-bytes") == "Compare LAX and SNA congestion."
    assert sent["model"] == "whisper-large-v3-turbo"
    assert sent["file"] == ("question.wav", b"fake-wav-bytes")
    assert sent["language"] == "en"

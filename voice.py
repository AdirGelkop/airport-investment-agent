"""Voice input (bonus): turn a recorded question into text with Whisper.
Uses the same OpenAI-compatible provider and key as the agent (Groq by default)."""
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Helps Whisper spell airport names and codes correctly
VOCABULARY_HINT = ("US airports, IATA codes like SFO, LAX, SNA, ANC, BOS, BDL, PVD. "
                   "New England, Santa Ana, Anchorage, load factor, long-haul, unmet demand.")


def transcribe(audio_bytes: bytes) -> str:
    """Recorded audio (WAV bytes) -> question text."""
    client = OpenAI(api_key=os.getenv("LLM_API_KEY"),
                    base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"))
    result = client.audio.transcriptions.create(
        model=os.getenv("STT_MODEL", "whisper-large-v3-turbo"),
        file=("question.wav", audio_bytes),
        language="en",
        prompt=VOCABULARY_HINT,
    )
    return result.text.strip()

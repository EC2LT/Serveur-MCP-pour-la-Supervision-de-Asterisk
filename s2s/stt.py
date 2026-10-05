# s2s/stt.py
import logging
import asyncio
from faster_whisper import WhisperModel
from config import settings

logger = logging.getLogger(__name__)

_model = None


def get_model():
    global _model
    if _model is None:
        logger.info(f"Chargement Whisper '{settings.WHISPER_MODEL}'...")
        _model = WhisperModel(settings.WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


HALLUCINATIONS = ["sous-titres", "amara.org", "merci d'avoir regardé", "sous-titrage"]


async def transcribe(wav_path: str, language: str = "fr") -> str:
    """Transcrit un WAV en texte (non bloquant)."""
    def _run():
        segments, _ = get_model().transcribe(
            wav_path, language=language, beam_size=1,
            no_speech_threshold=0.5, condition_on_previous_text=False,
        )
        return "".join(s.text for s in segments).strip()

    text = await asyncio.to_thread(_run)
    if not text or len(text) < 3:
        return ""
    if any(h in text.lower() for h in HALLUCINATIONS):
        logger.info(f"Hallucination ignorée : '{text}'")
        return ""
    return text

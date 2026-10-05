# s2s/tts.py
import asyncio
import logging
import os
import subprocess
from config import settings

logger = logging.getLogger(__name__)


async def synthesize(text: str, output_wav: str) -> bool:
    """
    Synthétise un texte en WAV 8000 Hz mono (format Asterisk).
    Utilise Piper + ffmpeg.
    """
    if not text.strip():
        return False

    safe_text = text.replace('"', '\\"').replace("`", "")
    raw = output_wav.replace(".wav", "_raw.wav")

    cmd = (
        f'echo "{safe_text}" | piper --model {settings.PIPER_MODEL} '
        f'--output_file {raw} && '
        f'ffmpeg -y -i {raw} -ar 8000 -ac 1 -c:a pcm_s16le {output_wav}'
    )

    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()

    if os.path.exists(raw):
        os.remove(raw)

    return os.path.exists(output_wav)

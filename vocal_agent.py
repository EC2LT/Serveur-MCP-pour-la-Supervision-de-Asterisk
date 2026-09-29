import asyncio
import json
import logging
import os
import subprocess
import time
import numpy as np
import requests
import websockets
from faster_whisper import WhisperModel
import ollama

# --- CONFIGURATION ARI & NETWORK ---
ARI_WS_URL = "ws://localhost:8088/ari/events?api_key=mcp_user:mcp_secret_password&app=asterisk-vocal-ai"
ARI_HTTP_URL = "http://localhost:8088/ari"
AUTH = ("mcp_user", "mcp_secret_password")

UDP_IP = "127.0.0.1"
UDP_PORT = 5088

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- CHARGEMENT DU MODÈLE STT WHISPER ---
logging.info("Chargement du modèle STT Faster-Whisper...")
stt_model = WhisperModel("small", device="cpu", compute_type="int8")

SYSTEM_PROMPT = """Tu es un assistant vocal d'accueil et de supervision en temps réel pour un serveur VoIP Asterisk.
Tes réponses doivent être TRÈS COURTES, fluides et concises (maximum 2 phrases) pour être lues facilement au téléphone.
Si l'utilisateur pose une question sur l'état du serveur, les appels ou les lignes, utilise les outils mis à ta disposition pour obtenir les VRAIES données avant de répondre."""

# --- FONCTIONS DE SUPERVISION ASTERISK & SYSTÈME (TOOLS MCP) ---
def run_cli_command(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
        return result.stdout.strip()
    except Exception as e:
        return f"Erreur d'exécution : {e}"

def get_asterisk_status():
    """Rend l'état actuel d'Asterisk : temps de fonctionnement et nombre d'appels en cours."""
    uptime = run_cli_command("asterisk -rx 'core show uptime'")
    calls = run_cli_command("asterisk -rx 'core show calls'")
    return f"Statut Asterisk :\n{uptime}\n{calls}"

def get_pjsip_endpoints():
    """Rend la liste des extensions et la totalité des terminaux SIP configurés."""
    return run_cli_command("asterisk -rx 'pjsip show endpoints'")

def get_system_resources():
    """Rend l'utilisation de la mémoire RAM et du processeur du serveur."""
    mem = run_cli_command("free -h | grep Mem")
    load = run_cli_command("uptime | awk -F'load average:' '{ print $2 }'")
    return f"Charge CPU : {load}. Mémoire : {mem}"

# Mapping des outils pour Ollama
AVAILABLE_TOOLS = {
    'get_asterisk_status': get_asterisk_status,
    'get_pjsip_endpoints': get_pjsip_endpoints,
    'get_system_resources': get_system_resources
}

OLLAMA_TOOLS_SCHEMA = [
    {
        'type': 'function',
        'function': {
            'name': 'get_asterisk_status',
            'description': 'Obtient le statut en direct du serveur Asterisk (uptime et nombre d apparition d appels).',
            'parameters': {'type': 'object', 'properties': {}}
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_pjsip_endpoints',
            'description': 'Obtient le statut des extensions PJSIP et des comptes utilisateurs.',
            'parameters': {'type': 'object', 'properties': {}}
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_system_resources',
            'description': 'Obtient l utilisation CPU et RAM du serveur Linux.',
            'parameters': {'type': 'object', 'properties': {}}
        }
    }
]

# --- VARIABLES D'ÉTAT ---
active_caller_channel_id = None
snoop_bridge_id = None
is_processing = False

audio_buffer = bytearray()
last_speech_time = 0
SILENCE_THRESHOLD = 500  
SILENCE_DURATION = 1.2   
MAX_AUDIO_DURATION = 8.0 

class AudioUDPListener(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        global audio_buffer, last_speech_time
        if len(data) > 12:
            pcm_chunk = data[12:]
            audio_buffer.extend(pcm_chunk)
            samples = np.frombuffer(pcm_chunk, dtype='>i2')
            if len(samples) > 0:
                rms = np.sqrt(np.mean(samples.astype(np.float32)**2))
                if rms > SILENCE_THRESHOLD:
                    last_speech_time = time.time()

async def process_audio_and_respond(audio_data, channel_id):
    """Pipeline S2S : STT -> LLM avec Tool Calling -> TTS -> ARI Playback"""
    global is_processing
    is_processing = True

    try:
        raw_pcm = np.frombuffer(audio_data, dtype='>i2')
        if len(raw_pcm) == 0:
            is_processing = False
            return

        amplified_pcm = np.clip(raw_pcm.astype(np.float32) * 2.5, -32768, 32767).astype(np.int16)

        pcm_filename = f"/tmp/input_{channel_id}.raw"
        wav_input = f"/tmp/input_{channel_id}.wav"

        with open(pcm_filename, "wb") as f:
            f.write(amplified_pcm.astype('<i2').tobytes())

        os.system(f"ffmpeg -y -f s16le -ar 16000 -ac 1 -i {pcm_filename} {wav_input} >/dev/null 2>&1")

        segments, _ = stt_model.transcribe(
            wav_input,
            language="fr",
            beam_size=1,
            no_speech_threshold=0.5,
            condition_on_previous_text=False
        )
        user_text = "".join([segment.text for segment in segments]).strip()

    except Exception as e:
        logging.error(f"Erreur STT : {e}")
        is_processing = False
        return
    finally:
        for f in [pcm_filename, wav_input]:
            if os.path.exists(f):
                os.remove(f)

    hallucinations = ["sous-titres", "amara.org", "merci d'avoir regardé", "sous-titrage"]
    if not user_text or len(user_text) < 3 or any(h in user_text.lower() for h in hallucinations):
        logging.info(f"Ignoré (Bruit/Silence) : '{user_text}'")
        is_processing = False
        return

    logging.info(f"🎤 Utilisateur a dit : '{user_text}'")

    if active_caller_channel_id != channel_id:
        is_processing = False
        return

    # --- TRAITEMENT OLLAMA AVEC APPEL D'OUTILS (FUNCTION CALLING) ---
    try:
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_text}
        ]

        response = ollama.chat(
            model='qwen2.5:3b',
            messages=messages,
            tools=OLLAMA_TOOLS_SCHEMA
        )

        # Vérification si le LLM réclame l'exécution d'un outil
        if response.get('message', {}).get('tool_calls'):
            for tool in response['message']['tool_calls']:
                tool_name = tool['function']['name']
                if tool_name in AVAILABLE_TOOLS:
                    logging.info(f"🛠️ Exécution de l'outil système : {tool_name}")
                    tool_output = AVAILABLE_TOOLS[tool_name]()
                    
                    # Ajout de la réponse de l'outil au contexte
                    messages.append(response['message'])
                    messages.append({
                        'role': 'tool',
                        'content': str(tool_output),
                    })

            # Second passage pour que le LLM résume le résultat de l'outil
            final_response = ollama.chat(model='qwen2.5:3b', messages=messages)
            ai_text = final_response['message']['content']
        else:
            ai_text = response['message']['content']

        logging.info(f"🤖 Réponse LLM : '{ai_text}'")

    except Exception as e:
        logging.error(f"Erreur LLM : {e}")
        ai_text = "Désolé, une erreur s'est produite lors du contrôle du serveur."

    # --- TTS PIPER ---
    tts_raw = f"/tmp/response_raw_{channel_id}.wav"
    wav_out = f"/tmp/response_{channel_id}.wav"

    tts_cmd = f'echo "{ai_text}" | piper --model ./fr_FR-siwis-medium.onnx --output_file {tts_raw} && ffmpeg -y -i {tts_raw} -ar 8000 -ac 1 -c:a pcm_s16le {wav_out} >/dev/null 2>&1'
    proc = await asyncio.create_subprocess_shell(tts_cmd)
    await proc.wait()

    if active_caller_channel_id == channel_id:
        logging.info(f"🔊 Envoi immédiat de la réponse au canal : {channel_id}")
        media_url = f"{ARI_HTTP_URL}/channels/{channel_id}/play"
        sound_file = f"sound:{wav_out.replace('.wav', '')}"
        requests.post(media_url, auth=AUTH, params={"media": sound_file})

    is_processing = False

async def audio_stream_monitor():
    global audio_buffer, active_caller_channel_id, is_processing, last_speech_time

    max_bytes = int(32000 * MAX_AUDIO_DURATION)
    min_bytes = 32000 * 1

    while True:
        await asyncio.sleep(0.2)

        if active_caller_channel_id and not is_processing and len(audio_buffer) >= min_bytes:
            current_time = time.time()
            time_since_last_speech = current_time - last_speech_time

            if (last_speech_time > 0 and time_since_last_speech >= SILENCE_DURATION) or len(audio_buffer) >= max_bytes:
                data_to_process = bytes(audio_buffer)
                audio_buffer.clear()
                last_speech_time = 0
                asyncio.create_task(process_audio_and_respond(data_to_process, active_caller_channel_id))

async def ari_websocket_loop():
    global active_caller_channel_id, snoop_bridge_id, is_processing, audio_buffer

    async with websockets.connect(ARI_WS_URL) as ws:
        logging.info("Connecté au WebSocket ARI (Application Stasis: asterisk-vocal-ai)")
        loop = asyncio.get_running_loop()

        transport, _ = await loop.create_datagram_endpoint(
            AudioUDPListener,
            local_addr=(UDP_IP, UDP_PORT)
        )
        asyncio.create_task(audio_stream_monitor())

        try:
            async for msg in ws:
                event = json.loads(msg)
                event_type = event.get("type")

                if event_type == "StasisStart":
                    channel = event.get("channel", {})
                    channel_id = channel.get("id")

                    if "UnicastRTP" in channel.get("name", "") or "Snoop" in channel.get("name", ""):
                        continue

                    active_caller_channel_id = channel_id
                    audio_buffer.clear()
                    is_processing = False
                    logging.info(f"Nouveau canal d'appelant connecté : {active_caller_channel_id}")

                    bridge_res = requests.post(f"{ARI_HTTP_URL}/bridges", auth=AUTH, params={"type": "mixing"})
                    snoop_bridge_id = bridge_res.json().get("id")

                    snoop_res = requests.post(
                        f"{ARI_HTTP_URL}/channels/{active_caller_channel_id}/snoop",
                        auth=AUTH,
                        params={"app": "asterisk-vocal-ai", "spy": "in", "whisper": "none"}
                    )
                    snoop_channel_id = snoop_res.json().get("id")

                    ext_res = requests.post(
                        f"{ARI_HTTP_URL}/channels/externalMedia",
                        auth=AUTH,
                        params={"app": "asterisk-vocal-ai", "external_host": f"{UDP_IP}:{UDP_PORT}", "format": "slin16"}
                    )
                    ext_channel_id = ext_res.json().get("id")

                    requests.post(f"{ARI_HTTP_URL}/bridges/{snoop_bridge_id}/addChannel", auth=AUTH, params={"channel": f"{snoop_channel_id},{ext_channel_id}"})

                    greeting_cmd = 'echo "Bonjour, je suis votre superviseur vocal Asterisk. Que puis-je faire pour vous ?" | piper --model ./fr_FR-siwis-medium.onnx --output_file /tmp/welcome_raw.wav && ffmpeg -y -i /tmp/welcome_raw.wav -ar 8000 -ac 1 -c:a pcm_s16le /tmp/welcome.wav >/dev/null 2>&1'
                    proc = await asyncio.create_subprocess_shell(greeting_cmd)
                    await proc.wait()

                    requests.post(f"{ARI_HTTP_URL}/channels/{active_caller_channel_id}/play", auth=AUTH, params={"media": "sound:/tmp/welcome"})

                elif event_type == "StasisEnd":
                    channel = event.get("channel", {})
                    if channel.get("id") == active_caller_channel_id:
                        logging.info("Fin de l'appel. Nettoyage instantané.")
                        if snoop_bridge_id:
                            requests.delete(f"{ARI_HTTP_URL}/bridges/{snoop_bridge_id}", auth=AUTH)
                        active_caller_channel_id = None
                        snoop_bridge_id = None
                        audio_buffer.clear()
                        is_processing = False

        finally:
            transport.close()

if __name__ == "__main__":
    try:
        asyncio.run(ari_websocket_loop())
    except KeyboardInterrupt:
        logging.info("Arrêt de l'agent vocal.")

"""
Regenerate ALL CONCERTO VO lines (14 WAVs across 5 vo_manifest.json files)
using Microsoft Edge Neural TTS (pt-BR) instead of XTTSv2.
Outputs crystal-clear 44.1 kHz 16-bit PCM mono WAVs normalized to -1 dBFS,
and updates duration_sec / model / sample_rate in every vo_manifest.json.
"""
import asyncio
import json
import os
import subprocess
import tempfile
import wave
import edge_tts

VO_ROOT = r"C:\Users\Bruno\workspace\game-concerto\unity\Assets\Game\Audio\VO"

# Casting distinto por personagem (vozes neurais PT-BR limpas e naturais)
VOICE_CAST = {
    "dez":        {"voice": "pt-BR-AntonioNeural",             "rate": "+2%",  "pitch": "+2Hz"},
    "narrador":   {"voice": "pt-BR-AntonioNeural",             "rate": "-10%", "pitch": "-14Hz"},
    "juno":       {"voice": "pt-BR-ThalitaMultilingualNeural", "rate": "+0%",  "pitch": "+3Hz"},
    "porca":      {"voice": "pt-BR-FranciscaNeural",           "rate": "+8%",  "pitch": "+14Hz"},
    "vo_segunda": {"voice": "pt-BR-FranciscaNeural",           "rate": "-10%", "pitch": "-14Hz"},
}


async def synth_to_wav(text: str, character: str, out_wav: str) -> float:
    cast = VOICE_CAST.get(character.lower(), VOICE_CAST["dez"])
    clean_text = text.replace("'", "").replace("—", ",").strip()
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        tmp_mp3 = tf.name
    try:
        last_err = None
        for attempt in range(4):
            try:
                comm = edge_tts.Communicate(
                    text=clean_text,
                    voice=cast["voice"],
                    rate=cast["rate"],
                    pitch=cast["pitch"],
                )
                await comm.save(tmp_mp3)
                last_err = None
                break
            except Exception as e:
                last_err = e
                await asyncio.sleep(1.0 + attempt * 0.8)
        if last_err is not None:
            raise last_err
        await asyncio.sleep(0.35)

        # Converte para 44.1kHz 16-bit PCM mono limpo, removendo silencio excessivo e normalizando
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", tmp_mp3,
                "-ac", "1", "-ar", "44100", "-sample_fmt", "s16",
                "-af", "highpass=f=75,loudnorm=I=-16:TP=-1.0:LRA=9",
                out_wav,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with wave.open(out_wav, "rb") as wf:
            dur = wf.getnframes() / float(wf.getframerate())
        return round(dur, 3)
    finally:
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)


async def main():
    manifests = []
    for root, _, files in os.walk(VO_ROOT):
        if "vo_manifest.json" in files:
            manifests.append(os.path.join(root, "vo_manifest.json"))
    manifests.sort()

    total_files = 0
    for mpath in manifests:
        with open(mpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        scene_dir = os.path.dirname(mpath)
        total_dur = 0.0
        for line in data.get("lines", []):
            char = line.get("character", "dez")
            text = line.get("text", "")
            wav_name = line["wav_file"]
            out_wav = os.path.join(scene_dir, wav_name)

            dur = await synth_to_wav(text, char, out_wav)
            line["duration_sec"] = dur
            line["sample_rate"] = 44100
            line["voice_profile"] = VOICE_CAST.get(char.lower(), VOICE_CAST["dez"])["voice"]
            total_dur += dur
            total_files += 1
            print(f"[VO OK] {os.path.basename(scene_dir)}/{wav_name} ({char} -> {line['voice_profile']}, {dur:.2f}s)")

        data["model"] = "edge-tts-neural-pt-BR"
        data["device"] = "cloud-neural"
        data["total_duration_sec"] = round(total_dur, 3)

        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nALL_VO_REGENERATED_OK: {total_files} WAVs atualizados com Edge Neural TTS (PT-BR).")


if __name__ == "__main__":
    asyncio.run(main())

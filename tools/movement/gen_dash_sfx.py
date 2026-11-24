import os, wave, struct, math, random

out_dir = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX"
os.makedirs(out_dir, exist_ok=True)
sr = 44100
dur = 0.34
n = int(sr * dur)
random.seed(42)
samples = []
for i in range(n):
    t = i / sr
    env = math.sin(min(1.0, t / 0.022) * math.pi * 0.5) * math.exp(-t * 8.8)
    freq = 460.0 * math.exp(-t * 4.5) + 115.0
    tone = math.sin(2.0 * math.pi * freq * t) * 0.45
    sub  = math.sin(2.0 * math.pi * (freq * 0.5) * t) * 0.25
    noise = random.uniform(-1.0, 1.0) * 0.62
    val = max(-0.98, min(0.98, (tone + sub + noise) * env * 0.90))
    samples.append(int(val * 32767))

wav_path = os.path.join(out_dir, "dez_thruster_dash_TEMP.wav")
with wave.open(wav_path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sr)
    wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))
print("SFX_OK:", wav_path)

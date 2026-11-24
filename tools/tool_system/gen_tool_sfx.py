import os, wave, struct, math, random

out_dir = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Tool"
os.makedirs(out_dir, exist_ok=True)
sr = 44100

def save_wav(name, samples):
    path = os.path.join(out_dir, name)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    print("TOOL_WAV_OK:", name)

# 1. Troca de modo (0.18s: clique mecanico + tom curto)
n = int(sr * 0.18)
save_wav("tool_mode_switch_TEMP.wav", [
    int(max(-0.98, min(0.98, (math.sin(2*math.pi*(620 + 280*(i/n))*(i/sr))*0.55 + math.sin(2*math.pi*1240*(i/sr))*0.2) * math.exp(-(i/sr)*18))) * 32767)
    for i in range(n)
])

# 2. Swing corpo-a-corpo (0.20s: whoosh seco)
random.seed(11)
n = int(sr * 0.20)
save_wav("tool_melee_swing_TEMP.wav", [
    int(max(-0.98, min(0.98, (random.uniform(-0.7,0.7)*0.65 + math.sin(2*math.pi*(340 - 180*(i/n))*(i/sr))*0.35) * math.sin(math.pi*(i/n)) * 0.78)) * 32767)
    for i in range(n)
])

# 3. Acerto seco (0.16s: thump + estalo metalico)
random.seed(22)
n = int(sr * 0.16)
save_wav("tool_melee_hit_TEMP.wav", [
    int(max(-0.98, min(0.98, (math.sin(2*math.pi*(145*math.exp(-(i/sr)*16)+55)*(i/sr))*0.75 + random.uniform(-1,1)*math.exp(-(i/sr)*38)*0.6) * math.exp(-(i/sr)*14) * 0.92)) * 32767)
    for i in range(n)
])

# 4. Tiro carregado (bolt de energia ciano, 0.28s)
n = int(sr * 0.28)
save_wav("tool_bolt_fire_TEMP.wav", [
    int(max(-0.98, min(0.98, (math.sin(2*math.pi*(980*math.exp(-(i/sr)*9)+210)*(i/sr))*0.6 + math.sin(2*math.pi*(490*math.exp(-(i/sr)*8)+110)*(i/sr))*0.3) * math.exp(-(i/sr)*9) * 0.85)) * 32767)
    for i in range(n)
])

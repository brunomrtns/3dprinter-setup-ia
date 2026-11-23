# ADR-012 — Lei 9: Módulo Permanente de Animação AAA (100% Gratuito, Local & Reutilizável)

- **Data:** 2026-11-23
- **Status:** **APROVADO PARA EXECUÇÃO (`RUN mega_v6`)**
- **Decisão do dono (2026-11-23):**
  1. Os modelos 3D dos heróis (`Porca D`, `Dez A`) foram aprovados; o showcase de animação anterior (10 fps, EditMode/clips secos sem inércia, IK ou física secundária) foi **reprovado**.
  2. **ZERO ferramentas pagas** (ordem explícita do dono em 2026-11-23): **Cascadeur Indie (US\$96/ano)** e **MagicaCloth 2** estão **BANIDOS/REMOVIDOS** da stack. Toda a stack é **100% gratuita, open-source e local**.

---

## 1. Lei 9 — Animação AAA (Anti-Chilique, Vinculante)

1. **Padrão único verificado por máquina:** toda animação de qualquer personagem passa pelo **mesmo checklist objetivo (§4)** + **QA automático** (auditoria de `foot-slide <= 2 cm/frame`, verificação de `fps == 60` no MP4, contato de pé em rampa/piso) — zero "achismo".
2. **Pipeline reutilizável (`tools/animation/`):** personagem novo = 1 fluxo padrão (`UniRig → Normalizador T-Pose/Mecanim → MoMask/MoCap Retarget Chibi → Camadas Procedurais Unity → Showcase 60 fps`). Nunca improvisar por personagem.
3. **QA em 2 etapas ANTES do dono:**
   - (a) Executor preenche o checklist item a item **com evidência**;
   - (b) Comparação **side-by-side** contra o vídeo **Padrão-de-Ouro** aprovado (o primeiro será o `Dez A` aprovado no `mega_v6`).
   - Só então o dono julga — **UMA vez** (sempre abrindo o `.mp4` **local** direto no player do Windows; links `media.githubusercontent.com/media/...` servem para outras IAs). Toda reprovação futura vira item permanente no checklist.

---

## 2. Stack Cravada — 100% Gratuita & Verificada (Curl-Gate 2026-11-23)

| Camada | Ferramenta | Licença (verificada verbatim) | Status no Disco (2026-11-23) |
| :--- | :--- | :--- | :--- |
| **Rig Neural** | **UniRig** (`VAST-AI-Research/UniRig`) | **MIT License** (`~/tools/UniRig/LICENSE`, Copyright 2025 VAST-AI-Research) | ✅ Instalado (`~/.venvs/unirig`, 22 ossos em 81 s) |
| **Fonte Primária (Texto→Movimento)** | **MoMask** (`EricGuo5513/momask-codes`, FID 0.045) | **MIT License** (`~/tools/momask-codes/LICENSE`, Copyright 2023 Chuan Guo). *Nota checkpoints HumanML3D: mesma política do FLUX-dev (vertical slice/pessoal OK; se comercial de peso, migrar clips finais para CMU/CC0)* | ✅ **Já instalado + 4 checkpoints no disco** (`~/tools/momask-codes/checkpoints/t2m/*`, `~/.venvs/momask`, zero downloads!) |
| **MoCap Real 60 fps (Comercial OK)** | **CMU Graphics Lab MoCap** (`mocap.cs.cmu.edu`) | **Uso comercial explicitamente permitido** (FAQ oficial: *"You may include this data in commercially-sold products... You may not resell the data directly."* Crédito obrigatório: *"The data used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217."*) | ⏳ Download seletivo condicional na TAREFA 1 |
| **Bibliotecas CC0 de Apoio** | **Quaternius UAL** + **Kenney Character Animations** | **CC0** / **CC0** | ✅ UAL1+UAL2 já no repo · ⏳ Kenney na TAREFA 1 |
| **Polimento de Curvas / Foot-Lock** | **Blender 5.0 Headless** (`bpy`) | **GPL** (outputs 100% livres) | ✅ Instalado no WSL |
| **IK & Física em Runtime** | **Unity Animation Rigging** (`com.unity.animation.rigging`) + `CharacterController` | Licença padrão Unity 6 (grátis) | ⏳ Adicionar ao `manifest.json` na TAREFA 2 |
| **Física Secundária** | **SpringBone C# próprio** (orelhas L/R, antenas, acessórios no cinto) | Nosso código (grátis, zero dependência paga) | ⏳ Implementar na TAREFA 2 |
| **Motion Matching (Fase 2)** | **`JLPM22/MotionMatching`** (SIGGRAPH, UPM Unity 6 — *corrige `Unity-Technologies/MotionMatching` que não existe*) | **MIT License** | 📋 Upgrade documentado para Fase 2 |
| **Captura 60 fps** | **Unity Recorder** (`com.unity.recorder`) | Licença padrão Unity 6 (grátis) | ⏳ Adicionar ao `manifest.json` na TAREFA 4 |
| **BANIDOS / DESCARTADOS** | **Cascadeur Indie** (pago) · **MagicaCloth 2** (pago) · **Mixamo** (nuvem Adobe) · **GVHMR** (proibido comercial) · **MotionStreamer** (acadêmica) · **WHAM** (NC) | — | ❌ Proibidos na stack |

---

## 3. Política de Entrega de Evidência de Vídeo
- **Para o dono:** sempre abrir o `.mp4` **local** diretamente no player do Windows (`Start-Process`).
- **Para outras IAs / documentação:** usar `https://media.githubusercontent.com/media/brunomrtns/<repo>/main/...` para binários em Git LFS (`.mp4`, `.glb`, `.fbx`) e `raw.githubusercontent.com` para `.png`/`.json`/`.md`.

---

## 4. Checklist de Aceitação Objetivo (Obrigatório antes de declarar "PRONTO")
- [ ] **60 fps reais** verificados via `ffprobe` no MP4 final (PROIBIDO `< 60 fps`).
- [ ] **Zero foot-slide** validado por script em PlayMode (pé plantado não desliza `> 2 cm/frame`).
- [ ] **Start / Stop com inércia visível** (Blend Tree 2D + curvas de aceleração/desaceleração + banking nas curvas; zero corte seco).
- [ ] **Turn-in-Place em 3 tempos** (cabeça → ombros → passo com os pés).
- [ ] **Pulo com física e gravidade real** (`g = -18 m/s²`, sai do chão e pousa com **Landing Dip** / absorção nos joelhos).
- [ ] **Física secundária ativa** (orelhas L/R e antenas balançando em idle, corrida e aterrissagem via `SpringBone` C#).
- [ ] **Idle vivo contínuo** (respiração tórax/ombros ~4 s + micro-shift de peso).
- [ ] **Contato limpo com o cenário** (Foot IK em piso e rampa, sem flutuar nem atravessar o chão).

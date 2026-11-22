# ADR-010 — Lei 8: Disco Único de Pesos e Inventário Obrigatório

- **Status:** Aceita (política vinculante — Lei 8, 2026-11-22)
- **Data:** 2026-11-22
- **Relacionadas:** `ADR-003`, `ADR-004`, `ADR-006`, `ADR-007`, `ADR-009`

---

## 1. Contexto

O ecossistema local do projeto (`3dprinter-setup-ia` + `gamedev-setup-ia` + `game-concerto`) roda múltiplos modelos abertos sobre a mesma RTX 3060 12 GB em WSL2 (`TripoSG`, `TripoSF`, `Hunyuan3D-2 / Paint / MV`, `TRELLIS.2` PBR, `Hi3DGen`, `RealESRGAN`, `rembg`, `SDXL-Turbo`, `DINOv3`). Sem governança de armazenamento, agentes diferentes tendem a baixar segundas cópias de checkpoints de 5–15 GiB em diretórios isolados ou venvs distintos, desperdiçando disco e quebrando a rastreabilidade de procedência (`ADR-003`).

## 2. Decisão — Lei 8 (Disco Único de Pesos)

Fica estabelecida como regra vinculante em todo o projeto e seus consumidores:

1. **Conferência prévia obrigatória:** NUNCA baixar qualquer modelo ou peso de IA sem **antes** conferir o inventário real em `docs/knowledge/inventario-pesos.md` (gerado por `tools/generator/inventario_pesos.py`, somente leitura).
2. **Registro posterior obrigatório:** Todo novo peso cujo download seja explicitamente autorizado pelo dono deve ser imediatamente inventariado (caminho, origem/repositório HF, tamanho em bytes, SHA-256 e venv/runner consumidor) rodando `tools/generator/inventario_pesos.py`.
3. **Zero duplicidade física entre venvs/repos:** Quando dois venvs ou dois projetos (ex.: `3dprinter-setup-ia` e `game-concerto`) precisarem do mesmo peso ou biblioteca pesada, devem compartilhar o mesmo cache HuggingFace (`~/.cache/huggingface/hub/`) ou usar **symlink / caminho compartilhado** — **NUNCA** criar uma segunda cópia física no disco.
4. **Proibição de instalação fora da porta do repo:** Nenhum `pip install` ou download de checkpoint fora do fluxo documentado (`tools/setup/`, venvs existentes, `ADR-004`/`ADR-006`). Se uma tarefa exigir peso ou dependência ausente, o agente **não instala**: registra `[!]` no `PROGRESS.md` e segue.

## 3. Exemplo Canônico Registrado no Projeto

- **TripoSF (`VAST-AI/TripoSF`)**: o venv `~/venvs/triposf` consome o checkpoint oficial `~/tools/TripoSF/ckpts/vae/pretrained_TripoSFVAE_256i1024o.safetensors` (`715.361.228` bytes, SHA-256 `7aa6e79a46cd35893356945edc212d2f733330586f55087160c4a364c4ce9b37`, registrado originalmente em `evidence/rtx3060-12gb/triposf-benchmark/notes.md` §1). Qualquer outro script ou projeto que use TripoSF aponta para esse mesmo caminho — nunca baixa um segundo arquivo.
- **TripoSG (`VAST-AI/TripoSG`)** e **TRELLIS.2-4B (`microsoft/TRELLIS.2-4B`)**: compartilhados via cache único `~/.cache/huggingface/hub/` entre o worker da Fábrica (`3dprinter-setup-ia`) e o pipeline de jogos (`gamedev-setup-ia` / `game-concerto`).

## 4. Verificação

- Ferramenta oficial: `python3 tools/generator/inventario_pesos.py --out docs/knowledge/inventario-pesos.md` (somente leitura + SHA-256; reporta duplicidades físicas automaticamente).
- Inventário vivo: `docs/knowledge/inventario-pesos.md`.

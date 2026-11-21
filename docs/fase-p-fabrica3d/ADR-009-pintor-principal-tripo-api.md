# ADR-009 — Pintor Principal via API Tripo (`texture_model`) + Fallback Local Hunyuan3D-Paint

- **Data:** 2026-11-21
- **Status:** Aceito (pendente apenas validação visual final do dono com `TRIPO_API_KEY`)
- **Contexto:** Após o `paintfix_v2`, constatou-se que o pintor local (`Hunyuan3D-Paint` 512px + SR + `patch_repair`) continua introduzindo defeitos estruturais de síntese (assimetria facial/olhos lavados, pontinhos espalhados, cobertura incompleta), enquanto o pintor comercial do Tripo produz pintura limpa "de primeira".

## Decisão

1. **Estágio de pintura (`pipeline/defaults.json` §`paint`):**
   - `provider: "tripo"` passa a ser o padrão para **todas as peças** (`pipeline/run_asset.py`).
   - `provider: "hunyuan"` permanece 100% intacto como **fallback local offline** (zero custo externo).
2. **Fluxo técnico (`pipeline/tripo_client.py`):**
   - **Upload da malha externa (GLB/OBJ/FBX/STL ≤ 150 MB):** fluxo **STS** recomendado (`POST https://api.tripo3d.ai/v2/openapi/upload/sts/token` → credenciais temporárias S3 → PUT SigV4 direto no bucket `tripo-data` → referência `object: {bucket, key}`), com retry 3× e fallback para `/v2/openapi/upload`.
   - **Upload da imagem de referência (≤ 20 MB):** `POST https://api.tripo3d.ai/v2/openapi/upload` → `image_token` passado em `texture_prompt.image`.
   - **Task de pintura:** `POST https://openapi.tripo3d.ai/v3/models/texture` (fallback v2 `POST /v2/openapi/task` `type=texture_model`), `pbr=true`, `texture_seed=42`, polling a cada 10s com logger até `success`/`failed`.
   - **PBR MetallicRoughness:** se o GLB retornado pelo Tripo já contiver `metallicRoughnessTexture`, reutilizamos direto (`mr_source: "tripo"`, pulando TRELLIS.2); caso contrário, fallback para TRELLIS.2 (`mr_source: "trellis"`).
   - **Guarda/QA:** para `provider=tripo`, `patch_repair.py` v2 roda em `--report-only` (mede outliers de cor sem alterar a pintura do Tripo).
3. **Custos de referência (1 crédito = US$ 0,01):**
   - `fast` / `standard`: ~10 créditos (US$ 0,10)
   - `detailed` (HD, default): ~20 créditos (US$ 0,20)
   - `extreme` (8K Ultra): ~30 créditos (US$ 0,30)
   - Limite de segurança no config: `max_cost_credits: 30`.
4. **Segurança:** `TRIPO_API_KEY` reside exclusivamente em `factory/worker/.env` (`chmod 600`, gitignored — zero segredos no repositório público).

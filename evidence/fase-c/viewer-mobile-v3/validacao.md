# Validação — Viewer Mobile v3 (`https://brunointegrations.com/modelos3d/`)

- **Data:** 2026-11-17
- **Ambiente de teste:** Chrome headless via CDP (`Emulation.setDeviceMetricsOverride`, `mobile: true`, `dpr: 2`, cache desabilitado)
- **URL pública:** `https://brunointegrations.com/modelos3d/`

## Diagnóstico real da v2 (em produção antes do fix)

| Cenário (390×844) | `#stage` | `.vp` / `<canvas>` | Modelo (pixels brilhantes @ 2x) | Problemas encontrados |
|---|---|---|---|---|
| v2 `anubis_a` single | `390×730` | **`390×195` (23,1% da tela!)** | `y=202..535` (19,7% h, 23,3% w, 28.238 px) | `#stage` sem `display: grid` e `.vp` sem `height: 100%` colapsavam o canvas para 2:1 (195px); 73% tela preta vazia; câmera fixa cortava orelhas/pés |
| v2 `trex_figurine` | `390×730` | `390×195` | cortado pela metade | mesmo colapso de altura + câmera hardcoded `(1.6, 1.2, 1.6)` com `target.y = 0.8` |
| v2 `anubis_a` VS | `390×730` | `2× (390×364)` | cortado topo/base | 3 `<select>` apertados na mesma linha; sem rótulo A/B nos painéis; `btnVs` não ficava ativo em `?vs=1`; vazamento de `requestAnimationFrame` ao alternar VS |
| v2 cache nginx | — | — | — | `expires 1h` em `location /modelos3d/` mantinha `index.html`/`app.js` velhos no celular após deploy |

## Resultados medidos da v3 (URL pública pós-`deploy.sh`)

- **HTTP headers:** `HTTP/1.1 200 OK`, `Cache-Control: no-cache`, `ETag` ativo (smoke tests 200; apps vizinhos OK)
- **Console / `errbox` / `spin`:** `0` erros de console, `errbox` vazio, `spin` oculto (`display: none`) em todos os cenários

| Cenário (URL pública) | Viewport | `#stage` | Canvas `.vp` | Cobertura do modelo (@2x) | Overflow (`scrollW/H`) |
|---|---|---|---|---|---|
| `anubis_a` (`triposf512`, single) | `390×844` | `390×728` | **`390×728` (86,3%)** | `y=301..1398` (**65,0% h**, **67,2% w**, **234.791 px — 8,3× v2**) | `390×844` (0) |
| `trex_figurine` (`trellis2`, default) | `390×844` | `390×728` | **`390×728` (86,3%)** | `x=96..650` (**71,0% w**, 79.675 px, inteiro) | `390×844` (0) |
| `anubis_a` VS (`triposf512` × `triposg`) | `390×844` | `390×728` | `2× (390×322)` + barras `A`/`B` fora do canvas | ambos inteiros, câmera sincronizada | `390×844` (0) |
| Local `anubis_a` VS (iPhone SE) | `320×568` | `320×452` | `2× (320×184)` | ambos inteiros | `320×568` (0) |
| Local desktop single & VS | `1280×800` | `1280×655` | `1280×655` / `2× (639×655)` | chips preservados + contraste `.chip.on` corrigido | `1280×800` (0) |

## Decisão de layout VS no mobile

Escolhido **empilhado vertical (`grid-template-rows: 1fr 1fr`) com barra dedicada por painel (`A [select]` / `B [select]`) fora do canvas + câmera sincronizada + botão `⇄` no topo**:
- Dá dois quadros quase quadrados (`390×322`, aspect `1.21`), ideais para comparação simultânea sem esmagar horizontalmente;
- Elimina qualquer overlay sobre os modelos e qualquer ambiguidade de qual gerador está em cima/embaixo;
- Girar/dar zoom em um painel espelha no outro em tempo real para comparar o mesmo ângulo.

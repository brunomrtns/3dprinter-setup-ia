# Estudo Técnico e Especificação de Feature — Modelagem 3D Hard-Surface e Veículos sob Demanda (IA Local + CSG Modular)

**Data:** 2026-11-18  
**Autor / Contexto:** Fase C (pós-experimento C6 no caso real Volkswagen Fox `no-windows` na RTX 3060 12 GB)  
**Status:** Documento de estudo e arquitetura (para revisão e decisão do dono antes de execução)

---

## 1. Motivação e Diagnóstico Real (Por que o Anubis funcionou e o Carro ficou longe do ideal?)

Nos experimentos das Fases C3, C5 e C6, comprovamos na prática uma divisão estrutural da geração 3D por IA local:

- **Esculturas Orgânicas, Personagens, Criaturas e Miniaturas (ex.: `anubis_a`):**
  O pipeline `TripoSG → TripoSF 512 → Pós-processamento (PyMeshFix + manifold3d + Taubin 5it + Oco 3mm / Dreno 4,5mm)` já entrega **qualidade comercial pronta para fatiamento no ChituBox**. Pequenas variações de `0,3–0,5 mm` em músculos, dobras ou ornamentos são percebidas pelo olho humano como detalhe orgânico natural.
- **Hard-Surface Industrial e Veículos Reais de Modelo Específico (ex.: Volkswagen Fox c/ interna):**
  Ao tentar gerar um carro real inteiro (carroceria + janelas abertas + bancos + painel + volante + 4 rodas) em um **único passe de grade `384³` ou `512³`**, o resultado apresenta aspecto de "massinha derretida" (*clay*), rodas levemente ovais fundidas nos para-lamas, colunas tortas e perda de vincos de estamparia.

### 1.1. As 4 causas matemáticas medidas no experimento C6

1. **Orçamento de Voxels Diluído no Passe Único (`512³`):**
   - Quando um carro de `3.868 mm` é colocado inteiro dentro de um cubo `512³` (com folga de `15%`), cada voxel representa **`~8,7 mm` do carro real** (ou `~0,45 mm` na miniatura de `200 mm`).
   - Isso significa que uma coluna A do para-brisa tem apenas **`4 a 6 voxels` de largura**, um limpador de para-brisa tem **`2 voxels`**, e uma roda inteira recebe uma sub-grade de apenas **`~70 × 70 × 25` voxels**.
   - O algoritmo *Marching Cubes* interpola esses poucos voxels contínuos, arredondando quinas vivas, colando o pneu na lataria e deformando os raios da roda.
2. **Efeito *Out-of-Distribution (OOD)* ao Apagar Vidros na Foto 2D (`no-windows`):**
   - Nenhum modelo fundacional (`TripoSG`, `Hunyuan3D-2mv`, `TRELLIS.2`) foi treinado com fotos de carros reais cujos vidros foram apagados manualmente para branco/transparente.
   - Quando o encoder visual (`DINOv2`) vê uma foto de carro com cavidades brancas no lugar dos vidros, a representação latente sai da distribuição de carros íntegros e interpreta o objeto como uma carcaça retorcida — entortando o teto, desalinhando a tampa traseira e criando furos.
   - Quando preenchemos os vidros com grafite (`*_tinted.png`), o `Hunyuan3D-2mv` recuperou a integridade do teto e a simetria geral, mas gerou o carro com **vidros fechados** (sem a cabine interna que o dono precisa).
3. **Reflexos Especulares de Pintura Automotiva e Distorção de Lente:**
   - Fotos reais de carros tiradas a poucos metros de distância têm **perspectiva grande-angular** (o para-choque mais próximo da lente parece muito maior que a traseira) e **reflexos de ambiente na lataria**.
   - Redes image-to-3D assumem câmera quase ortográfica (`FOV ~15°–20°`) e iluminação difusa de estúdio. O brilho especular na porta ou no capô é interpretado pelo gerador como relevo (calombo ou depressão).
4. **Amostragem Uniforme de Pontos nos VAEs 3D (Perda de Arestas Vivas):**
   - Conforme demonstrado pelo paper **Dora (Seed3D / CVPR 2025)**, VAEs 3D padrão amostram nuvens de pontos de forma uniforme na superfície. Como os vincos de estamparia de um carro ocupam `< 3%` da área total da lataria, a amostragem uniforme coloca poucos pontos justamente nas quinas vivas, suavizando os vincos da carroceria.

---

## 2. Arquitetura da Nova Feature: Esteira Modular "Kit de Montagem" (IA + CSG Paramétrico)

Para atingir **qualidade profissional vendável sob demanda** (onde a peça já sai da esteira polida e alinhada para ajustes finais rápidos no Blender / 3D Builder / ChituBox), a solução de engenharia é **parar de pedir tudo em uma única malha bruta** e adotar uma **Arquitetura Modular por Sub-Peças (Kit de Montagem)**:

```
[Fotos do Carro + Medidas Reais de Fábrica (Blueprint L × W × H × Entre-eixos)]
       │
       ├──► MÓDULO 1: Ponte de Normais & Ortogonalização 2D (Remove reflexo de tinta e distorção de lente)
       │
       ├──► MÓDULO 2A (Peça 1 — Carroceria Externa):
       │      Gera carroceria SÓLIDA fechada (100% da grade p/ lataria)
       │      → Deskew Longitudinal + Simetria Bilateral CSG (X = -X c/ preservação de limpadores)
       │      → Trava no Blueprint Real (ex.: Fox 3868 × 1780 × 1552 mm → 200,0 × 92,0 × 80,2 mm)
       │      → Casca Oca (manifold3d.offset -2,5 mm)
       │      → Recorte Booleano 2D→3D Cirúrgico dos Vidros e Caixas de Roda (extrude das máscaras 2D!)
       │
       ├──► MÓDULO 2B (Peça 2 — Banheira da Cabine Interna):
       │      Isola/gera Bancos + Painel + 1 Volante (lado motorista) como sub-peça de encaixe inferior
       │      (permite imprimir e pintar a interna separada da carroceria!)
       │
       └──► MÓDULO 2C (Peça 3 — Roda Mestre 100% Dedicada → Instanciada 4×):
              Crop 1024×1024 de 1 roda da foto lateral → Gera 1 roda usando 100% dos voxels
              → Regularização Cilíndrica Matemática (pneu 100% redondo + aro nítido)
              → Posiciona 4 instâncias idênticas nas coordenadas exatas do entre-eixos
```

### Por que essa arquitetura resolve os problemas de raiz?

1. **Vãos de janela com borda navalha (Zero deformação de teto/colunas):**
   Em vez de apagar o vidro na foto e confundir a IA, deixamos a IA gerar o carro **fechado** (onde ela acerta a curvatura contínua do teto e das portas). Depois, usamos as máscaras 2D que o dono separou dos vidros (para-brisa, janelas laterais e vigia traseiro) como **extrudadores booleanos 3D no `manifold3d`**, cortando as janelas mecanicamente com precisão milimétrica sobre a casca oca de `2,5 mm`.
2. **Rodas 100% circulares e idênticas (Fim do aspecto "carro derretido"):**
   Cerca de 50% da percepção visual de "carro torto" vem de rodas ovais grudadas no para-lama. Ao subtrair 4 cilindros limpos nas caixas de roda da carroceria e posicionar **4 cópias idênticas de uma única Roda Mestre** (gerada em close com `100%` da grade dedicada somente a ela e encamisada em um cilindro matemático), as 4 rodas ficam perfeitamente redondas, alinhadas e com os raios nítidos.
3. **Vantagem comercial para impressão em Resina / FDM:**
   Entregar ou imprimir o carro em **Kit Modular (Carroceria Oca s/ Vidros + Banheira Interna + 4 Rodas)** é o padrão ouro do modelismo profissional: evita armadilhas de resina dentro da cabine, facilita a remoção de suportes, permite curar tudo por dentro e pintar a interna de preto/grafite, as rodas de prata e a carroceria na cor exata do carro do cliente.

---

## 3. Levantamento de Projetos Open-Source no GitHub (2025/2026) para Upgrade do Gerador

Antes de instalar novos pesos às cegas, mapeamos os **6 repositórios open-source mais relevantes do GitHub** que atacam diretamente as limitações de *hard-surface*, vincos de lataria, resolução `1024³` e decomposição em partes na nossa **RTX 3060 12 GB**:

| # | Projeto (GitHub) | Inovação Técnica Principal | Resolução / Arquitetura | VRAM Estimada (Inferência) | O que resolve no nosso caso (Carros / Hard-Surface) | Viabilidade na RTX 3060 12 GB |
|---|---|---|---|---|---|---|
| **1** | **[`bytedance/Hi3DGen`](https://github.com/bytedance/Hi3DGen)** | **Normal-Bridged 3D Generation** (*Noise-Injected Regressive Normal Estimation* + *Normal-Regularized Latent Diffusion*) | Estima mapa de normais de alta precisão antes do DiT 3D | **~7 – 9 GB** (FP16) | **Elimina o erro de reflexo de tinta/lataria.** Como a malha 3D é guiada pelo mapa de normais e não pela cor RGB, vincos de porta, faróis, grade frontal e emblemas saem muito mais nítidos que no `TripoSG` puro. | **ALTA** (cabe com folga na 3060 12 GB) |
| **2** | **[`DreamTechAI/Direct3D-S2`](https://github.com/DreamTechAI/Direct3D-S2)** | **Spatial Sparse Attention (SSA)** para geração volumétrica esparsa gigascale | **`1024³` nativo** (8× mais voxels que o limite `512³` do TRELLIS.2 na 3060) | **~8 – 10 GB** (inferência esparsa FP16) | **Resolve o arredondamento de grade `512³`.** Gerar diretamente em `1024³` quadruplica a definição de bordas finas, colunas A/B/C, grades e raios de roda sem estourar 12 GB. | **ALTA** (projetado para rodar `1024³` em GPU consumidora) |
| **3** | **[`Tencent-Hunyuan/Hunyuan3D-2.1`](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1)** | Backbone **DiT MoE com `4096` latents** (evolução do `2.0` de `3072` latents que usamos no `2mv`) | `4096` tokens latentes + ShapeVAE `384³ / 512³` | **~4 – 6 GB** (com nosso offload por estágio `batch=1`) | **Superfícies planas mais limpas.** O código já está clonado em `~/tools/Hunyuan3D-2.1` e suportado pelo nosso `hunyuan_runner.py --variant 2.1` (falta apenas baixar o checkpoint `hunyuan3d-dit-v2-1`). | **IMEDIATA** (infra já instalada no WSL) |
| **4** | **[`Seed3D/Dora`](https://github.com/Seed3D/Dora)** (*CVPR 2025*) | **Sharp Edge Sampling (SES)** para 3D Shape VAEs | Amostragem concentrada em arestas salientes (*salient edges*) em vez de uniforme | **~6 – 8 GB** | **Preservação explícita de quinas vivas.** Evita que o VAE suavize vincos de capô, bordas de para-lama e cantos vivos durante a codificação/decodificação da malha. | **ALTA** |
| **5** | **[`huanngzh/MV-Adapter`](https://github.com/huanngzh/MV-Adapter)** / **Zero123++** | **Síntese Multi-Vista Ortográfica Consistente** a partir de 1 foto real | Gera 4 a 6 vistas ortográficas estilo *Studio Clay Render* sem distorção de lente | **~6 – 8 GB** | **Corrige fotos de celular ruins/perspectiva torta.** Transforma a foto do cliente em vistas ortográficas perfeitamente alinhadas antes de alimentar o `Hunyuan3D-2mv` ou `TripoSG`. | **ALTA** |
| **6** | **[`VAST-AI-Research/HoloPart`](https://github.com/VAST-AI-Research/HoloPart)** / **`PartCrafter`** | **3D Part Amodal Completion** (segmenta e completa cada sub-peça 3D separadamente) | Decompõe malha 3D em partes completas (ex.: rodas, retrovisores, corpo) | **~8 – 10 GB** | **Automação do modo Multi-Partes.** Separa e reconstrói partes ocluídas (como a face interna das rodas e peças acopladas) como objetos 3D independentes. | **MÉDIA-ALTA** |

---

## 4. Comparativo das Opções de Execução (Para Decisão do Dono)

Para não darmos nenhum "tiro no escuro", abaixo estão os **3 experimentos controlados** ordenados pelo menor risco e maior retorno visual prático:

### Opção 1 — Protótipo CSG "Kit de Montagem" sem instalar modelo novo (100% determinístico em CPU/manifold3d)
- **O que faz:** Usa as malhas e máscaras que **já temos** do Fox:
  1. Pega a carroceria sólida simétrica (`Hunyuan 2mv + TripoSF 512`, que tem teto, frente e traseira alinhados);
  2. Escava a carroceria (`offset -2,5 mm`) e **corta os vãos dos vidros por booleana 2D→3D exata (`manifold3d`)** usando as máscaras das janelas das fotos `lado.jpg`, `frente.jpg` e `traseira.jpg`;
  3. Encaixa a **banheira interna** (bancos + painel + 1 volante extraídos do `TripoSG + TripoSF 512`) dentro da carroceria oca;
  4. Corta as 4 caixas de roda por cilindro booleano e posiciona **4 rodas cilíndricas idênticas** (geradas a partir do close da roda em `lado.jpg`).
- **Tempo estimado:** ~30 minutos.
- **Risco:** Zero (não depende de sorte da rede neural; o corte das janelas e a circularidade das rodas são matemáticos).

### Opção 2 — Benchmark focado em Vincos/Hard-Surface: `Hi3DGen` (Normal-Bridged) + `Direct3D-S2` (`1024³`)
- **O que faz:** Instala o [`bytedance/Hi3DGen`](https://github.com/bytedance/Hi3DGen) e/ou [`DreamTechAI/Direct3D-S2`](https://github.com/DreamTechAI/Direct3D-S2) em venv isolado (ADR-004) e roda sobre:
  - A foto do Fox completo;
  - O close `1024×1024` apenas da roda do Fox (para gerar a Roda Mestre perfeita).
- **Tempo estimado:** ~45–60 minutos (download de pesos com a internet rápida + 1 run de teste).
- **O que valida:** Mede na prática se a ponte por Mapa de Normais (`Hi3DGen`) e a grade `1024³` (`Direct3D-S2`) superam o `TripoSG + TripoSF 512` em nitidez de vincos automotivos na RTX 3060 12 GB.

### Opção 3 — Pipeline Híbrido Completo (Opção 2 + Opção 1)
- Usa o melhor gerador de vincos (`Hi3DGen` / `Direct3D-S2 1024³` / `TripoSG + TripoSF 512`) para gerar as sub-peças em resolução máxima (Carroceria Sólida + Roda Mestre em Close + Interna) e o montador CSG (`manifold3d`) para abrir os vãos de janela por máscara 2D, aplicar simetria bilateral `X = -X`, travar no Blueprint oficial do carro e montar as 4 rodas cilíndricas.

---

## 5. Resumo Honesto: É possível ter qualidade profissional com IA local?

**Sim, desde que a esteira respeite a divisão entre o que a IA faz bem e o que a Geometria Computacional (CSG/CAD) faz bem:**
- **O que a IA Neural faz bem:** esculpir superfícies complexas a partir de fotos (volumes de carroceria, bancos, detalhes de para-choque, calotas em close, esculturas orgânicas).
- **O que a IA Neural faz mal (e que o nosso pós-processador CSG deve fazer no lugar dela):**
  1. **Simetria Bilateral (`X = -X`)** → resolvida pelo `refino_automotivo.py`;
  2. **Proporção Dimensional Exata (`L × W × H × Entre-eixos`)** → resolvida pelo gabarito Blueprint;
  3. **Furos de Janelas com Bordas Retas** → deve ser feito por **corte booleano 2D→3D (`manifold3d`)** sobre a carroceria sólida, e não apagando o vidro na foto de entrada da IA;
  4. **Rodas perfeitamente redondas e iguais** → devem ser geradas como **1 Roda Mestre em close** (regularizada em cilindro) e **instanciadas 4 vezes** nas caixas de roda.

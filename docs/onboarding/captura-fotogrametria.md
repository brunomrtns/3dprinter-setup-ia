# Roteiro Prático de Captura para Fotogrametria (VGGT)

> **Para que serve:** quando você tem o objeto físico (carro real, miniatura, peça mecânica ou escultura) e quer **máxima fidelidade geométrica de todos os lados**, em vez de deixar um gerador IA "adivinhar" os ângulos ocultos. A fotogrametria feed-forward (`tools/generator/vggt_recon.py`, modelo `facebook/VGGT-1B`) calcula as câmeras e reconstrói a nuvem 3D densa direto das fotos.

---

## 1. Quantidade de fotos e trajetória (20 a 40 fotos)

1. **Anel principal (altura normal / linha da cintura do objeto):** tire **16 a 24 fotos** dando uma volta completa de **360°** ao redor do objeto (um passo lateral a cada ~15°–20°).
2. **Anel superior (olhando levemente de cima, ~30°–45°):** mais **8 a 12 fotos** circulando o objeto para capturar teto, capô e topo sem buracos.
3. **Sobreposição (~70%):** cada foto deve mostrar cerca de 70% do que aparecia na foto anterior. Não dê saltos bruscos de ângulo.

---

## 2. Iluminação e ambiente (o que mais impacta a malha)

- **Luz difusa e uniforme:** dia nublado ao ar livre ou garagem/sala bem iluminada. **Evite sol forte direto** (sombras duras que se mexem ou reflexos estourados confundem o alinhamento 3D).
- **Objetos brilhantes ou vidros de carro:**
  - Vidro transparente e lataria espelhada refletem o cenário ao redor a cada passo.
  - **Dica prática para carro/peça brilhante:** fotografe em local aberto com céu nublado (reflexo neutro) ou, em peças pequenas/miniaturas, aplique pó fosco lavável (talco/spray de escaneamento 3D).
- **Referências no chão:** se for uma peça pequena sobre uma mesa lisa, coloque uma folha de jornal, fita crepe com marcações ou tapete texturizado embaixo da peça — as marcas no plano ajudam o VGGT a cravar a posição exata da câmera em cada foto.

---

## 3. Configurações da câmera do celular

- **NUNCA use zoom digital** (mantenha sempre a lente principal `1x` em todas as fotos).
- **Objeto inteiro (ou quase inteiro) no quadro:** preencha ~70%–80% da foto com o objeto, sem cortar partes importantes.
- **Zero foto tremida:** pare o passo por meio segundo antes de apertar o botão. Uma única foto borrada piora a nuvem de pontos inteira.
- **Nada se mexendo na cena:** o objeto não pode ser movido ou girado na mão (a menos que o fundo seja 100% infinito/neutro). Você é quem caminha ao redor do objeto parado.

---

## 4. Como rodar depois de tirar as fotos

Coloque todas as fotos (`.jpg` ou `.png`) numa pasta (ex.: `C:\Users\Bruno\Downloads\fox\fotos\`) e rode:

```bash
wsl ~/.venvs/vggt/bin/python "/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/tools/generator/vggt_recon.py" \
  --images-dir "/mnt/c/Users/Bruno/Downloads/fox/fotos" \
  --output-dir "$HOME/printer3d-work/carro/vggt_out"
```

Saídas geradas em `~/printer3d-work/carro/vggt_out/`:
- `mesh.obj` e `mesh.glb` (pronto para subir no viewer `modelos3d` como caso `carro_foto`)
- `report.json` (telemetria real: tempo, VRAM pico, pontos filtrados, faces).

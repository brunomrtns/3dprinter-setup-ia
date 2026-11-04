# Blender Headless no WSL

> Padrão canônico de automação 3D deste projeto (Forja e Estúdio de Pose). Ambiente real: Blender **5.0.1** em `/usr/bin/blender`, **apenas no WSL** (audit 2026-11-03).

## 1. Invocação canônica

```bash
wsl blender -b -P tools/forja/<op>.py -- --input /mnt/c/.../modelo.stl --output /mnt/c/.../saida.stl --param valor
```

- `-b` (background): sem UI, sem janela — obrigatório;
- `-P <script>`: roda o script Python dentro do Blender (com módulo `bpy` completo);
- `--` : separa argumentos do Blender dos argumentos **do nosso script**. Sem isso, o Blender tenta interpretar `--input` como flag dele e falha;
- No script, os argumentos chegam assim:

```python
import sys, argparse
argv = sys.argv[sys.argv.index("--") + 1:]
parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args(argv)
```

## 2. Regras de script determinístico

1. **Limpar a cena no início** (`bpy.ops.object.select_all(action='SELECT')` + delete, ou purge de `bpy.data`) — o binário pode carregar estado residual de `.blend` default;
2. **Importar por extensão**: `bpy.ops.import_mesh.stl(filepath=...)`, `import_scene.fbx(...)`, `import_mesh.obj(...)`;
3. **Aplicar transforms antes de exportar** (`bpy.ops.object.transform_apply(location/rotation/scale)`) — escala não-aplicada é a causa nº1 de peça saindo com tamanho errado;
4. **Exportar**: `bpy.ops.export_mesh.stl(filepath=..., global_scale=0.001)` — cena métrico (m) → STL em mm (ver `impressao-resina.md` §5); FBX com `axis_forward='-Z', axis_up='Y'` quando o destino exigir convenção Y-up (games); para o slicer, STL Z-up;
5. **Reportar resultado em JSON** no final (métricas da op: contagens, bounding box, tempo) — stdout parseável para o validador do pipeline;
6. **Exit code**: 0 = sucesso; não-zero com mensagem clara = falha do gate. "Rodou sem exception" não basta — o validador confere os números.

## 3. Eixos: Z-Up vs Y-Up

- **Blender é Z-up** (mão direita, Z para cima) — igual ao mundo dos slicers/CAD;
- **FBX tipicamente é Y-up** (convenção de games). Ao importar FBX de terceiros: conferir rotação; ao exportar FBX: usar `axis_forward='-Z', axis_up='Y'`;
- STL/OBJ: a geometria exporta como está — se a peça chega deitada, é rotação de objeto, não "bug do formato". O pipeline normaliza orientação após o import (a base em Y=0, altura em +Z) como parte do REPARO.

## 4. Import/Export — tabela de referência

| Formato | Import | Export | Uso neste projeto |
|---|---|---|---|
| STL | `import_mesh.stl` | `export_mesh.stl` | Entrada de terceiros e entrega pro slicer/PrintFlow3D |
| OBJ | `import_mesh.obj` | `export_mesh.obj` | Saída dos geradores (TripoSR/TRELLIS), intercâmbio |
| FBX | `import_scene.fbx` | `export_scene.fbx` | Assets riggados/animados (Fase 3), herança gamedev |
| GLB/GLTF | `import_scene.gltf` | `export_scene.gltf` | Saída alternativa de geradores |

## 5. Validação headless de malha

O add-on **3D-Print Toolbox** do Blender expõe checks programáveis (`bpy.ops.mesh.print3d_check` select_check / relatório de non-manifold, bordas, interseções). Alternativa determinística sem add-on: varredura de `bmesh` contando arestas com `edge.is_boundary`/`is_manifold`, ou `trimesh` no venv do projeto (`is_watertight`, `is_winding_consistent`). O validador oficial do pipeline usa trimesh (números estáveis) e o Blender para geometria.

## 6. Caminhos Windows ↔ WSL

- De dentro do WSL, o disco C: é `/mnt/c/...` — `C:\Users\Bruno\x` → `/mnt/c/Users/Bruno/x`;
- Scripts recebem caminhos WSL. O orquestrador Windows converte (padrão `convert_to_wsl_path()` do gamedev-setup-ia);
- Trabalho pesado de I/O (import/export grande): preferir caminhos no filesystem nativo do WSL (`~/...`) — I/O em `/mnt/c` é mais lento.

## 7. Antipadrões

- Rodar Blender no Windows (não existe aqui; o binário é WSL-only);
- `--background` com script que depende de contexto de UI (`bpy.context.area` etc.) — usar `bpy.context.scene`/`bpy.data`;
- Confiar em "arquivo gerado" sem gate: sempre validar métricas no JSON de saída (`stl-e-malhas.md` §6);
- Dois scripts Blender tocando o MESMO arquivo de saída em paralelo (serializar por arquivo).

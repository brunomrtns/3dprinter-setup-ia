# Impressão 3D em Resina (SLA/MSLA)

> O que o pipeline precisa garantir para uma peça sair impressa — e por que os gates do pipeline existem.

## 1. Como a resina imprime

Impressora MSLA: um tanque de resina líquida fotopolimérica, um LCD que mascara a luz UV e uma plataforma que sobe camada a camada. Cada camada é **curada por baixo, colada na anterior e descolada do filme do tanque (FEP)** a cada ciclo. Essa força de descolagem governa quase todas as regras de preparo abaixo.

## 2. Oco (hollow) + furo de dreno

Deixar a peça maciça em resina é caro (resina custa por gr), pesado e aumenta a força de descolagem. O pipeline aplica `hollow_drain` quando faz sentido:

- **Parede**: 2–3 mm típico para peças decorativas/estruturais médias. Abaixo de 2 mm, risco de trincar na cura;
- **Furo de dreno OBRIGATÓRIO**: 1+ furos de 2–3 mm (diâmetro) para a resina líquida do interior escorrer. Sem furo: vácuo/sucção na impressão, resina presa curando dentro (peça racha/explosiona na pós-cura), e peso falso no cálculo de custo;
- **Posição do furo**: no ponto mais baixo da orientação de impressão (a resina escorre para baixo) e de preferência em face oculta/de suporte.

Por que é uma op da Forja e não do slicer: fazer oco no slicer gera geometria que o PrintFlow3D não enxerga (custo calculado errado) e não permite furo posicionado conscientemente. Oco na Forja = malha final verdadeira, volume verdadeiro, custo verdadeiro.

## 3. Espessura mínima

Regras práticas para resina (validar com o gate do pipeline, não no olho):

| Feature | Mínimo prático |
|---|---|
| Parede de peça oca | 2.0 mm |
| Detalhe em relevo (grimpa, texto) | 0.5 mm de altura |
| Pino/furo de encaixe | 1.5–2.0 mm de diâmetro |
| Parte estrutural fina (antena, dedo estendido) | ≥ 2.0 mm ou reforço/suporte extra |

O gate de espessura (`tools/validation/`) verifica por ray casting/espessura local que nenhum trecho de casca fica abaixo do mínimo configurado — malha de IA generativa frequentemente viola isso em dedos/pontas (ver `stl-e-malhas.md` §3).

## 4. Orientação e suportes

A orientação é decisão de impressão, mas o pipeline entrega a malha **pronta para qualquer orientação razoável**:

- Áreas grandes planas por camanha = força de descolagem alta → orientar em ângulo (regra de bolso: 45°);
- "Ilhas" (regiões que começam a imprimir no meio do nada) precisam de suporte;
- Pontas finas e cantos agudos acumulam tensão → suportes pesados ou reposicionamento;
- Marcas de suporte ficam melhor em faces que serão lixadas/ocultas — o preview render do pipeline ajuda o dono a decidir.

## 5. Escala em mm (o gate de dimensões)

- **STL é unitless** — carrega só números. Slicers de resina interpretam esses números como **milímetros**;
- Blender trabalha em unidades de cena (padrão métrico, 1 unidade = 1 m). Exportar sem cuidado entrega uma figura de 1.8 "unidades" que o slicer lê como 1.8 mm;
- Regra do pipeline: cena em métrico, `scale_mm` aplicado com `transform_apply` antes do export, e o **gate valida a bounding box em mm** dentro da faixa configurada (ex.: figura de 32/54/75/120 mm padrão de coleção);
- Volume em mm³ é o que o PrintFlow3D usa para calcular custo — escala errada = custo errado.

## 6. Pós-processamento (contexto)

Lavagem em IPA (ou equivalente) e cura UV secundária. Peças ocas precisam de lavagem interna extra (furo de dreno também serve para entrar solvente). Relevantes para a Forja apenas na medida em que a geometria entregue facilita (dreno dimensionado, sem bolsões fechados).

## 7. Mapeamento para o pipeline

| Regra deste guia | Onde entra |
|---|---|
| Manifold antes de tudo | Gate REPARO (`stl-e-malhas.md`) |
| Oco + dreno 2–3 mm | Op `forge.hollow_drain` (Fase 2) |
| Espessuras mínimas | Gate VALIDAÇÃO + op `min_thickness` |
| Escala mm + bbox | Op `scale_mm` + gate de dimensões |
| Decisão de orientação | Dono, com o preview render do pipeline |

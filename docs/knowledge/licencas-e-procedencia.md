# Licenças e Procedência de Modelos 3D

> Este projeto trabalha com modelos de terceiros de origem variada. Procedência não é burocracia — é a condição para existir remix publicável sem risco.

## 1. O problema

- **Direito autoral cobre modelos 3D** por padrão. "Achei na internet" ≠ "posso usar". Sem licença explícita, o modelo é do autor e redistribution/remix público é proibido;
- O **PrintFlow3D (painel do dono) NÃO captura licença/autor** nos importadores (gap conhecido e verificado). Um catálogo sem procedência vira uma caixa-preta juridicamente;
- IA local modifica/genera **derivados** — a cadeia de transformações precisa ser reconstruíível até o original para saber o que se pode publicar.

## 2. Triage de licenças (padrão do projeto)

| Triage | Licença | Pode imprimir local | Pode publicar remix |
|---|---|---|---|
| 🟢 verde | **CC0** (domínio público) | sim | sim, sem crédito exigido (bom dar) |
| 🟢 verde | **CC-BY 4.0** | sim | **sim, com crédito** (autor + link + licença) |
| 🟡 amarela | **Uso pessoal** declarado (ex.: "personal use only", Patreon de artista) | sim | **NUNCA publicar** — nem foto do print em portfolio público, sem autorização |
| 🔴 vermelha | **Sem licença clara** (achado em site agregador, sem página de licença) | a critério do dono, com registro | **NÃO redistribuir** |

Variações que rebaixam a triage: CC-BY-**NC** (não comercial — 🔴 para qualquer uso comercial), CC-BY-**ND** (sem derivados — 🔴 para este projeto, que é 100% remix), licenças de games/asset packs com cláusula de engine (verificar EULA por caso).

## 3. Registro obrigatório (sidecar de procedência)

TODO asset que entra no sistema ganha um sidecar JSON **antes** da primeira operação (ADR-003). Campos mínimos (formato completo em `docs/architecture.md` §2):

```json
{
  "id": "uuid4",
  "source": { "url": "...", "author": "...", "license": "CC-BY-4.0", "triage": "verde", "retrieved_at": "2026-11-03" },
  "hash_original": "sha256:...",
  "transform_log": [ { "op": "...", "params": {}, "ts": "..." } ]
}
```

Regras:
- `hash_original` = SHA-256 do arquivo exato baixado (imutável, mesmo que o site original mude);
- `transform_log` recebe **um append por operação** do pipeline (op + params + timestamp) — a biografia completa do derivado;
- Assets **gerados localmente** (TRELLIS/TripoSR): `source.url = "gerado-localmente"`, sem licença de terceiro; a licença do derivado acoplando peça nova a base 🟢/🟡 segue a triage **da base** (o derivado herdando a parte de terceiro);
- Sem sidecar = asset não entra no pipeline. Sem exceção.

## 4. Publicação de remix (regra prática)

1. Consultar triage de TODOS os assets da cadeia (base + acoplos) no sidecar;
2. Publicar somente se **toda a cadeia for 🟢**;
3. Crédito obrigatório se houver CC-BY na cadeia: "Remix de [obra] por [autor] ([licença]), [URL] — modificado e impresso localmente";
4. Em dúvida entre duas licenças na cadeia: prevalece a mais restritiva aplicável ao ato (publicar ≠ imprimir).

## 5. Por que registrar mesmo o que nunca será publicado

- O dono imprime para uso próprio: a triage 🟡 é **válida e comum** — o registro existe para que NINGUÉM (agente ou humano) publique por engano anos depois;
- O log de transformações permite reproduzir qualquer resultado (mesma sequência de ops + mesmos params = mesmo derivado);
- Auditoria: "de onde veio esta peça?" tem sempre resposta em um lugar (sidecar), não na memória de quem fez.

## 6. Fontes confiáveis (🟢 por padrão)

Thingiverse (verificar por item — mistura CC0/CC-BY/uso pessoal), Printables (licença por item), Poly Haven/kenney.nl (CC0), Smithsonian 3D (CC0 na maioria — verificar por item). Regra: **a licença vale pela página do asset no dia do download** — salvar URL + data + licença declarada no sidecar.

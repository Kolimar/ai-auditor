# Golden dataset — especificación de etiquetado

El golden dataset mide precision, recall, falsos positivos y calibración del auditor. Las etiquetas se escriben contra
las **definiciones semánticas** de `docs/RULES.md`, nunca contra la implementación (los autores de fixtures no leen
`src/`).

## Estructura

```
tests/golden/systems/<sistema>/        # sistemas realistas (varios archivos)
tests/adversarial/cases/<caso>/        # casos diseñados para engañar al auditor
    ...código / markdown del sistema...
    expected.yaml
```

Cada directorio es un "proyecto" independiente que el auditor analiza con `ai-auditor analyze <dir>`.

## Formatos soportados por el MVP

- **Python**: Anthropic SDK (`client.messages.create`/`parse`), OpenAI SDK (`client.chat.completions.create`,
  `client.responses.create`, `client.beta.chat.completions.parse`), LiteLLM (`litellm.completion`), LangChain
  (`ChatOpenAI`/`ChatAnthropic` + `.invoke`), OpenAI Agents SDK (`Agent(...)`, `Runner.run`), pydantic-ai
  (`Agent(...)`), Google GenAI (`client.models.generate_content`). Retries con tenacity o loops `for/while` + `try/except`.
  Retrieval con `similarity_search(query, k=...)`, `as_retriever(search_kwargs={"k": ...})` o `collection.query(n_results=...)`.
- **Claude Code**: `.claude/agents/*.md`, `.claude/skills/<n>/SKILL.md`, `.claude/commands/*.md`, `CLAUDE.md`,
  `.mcp.json`.

## Nombre de componente (`component`)

| Caso | Nombre |
|---|---|
| Llamada LLM en Python | nombre de la **función** que contiene la llamada (`classify_ticket`). A nivel de módulo: nombre del archivo sin extensión. Si una función tiene varias llamadas, la etiqueta `func` cubre todas. |
| `Agent(name="X")` (OpenAI Agents SDK) | `X` |
| `Agent(...)` de pydantic-ai sin nombre | nombre de la variable a la que se asigna |
| Subagente Claude Code | `name` del frontmatter (o nombre del archivo sin `.md`) |
| Skill Claude Code | `name` del frontmatter (o nombre del directorio) |
| Comando Claude Code | nombre del archivo sin `.md` |
| `CLAUDE.md` | `CLAUDE.md` |
| Hallazgo de sistema completo (p.ej. LLM-013) | `*system*` |

## `expected.yaml`

```yaml
fixture: support_triage
description: Pipeline de triage de tickets de soporte con 5 pasos LLM.
labeled_by: <quién etiqueta>
expectations:
  - id: E1
    rule: LLM-009                 # o lista: [LLM-009, LLM-018] = cualquiera cuenta como acierto
    component: parse_invoice_email
    expect: present               # present | absent | optional
    min_level: LIKELY             # opcional: nivel mínimo para contar como acierto
    rationale: >-
      El email llega como JSON de la API del proveedor con campos fijos; extraer total y fecha es json.loads.
  - id: E2
    rule: ANY                     # ANY = ninguna recomendación de optimización (de ninguna regla)
    component: write_apology_email
    expect: absent
    rationale: Generación empática abierta dirigida al cliente; el LLM está justificado.
```

Semántica:

- `present`: el auditor **debe** emitir un finding de esa(s) regla(s) sobre ese componente. Si no → falso negativo.
- `absent`: el auditor **no debe** emitirlo. Si lo emite → falso positivo. `rule: ANY` prohíbe cualquier finding de
  optimización sobre el componente (las conclusiones `DO_NOT_OPTIMIZE` no cuentan como finding de optimización).
- `optional`: caso límite; se acepta tanto emitirlo como no. No cuenta para precision ni recall.
- Findings sobre componentes/reglas sin etiqueta se reportan como **no etiquetados**: la precisión se publica en dos
  versiones, "etiquetada" (ignora no etiquetados) y "estricta" (los cuenta como falsos positivos).
- Si una etiqueta se añade **después** de ver la salida del auditor, debe llevar `added_after_review: true`. El informe
  de evaluación separa estas etiquetas para que el sesgo post-hoc sea visible.

## Reglas para autores de fixtures

1. Código realista: como lo escribiría un equipo real, no un caso de libro de texto con comentarios que delatan la
   respuesta. **Prohibido** escribir comentarios como `# smell: LLM-009` o nombres que revelen la etiqueta.
2. Al menos el 40 % de los componentes deben ser usos **legítimos** del LLM (etiquetados `absent`), incluidos casos que
   superficialmente se parecen a un smell pero no lo son según las exclusiones de `docs/RULES.md`.
3. Cada `rationale` explica por qué, citando la definición y la exclusión aplicable.
4. El código no necesita ejecutarse, pero debe ser Python sintácticamente válido.
5. Nada de credenciales reales.

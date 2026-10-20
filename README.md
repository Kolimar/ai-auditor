# ai-auditor — AI Workflow Optimization Auditor

Analiza un sistema basado en LLMs: código Python con SDKs y frameworks, agentes, skills y comandos de Claude Code,
skills de Devin y Cursor, playbooks de Devin, reglas y comandos de Cursor, stages, agentes y plugins de AI-DLC, o
carpetas de prompts sueltos. Responde a esta pregunta:

> **¿Qué partes de este sistema necesitan realmente un LLM y cuáles podrían resolverse de forma más barata, rápida,
> determinística o fiable — y con qué evidencia?**

No es un "LLM que revisa prompts". El análisis por defecto es **determinístico y no hace ninguna llamada a un LLM**
(hay un test que lo comprueba con la red bloqueada). Combina:

- un **IR** del sistema (pasos LLM, prompts por partes, origen de cada variable, salida esperada, herramientas, loops,
  retries, validadores, retrieval) y un **grafo** consultable;
- un catálogo extensible de **smells** (`LLM-001`…`LLM-027`, ver `docs/RULES.md`) con evidencia a favor y en contra;
- una **revisión adversarial** que intenta tumbar cada hallazgo antes de mostrarlo;
- conclusiones positivas (**LLM-000, el uso del LLM está justificado**), para que se vea qué se consideró y por qué no se toca;
- opcionalmente, **trazas runtime**, **destilación** y **experimentos contrafactuales** que convierten hipótesis en
  mediciones.

Se puede usar sola, desde la terminal, o desde un agente de IA (Claude Code, Devin, Cursor) con su skill. Esta segunda
forma es **la más completa**: el agente revisa lo que el análisis determinista no supo clasificar y audita el flujo
entero, incluidos los repos, paquetes y scripts que el flujo usa (ver [Uso desde un agente de IA](#uso-desde-un-agente-de-ia)).

> ¿No programas? Empieza por la **[guía fácil](GUIA.md)**: qué es, cómo usarlo en 3 pasos y cómo leer el informe.

## Instalación

```bash
git clone https://github.com/Kolimar/ai-auditor.git && cd ai-auditor
uv sync            # Python ≥ 3.11; única dependencia: pyyaml
uv run ai-auditor --help
```

## Uso rápido

```bash
ai-auditor analyze ./my-agent-system                       # informe en terminal
ai-auditor analyze ./my-agent-system -f markdown -o audit.md
ai-auditor analyze ./my-agent-system --traces ./traces     # + datos runtime (JSONL / OTLP-JSON)
ai-auditor analyze ./my-agent-system -f sarif -o audit.sarif --fail-on HIGH_CONFIDENCE   # CI
ai-auditor analyze ~/.claude                               # agentes, skills y comandos de Claude Code
ai-auditor analyze .claude/agents/reviewer.md              # un solo archivo (cualquier .md se lee como instrucciones)
ai-auditor analyze ./mi-repo                               # también *.devin.md, .cursorrules, .cursor/rules, .cursor/commands
ai-auditor analyze ./playbooks --md-instructions           # carpeta de .md sueltos (p. ej. playbooks exportados)
ai-auditor analyze ./mi-plugin-aidlc                       # AI-DLC: stages, agentes, knowledge, scopes y sensores
ai-auditor analyze ./my-agent-system --for-agent           # + encargo y mapa del flujo para el agente de IA
ai-auditor report ./my-agent-system --review revision.json # verifica la revisión del agente y arma el informe final
```

## Uso desde un agente de IA

Es la forma más completa de usar la herramienta. El análisis sigue sin llamar a ninguna IA: el refuerzo lo aporta el
agente que ya la está ejecutando, con su propio criterio.

Con `--for-agent`, el informe termina con un encargo para ese agente:

- los pasos que el análisis determinista no supo clasificar, o que dio por justificados con poca evidencia;
- los avisos más débiles, para confirmarlos o descartarlos;
- un **mapa del flujo** con hechos medidos:
  - qué carga cada paso en su contexto: su texto, el agente líder, el knowledge, la memoria y los archivos que le
    mandan leer, con los tokens estimados y lo que alcanzaría siguiendo más referencias;
  - qué ejecuta cada paso: scripts y sensores;
  - frases repetidas entre archivos que acaban juntos en el mismo contexto;
  - el código que la herramienta no parsea (TypeScript, JavaScript, shell…), con un escaneo de imports de SDKs de IA,
    programas que lanza y repos que menciona;
- las **piezas externas**: repos que se clonan (también desde código, como un script que clona una herramienta),
  descargas, paquetes (`uvx`, `npx`…), programas, servidores MCP y archivos referenciados que no están en la carpeta;
- una rúbrica con los patrones de cada paso y los del flujo entero: contexto repetido entre fases, saltos que no
  aportan, pasos independientes en serie, trabajo repetido en cada ejecución, repos enteros en contexto, bucles sin
  límite y comprobaciones que el modelo repite aunque ya las hace un sensor o un script;
- el formato JSON de la respuesta.

`ai-auditor report RUTA --review revision.json` cierra el ciclo. Busca cada cita del agente en su archivo y le pone el
número de línea. Marca como no verificado lo que no encuentra: citas inexistentes, archivos o reglas desconocidos,
niveles que una revisión no puede tener e ids de avisos que no existen. Después arma el informe final con estructura
fija:

1. resumen y mejoras principales;
2. recomendaciones de la herramienta, con el veredicto del agente;
3. revisión del agente por paso y por flujo;
4. lo no verificado;
5. piezas externas;
6. lo que sí necesita IA;
7. los hechos medidos.

La skill `skills/ai-auditor/SKILL.md` hace todo el recorrido:

1. Elige qué analizar: un archivo, una carpeta, un repositorio (si es una URL, lo clona sin historial en una carpeta
   temporal) o tus skills instaladas.
2. Ejecuta el auditor con `--for-agent` y sigue el encargo, empezando por el mapa del flujo.
3. Si pides el flujo completo, dibuja la cadena, audita cada pieza externa (sin ejecutarla) y revisa la cadena entera.
4. Escribe su revisión en JSON, la pasa por `ai-auditor report` y corrige lo no verificado.
5. Te devuelve el informe final: recomendaciones de la herramienta, revisión del agente (marcada como su criterio, no
   como medición), problemas del flujo, piezas externas y lo que sí necesita IA. Si se lo pides, lo guarda en un
   `.md`.

Instalación de la skill (una vez):

| agente | carpeta |
|---|---|
| Claude Code | `~/.claude/skills/ai-auditor/` (o `.claude/skills/` del proyecto) |
| Cursor | lee también `~/.claude/skills/`; si no usas Claude Code, `~/.cursor/skills/ai-auditor/` |
| Devin CLI (local) | `~/.config/devin/skills/ai-auditor/` (o `.devin/skills/` del proyecto) |
| Devin (web) | pega el contenido de `SKILL.md` como playbook |

```bash
mkdir -p ~/.claude/skills && cp -r skills/ai-auditor ~/.claude/skills/
```

La skill usa `ai-auditor` si está instalado y, si no, lo ejecuta con
`uvx --from git+https://github.com/Kolimar/ai-auditor`, así que basta con tener `uv`.

Ejemplos de lo que se le puede pedir:

- «audítame la carpeta ~/proyectos/bot»
- «audita este archivo: .claude/agents/reviewer.md»
- «audita https://github.com/usuario/repo»
- «audita el flujo completo de la skill deploy, incluidos los repos que clona»
- «revisa si mi ciclo SDD tiene pasos que sobran o contexto repetido y guárdame el informe en informe.md»

Otros comandos:

| Comando | Para qué |
|---|---|
| `ai-auditor rules` | lista las reglas registradas |
| `ai-auditor ir PATH` / `graph PATH [--dot]` | IR en JSON / grafo en Mermaid o DOT |
| `ai-auditor trace stats TRACES` | coste, llamadas, reintentos, caché y duplicados por componente |
| `ai-auditor trace synth PATH` | trazas **sintéticas** etiquetadas (demo/tests; nunca cuentan como evidencia) |
| `ai-auditor distill TRACES --component X [--emit-python f.py]` | aprende reglas a partir de decisiones registradas del LLM |
| `ai-auditor experiment run SPEC.yaml [--save DIR]` | experimento ACCEPT / REJECT / INCONCLUSIVE |
| `ai-auditor analyze PATH --experiments DIR` | adjunta resultados: un ACCEPT lleva el hallazgo a PROVEN |
| `ai-auditor benchmark [--split dev\|tuning\|holdout_v3 --confirm-holdout]` | precisión, recall y calibración del propio auditor |

## Cómo leer el informe

**Niveles de evidencia**

| Nivel | Significado |
|---|---|
| `PROVEN` | Hay un experimento ACCEPT. Es el **único** camino a este nivel. |
| `HIGH_CONFIDENCE` | Evidencia estructural fuerte, o trazas reales que la confirman. |
| `LIKELY` | Evidencia heurística consistente. Tope estático para los cambios que afectan a la calidad. |
| `HYPOTHESIS` | Merece comprobarse; no actuar sin validar. |
| `DO_NOT_OPTIMIZE` | El LLM está justificado, o el hallazgo fue descartado por la revisión adversarial o por un experimento (con el motivo). |

Cada hallazgo incluye: `id`, regla, categoría, severidad, confianza, ubicación, evidencia a favor y en contra,
razonamiento, comportamiento actual, cambio recomendado, alternativa, efecto esperado, riesgos, cómo validarlo y si
requiere datos runtime.

**Impacto en cuatro categorías que nunca se suman ni se mezclan**

1. **Static potential**: llamadas o tokens eliminables por invocación. Es estructural, no está medido.
2. **Observed runtime**: lo que el componente costó y hizo según las trazas.
3. **Estimated saving**: lo observado multiplicado por un modelo de ahorro específico de la regla, con los supuestos escritos.
4. **Validated**: el resultado de un experimento.

Sin trazas, el informe dice *not available* y no estima dólares. Un modelo sin precio o un *usage* incompleto da
`UNKNOWN`, nunca un número rellenado. Las trazas sintéticas se marcan como **SYNTHETIC** en cada número.

## Trazas runtime

Se ingieren atributos OTel GenAI, OpenInference/OpenLLMetry/LangSmith, OTLP-JSON y un JSONL propio. Los tokens se
normalizan a cubos disjuntos según la semántica de cada proveedor (OTel y OpenAI incluyen la caché en `input`; Anthropic
no). Instrumentación mínima sin dependencias:

```python
from ai_auditor.tracing.sdk import Tracer

tracer = Tracer("traces/run.jsonl", workflow="support", store_values=False)  # True para poder destilar
with tracer.execution():
    with tracer.step("classify_ticket", input_value=ticket) as span:
        resp = client.messages.create(...)
        span.record(resp, output_value=label)
```

La evidencia runtime solo cuenta con trazas **reales** y al menos 30 llamadas del componente. Las contradicciones (por
ejemplo, "falta caché" cuando el prefijo ya se lee de caché) descartan el hallazgo.

## Experimentos

```yaml
# exp/lane.yaml
id: lane-as-code
component: pick_lane
rule: LLM-001                 # o `finding: <id del informe>`
dataset: data.jsonl           # {"input": ..., "baseline_output": ..., "expected"?: ..., "baseline_cost_usd"?: ...}
candidate: {kind: python, target: "lane_rules:lane"}   # devuelve None para abstenerse (fallback al LLM)
metric: exact_match           # normalized_match | json_equal | numeric_close:0.01 | python:mod:fn
margin: 0.01                  # δ de no inferioridad, decidido antes de ver resultados
```

```bash
ai-auditor experiment run exp/lane.yaml --save results/
ai-auditor analyze . --experiments results/
```

- **Sin etiquetas gold** se mide la fidelidad al LLM (límite de Wilson frente a 1 − δ).
- **Con etiquetas gold** se aplica no inferioridad pareada (bootstrap por traza y McNemar exacto). El cambio tampoco puede
  romper un `quality_target` que el sistema actual cumple.
- Un ACCEPT exige además no empeorar el coste ni superar `latency_target_ms`.
- Por defecto todo es *replay* offline. Para llamar a un modelo hacen falta `--allow-live --budget-usd X`.

## Configuración (`.ai-auditor.yaml`)

```yaml
quality_target: 0.95
reliability_target: 0.99
latency_target_ms: null
non_inferiority_margin: 0.01
min_level: HYPOTHESIS
disabled_rules: [LLM-025]
model_tiers: {"my-finetune-*": small}
pricing_file: my-prices.yaml   # sobrescribe cost/data/pricing.yaml
exclude: [examples, notebooks]
notebooks: exploratory         # .ipynb: exploratory (por defecto) | production | skip
```

Los pasos en `tests/`, `examples/` y `docs/`, y los ficheros `test_*.py`, se extraen pero no se reportan como hallazgos
de producción. Los notebooks se tratan igual salvo `notebooks: production`.

El auditor no escribe en el proyecto analizado: la caché del IR va a `$AI_AUDITOR_CACHE` o a
`~/.cache/ai-auditor` (`--no-cache` la desactiva).

## Calidad medida del propio auditor

Las cifras completas y sus advertencias están en [`docs/EVALUATION.md`](docs/EVALUATION.md). Resumen:

| Split | Precisión (hallazgos etiquetados) | Recall | Absent respetado | FP (etiquetas) |
|---|---|---|---|---|
| tuning = dev + holdout v1 + holdout v2 (61 fixtures, **usado para ajustar**) | 0.99 [0.95, 1.00] | 0.95 [0.90, 0.98] | 0.99 | 1 |
| holdout v1 (20 fixtures, iteración 1, medido una vez) | 0.82 [0.52, 0.95] | 0.32 [0.18, 0.51] | 0.94 | 2 |
| holdout v2 (31 fixtures, iteración 2, medido una vez) | 0.94 [0.81, 0.98] | 0.46 [0.35, 0.58] | 0.98 | 2 |
| **holdout v3** (40 fixtures nuevos, iteración 3, medido una vez) | **0.80 [0.69, 0.88]** | **0.49 [0.39, 0.58]** | **0.90 [0.84, 0.94]** | **13** |

Intervalos de Wilson al 95 %. La cifra que vale para sistemas no vistos es la de **holdout v3**. La de tuning está
inflada por construcción, porque esos fixtures se usaron para ajustar.

La iteración 3 **no cumplió dos de sus cuatro hipótesis prerregistradas**:

- la precisión etiquetada cayó por debajo de 0.85;
- el absent respetado cayó por debajo de 0.95, con todo el intervalo por debajo.

El recall subió (global de 0.46 a 0.49; Claude Code de 0.33 a 0.51), pero los intervalos se solapan con los de v2: la
mejora es **indicativa, no demostrada**. Según el prerregistro, la caída de precisión se atribuye a la iteración 3 aunque
suba el recall. El análisis posterior lo confirma: 9 de los 13 FP salen de código de la iteración 3.

- 7 son LLM-024 sobre bucles que leen un fichero. Encajan con la regla, pero las etiquetas `ANY absent` no los
  admiten.
- 2 son colisiones léxicas.

El auditor sigue encontrando solo la mitad de lo etiquetado en sistemas nuevos. 38 de los 55 FN son del perfil de tarea.
Detalle, análisis de errores y declaraciones en `docs/EVALUATION.md`.

## Limitaciones conocidas

- Extractores: Python y notebooks Jupyter (SDKs de Anthropic, OpenAI —Chat Completions y Responses—, Google GenAI,
  LiteLLM, Ollama; modelos de chat de LangChain; agentes de OpenAI Agents SDK, PydanticAI, CrewAI, Google ADK, Claude
  Agent SDK, LangGraph/LangChain y, sin verificar, AutoGen), Claude Code (Markdown con frontmatter), playbooks de Devin
  (`*.devin.md`), skills de Devin y Cursor (`SKILL.md`) y reglas y comandos de Cursor. Los playbooks que solo existen en la web de Devin hay que exportarlos
  primero; en Devin y Cursor no se evalúa la elección de modelo, porque el fichero no la fija. No hay extractores
  para TypeScript ni para configuraciones YAML de orquestadores: los agentes de CrewAI definidos en `agents.yaml`
  aparecen sin prompt.
- La herramienta solo ve el archivo o la carpeta que recibe: no sigue repos clonados, paquetes ni scripts externos.
  Con `--for-agent` los lista, y es el agente quien los audita. Esa revisión del agente no está medida: `report`
  garantiza que sus citas existen, no que sus conclusiones sean correctas.
- El código que no es Python (TypeScript, JavaScript, shell…) no se parsea. Solo se escanea en busca de imports de SDKs
  de IA, programas que lanza y repos que menciona.
- AI-DLC: un stage cuenta con su agente líder y el knowledge de ese agente, como en los stages *inline*. Los tokens
  son estimaciones y las referencias se detectan por texto («Follow X.md», rutas, enlaces).
- Los tokens se cuentan con una heurística (±25 %) salvo que `tiktoken` esté instalado; en ambos casos es una aproximación.
- La confianza es heurística. En holdout v3 acertaron el 73 % de los hallazgos HYPOTHESIS (44) y el 83 % de los LIKELY
  (24), con ECE 0.20. En holdout v2 eran el 95 % y el 87 %. La brecha de confianza baja porque bajan los aciertos, no
  porque la confianza esté mejor calibrada. No se recalibró porque n es pequeño.
- Rendimiento y memoria: ~25 s y ~850 MB para 1.000 ficheros Python con 2.700 pasos, y ~60 s y ~1,7 GB para 2.000
  ficheros (pydantic-ai). La memoria la dominan los AST en memoria. En proyectos de unos cientos de ficheros, pocos
  segundos.
- La vinculación de trazas a pasos se hace por nombre de componente o agente, no por huella de prompt.
- No se ha ejecutado ningún experimento contra un modelo real; el modo live está implementado y testeado con dobles.

## Documentación

- `docs/ARCHITECTURE.md`: pipeline, IR, reglas, revisión adversarial, runtime, coste, experimentos y robustez.
- `docs/RULES.md`: definición de cada smell, qué *no* es, cambio recomendado y política para Claude Code.
- `docs/EVALUATION.md`: benchmark, calibración, autoauditoría y declaraciones metodológicas.

Añadir reglas: subclase de `Rule` registrada con `@register` o mediante el entry point `ai_auditor.rules` de un paquete externo.

# Arquitectura — AI Workflow Optimization Auditor

Pregunta que responde: **¿qué partes de este sistema necesitan realmente un LLM y cuáles podrían resolverse de forma
más barata, rápida, determinística o fiable — y con qué evidencia?**

Definiciones de smells: `docs/RULES.md`.

## 1. Pipeline

```text
                ┌────────────── parser/ ───────────────┐
 proyecto ──►   discovery ─► extractors (python AST,    ─►  SystemIR  ─► graph/ ─┐
                             claude code md, yaml, ...)      (ir/)               │
                └──── caché por hash de archivo ───────┘                         │
                                                                                  ▼
 trazas (opcional) ─► tracing/ingest ─► RuntimeStats ───────────────►  analyzers/engine ─► rules/*
                                                                                  │  (perfil de tarea compartido,
 pricing.yaml, tiers.yaml ─► cost/, model_routing/ ───────────────────────────────┤   determinism score)
                                                                                  ▼
                                              optimization/adversarial (challenges) ─► prioritization
                                                                                  ▼
                                                     reporting/ (text, md, json, sarif)
 experimentos (opcional): experiments/ ─► evaluation/ (métricas + estadística) ─► Validated ─► findings PROVEN
```

Acoplamiento permitido (las flechas son las únicas dependencias):

- `parser` → `ir`. Ningún otro módulo lee código fuente.
- `rules` → `ir`, `graph`, `analyzers`, `optimization.profile`, `model_routing`. Las reglas no conocen proveedores ni
  precios en dólares: hablan de llamadas, tokens y tiers.
- `cost` → solo datos de precios + usage normalizado. Se usa para impacto observado/estimado, nunca en detección.
- `tracing` → normalización de usage por proveedor y estadísticas runtime; `experiments/live.py` es el único módulo que
  puede importar SDKs de proveedores, y solo con `--allow-live`. El análisis por defecto no importa ningún SDK (hay un
  test que lo comprueba con la red bloqueada).
- `reporting` → solo `Finding` y resultados agregados.

## 2. IR (`ir/model.py`)

Unidad de análisis: `LLMStep` (`kind: call | agent`). Nodos: `workflow, llm_step, tool, retrieval, conditional, loop,
retry, validation, context_source, code_step, skill`. Aristas: `contains, delegates, data_flow, controls, uses_tool,
retrieves, validates, retries, injects_context`.

Cada `LLMStep` lleva: modelo (`raw`, `resolved`, `tier`, `dynamic`, `inherited`), prompt por partes (rol, texto estático
con `{var}`, variables con origen: `constant | user_input | llm_output | file | retrieval | tool_result | history |
parameter | unknown`), especificación de salida (tipo, enforcement, etiquetas cerradas, campos de schema), parámetros
(temperatura, thinking, tool_choice, tools, cache_control, max_iterations) y `attrs["provenance"]`
(`literal | constant | config | sdk_default | unresolved | absent` por atributo).

Lo desconocido es explícito (`None` + diagnóstico). Ninguna regla puede tratar `None` como "falso".

El IR es serializable (JSON) y se cachea por `sha256(archivo) + versión del extractor`, de modo que un segundo análisis
no reprocesa archivos sin cambios. `tests/regression/test_ir_fingerprint.py` guarda una huella canónica del IR de los
sistemas golden junto a las versiones de los extractores: si el IR cambia sin subir la versión, el test falla. Así una
caché antigua no puede servir un IR obsoleto.

Resolución estática del extractor Python (`parser/python/resolve.py`):

- constantes de otros módulos del proyecto, por nombre importado (`from prompts import RULES`) o por atributo
  (`prompts.RULES`, `pkg.prompts.RULES`);
- `"sep".join(<expr> for <vars> in <contenedor constante>)` (también `.items()`, `.values()`) se pliega a texto
  estático con un mini-evaluador acotado (f-strings, `str()`, `+`, máximo 500 elementos, sin efectos);
- una expresión que se resuelve a un literal, nunca se reasigna y no depende de parámetros es `VarSource.CONSTANT`
  (base de LLM-020);
- taint de salidas LLM con **flujo implícito**: lo que se asigna, muta (`append`, `extend`, `add`…) o devuelve dentro de
  un `if` que depende de la salida de un LLM hereda ese taint. Por ejemplo, un filtro `if verdict == "yes":
  kept.append(doc)` hace que `kept` dependa del paso que dio el veredicto;
- las variables de una plantilla LangChain se renombran a su clave (`{"text": result["answer"]}`), pero el flujo
  parámetro→paso usa la raíz de la expresión;
- un helper LangChain con plantilla propia (`chain = TMPL | llm`) es un paso con su nombre, no un wrapper genérico que
  se materializa en cada llamada;
- notebooks Jupyter: se concatenan las celdas de código (cada una precedida de `# %% [cell N]`, al que remiten los números
  de línea). Las magias de IPython (`%`, `!`, `%%bash`…) se neutralizan, se admite `await` de nivel superior y las
  celdas que no parsean se descartan una a una con diagnóstico;
- el análisis de funciones es un punto fijo sobre resúmenes (`returns`, `param_flows`, `reach`). Tras la primera ronda
  solo se reanalizan las funciones que llaman a alguna cuyo resumen cambió. El resultado se verificó idéntico (IR
  canónico) al de reanalizar todo en 35 proyectos.

## 3. Grafo (`graph/workflow_graph.py`)

Consultas: consumidores/productores de datos, ramas que controla un paso, validadores, políticas de retry, loops
envolventes (multiplicidad estática), herramientas, retrievals, fuentes de contexto, delegaciones, alcanzabilidad.
Export a Mermaid y DOT.

## 4. Perfil de tarea y determinism score (`optimization/profile.py`, `optimization/determinism.py`)

Se calcula **una vez por paso** y lo comparten todas las reglas. Rasgos determinísticos (léxico EN/ES + estructura):
tipo de tarea candidato (clasificar, extraer, formatear, validar schema, validar semántica, decidir/rutear, resumir,
generar abierto, razonar, traducir, código, conversación), espacio de salida (cerrado/estructurado/abierto), etiquetas
cerradas (de schema, de prompt y de comparaciones en el código consumidor), reglas explícitas en el prompt
(umbrales/condiciones), naturaleza de la entrada (estructurada / texto libre), marcadores de juicio, razonamiento pedido
y si se consume, dominio de riesgo, entrada no confiable, ejemplos few-shot, tamaño estático.

**Determinism score** (0–100): suma explicada de contribuciones (cada una con su evidencia). Bandas:
0–30 generativo, 31–60 dependiente del modelo, 61–80 candidato a modelo pequeño, 81–95 candidato determinístico fuerte,
96–100 determinístico. Es heurístico: el informe declara si está calibrado y contra cuántos casos.

## 5. Reglas (`rules/`) y motor (`analyzers/engine.py`)

`Rule.check(ctx) -> Iterable[Finding]`. Registro por decorador y por entry points (`ai_auditor.rules`): añadir un
analizador no toca el core. Reglas con `needs={"runtime"}` se saltan sin trazas (y se informa).

Confianza: noisy-OR de evidencias a favor con descuento multiplicativo por contra-evidencia. Nivel = f(confianza) con
**tope por clase de riesgo y tipo de evidencia**:

| Clase | Ejemplos | Tope estático | Tope con trazas | PROVEN |
|---|---|---|---|---|
| A preserva semántica | caching, batch, paralelizar, acotar loops/retries | HIGH_CONFIDENCE | HIGH_CONFIDENCE | experimento ACCEPT |
| B reemplazo mecánico | parser, formatter, schema check, precomputar, tool call fijo | HIGH_CONFIDENCE (entrada estructurada probada) / LIKELY | HIGH_CONFIDENCE | experimento ACCEPT |
| C afecta calidad | modelo menor, routing, quitar agente/validador, recortar contexto/RAG, destilar | LIKELY | HIGH_CONFIDENCE | experimento ACCEPT |

## 6. Revisión adversarial (`optimization/adversarial.py`)

Tras generar findings, cada uno pasa por *challenges* determinísticos ("¿por qué podría estar mal?"): marcadores de
juicio, dominio de alto riesgo, entrada libre no confiable, salida consumida por generación de cara al usuario, prompt
dinámico no resuelto, dependencia implícita de contexto/historial, validador que comprueba semántica, guardarraíl de
seguridad, código muerto/ejemplo, muestra runtime insuficiente o no independiente. Un challenge bloqueante fallido
convierte el finding en `DO_NOT_OPTIMIZE` (visible en el informe como "considerado y descartado", con motivo); uno no
bloqueante baja un nivel. Un revisor LLM opcional (apagado por defecto) **solo puede degradar**.

## 7. Impacto: cuatro categorías que nunca se suman

`static_potential` (llamadas/tokens eliminables por invocación; multiplicidad estática), `observed` (trazas),
`estimated` (observado × supuestos explícitos), `validated` (experimento). Sin trazas, el informe dice
"Observed: not available" y no estima dólares.

## 8. Runtime (`tracing/`)

Esquema de span (`tracing/schema.py`) compatible con OTel GenAI (+ prefijo `auditor.*`). Ingesta (`tracing/ingest.py`)
de JSONL propio, atributos OTel aplanados y OTLP-JSON, con alias de OpenInference/OpenLLMetry/LangSmith y los legados de
OTel (`gen_ai.system`, `gen_ai.usage.prompt_tokens`, …). Cada importador declara la semántica de tokens que lee y
normaliza a **cubos disjuntos** (`uncached_input`, `cache_read`, `cache_write`, `output`, `reasoning` como subconjunto):

| Fuente | `input` incluye caché | Normalización |
|---|---|---|
| OTel GenAI `gen_ai.usage.input_tokens` | sí (total) | total − cache_read − cache_write (o `auditor.usage.input_excludes_cache`) |
| Anthropic nativo `input_tokens` | no | tal cual |
| OpenAI `prompt_tokens` / `input_tokens` | sí (`cached_tokens`) | total − cached |
| Gemini `promptTokenCount` | sí (`cachedContentTokenCount`) | total − cached; output = candidates + thoughts |
| `{input_tokens, output_tokens}` sin campos de caché | indistinguible | se valora sin caché y se anota (cota superior) |

Casos ambiguos (input < subtotales de caché) se marcan y se informan. Vinculación span → paso por `component`
(`auditor.component`) o `gen_ai.agent.name`, comparando con el nombre o el `qualname` del paso; el informe lista pasos
observados, no observados y componentes de trazas que no corresponden a ningún paso. No hay vinculación por huella de
prompt (pendiente).

Estadísticas por componente (`tracing/stats.py`): llamadas/ejecución, tokens, coste (o UNKNOWN con motivo), latencia
p50/p95, reintentos, errores y fallos de validador como `Rate` (Wilson; regla de tres con 0 eventos), duplicados exactos
por ejecución, entradas/salidas distintas, autoconsistencia en entradas repetidas, cuota de lectura de caché y separación
mediana entre llamadas (para razonar sobre el TTL de caché).

`tracing/attach.py` une trazas y findings: `observed`, `estimated` (modelo de ahorro **por regla**, con supuestos
escritos; si no es calculable lo dice con el motivo específico) y evidencia runtime. La evidencia runtime solo cuenta con
trazas **reales** y ≥ 30 llamadas; entonces puede subir el tope de clase C a HIGH_CONFIDENCE. Una contradicción fuerte
(peso ≤ −0.6, p. ej. el prefijo ya se lee de caché) es un challenge adversarial bloqueante. Las trazas sintéticas
(`ai-auditor trace synth`, marcadas `synthetic: true`) nunca cambian niveles y todo número derivado se etiqueta SYNTHETIC.

Cuando las trazas reales incluyen valores de entrada/salida (`Tracer(store_values=True)`), los findings de reemplazo por
código (001/009/011/026/019) se contrastan con destilación (§10): si un árbol pequeño reproduce las decisiones del LLM en
entradas retenidas, es evidencia a favor y acota el ahorro estimado a la cobertura medida; si no, es contra-evidencia.

Instrumentación mínima sin dependencias: `ai_auditor.tracing.sdk.Tracer` (escribe JSONL local; guarda solo hashes salvo
que se pidan valores).

## 9. Coste (`cost/`)

`Usage` normalizado × `PriceTable` versionada (`cost/data/pricing.yaml`: fuente y fecha por modelo; precios de caché y
de Batch API cuando existen). Modelo sin precio o usage incompleto → `UNKNOWN` con motivo; los totales se informan como
`coste conocido + N llamadas con coste UNKNOWN`, nunca rellenando huecos. No implementado: costes de embeddings, rerank,
herramientas o infraestructura por ejecución.

## 10. Experimentos y destilación (`experiments/`, `optimization/distill.py`)

**Experimento contrafactual** (`ai-auditor experiment run SPEC.yaml`): especificación YAML con `component`, `finding` o
`rule`, `dataset` JSONL, `candidate` (`python: módulo:función`, o `llm` solo en modo live), `baseline` (por defecto,
salidas LLM registradas), `metric` (`exact_match`, `normalized_match`, `json_equal`, `numeric_close:tol`,
`python:módulo:función`), `margin` δ (pre-registrado; por defecto `non_inferiority_margin` de la config) y `alpha`.

- Sistema compuesto: si el candidato se abstiene (`None`), se usa la salida, el coste y la latencia del baseline para ese
  ítem (fast-path + fallback, como se desplegaría).
- Modo **fidelidad** (sin etiquetas gold): acuerdo con el LLM; ACCEPT si el límite inferior de Wilson ≥ 1 − δ, REJECT si
  el superior < 1 − δ.
- Modo **corrección** (con `expected`): diferencia pareada de exactitud con bootstrap (por cluster de `trace_id` si hay
  varias filas por traza) y McNemar exacto. ACCEPT si el límite inferior > −δ (no inferioridad), REJECT si el superior < −δ.
- INCONCLUSIVE en otro caso, con el n aproximado necesario.
- ACCEPT exige además: coste compuesto ≤ baseline, latencia ≤ `latency_target_ms` si se configuró, y tasa de fallos del
  candidato compatible con `reliability_target`. Un dataset sintético nunca valida (INCONCLUSIVE).
- Por defecto todo es *replay* offline (coste LLM cero). `kind: llm` exige `--allow-live --budget-usd X`; el presupuesto
  se comprueba **antes** de cada llamada con una estimación pesimista.
- `--save DIR` guarda el resultado; `ai-auditor analyze --experiments DIR` lo adjunta: ACCEPT sobre un finding que
  sobrevivió la revisión adversarial ⇒ **PROVEN** (único camino); ACCEPT sobre uno bloqueado conserva el nivel (el
  experimento no mide el motivo del bloqueo); REJECT ⇒ descartado (challenge bloqueante `experiment`).

No hay juez LLM integrado: una métrica `python:` del usuario podría usarlo, pero la decisión siempre la toma la
estadística determinística.

**Destilación** (`ai-auditor distill TRACES --component NAME [--emit-python FILE]`): con entradas estructuradas (dict o
JSON) y salidas registradas, ajusta un árbol CART pequeño con abstención (hojas impuras o con poco soporte devuelven
`None`). Las entradas se agrupan por sus campos canónicos (no por hash, que depende de la serialización) y el split es
por grupo; el árbol se entrena con un ejemplo por entrada distinta y se evalúa sobre entradas **distintas** retenidas,
de modo que el tráfico repetido no infla n ni el intervalo. Cobertura y fidelidad con IC de Wilson; decisión
`distillable | not_distillable | insufficient_data` (≥ 30 entradas distintas de test). Las repeticiones exactas
(memoización) no son destilación: las miden LLM-020 y LLM-027. Solo emite código si el árbol supera el listón;
el código generado acepta la entrada cruda y devuelve `None` cuando no está seguro (el LLM queda como fallback).

## 11. Evaluación del propio auditor

Golden dataset (`tests/golden`, `tests/adversarial`) con split dev/holdout pre-registrado; métricas: precision
etiquetada y estricta, recall, FP/FN por regla, calibración (Brier, ECE por bandas), tiempo de ejecución y coste LLM del
auditor (debe ser 0 en modo por defecto; test con red bloqueada).

Resultados: `docs/EVALUATION.md`.

## 12. Robustez

- Un fallo de un extractor no tumba el análisis: se convierte en el diagnóstico `EXTRACTOR_CRASH` (nivel error), el
  resto del proyecto se analiza, el informe lo muestra arriba como "resultados parciales" y el resultado no se cachea.
  En el benchmark, un crash cuenta todas las expectativas `present` del fixture como FN.
- Código muerto (`if False`, constantes de módulo a `False`) y código no productivo se marcan `non_production` y se
  descartan en la revisión adversarial con el motivo visible. Cuentan como no productivos: `tests/`, `*_tests/`,
  `examples/`, `samples/`, `docs/`, `test_*.py`, `conftest.py` y, por defecto, los notebooks. Aplica a todos los nodos
  y frameworks.
- Errores de uso (ruta inexistente, configuración o spec de experimento inválidos) salen con código 2 y un mensaje
  (`UsageError`). Los bugs internos conservan su traceback.
- `SyntaxWarning` del código auditado se silencia: no es salida del auditor.
- Probado sin crashes sobre 10 proyectos reales (9.660 ficheros; ver `docs/EVALUATION.md`).
- Rendimiento medido sin caché:
  - una carpeta `~/.claude` con ~300 archivos y ~100 agentes y skills: ~5 s, dominado por los léxicos regex del perfil de tarea;
  - repos de 1 000–2 000 ficheros Python: 25–60 s y 0,9–1,8 GB, dominados por el extractor y los AST en memoria;
  - fixtures del golden set: ~30 ms cada uno. El IR se cachea por hash de archivo
  **fuera** del proyecto auditado (`$AI_AUDITOR_CACHE`, o `$XDG_CACHE_HOME/ai-auditor`, o `~/.cache/ai-auditor`):
  el auditor no escribe nada en el sistema que audita.

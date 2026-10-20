# Catálogo de LLM smells — definiciones semánticas

Este documento define **qué es** y **qué no es** cada smell. Es el contrato entre:

- los detectores (`src/ai_auditor/rules/`), que intentan reconocerlo con evidencia;
- el golden dataset (`tests/golden/`), cuyas etiquetas se escriben contra estas definiciones, **no** contra la implementación.

Cada definición incluye exclusiones explícitas. Un detector que dispara sobre una exclusión es un falso positivo,
y los falsos positivos son el fallo más grave del auditor: recomendar quitar razonamiento necesario es peligroso.

Unidad de análisis: un **paso LLM** (`LLMStep`), que es una llamada a un modelo (`kind: call`) o un agente que
itera con un modelo (`kind: agent`: subagente de Claude Code, `Agent(...)` de un SDK, etc.).

Niveles de evidencia (ver `docs/ARCHITECTURE.md` §Evidencia):
`PROVEN` (solo con experimento validado) > `HIGH_CONFIDENCE` > `LIKELY` > `HYPOTHESIS`; `DO_NOT_OPTIMIZE` es una conclusión
explícita de que el LLM está justificado.

---

## LLM-001 Deterministic Decision Delegated to LLM

**Es:** un paso LLM cuya salida elige entre un conjunto cerrado de alternativas (ruta, aprobar/rechazar, prioridad) y cuyos
criterios de decisión están **completamente especificados como reglas explícitas** sobre entradas estructuradas
(umbrales numéricos, igualdad de campos, pertenencia a listas, fechas). La función de decisión es computable por código.

**No es:** decidir interpretando lenguaje natural libre ("¿el cliente está enfadado?") — eso es clasificación semántica
(candidato a LLM-018 como mucho). Tampoco cuando el prompt pide "criterio", "juicio" o "considerar el contexto".

## LLM-002 Redundant LLM Validation

**Es:** un paso LLM que verifica propiedades de la salida de otro paso que **ya están garantizadas** por un mecanismo
existente (structured outputs / constrained decoding, validación pydantic o JSON Schema, chequeos de tipo), o una segunda
verificación LLM que duplica otra de la misma propiedad.

**No es:** validación semántica no cubierta por ningún otro mecanismo: fact-checking contra fuentes, grounding,
cumplimiento de políticas, tono, seguridad.

## LLM-003 Large Model for Simple Task

**Es:** un modelo de tier frontier/large usado en una tarea cuyo perfil es simple: salida corta y cerrada,
clasificación/extracción/formateo, entrada acotada, sin razonamiento multi-paso.

**No es:** tareas con razonamiento multi-paso, generación abierta larga, uso de muchas herramientas en horizonte largo,
código complejo, o dominios de alto riesgo sin evidencia runtime.

## LLM-004 Excessive Context Injection

**Es:** el prompt incluye contexto grande que no es necesario para la tarea: archivos o documentos completos, volcados de
estado/objetos enteros, historial completo para una tarea de un campo, instrucciones siempre cargadas desproporcionadas.

**No es:** contexto que es el objeto de la tarea ("resume este documento", "revisa este diff"). Tampoco un `CLAUDE.md`
anidado (`pkg/CLAUDE.md`): Claude Code solo lo carga al trabajar en ese subárbol. Solo cuenta como "siempre cargada" la
memoria de la raíz (o `.claude/CLAUDE.md`). Un `AGENTS.md` lo leen Codex y otros agentes, no Claude Code, y si
`CLAUDE.md` es un enlace a `AGENTS.md` se cuenta una sola vez. El historial de un agente que crece sin recorte cuenta
menos si el bucle tiene un tope pequeño (≤ 20 vueltas). Una descripción de agente o skill de más de 4 veces
`always_loaded_description_tokens` (150 por defecto, es decir, más de 600 tokens) y sin ejemplos de enrutado
(`<example>`, `examples:`, líneas `user:`) se reporta por sí sola, además del total de descripciones.

## LLM-005 Repeated Context

**Es:** el mismo bloque grande de texto se envía en varias llamadas o pasos (varios agentes, iteraciones de un loop) sin
prompt caching ni compartición.

**No es:** bloques pequeños (por debajo del umbral configurado) ni repeticiones que ya usan caching de prefijo.

## LLM-006 Redundant Agent

**Es:** un agente/paso cuya función ya está cubierta por otro: agentes casi duplicados (mismo rol/prompt), agentes
pass-through que reformulan o reenvían sin aportar información, o pasos que rehacen el trabajo del anterior
("resume el resumen").

**No es:** pasos que aportan una perspectiva, herramienta, fuente de datos o verificación distinta (p.ej. un crítico que
revisa con criterios diferentes del generador). Tampoco copias del mismo agente en **aplicaciones distintas** de un
monorepo o colección de ejemplos (cada directorio con `pyproject.toml`, `setup.py`, `requirements*.txt`, `Pipfile` o
`.git` es una aplicación), porque nunca se ejecutan en el mismo sistema.

## LLM-007 Redundant Reasoning

**Es:** razonamiento explícito pedido (chain-of-thought, "explica tu razonamiento", extended thinking con presupuesto alto)
que los consumidores descartan y en una tarea simple; o el mismo razonamiento calculado dos veces por dos pasos.

**No es:** razonamiento que se muestra al usuario, se audita, o mejora una tarea compleja.

## LLM-008 Retry Instead of Validation

**Es:** reintentos de una llamada LLM disparados por fallos de formato/parseo/validación, cuando structured outputs,
constrained decoding o una reparación determinística evitarían el fallo. También reintentos sin límite.

**No es:** reintentos por errores de red/rate limit (eso es resiliencia legítima).

## LLM-009 LLM Used as Parser

**Es:** un LLM extrae campos de una entrada con **estructura legible por máquina**: JSON, CSV, XML/HTML con estructura
estable, líneas de log de formato fijo, cabeceras de email, fechas/importes/IDs con formato regular.

**No es:** extracción desde prosa libre con redacción variable (uso legítimo; como mucho candidato a LLM-018).

## LLM-010 LLM Used as Formatter

**Es:** el LLM transforma la presentación de datos sin cambio semántico: JSON→YAML/CSV/tabla Markdown, mayúsculas,
formato de fechas, rellenar una plantilla con campos ya disponibles.

**No es:** reescritura de prosa (tono, claridad), traducción, resumen.

## LLM-011 LLM Used for Schema Validation

**Es:** se pide al LLM comprobar que unos datos cumplen un schema: campos requeridos, tipos, formatos, rangos.

**No es:** validación semántica (ver exclusiones de LLM-002). LLM-002 trata la *redundancia* con validación existente;
LLM-011 trata que el LLM haga un trabajo de schema en absoluto.

## LLM-012 Unnecessary Multi-Agent Delegation

**Es:** delegación a subagentes que no aporta ninguna de: aislamiento de contexto para trabajo exploratorio grande,
paralelismo, herramientas/permisos distintos, modelo distinto. Ejemplos: cadena lineal de agentes que hacen
transformaciones pequeñas que una sola llamada haría; orquestador cuyo único trabajo es invocar un subagente.

**No es:** delegación con paralelismo real, aislamiento de contexto de búsquedas grandes, o separación de permisos.
Las herramientas o el modelo propios del delegado justifican al delegado, no a un intermediario que solo le reenvía la
petición: el intermediario sigue siendo candidato. Un comando de Claude Code que invoca un agente no es un
intermediario: es el texto que la persona escribe en la sesión principal, que se ejecuta de todos modos.

## LLM-013 Missing Model Routing

**Es:** el sistema usa un único modelo grande para pasos con perfiles de complejidad heterogéneos (algunos simples,
otros complejos) sin routing por tier; o un paso de alto volumen y dificultad variable sin cascada.

**No es:** sistemas cuyos pasos son todos complejos, o que ya usan modelos distintos por paso.

## LLM-014 Missing Caching Opportunity

**Es:** (a) prefijo de prompt estable y grande (≥ mínimo del proveedor) reutilizado sin prompt caching cuando el proveedor
requiere activarlo explícitamente; (b) llamadas deterministas (temperatura 0, entradas finitas o repetidas) sin
memoización; (c) en runtime, entradas duplicadas observadas.

**No es:** prefijos por debajo del mínimo cacheable, contenido que cambia en cada llamada, o proveedores con caching
automático ya aplicado.

## LLM-015 Repeated Retrieval

**Es:** la misma recuperación (misma consulta/fuente) se ejecuta varias veces dentro de una ejecución (loops, varios
agentes) sin reutilizar el resultado.

**No es:** la misma consulta contra **otro** índice o retriever: un router que recorre `for r in retrievers:
r.retrieve(q)`, o un retriever por tabla o columna. Para el detector, la recuperación es invariante solo si la consulta
y el receptor no dependen de la variable del loop.

## LLM-016 Excessive RAG Context

**Es:** la recuperación inyecta muchos o muy grandes fragmentos (top_k alto sin reranking, documentos completos) en
relación con la necesidad de la tarea; en runtime, los tokens recuperados dominan la entrada.

## LLM-017 Deterministic Tool Calling Opportunity

**Es:** se usa el LLM para decidir una llamada a herramienta que es **invariante**: `tool_choice` forzado a una
herramienta concreta, instrucciones "llama siempre primero a X", o secuencias fijas de herramientas. La llamada puede
hacerse en código antes/después del LLM.

**No es:** elección de herramienta que depende del contenido de la entrada.

## LLM-018 Candidate for Small Model

**Es:** la tarea necesita comprensión de lenguaje (no es determinística) pero es estrecha (clasificación/extracción sobre
texto libre con salida cerrada) y el modelo actual no es pequeño. Recomendación: cascada pequeño→grande con escalado
por validación o confianza, **siempre sujeta a experimento**.

## LLM-019 Candidate for Distillation

**Es:** tarea de alto volumen, estrecha y estable cuyas salidas muestran un mapeo entrada→salida consistente (en trazas o en
los ejemplos few-shot del propio prompt). Destinos: reglas, tabla de decisión, clasificador, modelo pequeño ajustado.

## LLM-020 Candidate for Precomputation

**Es:** llamada LLM cuyas entradas son estáticas (sin variables runtime) o provienen de un dominio finito y pequeño conocido
de antemano (enum de categorías, catálogo fijo) → calcular offline una vez y consultar. El dominio cuenta como
conocido si el parámetro está tipado (`Enum` del proyecto, `Literal[...]`, `bool`), también a través de una función del
proyecto que lo transforma (`label_for(category)`); si solo se infiere del nombre, hace falta además que la llamada se
repita (bucle o punto de entrada).

---

## Reglas adicionales (no incluidas en el planteamiento inicial)

## LLM-021 Unbounded Agent Loop

**Es:** loop alrededor de un LLM o agente sin límite de iteraciones (`while True` sin cota, agente sin `max_turns`).
Riesgo de coste y de fiabilidad, no de calidad.

**No es:** un REPL de chat donde cada vuelta espera a una persona (`input()`, `getpass`, `sys.stdin.readline`,
`Prompt.ask`, `st.chat_input`, `websocket.receive_*`, también dentro de un helper llamado en el loop). Ese loop lo
acota quien escribe. Un loop agéntico interno sin cota se reporta aparte. Tampoco un `while True` con contador y tope
(`n += 1; if n > MAX: …`) cuyo cuerpo sale del bucle o desarma las herramientas (`tools = []`), lo que fuerza la
respuesta final.

## LLM-022 Free-Text Output Parsed as Structure

**Es:** la salida en texto libre de un LLM se parsea como estructura (`json.loads`, regex) sin structured outputs ni
constrained decoding. Fuente frecuente de LLM-008.

**No es:** limpiar el texto con `re.sub` o `re.split` (quitar acotaciones, normalizar espacios). Solo se cuentan como
parseo las funciones que extraen (`search`, `match`, `fullmatch`, `findall`, `finditer`).

## LLM-023 Excessive Tool Definitions

**Es:** un paso recibe muchas definiciones de herramientas (tokens de schema en cada llamada) cuando su tarea usa pocas.

## LLM-024 Batch API Opportunity

**Es:** procesamiento masivo no interactivo (loop sobre un dataset/archivo, script batch/cron) con llamadas síncronas,
donde una Batch API con descuento sería aplicable porque la latencia no importa.

## LLM-025 Sequential Independent Calls

**Es:** varias llamadas LLM secuenciales sin dependencia de datos entre ellas → paralelizables (optimiza latencia, no coste).

## LLM-026 Deterministic Computation Delegated to LLM

**Es:** el LLM calcula algo exacto sobre valores ya conocidos (sumas, totales, impuestos, conversiones de unidades,
diferencias de fechas) cuando el código lo haría sin error. **No es:** pedirle al LLM que *explique* un cálculo hecho en
código, ni estimaciones aproximadas sobre texto libre. Clase B (reemplazo mecánico); se bloquea con entrada en texto libre.
**Cambio:** calcular en código (`Decimal` para dinero) y, si hace falta, dejar al LLM solo la redacción.

## LLM-027 Duplicate LLM Calls (solo runtime)

**Es:** en las trazas, la misma petición (mismo `prompt_hash`) se repite dentro de una misma ejecución. Requiere trazas
(`needs={"runtime"}`); sin ellas la regla se salta y el informe lo dice. Clase A (preserva semántica): memoizar por
ejecución. **No es:** muestreo deliberado (self-consistency, temperatura > 0 buscando variedad): queda como riesgo
explícito. Con trazas sintéticas o < 30 llamadas, la evidencia tiene peso bajo.

---

## LLM-000 LLM use justified (DO_NOT_OPTIMIZE)

El auditor también emite conclusiones positivas: pasos donde el LLM está justificado. Lo calcula un post-paso
(`optimization/necessity.py`) que combina evidencia de: tarea abierta (generar, resumir, razonar, conversar), marcadores
de juicio, interpretación de texto libre, validación semántica, agente con herramientas, dominio de riesgo y banda baja
del determinism score. Solo se emite si la combinación es ≥ 0.5 y no hay una recomendación accionable sobre el mismo
paso. Sirve para que el informe muestre que esos pasos **se consideraron** y por qué no se tocan, y para medir falsos
positivos en el golden dataset. Un experimento REJECT también convierte la recomendación en DO_NOT_OPTIMIZE.

## Política para Claude Code (agentes, skills, comandos)

- Subagentes y skills se ejecutan en contextos separados: LLM-005 (contexto repetido) no se aplica entre ellos.
- Una lista explícita de herramientas built-in **restringe** el conjunto por defecto; solo las herramientas `mcp__`
  añaden schemas (LLM-023).
- Copias idénticas del mismo plugin/agente se deduplican (diagnóstico `DUPLICATE_DEFINITION`); copias que divergen
  pueden disparar LLM-006 con la recomendación "quedarse con una versión".
- Guardia `cc_procedure`: cuerpo > 600 tokens, o herramientas que actúan (Bash, Edit, Write, WebFetch, Task…) o
  heredadas en un agente cuya tarea no es mecánica ⇒ no se proponen reglas de reemplazo por código
  (001/003/009/010/011/026). Tener herramientas que actúan no basta para descartar: si el cuerpo describe una
  transformación mecánica y acotada de ficheros o datos, el agente sigue siendo candidato.
- LLM-017 solo cuenta comandos que se leen como pasos, en línea o en bloques de código: se excluyen las cláusulas de
  política o ejemplos ("ONLY", "never", "e.g."), las enumeraciones de comandos permitidos (allowlists) y las utilidades
  de búsqueda sin argumentos. Varios comandos encadenados como secuencia ("A, then B, then C") son pasos, no una
  allowlist.

## Código que no es de producción

Los pasos y recuperaciones en `tests/`, `test/`, `examples/`, `example/` y `docs/`, y en ficheros `test_*.py`,
`*_test.py` o `conftest.py`, se extraen para el grafo, pero sus hallazgos se descartan en la revisión adversarial con el
motivo visible (`non_production_code`). Los notebooks (`.ipynb`) se tratan igual por defecto (`notebooks: exploratory`).
Con `notebooks: production` se auditan como código de producción y con `notebooks: skip` no se leen.

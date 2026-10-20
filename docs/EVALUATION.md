# Evaluación del auditor

Cómo se mide la calidad del propio auditor, qué resultados da y qué limitaciones tienen esas cifras. Todos los
intervalos son de Wilson al 95 %. Con estos tamaños de muestra, las cifras por regla son solo indicativas.

## Qué se mide

Cada fixture es un sistema pequeño (código Python o configuración de Claude Code) con un `expected.yaml` que fija qué
debe decir el auditor sobre cada componente (formato en `docs/GOLDEN_SPEC.md`):

- `present`: debe emitir un hallazgo de esa regla. Si no lo emite, es un falso negativo (FN).
- `absent`: no debe emitirlo. Si lo emite, es un falso positivo (FP). `rule: ANY` prohíbe cualquier hallazgo de
  optimización sobre ese componente.
- `optional`: caso límite; no cuenta.

Métricas:

- **precisión etiquetada**: TP / (TP + FP), solo sobre hallazgos con etiqueta;
- **precisión estricta**: cuenta también como fallos los hallazgos sin etiqueta;
- **recall**: TP / (TP + FN);
- **absent respetado**: proporción de expectativas `absent` que se cumplen;
- **calibración**: Brier y ECE de la confianza frente al acierto.

## Conjuntos

| conjunto | fixtures | uso |
|---|---|---|
| dev + holdout v1 (`tests/golden`, `tests/adversarial`) | 30 | ajuste |
| holdout v2 (`tests/holdout_v2`) | 31 | medido una vez; después, ajuste |
| holdout v3 (`tests/holdout_v3`) | 40 | medido una vez con el código congelado: **la cifra de referencia** |

Cada holdout se prerregistró antes de que existieran sus fixtures (`tests/holdout_v*/PREREGISTRATION.md`). Sus
fixtures los escribieron autores aislados que solo tenían acceso a `docs/RULES.md` y `docs/GOLDEN_SPEC.md`, nunca al
código. Se midió una sola vez, y el análisis de errores se hizo después.

## Resultados

| conjunto | precisión etiquetada | recall | absent respetado | TP / FN / FP |
|---|---|---|---|---|
| ajuste (dev + v1 + v2, 61 fixtures) | 0.99 [0.95, 1.00] | 0.95 [0.90, 0.98] | 0.99 | 106 / 5 / 1 |
| holdout v1 (20) | 0.82 [0.52, 0.95] | 0.32 [0.18, 0.51] | 0.94 | 9 / 19 / 2 |
| holdout v2 (31) | 0.94 [0.81, 0.98] | 0.46 [0.35, 0.58] | 0.98 | 33 / 38 / 2 |
| **holdout v3 (40)** | **0.80 [0.69, 0.88]** | **0.49 [0.39, 0.58]** | **0.90 [0.84, 0.94]** | **52 / 55 / 13** |

La cifra del conjunto de ajuste está inflada por construcción. La que vale para sistemas nuevos es la de holdout v3.

Holdout v3 por familia:

| familia | fixtures | TP / FN / FP | recall | precisión etiquetada |
|---|---|---|---|---|
| sistemas Python | 10 | 22 / 21 / 8 | 0.51 [0.37, 0.65] | 0.73 [0.56, 0.86] |
| adversariales | 20 | 4 / 9 / 2 | 0.31 [0.13, 0.58] | 0.67 [0.30, 0.90] |
| Claude Code | 10 | 26 / 25 / 3 | 0.51 [0.38, 0.64] | 0.90 [0.74, 0.96] |

Calibración en holdout v3: aciertan el 73 % de los hallazgos HYPOTHESIS (44) y el 83 % de los LIKELY (24). Brier
0.20, ECE 0.20.

Hipótesis prerregistradas para holdout v3:

| hipótesis | resultado | veredicto |
|---|---|---|
| precisión etiquetada ≥ 0.85 | 0.80 | no cumplida |
| absent respetado ≥ 0.95 | 0.90 | no cumplida |
| recall > 0.46 | 0.49 | cumplida, pero indicativa (los intervalos se solapan con v2) |
| recall en Claude Code > 0.33 | 0.51 | cumplida, pero indicativa |

## Análisis de errores de holdout v3

**FP (13 etiquetas):**

- 7 son LLM-024 (oportunidad de Batch API) en sistemas que recorren un fichero con llamadas síncronas. Encajan con la
  definición de la regla, pero chocan con etiquetas `ANY absent` cuyos autores solo pensaban en reglas de tarea.
  Además, la regla se informa por paso y no por bucle, lo que multiplica los avisos.
- 2 son colisiones léxicas del perfil de tarea: "work out what…" se toma como cálculo, y la extensión `.json` de un
  nombre de fichero se toma como validación.
- 4 son patrones ya conocidos:
  - historial de un REPL humano tomado como contexto excesivo;
  - un bucle acotado por `while a < X and b < Y` que no se reconoce como acotado;
  - evidencia débil de exceso de herramientas MCP.

**FN (55):**

| causa | FN |
|---|---|
| perfil de tarea: vocabulario no reconocido o colisiones | 38 |
| guardas de las reglas | 11 |
| extracción | 4 |
| defectos del fixture | 2 |

Ejemplos de guardas: LLM-001 descarta agentes de Claude Code con herramientas aunque solo tengan `Read`, y LLM-022 cede
ante LLM-008 en el mismo paso. Ningún FN se debe a la revisión adversarial.

## Robustez

Sin crashes en 10 proyectos reales (9.660 ficheros): openai-agents-python, pydantic-ai, llama_index, langgraph,
autogen, claude-cookbooks, crewAI-examples, claude-agent-sdk-python y dos proyectos locales, uno de ellos una
configuración real de Claude Code.

- Rendimiento sin caché:
  - pocos segundos en proyectos de unos cientos de ficheros;
  - 25–60 s y 0,9–1,8 GB en repos de 1.000–2.000 ficheros Python.
- Los hallazgos son deterministas entre ejecuciones.
- El ruido encontrado en estos repos se corrigió con reglas genéricas y tests, por ejemplo:
  - código de tests y ejemplos;
  - `CLAUDE.md` anidados;
  - REPL humanos;
  - copias de un mismo agente en apps distintas.
- Quedan avisos dudosos de LLM-017 en skills con bloques shell de referencia.

## Declaraciones

- La especificación que vieron los autores de holdout v3 incluía tres aclaraciones (LLM-012, guarda `cc_procedure`,
  LLM-017) que coinciden con lo implementado. Eso puede favorecer al auditor en esos puntos.
- Cambios posteriores a la medición de holdout v3:
  - se corrigió el texto de la nota de LLM-004 en `docs/RULES.md` para que coincida con el código;
  - el auditor ya no recorre `~/.claude/plugins/marketplaces/`, el catálogo de marketplace que Claude Code no carga;
  - un archivo suelto pasado como ruta se clasifica por su ruta completa y, si es otro `.md`, se lee como
    instrucciones.

  Ningún fixture tiene esa carpeta ni se analiza como archivo suelto, así que las cifras no cambian.

## Limitaciones

- Los fixtures son sistemas pequeños escritos para la evaluación. Los de los holdouts los escribieron modelos de
  lenguaje con instrucciones parecidas, así que pueden parecerse entre sí más que el código real.
- El recall en sistemas nuevos ronda 0.5: el auditor encuentra más o menos la mitad de lo etiquetado.
- La confianza es heurística y no está recalibrada.
- No se ha ejecutado ningún experimento contra un modelo real.
- El soporte para Devin, Cursor y `.md` sueltos (`--md-instructions`), y el encargo para el agente (`--for-agent`,
  con su lista de piezas externas), se añadieron después de estas mediciones. Tienen tests unitarios, pero ningún fixture del benchmark los cubre:
  su calidad no está medida. Lo que encuentre el agente con `--for-agent` es su criterio, no una medición.

## Cómo reproducir

```bash
uv run ai-auditor benchmark --split tuning                          # conjunto de ajuste
uv run ai-auditor benchmark --split holdout_v3 --confirm-holdout    # holdout v3
uv run pytest                                                       # tests
```

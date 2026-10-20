# Holdout v2 — pre-registro

Registrado el 2026-10-19, **antes** de que existan los fixtures.

## Por qué

El holdout v1 (`tests/golden`, `tests/adversarial`, split por `sha1(nombre) % 2`) se midió una vez y después se
inspeccionó para analizar errores. Desde ese momento forma parte del conjunto de desarrollo. Para medir la siguiente
iteración hace falta un conjunto que nadie haya visto.

## Protocolo

- **Autoría.** Escriben los fixtures tres subagentes aislados (sistemas Python, casos adversariales y configuraciones
  Claude Code). Solo pueden leer `docs/RULES.md` y `docs/GOLDEN_SPEC.md`. No pueden leer `src/`, ni `tests/` fuera de
  su propio directorio, ni `docs/EVALUATION.md` (que describe debilidades conocidas). Tampoco pueden ejecutar el auditor.
- **Etiquetado.** Las etiquetas siguen las definiciones semánticas de `docs/RULES.md`, con el formato de
  `docs/GOLDEN_SPEC.md`.
- **No inspección.** El autor del auditor no abre estos directorios hasta la medición. Solo se permiten operaciones
  sin contenido, como contar archivos o validar la sintaxis YAML y Python, y si alguna se usa queda declarada.
- **Medición.** Se mide **una vez**, al final de la iteración, con `ai-auditor benchmark --split holdout_v2
  --confirm-holdout`, y el resultado se publica tal cual.
- **Cambios posteriores.** Cualquier cambio de reglas después de medir se declara, y el holdout v2 deja de ser limpio.
- **Conjunto de desarrollo de esta iteración.** Dev v1 más holdout v1, 30 fixtures en total.

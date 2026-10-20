# Holdout v3: prerregistro

Registrado el 2026-10-19, **antes** de que existan los fixtures y antes de cualquier cambio de código de la iteración 3.

## Por qué

Holdout v2 se midió una vez y después se analizaron sus errores. Desde ese momento forma parte del conjunto de ajuste.
La iteración 3 necesita un conjunto que nadie haya visto para poder medirse.

## Conjunto de ajuste de la iteración 3

Lo forman dev, holdout v1 y holdout v2: 61 fixtures, todos ya inspeccionados. Las mejoras se ajustan sobre ellos y
sobre repos reales, nunca sobre holdout v3.

## Especificación congelada

Los fixtures se etiquetan contra `docs/RULES.md` y `docs/GOLDEN_SPEC.md` en el estado que tienen al lanzar a los
autores. Huellas sha256, primeros 16 caracteres:

- `docs/RULES.md`: `d0889562b2999d27`
- `docs/GOLDEN_SPEC.md`: `80a1daaee615c942`

Las aclaraciones hechas en la especificación antes de escribir los fixtures se declaran en `docs/EVALUATION.md`. Si la
especificación cambia durante la iteración, el cambio se declara, y las etiquetas siguen valiendo según la versión
congelada.

## Protocolo

- **Autoría.** Escriben los fixtures cinco subagentes Sonnet aislados:
  - dos escriben sistemas Python;
  - uno escribe casos adversariales;
  - dos escriben configuraciones de Claude Code.

  Solo pueden leer `docs/RULES.md`, `docs/GOLDEN_SPEC.md` y este fichero. No pueden leer `src/`, ni `tests/` fuera de
  su propio directorio, ni `docs/EVALUATION.md`, `docs/ARCHITECTURE.md`, `docs/MODEL_ALLOCATION.md` o `README.md`.
  Tampoco pueden ejecutar el auditor.
- **Tamaño.**
  - 10 sistemas Python, en `tests/holdout_v3/systems`;
  - 20 casos adversariales, en `tests/holdout_v3/adversarial`;
  - 10 configuraciones de Claude Code, en `tests/holdout_v3/claude_code`.

  Claude Code fue la familia más débil de v2 y la de intervalo más ancho, por eso lleva más fixtures que en v2.
- **Diversidad.** Los dominios y tipos de proyecto son distintos de los de v2. Los subagentes no saben qué falló en v2.
- **No inspección.** El autor del auditor no abre estos directorios hasta la medición. Solo se permiten operaciones sin
  contenido, como contar ficheros o validar la sintaxis YAML y Python. Si alguna se usa, queda declarada.
- **Medición.** Se mide **una vez**, al final de la iteración, con
  `ai-auditor benchmark --split holdout_v3 --confirm-holdout`. Antes se registra el hash de `src/`. El resultado se
  publica tal cual.
- **Análisis posterior.** Lo hace un subagente en solo lectura, después de medir.
- **Cambios posteriores.** Cualquier cambio de reglas después de medir se declara, y holdout v3 deja de ser limpio.

## Hipótesis, fijadas antes de cambiar código

| | referencia (holdout v2) | hipótesis para holdout v3 |
|---|---|---|
| precisión etiquetada | 0.94 | ≥ 0.85 |
| recall global | 0.46 [0.35, 0.58] | > 0.46 (estimación puntual) |
| recall en Claude Code | 0.33 | > 0.33 |
| absent respetado | 0.98 | ≥ 0.95 |

Una mejora de recall solo se declarará **demostrada** si el intervalo de Wilson al 95 % de v3 no se solapa con el de
v2. Si se solapan, se declara **indicativa**. Si la precisión etiquetada cae por debajo de 0.85, se considera que los
cambios de la iteración 3 introdujeron falsos positivos, y se informa así aunque el recall suba.

## Limitación conocida

Los holdouts v2 y v3 los escribe la misma familia de modelos (Sonnet) con instrucciones parecidas. Las mejoras
ajustadas sobre v2 pueden generalizar mejor a v3 que a código real, por parecido de estilo. Por eso la robustez sobre
repos reales sigue siendo una comprobación aparte.

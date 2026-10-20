---
name: runbook-migracion-estado
description: Guía la migración de recursos entre estados de Terraform (mover módulos, renombrar recursos, dividir un estado) sin recrear infraestructura. Úsalo cuando haya que reorganizar el código manteniendo los recursos existentes.
allowed-tools: Read, Grep, Bash
---
# Migración de estado

Esta tarea es delicada: un error puede destruir recursos con datos.

1. Entiende el objetivo: qué recursos cambian de dirección, de módulo o de estado. Pide aclaración si el alcance es ambiguo.
2. Haz una copia del estado actual: `terraform state pull > backup.tfstate`.
3. Lista los recursos afectados con `terraform state list` y relaciona cada dirección antigua con la nueva. Si hay recursos con `count` o `for_each`, decide cómo se traducen las claves.
4. Prefiere bloques `moved` cuando el cambio es dentro del mismo estado; usa `terraform state mv` solo si hay que cruzar estados.
5. Ejecuta `terraform plan` y examina cada línea: el plan debe mostrar cero destrucciones. Si aparece alguna, para y analiza por qué la dirección no coincide.
6. Si el plan es limpio, aplica en dev, verifica y repite en staging. Para prod, prepara el comunicado y espera aprobación.
7. Documenta lo que hiciste en `docs/migraciones/`.

Ante la duda entre dos estrategias, explica el compromiso y deja que decida la persona responsable.

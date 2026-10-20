---
name: auditoria-de-dashboard
description: Audita un dashboard de Tableau existente para decidir si sus cifras son fiables, están bien definidas y sirven a la decisión para la que se creó. Úsalo ante dudas del tipo "este dashboard no cuadra".
allowed-tools: Read, Grep, Glob, Bash(dbt compile:*)
---

# Auditoría de dashboard

Un dashboard puede estar técnicamente correcto y aun así llevar a malas decisiones. Esta auditoría evalúa ambas cosas.

## Pasos

1. Pregunta (o deduce de la documentación) quién usa el dashboard y qué decisión toma con él. Sin esto, no se puede juzgar la utilidad.
2. Lista cada indicador visible y localiza su definición en `metricas/catalogo.yml` y en el modelo dbt de origen. Marca los indicadores sin definición oficial.
3. Compara la lógica del modelo con la definición: filtros que excluyen filas, joins que pueden duplicar, tratamiento de nulos, zonas horarias.
4. Revisa la frescura: cuándo se actualizó por última vez la tabla de origen y si el dashboard dice la fecha de corte.
5. Busca inconsistencias entre hojas del mismo dashboard (mismo KPI con cifras distintas) y explica la causa probable.
6. Evalúa la presentación: escalas que exageran diferencias, ejes truncados, comparaciones sin contexto, exceso de indicadores.
7. Resume en tres niveles (crítico, importante, menor) con una recomendación concreta para cada hallazgo y tu grado de certeza.

No cambies nada en producción.

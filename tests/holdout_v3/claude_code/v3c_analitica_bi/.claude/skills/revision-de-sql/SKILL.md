---
name: revision-de-sql
description: Revisa consultas SQL de BigQuery buscando errores lógicos, duplicación por joins y costes de escaneo excesivos.
---

Lee la consulta completa y reconstruye qué granularidad tiene cada CTE. Busca joins que multiplican filas, agregaciones sobre columnas ya agregadas, ventanas sin `ORDER BY` determinista y filtros de partición ausentes. Estima el coste de bytes escaneados y propón reescrituras que mantengan el resultado idéntico, explicando por qué lo mantienen.

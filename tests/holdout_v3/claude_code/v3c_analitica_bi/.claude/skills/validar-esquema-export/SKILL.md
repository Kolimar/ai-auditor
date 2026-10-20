---
name: validar-esquema-export
description: Comprueba que un CSV exportado de Tableau cumple el esquema esperado (columnas, tipos y rangos) antes de cargarlo.
allowed-tools: Read
---

# Validar esquema de exportación

Para el CSV que indique el usuario comprueba:

- Existen las columnas `fecha`, `region`, `canal`, `importe`, `unidades`, en este orden.
- `fecha` tiene formato `aaaa-mm-dd`.
- `importe` es un número decimal con punto, mayor o igual que 0.
- `unidades` es un entero entre 0 y 100000.
- `region` es un valor de `metricas/regiones.txt`.

Devuelve la lista de filas que incumplen cada condición, o `ESQUEMA OK`.

# Espacio de trabajo de analítica

Equipo de BI de finanzas y comercial. Almacén en BigQuery (proyecto `acme-bi`), modelos con dbt, dashboards en Tableau.

## Convenciones

- Las tablas de hechos empiezan por `fct_`, las dimensiones por `dim_`.
- Las fechas se guardan en UTC; los informes se muestran en hora de Madrid.
- Ningún dato personal sale del almacén. Si una consulta devuelve emails o DNI, avisa al usuario y no los copies a ficheros.
- Las métricas oficiales están definidas en `metricas/catalogo.yml`. No inventes definiciones nuevas: si falta una, pregunta.

## Entorno

- `dbt` ya está configurado con el perfil `bi_prod` (solo lectura) y `bi_dev`.
- Los notebooks viven en `notebooks/` y no se ejecutan en producción.

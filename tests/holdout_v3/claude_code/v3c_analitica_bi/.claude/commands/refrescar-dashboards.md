---
description: Refresca los modelos y los extractos de Tableau
allowed-tools: Bash
---

Ejecuta lo siguiente en orden:

```bash
dbt run --select marts --target bi_prod
dbt test --select marts --target bi_prod
python scripts/refresh_tableau.py --workbook ventas_semanal
```

Cuando termine, muestra la salida de cada paso.

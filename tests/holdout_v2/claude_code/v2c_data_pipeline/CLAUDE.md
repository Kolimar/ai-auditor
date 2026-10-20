# Data platform

Airflow 2.9 DAGs in `dags/`, dbt project in `warehouse/`, BigQuery as the warehouse. Python 3.11, managed with uv.

- Run `uv run pytest dags/tests` before touching a DAG.
- dbt: `cd warehouse && dbt build --select state:modified+`.
- Staging tables are `stg_*`, marts are `mart_*`.

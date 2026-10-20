---
name: backfill-partition
description: Backfill one date of the orders pipeline.
allowed-tools: Bash
---
Given a date D (YYYY-MM-DD):

1. `airflow dags backfill ingest_orders -s D -e D --reset-dagruns -y`
2. `cd warehouse && dbt run --select stg_orders+ --vars '{run_date: D}'`
3. `cd warehouse && dbt test --select stg_orders+`
4. `bq query --use_legacy_sql=false "select count(*) from mart.orders where order_date = 'D'"`

Print the count from step 4.

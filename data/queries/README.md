# Stage 1 input CSV folder

Put Stage 1 batch input CSV files here.

Required columns:

- `query_id`
- `original_sql`

Example filename:

- `tpch10_stage1_input.csv`

Example row format:

```csv
query_id,original_sql
1,SELECT * FROM t WHERE a > 1
```

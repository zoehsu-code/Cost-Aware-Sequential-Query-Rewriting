# Baseline folder

Place your baseline CSV here.

Expected default file path for the offline greedy-backward script:

`baseline/baseline.csv`

Minimum required columns:

- `original_sql`
- `rewritten_sql`
- `query_id` (recommended for robust join with Stage1)

Run:

```bash
python -m scripts.run_stage2_greedy_backward \
  --input-csv baseline/baseline.csv \
  --stage1-csv outputs/stage1/stage1_results.csv \
  --output-csv baseline/baseline_reranked.csv \
  --benchmark tpch \
  --rewrite-jar-path build/single_rule_rewriter.jar
```

Rule set source:

- Rule set is read from Stage1 CSV (not baseline CSV).
- Matching order:
  1) `query_id` (if available in both files)
  2) fallback to `original_sql`

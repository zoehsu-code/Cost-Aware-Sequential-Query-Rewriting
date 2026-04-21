# Sequential Rule Scheduling for Query Rewrite

This repository uses a two-stage workflow:
- **Stage 1**: an LLM selects candidate rewrite rules for each query.
- **Stage 2**: runs `llm_sequence` evaluation and `greedy-backward` reranking/evaluation.

---

## 1) Environment setup

Use either setup method below.

### Option A: `requirements.txt` (venv + pip)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Option B: `environment.yml` (conda)

```bash
conda env create -f environment.yml
conda activate query-rewrite
```

---

## 2) Input CSV requirements (Stage 1)

Recommended input location:

```bash
data/queries/stage1_input.csv
```

Minimum required columns:

```csv
query_id,original_sql
1,SELECT * FROM t WHERE a > 1
2,SELECT c FROM t2 WHERE c IS NOT NULL
```

Run Stage 1:

```bash
python -m scripts.run_stage1 \
  --input-csv data/queries/stage1_input.csv \
  --max-rules 5 \
  --include-empty \
  --save-csv \
  --llm-model @azure-1/gpt-4o \
  --prompt-version v1 \
  --api-base-url https://genai.vocareum.com/v1 \
  --output-dir outputs/stage1 \
  --rule-library rule_library/standard.txt
```

Optional (online mode key):

```bash
export VOC_API_KEY="<your_api_key>"
```

---

## 3) Stage 1 outputs

Recommended output directory: `outputs/stage1`

- Per-query JSON: `outputs/stage1/json/<query_id>.json`
- Consolidated CSV: `outputs/stage1/stage1_results.csv`

---

## 4) Stage 2 input + run commands

Stage 2 can read from either source:

- `stage1` (default): `outputs/stage1/stage1_results.csv`
- `baseline`: `baseline/stage1_results.csv`

You can always override both with:

- `--stage1-csv <path>` (highest priority)

### Accepted rule columns when loading Stage 2 input

Stage 2 accepts either of these columns for rule candidates:
- `candidate_rules` (Stage 1 format)
- `rule_set` / `ruleset` (baseline-compatible fallback)

`candidate_rules`/`rule_set` can be:
- JSON list (recommended), e.g. `["RULE_A", "RULE_B"]`
- delimiter-separated text, e.g. `RULE_A,RULE_B`

### Run `llm_sequence`

From Stage 1 output (default):

```bash
python -m scripts.run_stage2_llm_sequence \
  --input-source stage1 \
  --output-csv outputs/stage2/llm_sequence.csv \
  --benchmark tpch
```

From baseline CSV:

```bash
python -m scripts.run_stage2_llm_sequence \
  --input-source baseline \
  --baseline-csv baseline/stage1_results.csv \
  --output-csv outputs/stage2/llm_sequence.csv \
  --benchmark tpch
```

### Run `greedy-backward` (recommended for baseline comparison)

`greedy-backward` reads:
- baseline rewritten results from `--input-csv` (default: `baseline/baseline.csv`)
- candidate/recommended rule sets from `--stage1-csv` (default: `outputs/stage1/stage1_results.csv`)

```bash
python -m scripts.run_stage2_greedy_backward \
  --input-csv baseline/baseline.csv \
  --stage1-csv outputs/stage1/stage1_results.csv \
  --output-csv outputs/stage2/greedy_backward.csv \
  --benchmark tpch \
  --rewrite-jar-path build/single_rule_rewriter.jar
```

If Stage 1 was generated from baseline rule sets, replace `--stage1-csv` with your baseline-compatible Stage 1 CSV path.

### Baseline comparison note

LLM rule selection is stochastic. Running baseline and this project independently may produce different rule sets.
For a fair comparison, place baseline output under `baseline/` and run Stage 2 with baseline-compatible inputs (`--input-source baseline` for `llm_sequence`, and matching `--input-csv` + `--stage1-csv` for `greedy-backward`) so both pipelines use the same rule set.

---

## 5) Stage 2 outputs

Recommended output directory: `outputs/stage2`

- `outputs/stage2/llm_sequence.csv`
- `outputs/stage2/greedy_backward.csv`

---

## Appendix: common Stage 2 options

```bash
python -m scripts.run_stage2_llm_sequence --help
python -m scripts.run_stage2_greedy_backward --help
```

Common options:
- `--benchmark {tpch,tpchj}` (default: `tpch`)
- `--rewrite-jar-path`
- `--runs`
- `--warmup-runs`

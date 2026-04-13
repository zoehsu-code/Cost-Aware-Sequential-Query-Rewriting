# Sequential Rule Scheduling for Query Rewrite

## 1) Project overview / structure

This repository is for query rewrite research with a two-stage workflow:

- **Stage 1**: LLM selects a query-specific candidate rule pool from Calcite rules.
- **Stage 2**: scheduler/executor applies rules sequentially (research modules exist, full pipeline wiring is still evolving).

Current key folders:

- `src/llm/` — Stage 1 candidate generation (`stage1_candidate_generation.py`).
- `src/rules/` — rule parsing, applicability, execution helpers.
- `src/schedulers/` — `greedy`, `bandit`, `lookahead` strategy modules.
- `src/pipeline/` — orchestration stubs (`orchestrator.py`, `run_rewrite.py`).
- `rule_library/` — canonical rules (`standard.txt`) + Java mapping self-check.
- `tests/` — unit tests (includes Stage 1 tests).
- `configs/` — currently only `__init__.py` (no runnable `*.yaml` config yet).

Important output from Stage 1:

- `outputs/stage1/<query_id>.json` (strict machine-readable artifact)
- `outputs/stage1/<query_id>.csv` (single-row inspection sidecar when enabled)

---

## 2) How to run (start from environment setup)

### Step 0: create environment

#### Option A: Conda (recommended)

```bash
conda env create -f environment.yml
conda activate query-rewrite
```

#### Option B: pip + venv

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

> Note: if you want to run Java self-check (`RuleMappingSelfCheck.java`) with pip route, install JDK + Maven separately.

### Step 1: run tests (recommended first)

```bash
pytest -q
```

### Step 2: run Stage 1 generator (CLI)

#### Option A: online mode (real LLM API)

Set API key first:

```bash
export OPENAI_API_KEY="<your_api_key>"
```

Then run:

```bash
python -m scripts.run_stage1 \
  --query-id q_001 \
  --original-sql "SELECT * FROM t WHERE a > 1" \
  --max-rules 5 \
  --include-empty \
  --save-csv \
  --llm-model gpt-4.1-mini \
  --prompt-version v1 \
  --output-dir outputs/stage1 \
  --rule-library rule_library/standard.txt
```

#### Option B: offline mode (no AI API needed)

If you do not have ChatGPT/OpenAI API access, run with `--llm-mode offline`:

```bash
python -m scripts.run_stage1 \
  --query-id q_001 \
  --original-sql "SELECT * FROM t WHERE a > 1" \
  --max-rules 5 \
  --include-empty \
  --save-csv \
  --llm-mode offline \
  --output-dir outputs/stage1 \
  --rule-library rule_library/standard.txt
```

This command prints Stage 1 JSON and writes:

- `outputs/stage1/q_001.json`
- `outputs/stage1/q_001.csv`

Batch mode (CSV input) is also supported. You can place the file anywhere (recommended:
`data/queries/stage1_input.csv`) and pass it with `--input-csv`.
Repository now includes:

- `data/queries/README.md`
- `data/queries/stage1_input_template.csv`

Example input CSV:

```csv
query_id,original_sql
q_001,SELECT * FROM t WHERE a > 1
q_002,SELECT c FROM t2 WHERE c IS NOT NULL
```

Run batch command:

```bash
python -m scripts.run_stage1 \
  --input-csv data/queries/stage1_input.csv \
  --max-rules 5 \
  --include-empty \
  --save-csv \
  --llm-mode offline \
  --output-dir outputs/stage1 \
  --rule-library rule_library/standard.txt
```

### Where API is configured

- CLI params:
  - `--api-base-url` (default `https://api.openai.com/v1`)
  - `--api-key-env-var` (default `OPENAI_API_KEY`)
  - `--llm-mode` (`openai` or `offline`)
- Config object: `Stage1Config.api_base_url`, `Stage1Config.api_key_env_var`
- HTTP client implementation: `src/llm/openai_compatible_client.py`

### Step 3: (optional) validate rule mapping with Java self-check

```bash
javac -d . rule_library/java/RuleMappingSelfCheck.java
java -cp .:<your_calcite_classpath> rulecheck.RuleMappingSelfCheck rule_library/standard.txt
```

For classpath generation details, see `rule_library/README.md`.

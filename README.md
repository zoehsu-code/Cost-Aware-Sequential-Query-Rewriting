# Sequential Rule Scheduling for Query Rewrite

This README is intentionally minimal and focuses only on the Stage 1 runbook.

## 1) Project overview and pipeline

This repository uses a two-stage rewrite workflow:

- **Stage 1 (current runnable part):** LLM selects a query-specific candidate rule pool from `rule_library/standard.txt` and writes JSON files under `outputs/stage1/json/` plus one consolidated CSV.
- **Stage 2:** scheduler/executor applies selected rules sequentially (separate module, not covered by this README runbook).

Pipeline:

1. Prepare runtime environment.
2. Run rule mapping self-check (`standard.txt` -> Calcite rule holders).
3. Run Stage 1 with input query CSV.
4. Get per-query outputs in `outputs/stage1/json/` and summary CSV in `outputs/stage1/`.

---

## 2) How to run

### Step 0: configure environment

#### Option A: Conda

```bash
conda env create -f environment.yml
conda activate query-rewrite
```

#### Option B: venv + pip

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

---

### Step 1: rule check (`standard.txt`)

Compile checker:

```bash
javac -d . rule_library/java/RuleMappingSelfCheck.java
```

Run checker (replace `<your_calcite_classpath>`):

```bash
java -cp .:<your_calcite_classpath> rulecheck.RuleMappingSelfCheck rule_library/standard.txt
```

If you need Maven to generate classpath:

```bash
mvn -f /tmp/calcite-check-pom.xml \
  org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath \
  -Dmdep.outputFile=/tmp/calcite.cp
CP=$(cat /tmp/calcite.cp)
java -cp ".:${CP}" rulecheck.RuleMappingSelfCheck rule_library/standard.txt
```

---

### Step 2: prepare query input CSV

Put your query file anywhere, e.g.:

```bash
data/queries/stage1_input.csv
```

Required columns:

```csv
query_id,original_sql
1,SELECT * FROM t WHERE a > 1
2,SELECT c FROM t2 WHERE c IS NOT NULL
```

---

### Step 3: run Stage 1 from query CSV and output consolidated CSV

Set API key (online mode):

```bash
export VOC_API_KEY="<your_api_key>"
```

Run:

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

You can also pass key directly:

```bash
python -m scripts.run_stage1 \
  --input-csv data/queries/stage1_input.csv \
  --api-base-url https://genai.vocareum.com/v1 \
  --api-key "voc-xxxxxxxx"
```

---

## 3) Output files

For each input row (`query_id`):

- `outputs/stage1/json/<query_id>.json`
- consolidated CSV: `outputs/stage1/stage1_results.csv`

So if your input has 10 queries, output will contain 10 JSON files + 1 CSV file.

---

## 4) Stage 2 (implemented policies: `llm_sequence`, `greedy`)

Stage 2 reads Stage 1 CSV only (no Stage 1 imports), performs real rewrite by calling Java jar, executes SQL on real benchmark (DuckDB TPC-H/TPC-HJ), and writes summary CSV.

### Run llm_sequence

```bash
python -m scripts.run_stage2_llm_sequence \
  --stage1-csv outputs/stage1/stage1_results.csv \
  --output-csv outputs/stage2/llm_sequence.csv \
  --benchmark tpch
```

### Run greedy

```bash
python -m scripts.run_stage2_greedy \
  --stage1-csv outputs/stage1/stage1_results.csv \
  --output-csv outputs/stage2/greedy.csv \
  --benchmark tpch
```

Notes:
- Stage 2 defaults to `tpch`: if `--benchmark` is omitted, `tpch` is used.
- `max_steps` is fixed to `3` in Stage 2.
- Greedy uses early stopping: stop if `best_reward <= 0`.
- Rewrite payload format sent to Java process is JSON array: `[db_id, sql, rule]` (`db_id` is optional in CLI; default is benchmark name).
- If you have your own rewrite engine jar (for example `rewriter_java.jar`), place it under
  `rule_library/calcite_core_main_jar/` and pass it explicitly to avoid auto-discovery ambiguity:

```bash
python -m scripts.run_stage2_llm_sequence \
  --stage1-csv outputs/stage1/stage1_results.csv \
  --output-csv outputs/stage2/llm_sequence.csv \
  --benchmark tpch \
  --rewrite-jar-path rule_library/calcite_core_main_jar/rewriter_java.jar
```

You can also put the jar anywhere else and provide an absolute/relative path via `--rewrite-jar-path`.

Quick check to confirm the command is running on TPC-H:

```bash
python -m scripts.run_stage2_llm_sequence --help
```

In the help output, you should see `--benchmark {tpch,tpchj}` with default `tpch`.

### How reward is computed today

- **Reward is explicitly used only by the `greedy` policy**.  
  For each candidate rewrite at a step, reward is:

  `reward = current_latency - candidate_latency`

  Here latency is the measured trimmed-mean execution time on the benchmark.
  Therefore:
  - `reward > 0`: candidate SQL is faster (positive gain)
  - `reward = 0`: no gain
  - `reward < 0`: candidate SQL is slower

- **`greedy` accepts only the rule with the highest reward at each step**, and stops early when `best_reward <= 0`.

- **`llm_sequence` does not use reward for step-by-step decision making**; it applies the chosen sequence directly.

- In final Stage 2 outputs, the overall gain-related fields are:
  - `improvement_sec = original_trimmed_mean_sec - rewritten_trimmed_mean_sec`
  - `speedup_ratio = original_trimmed_mean_sec / rewritten_trimmed_mean_sec` (when denominator > 0)
- Stage 2 CSV includes `step_rewards` (JSON array) to explicitly record the reward for each accepted step (populated for `greedy`; empty for `llm_sequence`).

### How `is equivalent` is decided

Stage 2 sets `equivalence_result` using `BenchmarkEvaluator.are_equivalent(...)` with this logic:

> This equivalence check is implemented in this repository's Python code (`src/stage2/evaluator.py`), not inside `rewrite.jar`.

1. **Column count must match**. If column counts differ, result is immediately `False`.
2. **Row count must match** (including duplicates). If row counts differ, result is immediately `False`.
3. Each cell is normalized with:
   - `None -> None`
   - `bool -> keep as-is`
   - `int/float/Decimal -> round(float(x), 8)`
   - `bytes -> decode utf-8 (replace errors) and strip`
   - other types -> `str(x).strip()`
4. Each row is converted to a normalized tuple and compared as a multiset (`Counter`).

So this is effectively a **bag-equality check with strict column-count matching**:
- Row order does **not** matter.
- Duplicate rows still matter (multiset semantics).
- If either SQL execution fails, the method returns `False` (no pipeline interruption).

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
- `run_stage2_llm_sequence` uses a larger rewrite timeout by default: `--rewrite-timeout-sec 300`.
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

Rewrite invocation compatibility note:
- Stage 2 sends rewrite payload as JSON array `[db_id, sql, rule]`.
- It first tries **argv mode** (`java ... <main> '<json_payload>'`).
- If that does not produce a valid SQL output, it automatically falls back to **stdin mode** (`java ... <main>` with JSON written to stdin), which matches older wrapper scripts.

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
- You can explicitly feed per-step rewards via optional Stage 1 CSV field `greedy_step_reward_overrides`
  (JSON array of objects), e.g. `[{"R1": 1.2, "R2": -0.1}, {"R2": 0.6}]`.
  At each greedy step, if current rule has an override value, that override is used as reward;
  otherwise it falls back to latency-delta reward.

- **`llm_sequence` does not use reward for step-by-step decision making**; it applies the chosen sequence directly.

- In final Stage 2 outputs, the overall gain-related fields are:
  - `improvement_sec = original_trimmed_mean_sec - rewritten_trimmed_mean_sec`
  - `speedup_ratio = original_trimmed_mean_sec / rewritten_trimmed_mean_sec` (when denominator > 0)
- Stage 2 CSV includes `step_rewards` (JSON array) to explicitly record the reward for each accepted step (populated for `greedy`; empty for `llm_sequence`).
- Stage 2 also prints `final_rule_sequence` and `step_rewards` to stdout for each query during runtime.

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

### How the Stage 2 rewrite process works now

For each input row from Stage 1 CSV, Stage 2 runs this flow:

1. Load `original_sql` and candidate rules from Stage 1 output.
2. Choose a policy:
   - `llm_sequence`: apply rules in recommended order (up to `MAX_STEPS`).
   - `greedy`: at each step, try remaining rules, estimate reward by latency delta, and accept the best positive reward.
3. For each selected rule, call Java rewrite engine (`rewrite.jar`) once via `CalciteRewriter.apply_rule(...)` to produce the next SQL.
4. After policy finishes, run final equivalence check **once** on:
   - `original_sql`
   - final `rewritten_sql`
5. If equivalent, evaluate latency metrics (`original_trimmed_mean_sec`, `rewritten_trimmed_mean_sec`, `speedup_ratio`, `improvement_sec`).
6. Write one output row to Stage 2 CSV (including `final_rule_sequence`, `step_rewards`, and `equivalence_result`), and print per-query progress to stdout.

## 5) Single-rule rewriter CLI (`build/single_rule_rewriter.jar`)

This repository now includes a standalone **single-rule** Calcite rewriter:

- input (stdin JSON array): `[db_id, sql, rule_name]`
- output (stdout): `rewritten_sql` (plain SQL text, not JSON)

### Quick start (copy/paste)

1) Build jar:

```bash
rm -rf build/classes build/fat build/single_rule_rewriter.jar build/manifest.mf
mkdir -p build/classes
javac -cp 'rule_library/calcite_core_main_jar/*' -d build/classes $(rg --files src rule_library/java | rg '\.java$')
mkdir -p build/fat
cp -r build/classes/* build/fat/
for j in rule_library/calcite_core_main_jar/*.jar; do (cd build/fat && jar xf ../../$j); done
rm -f build/fat/META-INF/*.SF build/fat/META-INF/*.DSA build/fat/META-INF/*.RSA
printf 'Main-Class: ruleexec.SingleRuleRewriterMain\n' > build/manifest.mf
jar cfm build/single_rule_rewriter.jar build/manifest.mf -C build/fat .
```

2) Check registry coverage:

```bash
java -cp build/single_rule_rewriter.jar rulecheck.RuleRegistryCoverageCheck rule_library/standard.txt
```

3) Run one rule:

```bash
echo '["tpch","select * from lineitem limit 1","PROJECT_TO_CALC"]' | \
  java -jar build/single_rule_rewriter.jar
```

4) Python call style:

```python
import json, subprocess

payload = json.dumps(["tpch", "select * from lineitem limit 1", "PROJECT_TO_CALC"])
p = subprocess.Popen(
    ["java", "-jar", "build/single_rule_rewriter.jar"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
out, err = p.communicate(payload)
print("returncode:", p.returncode)
print("rewritten_sql:", out.strip())
```

### Why not use current server `/rewrite`

The existing server endpoint is tied to automatic search/optimization flow and is not a strict
`apply_rule(sql, rule_name)` primitive. For policy learning (greedy/bandit/RL/llm_sequence), we need
a deterministic single-rule executor.

### Behavior summary

1. Load schema only from `schemas/<db_id>.json` (`SchemaLoader`).
2. Parse SQL to `RelNode`.
3. Resolve exactly one rule from `RuleRegistry`.
4. Apply exactly one HepPlanner program with that rule.
5. Compare `RelOptUtil.toString(before)` vs `RelOptUtil.toString(after)`:
   - same plan -> no-op, return original SQL
   - different plan -> convert `after` back to SQL and return it
6. On errors, print to stderr and exit non-zero.

### Coverage guarantees for `rule_library/standard.txt`

- `RuleRegistry` has explicit mappings for all rules listed in `rule_library/standard.txt`.
- `RuleRegistryCoverageCheck` validates this strictly and exits code `2` if anything is missing.

### Build

In this environment, Maven plugin download from central may be restricted. A local-jar build is provided:

```bash
rm -rf build/classes build/fat build/single_rule_rewriter.jar build/manifest.mf
mkdir -p build/classes
javac -cp 'rule_library/calcite_core_main_jar/*' -d build/classes $(rg --files src rule_library/java | rg '\.java$')
mkdir -p build/fat
cp -r build/classes/* build/fat/
for j in rule_library/calcite_core_main_jar/*.jar; do (cd build/fat && jar xf ../../$j); done
rm -f build/fat/META-INF/*.SF build/fat/META-INF/*.DSA build/fat/META-INF/*.RSA
printf 'Main-Class: ruleexec.SingleRuleRewriterMain\n' > build/manifest.mf
jar cfm build/single_rule_rewriter.jar build/manifest.mf -C build/fat .
```

### Quick tests

Coverage check:

```bash
java -cp build/single_rule_rewriter.jar rulecheck.RuleRegistryCoverageCheck rule_library/standard.txt
```

Single-rule rewrite:

```bash
echo '["tpch","select * from lineitem limit 1","PROJECT_TO_CALC"]' | \
  java -jar build/single_rule_rewriter.jar
```

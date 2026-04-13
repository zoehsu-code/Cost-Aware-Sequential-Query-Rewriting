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

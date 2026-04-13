 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/README.md b/README.md
index 7c01c8641037dde3272d79e52c1f73b6621b885a..31494ef45978c399b44b9c89d20767a3d2f78589 100644
--- a/README.md
+++ b/README.md
@@ -1,69 +1,115 @@
 # Sequential Rule Scheduling for Query Rewrite
 
-## 1) Project Overview
-- **Problem:** Query rewrite optimization aims to improve SQL execution cost by transforming a query into a semantically equivalent but faster form.
-- **Limitation of existing methods:**
-  - **Fixed-rule pipelines** use static rewrite orders and cannot adapt to query-specific behavior.
-  - **LLM one-shot rewriting** can be brittle, hard to control, and inconsistent in cost reduction.
-- **Our idea:** Model rewriting as a **sequential decision process** where each step chooses the next best rule based on the current rewrite state and observed cost feedback.
-
-## 2) Key Idea
-- **Two-stage pipeline:**
-  - **Stage 1 — Candidate Generation:** Enumerate applicable rewrite actions from the current query state.
-  - **Stage 2 — Rule Scheduling:** Select which candidate to apply next using a scheduling strategy.
-- **Scheduling strategies:**
-  - **Greedy**
-  - **Bandit**
-  - **Lookahead** (primary method)
-
-## 3) Pipeline
-- Core loop:
-  - `state → candidates → scheduler → apply → cost → update`
-- Intuition:
-  - Start from current query state.
-  - Generate valid rewrite candidates.
-  - Scheduler picks the next rule.
-  - Apply rule to get a new query.
-  - Evaluate execution cost.
-  - Update state/history and repeat until stop criteria.
-
-## 4) Repository Structure
-- `configs/` — Experiment and method configuration files.
-- `data/` — Input datasets, query workloads, and metadata.
-- `logs/` — Runtime logs and traces.
-- `outputs/` — Final rewrite results and analysis artifacts.
-- `scripts/` — Helper scripts for setup and experiments.
-- `notebooks/` — Exploratory analysis and visualization notebooks.
-- `docs/` — Project documentation and notes.
-- `tests/` — Unit/integration tests.
-- `src/` — Core implementation.
-  - `pipeline/` — Rewrite loop and orchestration.
-  - `env/` — State, transitions, and environment dynamics.
-  - `schedulers/` — Greedy, Bandit, and Lookahead policies.
-  - `rules/` — Rule library, applicability checks, execution.
-  - `plans/` — Plan parsing and feature extraction.
-  - `db/` — DB connectors and cost interfaces.
-  - `llm/` — Optional LLM-assisted components.
-  - `baselines/` — Baseline methods (fixed order, optional LLM).
-  - `evaluation/` — Metrics and method comparison.
-  - `utils/` — Config and logging utilities.
-
-## 5) How to Run
-- Example command:
+## 1) Project overview and pipeline
+
+This repository uses a two-stage rewrite workflow:
+
+- **Stage 1 (current runnable part):** LLM selects a query-specific candidate rule pool from `rule_library/standard.txt` and writes one JSON + one CSV per query.
+- **Stage 2:** scheduler/executor applies selected rules sequentially (separate module, not covered by this README runbook).
+
+Pipeline:
+
+1. Prepare runtime environment.
+2. Run rule mapping self-check (`standard.txt` -> Calcite rule holders).
+3. Run Stage 1 with input query CSV.
+4. Get per-query outputs in `outputs/stage1/`.
+
+---
+
+## 2) How to run
+
+### Step 0: configure environment
+
+#### Option A: Conda
+
+```bash
+conda env create -f environment.yml
+conda activate query-rewrite
+```
+
+#### Option B: venv + pip
 
 ```bash
-python -m src.main --config configs/lookahead.yaml
+python -m venv .venv
+source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
+pip install -r requirements.txt
 ```
 
-## 6) Methods
-- **Greedy:** Selects the immediate best candidate by current estimated gain.
-- **Bandit:** Balances exploration/exploitation across rewrite rules.
-- **Lookahead (main method):** Estimates multi-step benefit before choosing the next rule.
+---
+
+### Step 1: rule check (`standard.txt`)
+
+Compile checker:
+
+```bash
+javac -d . rule_library/java/RuleMappingSelfCheck.java
+```
+
+Run checker (replace `<your_calcite_classpath>`):
+
+```bash
+java -cp .:<your_calcite_classpath> rulecheck.RuleMappingSelfCheck rule_library/standard.txt
+```
+
+If you need Maven to generate classpath:
+
+```bash
+mvn -f /tmp/calcite-check-pom.xml \
+  org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath \
+  -Dmdep.outputFile=/tmp/calcite.cp
+CP=$(cat /tmp/calcite.cp)
+java -cp ".:${CP}" rulecheck.RuleMappingSelfCheck rule_library/standard.txt
+```
+
+---
+
+### Step 2: prepare query input CSV
+
+Put your query file anywhere, e.g.:
+
+```bash
+data/queries/stage1_input.csv
+```
+
+Required columns:
+
+```csv
+query_id,original_sql
+q_001,SELECT * FROM t WHERE a > 1
+q_002,SELECT c FROM t2 WHERE c IS NOT NULL
+```
+
+---
+
+### Step 3: run Stage 1 from query CSV and output per-query CSV
+
+Set API key (online mode):
+
+```bash
+export OPENAI_API_KEY="<your_api_key>"
+```
+
+Run:
+
+```bash
+python -m scripts.run_stage1 \
+  --input-csv data/queries/stage1_input.csv \
+  --max-rules 5 \
+  --include-empty \
+  --save-csv \
+  --llm-model gpt-4.1-mini \
+  --prompt-version v1 \
+  --output-dir outputs/stage1 \
+  --rule-library rule_library/standard.txt
+```
+
+---
+
+## 3) Output files
+
+For each input row (`query_id`):
 
-## 7) Baselines
-- **Fixed order:** Apply rewrite rules in a predefined static sequence.
-- **LLM-based (optional):** Use an LLM to propose rewrites or rule sequences.
+- `outputs/stage1/<query_id>.json`
+- `outputs/stage1/<query_id>.csv`
 
-## 8) Future Work
-- **RL-based schedulers:** Learn adaptive policies from long-horizon rewards.
-- **Deeper LLM integration:** Use LLMs for candidate proposal, pruning, or policy guidance.
+So if your input has 10 queries, output will contain 10 JSON + 10 CSV files.
 
EOF
)

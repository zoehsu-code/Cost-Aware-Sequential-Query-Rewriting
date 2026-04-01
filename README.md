# Sequential Rule Scheduling for Query Rewrite

## 1) Project Overview
- **Problem:** Query rewrite optimization aims to improve SQL execution cost by transforming a query into a semantically equivalent but faster form.
- **Limitation of existing methods:**
  - **Fixed-rule pipelines** use static rewrite orders and cannot adapt to query-specific behavior.
  - **LLM one-shot rewriting** can be brittle, hard to control, and inconsistent in cost reduction.
- **Our idea:** Model rewriting as a **sequential decision process** where each step chooses the next best rule based on the current rewrite state and observed cost feedback.

## 2) Key Idea
- **Two-stage pipeline:**
  - **Stage 1 — Candidate Generation:** Enumerate applicable rewrite actions from the current query state.
  - **Stage 2 — Rule Scheduling:** Select which candidate to apply next using a scheduling strategy.
- **Scheduling strategies:**
  - **Greedy**
  - **Bandit**
  - **Lookahead** (primary method)

## 3) Pipeline
- Core loop:
  - `state → candidates → scheduler → apply → cost → update`
- Intuition:
  - Start from current query state.
  - Generate valid rewrite candidates.
  - Scheduler picks the next rule.
  - Apply rule to get a new query.
  - Evaluate execution cost.
  - Update state/history and repeat until stop criteria.

## 4) Repository Structure
- `configs/` — Experiment and method configuration files.
- `data/` — Input datasets, query workloads, and metadata.
- `logs/` — Runtime logs and traces.
- `outputs/` — Final rewrite results and analysis artifacts.
- `scripts/` — Helper scripts for setup and experiments.
- `notebooks/` — Exploratory analysis and visualization notebooks.
- `docs/` — Project documentation and notes.
- `tests/` — Unit/integration tests.
- `src/` — Core implementation.
  - `pipeline/` — Rewrite loop and orchestration.
  - `env/` — State, transitions, and environment dynamics.
  - `schedulers/` — Greedy, Bandit, and Lookahead policies.
  - `rules/` — Rule library, applicability checks, execution.
  - `plans/` — Plan parsing and feature extraction.
  - `db/` — DB connectors and cost interfaces.
  - `llm/` — Optional LLM-assisted components.
  - `baselines/` — Baseline methods (fixed order, optional LLM).
  - `evaluation/` — Metrics and method comparison.
  - `utils/` — Config and logging utilities.

## 5) How to Run
- Example command:

```bash
python -m src.main --config configs/lookahead.yaml
```

## 6) Methods
- **Greedy:** Selects the immediate best candidate by current estimated gain.
- **Bandit:** Balances exploration/exploitation across rewrite rules.
- **Lookahead (main method):** Estimates multi-step benefit before choosing the next rule.

## 7) Baselines
- **Fixed order:** Apply rewrite rules in a predefined static sequence.
- **LLM-based (optional):** Use an LLM to propose rewrites or rule sequences.

## 8) Future Work
- **RL-based schedulers:** Learn adaptive policies from long-horizon rewards.
- **Deeper LLM integration:** Use LLMs for candidate proposal, pruning, or policy guidance.

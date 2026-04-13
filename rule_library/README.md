# Rule Library & Self-Check

This folder centralizes the Stage 1/Stage 2 rewrite action space.

- `standard.txt`: canonical rule-name pool used by Stage 1 candidate generation.
- `java/RuleMappingSelfCheck.java`: mapping self-check helper that can validate each
  rule name against Calcite rule instances (`CoreRules`/`PruneEmptyRules`) in your
  Calcite runtime.

## Quick run (Option 1)

> Goal: guarantee every rule in `standard.txt` is executable in Calcite.

```bash
# 1) compile checker
javac -d . rule_library/java/RuleMappingSelfCheck.java

# 2) run checker (IMPORTANT: classpath must include calcite-core + transitive deps)
java -cp .:<your_calcite_classpath> rulecheck.RuleMappingSelfCheck rule_library/standard.txt
```

## Pass/Fail criteria (hard gate)

- **PASS**: summary ends with `MISSING: 0`
- **FAIL**: any `[MISSING]` exists (or summary `MISSING > 0`)

If not pass, `standard.txt` must be fixed before running Stage 1/Stage 2 pipeline.

## Notes

- `standard.txt` may include category header lines like `rule_agg`; these are ignored by loaders.
- `EMPTY` is **not** part of `standard.txt`; it is a reserved Stage 1 stop/no-op action.

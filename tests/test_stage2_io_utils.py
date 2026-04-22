from pathlib import Path

from src.stage2.io_utils import read_stage1_csv


def test_read_stage1_csv_accepts_rule_set_json(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "query_id,original_sql,rule_set,llm_recommended_order\n"
        "q1,SELECT 1,\"[\"\"RULE_A\"\",\"\"RULE_B\"\"]\",\"[\"\"RULE_B\"\"]\"\n",
        encoding="utf-8",
    )

    rows = read_stage1_csv(csv_path)

    assert len(rows) == 1
    assert rows[0].candidate_rules == ["RULE_A", "RULE_B"]
    assert rows[0].llm_recommended_order == ["RULE_B"]


def test_read_stage1_csv_accepts_ruleset_delimited(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text(
        "query_id,original_sql,ruleset\n"
        "q2,SELECT 2,RULE_X|RULE_Y\n",
        encoding="utf-8",
    )

    rows = read_stage1_csv(csv_path)

    assert len(rows) == 1
    assert rows[0].candidate_rules == ["RULE_X", "RULE_Y"]
    assert rows[0].llm_recommended_order == []

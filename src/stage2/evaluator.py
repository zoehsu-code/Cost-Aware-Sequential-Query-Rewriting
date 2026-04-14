"""Real SQL evaluator for TPC-H / TPC-HJ benchmarks."""

from __future__ import annotations

import math
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path


class BenchmarkEvaluator:
    """Execute SQL against a real DuckDB benchmark and report latencies/equivalence."""

    def __init__(
        self,
        *,
        benchmark: str,
        database_path: Path | None = None,
        tpch_scale_factor: float = 1.0,
        tpchj_init_sql: Path | None = None,
    ) -> None:
        import duckdb

        self.benchmark = benchmark.lower()
        self.database_path = database_path
        self.tpch_scale_factor = tpch_scale_factor
        self.tpchj_init_sql = tpchj_init_sql

        db_path = str(database_path) if database_path else ":memory:"
        self.conn = duckdb.connect(db_path)
        self._prepare_benchmark()

    def _prepare_benchmark(self) -> None:
        if self.benchmark == "tpch":
            self.conn.execute("INSTALL tpch")
            self.conn.execute("LOAD tpch")
            self.conn.execute(f"CALL dbgen(sf={self.tpch_scale_factor})")
            return

        if self.benchmark == "tpchj":
            if self.tpchj_init_sql is None:
                raise ValueError("tpchj benchmark requires --tpchj-init-sql")
            script = self.tpchj_init_sql.read_text(encoding="utf-8")
            self.conn.execute(script)
            return

        raise ValueError("benchmark must be either 'tpch' or 'tpchj'")

    def execute_query(self, sql: str) -> tuple[list[str], list[tuple]]:
        cursor = self.conn.execute(sql)
        columns = [item[0] for item in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def trimmed_mean_latency_sec(
        self,
        sql: str,
        *,
        runs: int,
        warmup_runs: int,
        trim_ratio: float = 0.2,
    ) -> float:
        if runs <= 0:
            raise ValueError("runs must be > 0")
        if warmup_runs < 0:
            raise ValueError("warmup_runs must be >= 0")

        for _ in range(warmup_runs):
            self.conn.execute(sql).fetchall()

        samples: list[float] = []
        for _ in range(runs):
            start = time.perf_counter()
            self.conn.execute(sql).fetchall()
            samples.append(time.perf_counter() - start)

        sorted_samples = sorted(samples)
        trim_count = math.floor(len(sorted_samples) * trim_ratio)
        if 2 * trim_count >= len(sorted_samples):
            return sum(sorted_samples) / len(sorted_samples)
        trimmed = sorted_samples[trim_count : len(sorted_samples) - trim_count]
        return sum(trimmed) / len(trimmed)

    @staticmethod
    def normalize_value(value):
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            return round(float(value), 8)
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace").strip()
        return str(value).strip()

    @classmethod
    def are_equivalent(
        cls,
        original_columns: list[str],
        original_rows: list[tuple],
        rewritten_columns: list[str],
        rewritten_rows: list[tuple],
    ) -> bool:
        if len(original_columns) != len(rewritten_columns):
            return False
        if len(original_rows) != len(rewritten_rows):
            return False

        normalized_original = Counter(
            tuple(cls.normalize_value(value) for value in row) for row in original_rows
        )
        normalized_rewritten = Counter(
            tuple(cls.normalize_value(value) for value in row) for row in rewritten_rows
        )
        return normalized_original == normalized_rewritten

    def are_equivalent_sql(self, original_sql: str, rewritten_sql: str) -> bool:
        try:
            original_columns, original_rows = self.execute_query(original_sql)
            rewritten_columns, rewritten_rows = self.execute_query(rewritten_sql)
        except Exception:
            return False
        return self.are_equivalent(original_columns, original_rows, rewritten_columns, rewritten_rows)

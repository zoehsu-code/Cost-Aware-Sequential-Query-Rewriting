"""Calcite rewriter bridge that calls Java jars via subprocess."""

from __future__ import annotations

import json
import os
import subprocess
import time
import zipfile
from pathlib import Path


class CalciteRewriter:
    """Apply rewrite rules through a real Java subprocess call."""

    def __init__(
        self,
        *,
        jar_path: Path | None = None,
        java_main_class: str | None = None,
        timeout_sec: int = 120,
    ) -> None:
        self.jar_path = jar_path or self._discover_rewrite_jar()
        self.java_main_class = java_main_class or self._discover_main_class(self.jar_path)
        self.timeout_sec = timeout_sec
        self._rewrite_cache: dict[tuple[str, str], tuple[str, float]] = {}

    @staticmethod
    def _main_class_exists_in_jar(jar_path: Path, main_class: str) -> bool:
        class_entry = f"{main_class.replace('.', '/')}.class"
        try:
            with zipfile.ZipFile(jar_path) as archive:
                return class_entry in archive.namelist()
        except Exception:
            return False

    @classmethod
    def _has_runnable_main(cls, jar_path: Path) -> bool:
        main_class = cls._discover_main_class(jar_path)
        if not main_class:
            return False
        return cls._main_class_exists_in_jar(jar_path, main_class)

    @staticmethod
    def _discover_rewrite_jar() -> Path:
        candidates = sorted(Path(".").glob("**/*.jar"))
        if not candidates:
            raise FileNotFoundError("No jar files found in repository")

        priority_names = ["rewrite.jar", "rewriter_java.jar", "calcite.core.main.jar", "equitas.jar"]
        by_name = {path.name.lower(): path for path in candidates}
        for name in priority_names:
            match = by_name.get(name)
            if match and CalciteRewriter._has_runnable_main(match):
                return match

        # Fall back to runnable jars with rewrite-like naming first, then any runnable jar.
        rewrite_like = [
            p
            for p in candidates
            if ("rewrite" in p.name.lower() or "rewriter" in p.name.lower())
            and CalciteRewriter._has_runnable_main(p)
        ]
        if rewrite_like:
            return rewrite_like[0]

        runnable = [p for p in candidates if CalciteRewriter._has_runnable_main(p)]
        if runnable:
            return runnable[0]

        # Final fallback keeps previous behavior so explicit user overrides still work.
        return candidates[0]

    @staticmethod
    def _discover_main_class(jar_path: Path) -> str | None:
        try:
            with zipfile.ZipFile(jar_path) as archive:
                manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8", errors="ignore")
        except Exception:
            return None

        for line in manifest.splitlines():
            if line.lower().startswith("main-class:"):
                main_class = line.split(":", 1)[1].strip()
                if CalciteRewriter._main_class_exists_in_jar(jar_path, main_class):
                    return main_class
                return None
        return None

    def _build_java_cmd(self, payload: str) -> list[str]:
        if self.java_main_class:
            jar_dir = self.jar_path.parent
            classpath = os.pathsep.join(str(p) for p in sorted(jar_dir.glob("*.jar")))
            return ["java", "-cp", classpath, self.java_main_class, payload]
        return ["java", "-jar", str(self.jar_path), payload]

    @staticmethod
    def _parse_rewrite_stdout(stdout_text: str) -> str:
        lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("Rewrite command returned empty stdout")
        last = lines[-1]
        try:
            parsed = json.loads(last)
            if isinstance(parsed, dict):
                for key in ("rewritten_sql", "sql", "result"):
                    value = parsed.get(key)
                    if isinstance(value, str) and value.strip():
                        return value
            if isinstance(parsed, list) and parsed and isinstance(parsed[0], str):
                return parsed[0]
        except json.JSONDecodeError:
            pass
        return last

    def apply_rule(self, *, db_id: str, sql: str, rule: str) -> tuple[str, float]:
        """Apply one rule to one SQL, returning rewritten SQL and latency."""

        cache_key = (sql, rule)
        if cache_key in self._rewrite_cache:
            return self._rewrite_cache[cache_key]

        payload = json.dumps([db_id, sql, rule], ensure_ascii=False)
        cmd = self._build_java_cmd(payload)

        start = time.perf_counter()
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_sec,
        )
        elapsed = time.perf_counter() - start

        if completed.returncode != 0:
            raise RuntimeError(
                f"Rewrite subprocess failed (code={completed.returncode}): {completed.stderr.strip()}"
            )

        rewritten_sql = self._parse_rewrite_stdout(completed.stdout)
        self._rewrite_cache[cache_key] = (rewritten_sql, elapsed)
        return rewritten_sql, elapsed

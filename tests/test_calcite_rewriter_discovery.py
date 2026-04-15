from __future__ import annotations

import zipfile
from types import SimpleNamespace
from pathlib import Path

from src.stage2.calcite_rewriter import CalciteRewriter


def _make_fake_jar(path: Path, *, main_class: str | None, include_main_class_file: bool) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        if main_class is None:
            archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
            return

        archive.writestr(
            "META-INF/MANIFEST.MF",
            "Manifest-Version: 1.0\n" f"Main-Class: {main_class}\n",
        )
        if include_main_class_file:
            archive.writestr(f"{main_class.replace('.', '/')}.class", b"\xCA\xFE\xBA\xBE")


def test_discover_main_class_rejects_missing_class_file(tmp_path: Path) -> None:
    jar_path = tmp_path / "bad.jar"
    _make_fake_jar(jar_path, main_class="com.example.DoesNotExist", include_main_class_file=False)

    assert CalciteRewriter._discover_main_class(jar_path) is None


def test_discover_main_class_accepts_existing_class_file(tmp_path: Path) -> None:
    jar_path = tmp_path / "good.jar"
    _make_fake_jar(jar_path, main_class="com.example.Main", include_main_class_file=True)

    assert CalciteRewriter._discover_main_class(jar_path) == "com.example.Main"


def test_discover_rewrite_jar_prefers_runnable_priority_jar(tmp_path: Path, monkeypatch) -> None:
    bad_equitas = tmp_path / "equitas.jar"
    good_calcite = tmp_path / "calcite.core.main.jar"
    _make_fake_jar(
        bad_equitas,
        main_class="com.example.MissingMain",
        include_main_class_file=False,
    )
    _make_fake_jar(good_calcite, main_class="com.example.RealMain", include_main_class_file=True)

    monkeypatch.chdir(tmp_path)
    discovered = CalciteRewriter._discover_rewrite_jar()

    assert discovered.name == "calcite.core.main.jar"


def test_apply_rule_falls_back_to_stdin_payload_mode(tmp_path: Path, monkeypatch) -> None:
    jar_path = tmp_path / "rewriter_java.jar"
    _make_fake_jar(jar_path, main_class="com.example.Main", include_main_class_file=True)
    rewriter = CalciteRewriter(jar_path=jar_path, java_main_class="com.example.Main")

    calls: list[tuple[list[str], str | None]] = []

    def _fake_run(cmd, *, input=None, **kwargs):
        calls.append((cmd, input))
        if len(calls) == 1:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=0, stdout="SELECT 1", stderr="")

    monkeypatch.setattr("src.stage2.calcite_rewriter.subprocess.run", _fake_run)

    rewritten_sql, _ = rewriter.apply_rule(db_id="tpch", sql="SELECT 1", rule="PROJECT_TO_CALC")

    assert rewritten_sql == "SELECT 1"
    assert len(calls) == 2
    assert calls[0][1] is None
    assert calls[1][1] is not None

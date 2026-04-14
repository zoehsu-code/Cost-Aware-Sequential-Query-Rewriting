from __future__ import annotations

import zipfile
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

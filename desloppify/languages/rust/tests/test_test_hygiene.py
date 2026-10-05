"""Tests for the Rust test-hygiene detector."""

from __future__ import annotations

from pathlib import Path

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.languages.rust.detectors.test_hygiene import detect_test_hygiene

_MANIFEST = '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n'


def _names(tmp_path: Path, source: str, rel_path: str = "src/lib.rs") -> list[str]:
    (tmp_path / "Cargo.toml").write_text(_MANIFEST)
    target = tmp_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_test_hygiene(tmp_path)
    return [entry["name"] for entry in entries]


def _inline(tests: str) -> str:
    return f"#[cfg(test)]\nmod tests {{\n{tests}}}\n"


def test_sleep_in_inline_test_is_reported(tmp_path):
    source = _inline("    #[test]\n    fn waits() {\n        std::thread::sleep(DELAY);\n    }\n")
    assert _names(tmp_path, source) == ["sleep_in_test::waits"]


def test_sleep_under_paused_tokio_clock_is_not_reported(tmp_path):
    source = _inline(
        "    #[tokio::test(start_paused = true)]\n"
        "    async fn waits() {\n        tokio::time::sleep(DELAY).await;\n    }\n"
    )
    assert _names(tmp_path, source) == []


def test_sleep_in_non_test_helper_is_not_reported(tmp_path):
    source = _inline("    fn helper() {\n        std::thread::sleep(DELAY);\n    }\n")
    assert _names(tmp_path, source) == []


def test_bare_ignore_is_reported(tmp_path):
    source = _inline("    #[test]\n    #[ignore]\n    fn slow() {}\n")
    assert _names(tmp_path, source) == ["ignore_without_reason::slow"]


def test_ignore_with_reason_is_not_reported(tmp_path):
    source = _inline('    #[test]\n    #[ignore = "needs network"]\n    fn slow() {}\n')
    assert _names(tmp_path, source) == []


def test_bare_should_panic_is_reported(tmp_path):
    source = _inline("    #[test]\n    #[should_panic]\n    fn boom() { run(); }\n")
    assert _names(tmp_path, source) == ["should_panic_without_expected::boom"]


def test_should_panic_with_expected_is_not_reported(tmp_path):
    source = _inline(
        '    #[test]\n    #[should_panic(expected = "empty")]\n    fn boom() { run(); }\n'
    )
    assert _names(tmp_path, source) == []


def test_assert_with_top_level_equality_is_reported(tmp_path):
    source = _inline("    #[test]\n    fn adds() {\n        assert!(add(2, 2) == 4);\n    }\n")
    assert _names(tmp_path, source) == ["assert_equality::adds"]


def test_assert_with_nested_or_compound_equality_is_not_reported(tmp_path):
    source = _inline(
        "    #[test]\n    fn checks() {\n"
        "        assert!(items.iter().any(|i| i.id == 1));\n"
        "        assert!(a.ok && a.hp == 3);\n"
        "        assert!(a <= b);\n"
        "    }\n"
    )
    assert _names(tmp_path, source) == []


def test_integration_test_file_is_scanned_whole(tmp_path):
    source = "#[test]\n#[ignore]\nfn slow() {}\n"
    assert _names(tmp_path, source, "tests/api.rs") == ["ignore_without_reason::slow"]


def test_test_attribute_outside_test_module_in_src_is_not_scanned(tmp_path):
    source = "fn waits() {\n    std::thread::sleep(DELAY);\n}\n"
    assert _names(tmp_path, source) == []

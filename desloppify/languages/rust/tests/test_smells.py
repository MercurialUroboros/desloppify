"""Tests for Rust-specific code smell detectors."""

from __future__ import annotations

from pathlib import Path

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.languages.rust.detectors.smells import detect_smells


def _write(path: Path, rel_path: str, content: str) -> Path:
    target = path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return target


def _entry(entries: list[dict], smell_id: str) -> dict:
    return next(entry for entry in entries if entry["id"] == smell_id)


def test_detect_smells_reports_pub_use_glob(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub use crate::internal::*;\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, total_files = detect_smells(tmp_path)

    assert total_files == 1
    smell = _entry(entries, "pub_use_glob")
    assert smell["count"] == 1
    assert smell["matches"] == [
        {
            "file": "src/lib.rs",
            "line": 1,
            "content": "pub use crate::internal::*;",
        }
    ]


def test_detect_smells_ignores_restricted_glob_reexports(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub(crate) use crate::internal::*;\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "pub_use_glob" not in {entry["id"] for entry in entries}


def test_detect_smells_reports_result_unit_err(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn parse() -> Result<u32, ()> { Ok(1) }\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "result_unit_err")
    assert smell["count"] == 1
    assert smell["matches"][0]["line"] == 1


def test_detect_smells_reports_string_error(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn parse() -> Result<u32, String> { Err(String::new()) }\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "string_error")
    assert smell["count"] == 1
    assert smell["matches"][0]["line"] == 1


def test_detect_smells_ignores_nested_string_in_result_ok_type(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "\n".join(
            [
                "use std::collections::HashMap;",
                "pub fn parse() -> Result<HashMap<String, String>> { todo!() }",
                "pub fn parse2() -> Result<HashMap<String, String>, MyError> { todo!() }",
            ]
        ),
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert all(entry["id"] != "string_error" for entry in entries)


def test_detect_smells_reports_static_str_error_type(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn parse() -> Result<u32, &'static str> { Err(\"bad\") }\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "string_error")
    assert smell["count"] == 1


def test_detect_smells_reports_static_mut(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "static mut COUNTER: usize = 0;\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "static_mut")
    assert smell["count"] == 1
    assert smell["matches"][0]["content"] == "static mut COUNTER: usize = 0;"


def test_detect_smells_reports_process_exit(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn bail() { std::process::exit(1); }\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "process_exit")
    assert smell["count"] == 1
    assert smell["matches"][0]["line"] == 1


def test_detect_smells_reports_dbg_macro(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn inspect(value: u32) -> u32 { dbg!(value) }\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "dbg_macro")
    assert smell["count"] == 1
    assert smell["matches"][0]["line"] == 1


def test_detect_smells_reports_allow_attr(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "#[allow(dead_code)]\npub fn keep() {}\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "allow_attr")
    assert smell["count"] == 1
    assert smell["matches"][0]["content"] == "#[allow(dead_code)]"


def test_detect_smells_ignores_allow_attr_with_documented_bug_workaround(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "#[allow(clippy::derivable_impls)] // clippy bug: upstream false positive\nimpl Demo {}\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "allow_attr" not in {entry["id"] for entry in entries}


def test_detect_smells_ignores_crate_level_allow_attrs(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "#![allow(dead_code)]\npub fn keep() {}\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "allow_attr" not in {entry["id"] for entry in entries}


def test_detect_smells_ignores_allow_attr_on_imports(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "#[allow(unused_imports)]\nuse alloc::vec::Vec;\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "allow_attr" not in {entry["id"] for entry in entries}


def test_detect_smells_reports_undocumented_unsafe_block(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn read(ptr: *const u8) -> u8 {\n    unsafe { *ptr }\n}\n",
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    smell = _entry(entries, "undocumented_unsafe")
    assert smell["count"] == 1
    assert smell["matches"][0]["line"] == 2
    assert smell["matches"][0]["content"] == "unsafe { *ptr }"


def test_detect_smells_ignores_unsafe_with_safety_comment(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        (
            "pub fn read(ptr: *const u8) -> u8 {\n"
            "    // SAFETY: caller guarantees ptr is valid for reads.\n"
            "    unsafe { *ptr }\n"
            "}\n"
        ),
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "undocumented_unsafe" not in {entry["id"] for entry in entries}


def test_detect_smells_ignores_unsafe_with_utf8_comment_before_block(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        (
            "pub fn read(bytes: &[u8]) -> &str {\n"
            "    // The input is already validated UTF-8.\n"
            "    unsafe { core::str::from_utf8_unchecked(bytes) }\n"
            "}\n"
        ),
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "undocumented_unsafe" not in {entry["id"] for entry in entries}


def test_detect_smells_ignores_unsafe_with_utf8_comment_inside_block(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        (
            "pub fn render(bytes: Vec<u8>) -> String {\n"
            "    let text = unsafe {\n"
            "        // We do not emit invalid UTF-8.\n"
            "        String::from_utf8_unchecked(bytes)\n"
            "    };\n"
            "    text\n"
            "}\n"
        ),
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "undocumented_unsafe" not in {entry["id"] for entry in entries}


def test_detect_smells_ignores_repr_transparent_casts(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(
        tmp_path,
        "src/lib.rs",
        (
            "use core::mem;\n\n"
            "#[repr(transparent)]\n"
            "pub struct RawValue {\n"
            "    inner: str,\n"
            "}\n\n"
            "impl RawValue {\n"
            "    fn from_borrowed(text: &str) -> &Self {\n"
            "        unsafe { mem::transmute::<&str, &RawValue>(text) }\n"
            "    }\n"
            "}\n"
        ),
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)

    assert "undocumented_unsafe" not in {entry["id"] for entry in entries}


def test_detect_smells_only_counts_runtime_source_files(tmp_path):
    _write(
        tmp_path,
        "Cargo.toml",
        '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    _write(tmp_path, "src/lib.rs", "pub fn keep() {}\n")
    _write(tmp_path, "tests/api.rs", "pub fn helper() -> Result<(), ()> { Ok(()) }\n")
    _write(tmp_path, "examples/demo.rs", "pub use demo::*;\n")

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, total_files = detect_smells(tmp_path)

    assert entries == []
    assert total_files == 1


_DEMO_MANIFEST = '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n'


def _smell_lines(tmp_path: Path, source: str, smell_id: str) -> list[int]:
    _write(tmp_path, "Cargo.toml", _DEMO_MANIFEST)
    _write(tmp_path, "src/lib.rs", source)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_smells(tmp_path)
    return [
        match["line"]
        for entry in entries
        if entry["id"] == smell_id
        for match in entry["matches"]
    ]


def test_detect_smells_reports_eager_fallback_allocation(tmp_path):
    source = (
        "fn name(x: Option<String>) -> String {\n"
        '    x.unwrap_or(format!("anon-{}", ID))\n'
        "}\n"
        "fn code(x: Option<u8>) -> Result<u8, Error> {\n"
        "    x.ok_or(Error::Missing)\n"
        "}\n"
    )
    assert _smell_lines(tmp_path, source, "eager_fallback_alloc") == [2]


def test_detect_smells_ignores_lazy_fallback(tmp_path):
    source = 'fn name(x: Option<String>) -> String {\n    x.unwrap_or_else(|| format!("anon"))\n}\n'
    assert _smell_lines(tmp_path, source, "eager_fallback_alloc") == []


def test_detect_smells_reports_todo_without_issue_reference(tmp_path):
    source = (
        "// TODO: tidy this up\n"
        "// TODO(#42): remove after the upstream fix\n"
        'const HINT: &str = "// TODO not a comment";\n'
    )
    assert _smell_lines(tmp_path, source, "untracked_todo") == [1]


def test_detect_smells_skips_inline_test_modules(tmp_path):
    source = (
        "pub fn run() {}\n"
        "#[cfg(test)]\nmod tests {\n"
        "    #[test]\n    fn waits() {\n        std::thread::sleep(DELAY);\n        dbg!(1);\n    }\n"
        "}\n"
    )
    assert _smell_lines(tmp_path, source, "thread_sleep") == []
    assert _smell_lines(tmp_path, source, "dbg_macro") == []

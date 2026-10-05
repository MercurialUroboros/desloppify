"""Tests for the Rust async-runtime detector."""

from __future__ import annotations

from pathlib import Path

from desloppify.base.runtime_state import RuntimeContext, runtime_scope
from desloppify.languages.rust.detectors.async_runtime import detect_async_runtime

_MANIFEST = '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n'


def _names(tmp_path: Path, source: str) -> list[str]:
    (tmp_path / "Cargo.toml").write_text(_MANIFEST)
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "lib.rs").write_text(source)
    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_async_runtime(tmp_path)
    return [entry["name"] for entry in entries]


def test_thread_sleep_in_async_fn_is_reported_at_the_call_line(tmp_path):
    (tmp_path / "Cargo.toml").write_text(_MANIFEST)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text(
        "pub async fn poll() {\n    std::thread::sleep(DELAY);\n}\n"
    )

    with runtime_scope(RuntimeContext(project_root=tmp_path)):
        entries, _ = detect_async_runtime(tmp_path)

    assert [(entry["name"], entry["line"], entry["confidence"]) for entry in entries] == [
        ("blocking_sleep::poll", 2, "high")
    ]


def test_thread_sleep_in_sync_fn_is_not_reported(tmp_path):
    assert _names(tmp_path, "pub fn poll() {\n    std::thread::sleep(DELAY);\n}\n") == []


def test_blocking_call_inside_spawn_blocking_is_not_reported(tmp_path):
    source = (
        "pub async fn load() {\n"
        "    tokio::task::spawn_blocking(|| {\n"
        "        std::thread::sleep(DELAY);\n"
        "        std::fs::read(PATH)\n"
        "    }).await;\n"
        "}\n"
    )
    assert _names(tmp_path, source) == []


def test_block_on_in_async_fn_is_reported(tmp_path):
    source = "async fn run(rt: &Runtime) {\n    rt.block_on(work());\n}\n"
    assert _names(tmp_path, source) == ["nested_block_on::run"]


def test_std_fs_in_async_fn_is_reported_as_blocking_io(tmp_path):
    source = "async fn load() -> Vec<u8> {\n    std::fs::read(PATH).unwrap()\n}\n"
    assert _names(tmp_path, source) == ["blocking_io::load"]


def test_async_fn_in_inline_test_module_is_not_reported(tmp_path):
    source = (
        "#[cfg(test)]\nmod tests {\n"
        "    async fn helper() {\n        std::thread::sleep(DELAY);\n    }\n"
        "}\n"
    )
    assert _names(tmp_path, source) == []


def test_detached_spawn_per_item_is_reported(tmp_path):
    source = (
        "pub async fn fan_out(urls: Vec<String>) {\n"
        "    for url in urls {\n"
        "        tokio::spawn(async move { fetch(url).await });\n"
        "    }\n"
        "}\n"
    )
    assert _names(tmp_path, source) == ["unbounded_spawn::3"]


def test_spawn_loop_with_semaphore_is_not_reported(tmp_path):
    source = (
        "pub async fn fan_out(urls: Vec<String>, limit: Arc<Semaphore>) {\n"
        "    for url in urls {\n"
        "        let permit = limit.clone().acquire_owned().await;\n"
        "        tokio::spawn(async move { fetch(url).await; drop(permit) });\n"
        "    }\n"
        "}\n"
    )
    assert _names(tmp_path, source) == []


def test_spawn_loop_collecting_handles_is_not_reported(tmp_path):
    source = (
        "pub async fn fan_out(urls: Vec<String>) {\n"
        "    let mut handles = Vec::new();\n"
        "    for url in urls {\n"
        "        handles.push(tokio::spawn(async move { fetch(url).await }));\n"
        "    }\n"
        "}\n"
    )
    assert _names(tmp_path, source) == []

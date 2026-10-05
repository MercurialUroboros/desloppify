"""Rust-specific review heuristics and guidance."""

from __future__ import annotations

import re

from desloppify.languages.rust.support import USE_STATEMENT_RE

HOLISTIC_REVIEW_DIMENSIONS: list[str] = [
    "cross_module_architecture",
    "error_consistency",
    "abstraction_fitness",
    "test_strategy",
    "api_surface_coherence",
    "design_coherence",
]

# Distilled from three skills: `rust-best-practices` (Apollo GraphQL's Rust Best
# Practices handbook), `rust-async-patterns` (Tokio) and `rust-testing`. Rules
# that Clippy or the rust_* detectors already report are left out.
REVIEW_GUIDANCE = {
    "patterns": [
        # Ownership and borrowing
        "Flag `.clone()` used to satisfy the borrow checker where a borrow or a lifetime fix works; cloning `Arc`/`Rc`, cheap handles and deliberate snapshots is fine",
        "Flag parameters taking `String`, `Vec<T>`, `&String` or `&Vec<T>` when the body only reads them — take `&str`/`&[T]`; use `Cow<'_, T>` when ownership is only sometimes needed",
        "Flag functions that clone a `&T` argument to get ownership — the signature should ask for the owned value",
        "Flag `Copy` derived on large types (more than ~24 bytes) or on a type that also implements `Iterator`",
        # Option/Result
        "Flag `unwrap`/`expect` in production paths where failure is possible; prefer `?`, `let ... else`, or `unwrap_or*`",
        "Flag `match` blocks that only convert between `Option` and `Result` or re-wrap `Err` — use `.ok()`, `.ok_or_else()`, `.map_err()` and `?`",
        "Flag errors that are logged then dropped, or mapped without context — use `inspect_err` to log and `map_err` to add context before `?`",
        # Errors
        "Flag library crates exposing `anyhow::Result` or `Box<dyn Error>`; use a `thiserror` enum with `#[from]` per layer and keep `anyhow` in binaries",
        "Flag `panic!` used for recoverable conditions; reserve it for bugs, and prefer `unreachable!` with a reason for proven-impossible states",
        # Iterators and allocation
        "Flag intermediate `.collect()` calls whose result is only iterated again or passed on — pass the iterator",
        "Flag index-based loops and manual accumulation where an iterator chain is clearer; keep `for` when the loop needs early exit or side effects",
        "Flag `#[inline]` and other micro-optimizations with no benchmark behind them",
        # Dispatch and types
        "Flag `Box<dyn Trait>` fields and parameters where the concrete type is known — use generics, and box only at API boundaries or for heterogeneous collections",
        "Flag traits with a single implementation that only add indirection",
        "Flag state tracked with runtime booleans or `Option` fields plus `unreachable!` when the type-state pattern would make invalid states uncompilable; do not ask for it on trivial states",
        "Flag helpers that take a `bool` flag to pick between behaviours, and helpers extracted from two coincidentally similar blocks (rule of three)",
        # Lints, comments and docs
        "Flag `#[allow(...)]` without a justification comment; `#[expect(...)]` with a reason is the accepted form",
        "Flag comments that restate the code or narrate steps — extract a named function; keep comments for why (`// SAFETY:`, `// PERF:`, links to ADRs)",
        "Flag public items without `///` docs, fallible public functions without `# Errors`/`# Panics`, and crates without `//!` crate docs",
    ],
    "async": [
        "Flag blocking work inside async functions (`std::thread::sleep`, std file or network I/O, CPU-heavy loops) — use the runtime's async APIs or `spawn_blocking`",
        "Flag `std::sync` or async lock guards held across an `.await`; narrow the scope, clone the data out, or prefer a channel over shared state",
        "Flag tasks spawned per item or per request with no bound — use a `Semaphore`, `buffer_unordered(limit)` or a `JoinSet`",
        "Flag spawned tasks whose `JoinHandle` is dropped and whose errors are never observed; propagate with `?` or log",
        "Flag long-running tasks and loops with no cancellation path — use `tokio::select!` with a `CancellationToken` or shutdown channel",
        "Flag remote calls with no timeout (`tokio::time::timeout`), and error types crossing `spawn`/`.await` that are not `Send + Sync + 'static`",
        "Flag async functions on hot or debuggable paths without `#[tracing::instrument]` when the crate already uses `tracing`",
    ],
    "testing": [
        "Test names should describe behaviour (`process_returns_error_when_input_empty`), not `test_1` or `test_happy_path`; group tests for one unit in a nested `mod`",
        "Flag tests that check several behaviours or carry many unrelated assertions — one behaviour per test, with `rstest` cases for input tables",
        "Flag missing error-path tests: every `Err` variant a public function returns should be exercised, asserted with `matches!`/`assert_matches!` or `to_string()`",
        "Flag `#[should_panic]` where the code could return a `Result` and the test assert `is_err()`",
        "Flag sleeps and timing assumptions in tests — use channels, barriers or `tokio::time::pause()`",
        "Flag test logic hidden in shared helpers; share setup and fixtures, keep each test's action and assertion inline",
        "Flag mocks (`mockall`) standing in for code that an integration test under `tests/` could exercise for real; integration tests cover the public API only",
        "Flag snapshot tests (`insta`) of huge objects, primitives, or unredacted timestamps/ids; flag public APIs without a doc-test example",
    ],
    "auth": [
        "Audit CLI/server entrypoints for permission checks before mutating external state.",
        "Check secret-bearing environment variables and token handling for accidental logging.",
    ],
    "naming": (
        "Rust public APIs should use idiomatic names: `as_*/to_*/into_*`, clear getter "
        "and iterator naming, and trait impls that match standard-library expectations."
    ),
    "refactoring": [
        "Change read-only owned parameters to borrows (`&str`, `&[T]`, `&T`) and delete the caller-side `.clone()`s",
        "Replace `unwrap`/`expect` with `?` and a `thiserror` variant, or `let Some(x) = ... else { return ... }` when the miss is expected",
        "Replace eager fallbacks (`unwrap_or(format!(..))`, `ok_or(Error::new(..))`) with the lazy `_else` form, or `unwrap_or_default()`",
        "Move blocking calls out of async functions with `tokio::task::spawn_blocking`, or switch to `tokio::fs`/`tokio::time::sleep`",
        "Replace detached per-item `tokio::spawn` loops with a `JoinSet`, or `stream::iter(..).buffer_unordered(limit)`",
        "Turn `#[allow(lint)]` into `#[expect(lint)]` with a one-line reason, or fix the lint",
        "Turn `// TODO` comments into issues and reference them: `// TODO(#42): ...`",
        "Unwind a wrong abstraction: inline the helper into its callers, drop the dead branches, then extract only what they really share",
        "Split a test with many assertions into named tests or `#[rstest]` `#[case::name(..)]` rows; replace `assert!(a == b)` with `assert_eq!(a, b)`",
    ],
}

MIGRATION_PATTERN_PAIRS = [
    (
        "thiserror→anyhow boundary drift",
        re.compile(r"\bthiserror::Error\b"),
        re.compile(r"\banyhow::(?:Error|Result|Context)\b"),
    ),
]

MIGRATION_MIXED_EXTENSIONS: set[str] = set()

LOW_VALUE_PATTERN = re.compile(
    r"(?m)^\s*(?:#!\[(?:allow|cfg_attr)|mod\s+tests\s*\{|use\s+super::\*)"
)

_PUB_TYPE_RE = re.compile(
    r"(?m)^\s*pub\s+(?:struct|enum|trait|type)\s+([A-Za-z_]\w*)"
)
_PUB_FN_RE = re.compile(r"(?m)^\s*pub\s+(?:async\s+)?fn\s+([A-Za-z_]\w*)\s*\(")
_IMPL_RE = re.compile(r"(?m)^\s*impl(?:<[^>]+>)?\s+([A-Za-z_]\w*)\s+for\s+([A-Za-z_]\w*)")


def module_patterns(content: str) -> list[str]:
    """Return Rust-specific review markers for a file."""
    stripped = content
    out: list[str] = []
    if USE_STATEMENT_RE.search(stripped):
        out.append("use_declarations")
    if re.search(r"(?m)^\s*pub(?:\([^)]*\))?\s+trait\s+", stripped):
        out.append("public_traits")
    if re.search(r"(?m)^\s*impl(?:<[^>]+>)?\s+(?:From|TryFrom|Into|Iterator)\b", stripped):
        out.append("std_trait_impls")
    if re.search(r"\b(?:unwrap|expect|panic!|todo!|unimplemented!)", stripped):
        out.append("panic_paths")
    return out


def api_surface(file_contents: dict[str, str]) -> dict[str, list[str]]:
    """Summarize public Rust API shape across scanned files."""
    public_types: set[str] = set()
    public_functions: set[str] = set()
    trait_impls: set[str] = set()

    for content in file_contents.values():
        for match in _PUB_TYPE_RE.finditer(content):
            public_types.add(match.group(1))
        for match in _PUB_FN_RE.finditer(content):
            public_functions.add(match.group(1))
        for match in _IMPL_RE.finditer(content):
            trait_impls.add(f"{match.group(2)}::{match.group(1)}")

    return {
        "public_types": sorted(public_types),
        "public_functions": sorted(public_functions),
        "trait_impls": sorted(trait_impls),
    }


__all__ = [
    "HOLISTIC_REVIEW_DIMENSIONS",
    "LOW_VALUE_PATTERN",
    "MIGRATION_MIXED_EXTENSIONS",
    "MIGRATION_PATTERN_PAIRS",
    "REVIEW_GUIDANCE",
    "api_surface",
    "module_patterns",
]

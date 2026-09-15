"""Tests for plan reconciliation — supersede, prune, cluster desync fix."""

from __future__ import annotations

import pytest

from desloppify.engine._plan.operations.cluster import add_to_cluster, create_cluster
from desloppify.engine._plan.operations.skip import skip_items
from desloppify.engine._plan.scan_issue_reconcile import reconcile_plan_after_scan
from desloppify.engine._plan.schema import empty_plan, ensure_plan_defaults
from desloppify.engine._plan.skip_policy import skip_kind_state_status
from desloppify.engine._state.merge_issues import upsert_issues

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plan_with_queue(*ids: str) -> dict:
    plan = empty_plan()
    plan["queue_order"] = list(ids)
    return plan


def _state_with_issues(*ids: str, status: str = "open") -> dict:
    issues = {}
    for fid in ids:
        issues[fid] = {
            "id": fid,
            "status": status,
            "detector": "test",
            "file": "test.py",
            "tier": 1,
            "confidence": "high",
            "summary": f"Issue {fid}",
        }
    return {"issues": issues, "scan_count": 5}


# ---------------------------------------------------------------------------
# _supersede_id clears override cluster ref
# ---------------------------------------------------------------------------

def test_supersede_clears_override_cluster_ref():
    """When a issue is superseded, its override cluster ref should be cleared."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)

    # Create a cluster and add issue "a" to it
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a"])

    # Verify override has cluster ref
    assert plan["overrides"]["a"]["cluster"] == "my-cluster"

    # State where "a" is gone (not present = not alive)
    state = _state_with_issues("b")

    result = reconcile_plan_after_scan(plan, state)
    assert "a" in result.superseded

    # Override cluster ref should be cleared
    override = plan["overrides"].get("a")
    assert override is not None
    assert override.get("cluster") is None


def test_supersede_preserves_note_in_override():
    """Superseding should preserve the note in the override (for history)."""
    plan = _plan_with_queue("a")
    ensure_plan_defaults(plan)

    # Add an override with a note
    plan["overrides"]["a"] = {
        "issue_id": "a",
        "note": "important context",
        "cluster": None,
        "created_at": "2025-01-01T00:00:00+00:00",
    }

    state = _state_with_issues()  # "a" is gone
    reconcile_plan_after_scan(plan, state)

    # Superseded entry should have the note
    assert plan["superseded"]["a"]["note"] == "important context"


def test_supersede_removes_from_cluster_issue_ids():
    """Superseded issue should be removed from cluster issue_ids."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)

    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a", "b"])

    # "a" disappears
    state = _state_with_issues("b")
    reconcile_plan_after_scan(plan, state)

    assert "a" not in plan["clusters"]["my-cluster"]["issue_ids"]
    assert "b" in plan["clusters"]["my-cluster"]["issue_ids"]


def test_reconcile_clears_focus_when_focused_cluster_becomes_empty():
    """Reconcile should exit focus mode when the focused cluster loses its last issue."""
    plan = _plan_with_queue("a")
    ensure_plan_defaults(plan)
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a"])
    plan["active_cluster"] = "my-cluster"

    state = _state_with_issues()  # "a" disappeared
    result = reconcile_plan_after_scan(plan, state)

    assert "a" in result.superseded
    assert plan["clusters"]["my-cluster"]["issue_ids"] == []
    assert plan["active_cluster"] is None


# ---------------------------------------------------------------------------
# Reconcile logs execution
# ---------------------------------------------------------------------------

def test_reconcile_logs_execution_entry():
    """Reconciliation should append a log entry when changes are made."""
    plan = _plan_with_queue("gone")
    ensure_plan_defaults(plan)
    state = _state_with_issues("alive")

    result = reconcile_plan_after_scan(plan, state)
    assert result.changes > 0

    log = plan.get("execution_log", [])
    assert len(log) >= 1
    entry = log[-1]
    assert entry["action"] == "reconcile"
    assert entry["actor"] == "system"
    assert "superseded_count" in entry["detail"]


def test_reconcile_no_log_when_no_changes():
    """No log entry when reconciliation makes no changes."""
    plan = _plan_with_queue("a")
    ensure_plan_defaults(plan)
    state = _state_with_issues("a")  # "a" still alive

    result = reconcile_plan_after_scan(plan, state)
    assert result.changes == 0

    log = plan.get("execution_log", [])
    reconcile_entries = [e for e in log if e["action"] == "reconcile"]
    assert len(reconcile_entries) == 0


def test_reconcile_prunes_existing_superseded_references():
    """Already-superseded IDs should not linger in queue_order or clusters."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)
    plan["superseded"]["a"] = {
        "original_id": "a",
        "status": "superseded",
        "superseded_at": "2026-01-01T00:00:00+00:00",
    }
    plan["promoted_ids"] = ["a"]
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a", "b"])

    result = reconcile_plan_after_scan(plan, _state_with_issues("b"))

    assert result.changes > 0
    assert "a" not in plan["queue_order"]
    assert "a" not in plan["promoted_ids"]
    assert "a" not in plan["clusters"]["my-cluster"]["issue_ids"]


def test_reconcile_supersedes_resolved_action_references():
    """Resolved IDs should not linger as queue/promoted/cluster work."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)
    plan["promoted_ids"] = ["a", "b"]
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a", "b"])

    state = _state_with_issues("b")
    state["issues"]["a"] = {
        "id": "a",
        "status": "fixed",
        "detector": "test",
        "file": "test.py",
        "tier": 1,
        "confidence": "high",
        "summary": "Issue a",
    }

    result = reconcile_plan_after_scan(plan, state)

    assert "a" in result.superseded
    assert "a" not in plan["queue_order"]
    assert "a" not in plan["promoted_ids"]
    assert "a" not in plan["clusters"]["my-cluster"]["issue_ids"]
    assert "b" in plan["queue_order"]
    assert "b" in plan["promoted_ids"]


# ---------------------------------------------------------------------------
# Active clusters completed when all items resolved
# ---------------------------------------------------------------------------

def test_reconcile_marks_active_cluster_done_when_all_items_resolved():
    """An active cluster whose items are all fixed/wontfix should become done."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a", "b"])
    plan["clusters"]["my-cluster"]["execution_status"] = "active"

    # Both items are resolved in state
    state = _state_with_issues("a", "b", status="fixed")

    result = reconcile_plan_after_scan(plan, state)

    assert "my-cluster" in result.clusters_completed
    assert plan["clusters"]["my-cluster"]["execution_status"] == "done"


def test_reconcile_leaves_active_cluster_when_items_still_open():
    """An active cluster with open items should stay active."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a", "b"])
    plan["clusters"]["my-cluster"]["execution_status"] = "active"

    # "a" is fixed but "b" is still open
    state = _state_with_issues("b")
    state["issues"]["a"] = {
        "id": "a", "status": "fixed", "detector": "test",
        "file": "test.py", "tier": 1, "confidence": "high", "summary": "Issue a",
    }

    result = reconcile_plan_after_scan(plan, state)

    assert "my-cluster" not in result.clusters_completed
    assert plan["clusters"]["my-cluster"]["execution_status"] == "active"


# ---------------------------------------------------------------------------
# Skipped items still referenced by a cluster keep their skip entry
# ---------------------------------------------------------------------------

def _add_auto_cluster(plan: dict, name: str, issue_ids: list[str]) -> None:
    """Build an auto-cluster the way auto_cluster_issues stores one."""
    create_cluster(plan, "staging")
    add_to_cluster(plan, "staging", issue_ids)
    cluster = plan["clusters"].pop("staging")
    cluster.update(name=name, auto=True, cluster_key="auto::logs")
    plan["clusters"][name] = cluster
    for fid in issue_ids:
        plan["overrides"][fid]["cluster"] = name


@pytest.mark.parametrize("kind", ["false_positive", "permanent"])
def test_reconcile_keeps_skip_entry_of_clustered_dismissed_item(kind):
    """A dismissed item left in a cluster is detached, not superseded."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)
    _add_auto_cluster(plan, "auto/logs", ["a", "b"])
    skip_items(plan, ["a"], kind=kind, note="not a defect", attestation="attest")
    assert "a" in plan["clusters"]["auto/logs"]["issue_ids"]

    state = _state_with_issues("b")
    state["issues"]["a"] = {**state["issues"]["b"], "id": "a"}
    state["issues"]["a"]["status"] = skip_kind_state_status(kind)

    result = reconcile_plan_after_scan(plan, state)

    assert "a" not in result.superseded
    assert "a" not in plan["superseded"]
    assert plan["skipped"]["a"]["kind"] == kind
    assert "a" not in plan["clusters"]["auto/logs"]["issue_ids"]
    assert plan["overrides"]["a"]["cluster"] is None
    assert "b" in plan["clusters"]["auto/logs"]["issue_ids"]


def test_reconcile_supersedes_skipped_item_resolved_as_fixed():
    """A skip entry whose issue was later fixed is no longer a dismissal."""
    plan = _plan_with_queue("a")
    ensure_plan_defaults(plan)
    create_cluster(plan, "my-cluster")
    add_to_cluster(plan, "my-cluster", ["a"])
    skip_items(plan, ["a"], kind="false_positive", attestation="attest")

    state = _state_with_issues("a", status="fixed")
    result = reconcile_plan_after_scan(plan, state)

    assert "a" in result.superseded
    assert "a" not in plan["skipped"]


def test_false_positive_in_auto_cluster_stays_dismissed_across_two_scans():
    """Auto-cluster, skip --false-positive, then two unchanged scans."""
    raw = {
        "id": "logs::scripts/newswire.ts::${verdict}",
        "detector": "logs",
        "file": "scripts/newswire.ts",
        "tier": 1,
        "confidence": "high",
        "summary": "1 tagged logs [${verdict}]",
        "detail": {"count": 1, "lines": [49]},
    }
    fid = raw["id"]
    state = {"issues": {fid: {**raw, "status": "open"}}, "scan_count": 19}
    issues = state["issues"]

    plan = _plan_with_queue(fid)
    ensure_plan_defaults(plan)
    _add_auto_cluster(plan, "auto/logs", [fid])

    skip_items(plan, [fid], kind="false_positive", note="CLI output", attestation="attest")
    issues[fid]["status"] = "false_positive"

    for scan_count in (20, 21):
        state["scan_count"] = scan_count
        now = f"2026-09-15T21:{scan_count}:00+00:00"
        upsert_issues(issues, [dict(raw)], [], now, lang="typescript")
        reconcile_plan_after_scan(plan, state)

        assert fid in plan["skipped"], f"skip entry lost at scan {scan_count}"
        assert fid not in plan["superseded"]
        assert issues[fid]["status"] == "false_positive", f"reopened at scan {scan_count}"


# ---------------------------------------------------------------------------
# A user skip recorded after a supersede outlives the next scan
# ---------------------------------------------------------------------------

def _logs_raw_issue() -> dict:
    return {
        "id": "logs::scripts/newswire.ts::${verdict}",
        "detector": "logs",
        "file": "scripts/newswire.ts",
        "tier": 1,
        "confidence": "high",
        "summary": "1 tagged logs [${verdict}]",
        "detail": {"count": 1, "lines": [49]},
    }


@pytest.mark.parametrize("kind", ["false_positive", "permanent"])
def test_skip_after_supersede_survives_next_scan(kind):
    """Superseded by an earlier reconcile, skipped again, then one scan."""
    raw = _logs_raw_issue()
    fid = raw["id"]
    dismissed_status = skip_kind_state_status(kind)
    state = {"issues": {fid: {**raw, "status": dismissed_status}}, "scan_count": 20}
    issues = state["issues"]

    # The status was set without a skip entry, so reconcile supersedes the id.
    plan = _plan_with_queue(fid)
    ensure_plan_defaults(plan)
    first = reconcile_plan_after_scan(plan, state)
    assert fid in first.superseded
    assert fid in plan["superseded"]

    skip_items(plan, [fid], kind=kind, note="CLI output", attestation="attest")
    issues[fid]["status"] = dismissed_status

    state["scan_count"] = 21
    upsert_issues(issues, [dict(raw)], [], "2026-09-15T21:50:00+00:00", lang="typescript")
    reconcile_plan_after_scan(plan, state)

    assert plan["skipped"][fid]["kind"] == kind
    assert fid not in plan["superseded"]
    assert issues[fid]["status"] == dismissed_status


def test_genuinely_superseded_id_is_still_pruned_from_plan_lists():
    """With no newer user action, a superseded id's leftover references go."""
    plan = _plan_with_queue("a", "b")
    ensure_plan_defaults(plan)
    plan["skipped"]["a"] = {"issue_id": "a", "kind": "temporary"}
    plan["superseded"]["a"] = {
        "original_id": "a",
        "status": "superseded",
        "superseded_at": "2026-09-15T21:28:05+00:00",
    }
    state = _state_with_issues("a", "b")

    reconcile_plan_after_scan(plan, state)

    assert "a" not in plan["queue_order"]
    assert "a" not in plan["skipped"]
    assert "a" in plan["superseded"]

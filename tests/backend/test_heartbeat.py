"""Tests for HeartbeatManager."""

import time

from taim.orchestrator.heartbeat import HeartbeatManager


class TestActivityTracking:
    def test_report_activity_tracks_task(self) -> None:
        hb = HeartbeatManager()
        hb.report_activity("t1")
        assert hb.active_count == 1

    def test_mark_complete_removes_task(self) -> None:
        hb = HeartbeatManager()
        hb.report_activity("t1")
        hb.mark_complete("t1")
        assert hb.active_count == 0

    def test_mark_complete_missing_is_safe(self) -> None:
        hb = HeartbeatManager()
        hb.mark_complete("nonexistent")  # should not raise
        assert hb.active_count == 0


class TestStaleDetection:
    def test_fresh_task_not_stale(self) -> None:
        hb = HeartbeatManager(agent_timeout_seconds=60)
        hb.report_activity("t1")
        assert hb.get_stale_tasks() == []

    def test_old_task_is_stale(self) -> None:
        hb = HeartbeatManager(agent_timeout_seconds=0)  # immediate timeout
        hb.report_activity("t1")
        time.sleep(0.01)  # ensure monotonic clock advances
        stale = hb.get_stale_tasks()
        assert "t1" in stale

    def test_multiple_tasks_mixed(self) -> None:
        hb = HeartbeatManager(agent_timeout_seconds=1000)
        hb.report_activity("fresh")
        # Manually backdate one task
        hb._active_tasks["old"] = time.monotonic() - 2000
        stale = hb.get_stale_tasks()
        assert "old" in stale
        assert "fresh" not in stale

"""Tests for the service status calls: status() and status_history(), sync and async."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from lnbot import (
    BadRequestError,
    LnBotError,
    NoticeLevel,
    ServiceState,
    ServiceStatusHistoryResponse,
    ServiceStatusResponse,
    StatusBucket,
    TooManyRequestsError,
)
from lnbot.types import parse_service_status, parse_service_status_history
from conftest import create_async_client, create_client

FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Fixtures (the contract's examples; the live responses are in tests/fixtures)
# ---------------------------------------------------------------------------

STATUS_OPERATIONAL = '{"status":"operational","updatedAt":"2026-10-25T14:33:53.06+00:00","notice":null,"components":{"sending":{"status":"operational","inProgress":1,"byStage":{"in_flight":1},"longestWaitSeconds":3,"sentLastHour":42,"failedLastHour":1,"serviceFailuresLastHour":0,"medianSeconds":2.1,"p95Seconds":6.8},"receiving":{"status":"operational","creditedLastHour":97,"creditBacklog":0},"node":{"status":"operational","latencyMs":284},"webhooks":{"status":"operational","backlog":0}}}'
STATUS_OUTAGE = '{"status":"outage","updatedAt":"2026-10-25T14:33:53.06+00:00","notice":{"level":"outage","message":"Payments are paused while the node recovers.","since":"2026-10-25T14:10:00+00:00","until":null},"components":{"sending":{"status":"outage","inProgress":6,"byStage":{"queued":2,"retrying":4},"longestWaitSeconds":1260,"sentLastHour":3,"failedLastHour":5,"serviceFailuresLastHour":5,"medianSeconds":2.4,"p95Seconds":3.0},"receiving":{"status":"outage","creditedLastHour":4,"creditBacklog":0},"node":{"status":"outage","latencyMs":null},"webhooks":{"status":"operational","backlog":0}}}'
STATUS_STALE = '{"status":"unknown","updatedAt":"2026-10-25T13:02:11.00+00:00","notice":null,"components":{"sending":{"status":"unknown","inProgress":0,"byStage":{},"longestWaitSeconds":null,"sentLastHour":12,"failedLastHour":0,"serviceFailuresLastHour":0,"medianSeconds":2.0,"p95Seconds":5.5},"receiving":{"status":"unknown","creditedLastHour":30,"creditBacklog":0},"node":{"status":"unknown","latencyMs":250},"webhooks":{"status":"unknown","backlog":0}}}'
STATUS_NEVER_MEASURED = '{"status":"unknown","updatedAt":null,"notice":null,"components":{"sending":{"status":"unknown","inProgress":0,"byStage":{},"longestWaitSeconds":null,"sentLastHour":0,"failedLastHour":0,"serviceFailuresLastHour":0,"medianSeconds":null,"p95Seconds":null},"receiving":{"status":"unknown","creditedLastHour":0,"creditBacklog":null},"node":{"status":"unknown","latencyMs":null},"webhooks":{"status":"unknown","backlog":null}}}'

HISTORY_90D = '{"range":"90d","bucketSeconds":86400,"from":"2026-07-27T00:00:00+00:00","to":"2026-10-25T14:35:12+00:00","summary":{"samples":2850,"uptime":{"overall":{"operational":99.123,"degraded":0,"outage":0.877},"sending":{"operational":99.123,"degraded":0,"outage":0.877},"receiving":{"operational":99.123,"degraded":0,"outage":0.877},"node":{"operational":99.123,"degraded":0,"outage":0.877},"webhooks":{"operational":100,"degraded":0,"outage":0}},"sent":2410,"failed":31,"serviceFailures":6,"credited":5012,"medianSeconds":2.2,"p95Seconds":7.9,"settleTimes":[{"upToSeconds":1,"count":70},{"upToSeconds":2,"count":1100},{"upToSeconds":3,"count":690},{"upToSeconds":5,"count":300},{"upToSeconds":10,"count":160},{"upToSeconds":20,"count":50},{"upToSeconds":30,"count":20},{"upToSeconds":60,"count":12},{"upToSeconds":120,"count":5},{"upToSeconds":300,"count":2},{"upToSeconds":600,"count":1},{"upToSeconds":null,"count":0}],"avgLatencyMs":301,"maxLatencyMs":20000},"buckets":[{"at":"2026-10-23T00:00:00+00:00","samples":1425,"overall":{"degraded":0,"outage":0},"sending":{"degraded":0,"outage":0,"sent":1200,"failed":12,"serviceFailures":1,"medianSeconds":2.2,"p95Seconds":7.5,"maxInProgress":4,"maxWaitSeconds":41},"receiving":{"degraded":0,"outage":0,"credited":2500,"maxBacklog":3},"node":{"degraded":0,"outage":0,"avgLatencyMs":290,"maxLatencyMs":1900},"webhooks":{"degraded":0,"outage":0,"maxBacklog":4}},{"at":"2026-10-24T00:00:00+00:00","samples":1425,"overall":{"degraded":0,"outage":25},"sending":{"degraded":0,"outage":25,"sent":1210,"failed":19,"serviceFailures":5,"medianSeconds":2.3,"p95Seconds":8.4,"maxInProgress":9,"maxWaitSeconds":1500},"receiving":{"degraded":0,"outage":25,"credited":2512,"maxBacklog":40},"node":{"degraded":0,"outage":25,"avgLatencyMs":312,"maxLatencyMs":20000},"webhooks":{"degraded":0,"outage":0,"maxBacklog":6}},{"at":"2026-10-25T00:00:00+00:00","samples":0,"overall":{"degraded":0,"outage":0},"sending":{"degraded":0,"outage":0,"sent":0,"failed":0,"serviceFailures":0,"medianSeconds":null,"p95Seconds":null,"maxInProgress":0,"maxWaitSeconds":null},"receiving":{"degraded":0,"outage":0,"credited":0,"maxBacklog":null},"node":{"degraded":0,"outage":0,"avgLatencyMs":null,"maxLatencyMs":null},"webhooks":{"degraded":0,"outage":0,"maxBacklog":null}}],"notices":[{"level":"outage","message":"Payments are paused while the node recovers.","since":"2026-10-24T09:05:00+00:00","until":"2026-10-24T09:32:00+00:00"},{"level":"info","message":"Payments are flowing again. We are watching it.","since":"2026-10-24T09:32:00+00:00","until":"2026-10-24T11:00:00+00:00"}]}'

RATE_LIMITED = {"error": "Too many requests. Please try again later."}


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def _with_extra_keys(value: Any) -> Any:
    """Add an unknown key to every object, at every level (but not inside ``byStage``, which is an open map)."""
    if isinstance(value, dict):
        out = {k: (v if k == "byStage" else _with_extra_keys(v)) for k, v in value.items()}
        out["addedLater"] = {"nested": [1, 2]}
        return out
    if isinstance(value, list):
        return [_with_extra_keys(v) for v in value]
    return value


def _call(use_async: bool, method: str, *args: Any, status: int = 200, json_body: Any = None, api_key: str | None = "key_test"):
    """Run ``ln.<method>(*args)`` against a mock response, with the sync or the async client."""
    if use_async:
        aln, cap = create_async_client(status=status, json_body=json_body, api_key=api_key)

        async def run():
            return await getattr(aln, method)(*args)

        return asyncio.run(run()), cap
    ln, cap = create_client(status=status, json_body=json_body, api_key=api_key)
    return getattr(ln, method)(*args), cap


# ---------------------------------------------------------------------------
# GET /v1/status
# ---------------------------------------------------------------------------


class TestParseStatus:
    def test_operational(self):
        s = parse_service_status(json.loads(STATUS_OPERATIONAL))
        assert isinstance(s, ServiceStatusResponse)
        assert s.status == ServiceState.OPERATIONAL
        assert s.updated_at == "2026-10-25T14:33:53.06+00:00"
        assert s.notice is None
        sending = s.components.sending
        assert sending.status == "operational"
        assert sending.in_progress == 1
        assert sending.by_stage == {"in_flight": 1}
        assert sending.longest_wait_seconds == 3
        assert (sending.sent_last_hour, sending.failed_last_hour, sending.service_failures_last_hour) == (42, 1, 0)
        assert (sending.median_seconds, sending.p95_seconds) == (2.1, 6.8)
        assert (s.components.receiving.credited_last_hour, s.components.receiving.credit_backlog) == (97, 0)
        assert s.components.node.latency_ms == 284
        assert s.components.webhooks.backlog == 0

    def test_outage_with_notice(self):
        s = parse_service_status(json.loads(STATUS_OUTAGE))
        assert s.status == ServiceState.OUTAGE
        assert s.notice is not None
        assert s.notice.level == NoticeLevel.OUTAGE
        assert s.notice.message == "Payments are paused while the node recovers."
        assert s.notice.since == "2026-10-25T14:10:00+00:00"
        assert s.notice.until is None
        assert s.components.sending.by_stage == {"queued": 2, "retrying": 4}
        assert s.components.sending.longest_wait_seconds == 1260
        assert s.components.node.status == "outage"
        assert s.components.node.latency_ms is None
        assert s.components.webhooks.status == "operational"

    def test_stale(self):
        s = parse_service_status(json.loads(STATUS_STALE))
        assert s.status == ServiceState.UNKNOWN
        assert s.updated_at == "2026-10-25T13:02:11.00+00:00"
        assert s.components.sending.by_stage == {}
        assert s.components.sending.longest_wait_seconds is None
        assert s.components.sending.sent_last_hour == 12
        assert s.components.node.latency_ms == 250

    def test_never_measured(self):
        s = parse_service_status(json.loads(STATUS_NEVER_MEASURED))
        assert s.status == "unknown"
        assert s.updated_at is None
        sending = s.components.sending
        assert (sending.longest_wait_seconds, sending.median_seconds, sending.p95_seconds) == (None, None, None)
        assert s.components.receiving.credit_backlog is None
        assert s.components.node.latency_ms is None
        assert s.components.webhooks.backlog is None

    def test_live_response(self):
        s = parse_service_status(_load("status_live.json"))
        assert s.status == "operational"
        # Seven fractional-second digits: kept as sent.
        assert s.updated_at == "2026-10-25T17:16:11.9284738+00:00"
        assert s.components.sending.by_stage == {}
        assert s.components.sending.median_seconds is None
        assert s.components.node.latency_ms == 885

    def test_unknown_status_and_notice_level(self):
        data = json.loads(STATUS_OUTAGE)
        data["status"] = "maintenance"
        data["notice"]["level"] = "critical"
        data["components"]["webhooks"]["status"] = "paused"
        data["components"]["sending"]["byStage"]["teleporting"] = 1
        s = parse_service_status(data)
        assert s.status == "maintenance"
        assert s.notice is not None and s.notice.level == "critical"
        assert s.components.webhooks.status == "paused"
        assert s.components.sending.by_stage == {"queued": 2, "retrying": 4, "teleporting": 1}

    def test_unknown_keys_dropped_at_every_level(self):
        data = _with_extra_keys(json.loads(STATUS_OUTAGE))
        data["components"]["treasury"] = {"status": "operational"}
        s = parse_service_status(data)
        assert s == parse_service_status(json.loads(STATUS_OUTAGE))

    def test_is_frozen(self):
        s = parse_service_status(json.loads(STATUS_OPERATIONAL))
        with pytest.raises(AttributeError):
            s.status = "outage"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GET /v1/status/history
# ---------------------------------------------------------------------------


class TestParseStatusHistory:
    def test_90d(self):
        h = parse_service_status_history(json.loads(HISTORY_90D))
        assert isinstance(h, ServiceStatusHistoryResponse)
        assert (h.range, h.bucket_seconds) == ("90d", 86400)
        assert h.from_ == "2026-07-27T00:00:00+00:00"
        assert h.to == "2026-10-25T14:35:12+00:00"
        sm = h.summary
        assert sm.samples == 2850
        assert (sm.uptime.overall.operational, sm.uptime.overall.degraded, sm.uptime.overall.outage) == (99.123, 0, 0.877)
        assert sm.uptime.webhooks.operational == 100
        assert (sm.sent, sm.failed, sm.service_failures, sm.credited) == (2410, 31, 6, 5012)
        assert (sm.median_seconds, sm.p95_seconds) == (2.2, 7.9)
        assert (sm.avg_latency_ms, sm.max_latency_ms) == (301, 20000)
        assert [t.up_to_seconds for t in sm.settle_times] == [1, 2, 3, 5, 10, 20, 30, 60, 120, 300, 600, None]
        assert sum(t.count for t in sm.settle_times) == 2410

    def test_90d_buckets(self):
        h = parse_service_status_history(json.loads(HISTORY_90D))
        assert len(h.buckets) == 3
        assert all(isinstance(b, StatusBucket) for b in h.buckets)
        measured, outage, _ = h.buckets
        assert measured.at == "2026-10-23T00:00:00+00:00"
        assert measured.samples == 1425
        assert (measured.sending.sent, measured.sending.failed, measured.sending.service_failures) == (1200, 12, 1)
        assert (measured.sending.max_in_progress, measured.sending.max_wait_seconds) == (4, 41)
        assert (measured.receiving.credited, measured.receiving.max_backlog) == (2500, 3)
        assert (measured.node.avg_latency_ms, measured.node.max_latency_ms) == (290, 1900)
        assert measured.webhooks.max_backlog == 4
        assert (outage.overall.degraded, outage.overall.outage) == (0, 25)
        assert outage.node.outage == 25
        uptime = (outage.samples - outage.overall.degraded - outage.overall.outage) / outage.samples
        assert round(uptime * 100, 3) == 98.246

    def test_bucket_not_measured(self):
        b = parse_service_status_history(json.loads(HISTORY_90D)).buckets[2]
        assert b.samples == 0
        assert (b.overall.degraded, b.overall.outage) == (0, 0)
        assert (b.sending.sent, b.sending.failed, b.sending.service_failures) == (0, 0, 0)
        assert (b.sending.median_seconds, b.sending.p95_seconds, b.sending.max_wait_seconds) == (None, None, None)
        assert b.receiving.max_backlog is None
        assert (b.node.avg_latency_ms, b.node.max_latency_ms) == (None, None)
        assert b.webhooks.max_backlog is None

    def test_bucket_null_gauges(self):
        data = json.loads(HISTORY_90D)
        data["buckets"][2]["sending"]["maxInProgress"] = None
        b = parse_service_status_history(data).buckets[2]
        assert b.sending.max_in_progress is None

    def test_notices_oldest_first(self):
        h = parse_service_status_history(json.loads(HISTORY_90D))
        assert [n.level for n in h.notices] == ["outage", "info"]
        assert h.notices[0].until == "2026-10-24T09:32:00+00:00"
        assert h.notices[1].message == "Payments are flowing again. We are watching it."

    def test_live_24h(self):
        h = parse_service_status_history(_load("status_history_24h_live.json"))
        assert (h.range, h.bucket_seconds) == ("24h", 300)
        assert len(h.buckets) == 289
        assert h.to == "2026-10-25T17:16:44.1635789+00:00"
        assert h.notices == []
        assert len(h.summary.settle_times) == 12
        assert h.summary.settle_times[-1].up_to_seconds is None
        unmeasured = [b for b in h.buckets if b.samples == 0]
        assert unmeasured and all(b.sending.median_seconds is None and b.node.avg_latency_ms is None for b in unmeasured)
        last = h.buckets[-1]
        assert last.at == "2026-10-25T17:15:00+00:00"
        assert last.samples == 1
        assert last.node.avg_latency_ms == 885

    def test_nothing_measured_uptime_is_none(self):
        data = json.loads(HISTORY_90D)
        data["summary"]["samples"] = 0
        for part in data["summary"]["uptime"].values():
            part.update(operational=None, degraded=None, outage=None)
        data["summary"].update(medianSeconds=None, p95Seconds=None, avgLatencyMs=None, maxLatencyMs=None)
        sm = parse_service_status_history(data).summary
        assert (sm.uptime.overall.operational, sm.uptime.overall.degraded, sm.uptime.overall.outage) == (None, None, None)
        assert (sm.median_seconds, sm.p95_seconds, sm.avg_latency_ms, sm.max_latency_ms) == (None, None, None, None)

    def test_unknown_values_kept(self):
        data = json.loads(HISTORY_90D)
        data["range"] = "1y"
        data["notices"][0]["level"] = "critical"
        h = parse_service_status_history(data)
        assert h.range == "1y"
        assert h.notices[0].level == "critical"

    def test_unknown_keys_dropped_at_every_level(self):
        data = _with_extra_keys(json.loads(HISTORY_90D))
        data["summary"]["uptime"]["treasury"] = {"operational": 100, "degraded": 0, "outage": 0}
        data["buckets"][0]["treasury"] = {"degraded": 0, "outage": 0}
        h = parse_service_status_history(data)
        assert h == parse_service_status_history(json.loads(HISTORY_90D))


# ---------------------------------------------------------------------------
# The calls, sync and async
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("use_async", [False, True], ids=["sync", "async"])
class TestStatusCalls:
    def test_status(self, use_async):
        s, cap = _call(use_async, "status", json_body=json.loads(STATUS_OPERATIONAL))
        assert cap.method == "GET"
        assert cap.path == "/v1/status"
        assert cap.query == ""
        assert isinstance(s, ServiceStatusResponse)
        assert s.components.sending.by_stage == {"in_flight": 1}

    def test_status_history_defaults_to_24h(self, use_async):
        h, cap = _call(use_async, "status_history", json_body=_load("status_history_24h_live.json"))
        assert cap.method == "GET"
        assert cap.path == "/v1/status/history"
        assert cap.query == "range=24h"
        assert isinstance(h, ServiceStatusHistoryResponse)
        assert len(h.buckets) == 289

    @pytest.mark.parametrize("range_", ["7d", "30d", "90d"])
    def test_status_history_range(self, use_async, range_):
        _, cap = _call(use_async, "status_history", range_, json_body=json.loads(HISTORY_90D))
        assert cap.query == f"range={range_}"

    def test_status_history_passes_any_range(self, use_async):
        body = {"error": "range must be 24h, 7d, 30d or 90d."}
        with pytest.raises(BadRequestError) as exc_info:
            _call(use_async, "status_history", "1y", status=400, json_body=body)
        assert str(exc_info.value) == "range must be 24h, 7d, 30d or 90d."

    def test_no_api_key(self, use_async, monkeypatch):
        monkeypatch.delenv("LNBOT_API_KEY", raising=False)
        s, cap = _call(use_async, "status", json_body=json.loads(STATUS_NEVER_MEASURED), api_key=None)
        assert "authorization" not in cap.headers
        assert s.status == "unknown"
        h, cap = _call(use_async, "status_history", "90d", json_body=json.loads(HISTORY_90D), api_key=None)
        assert "authorization" not in cap.headers
        assert h.range == "90d"

    def test_with_api_key(self, use_async):
        _, cap = _call(use_async, "status", json_body=json.loads(STATUS_OPERATIONAL))
        assert cap.headers["authorization"] == "Bearer key_test"

    @pytest.mark.parametrize("method", ["status", "status_history"])
    def test_rate_limited(self, use_async, method, monkeypatch):
        monkeypatch.delenv("LNBOT_API_KEY", raising=False)
        with pytest.raises(TooManyRequestsError) as exc_info:
            _call(use_async, method, status=429, json_body=RATE_LIMITED, api_key=None)
        e = exc_info.value
        assert isinstance(e, LnBotError)
        assert e.status == 429
        assert str(e) == "Too many requests. Please try again later."
        assert json.loads(e.body) == RATE_LIMITED

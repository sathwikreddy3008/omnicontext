"""
core/telemetry.py — OmniContext Observability Module.

Tracks:
  - ingestion_duration
  - embedding_time (proxied via retrieval timing)
  - retrieval_latency
  - llm_response_time
  - retrieved_chunks count
  - endpoint_latency per route

Thread-safe singleton. Emits structured JSON logs.
All timing values are in seconds.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Any, Generator, Optional

# ── Structured JSON logger ────────────────────────────────────────────────────

_log_handler = logging.StreamHandler()
_log_handler.setFormatter(logging.Formatter("%(message)s"))

telemetry_logger = logging.getLogger("omnicontext.telemetry")
telemetry_logger.addHandler(_log_handler)
telemetry_logger.setLevel(logging.INFO)
telemetry_logger.propagate = False


def _emit(event: str, data: dict):
    telemetry_logger.info(json.dumps({"event": event, "ts": time.time(), **data}))


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class LatencySeries:
    """Rolling window of latency measurements."""
    _values: list[float] = field(default_factory=list)
    _max_size: int = 500

    def record(self, seconds: float):
        self._values.append(seconds)
        if len(self._values) > self._max_size:
            self._values = self._values[-self._max_size:]

    def stats(self) -> dict:
        if not self._values:
            return {"count": 0, "mean_ms": 0, "median_ms": 0, "p95_ms": 0, "max_ms": 0}
        ms = [v * 1000 for v in self._values]
        sorted_ms = sorted(ms)
        p95_idx = int(len(sorted_ms) * 0.95)
        return {
            "count": len(ms),
            "mean_ms": round(mean(ms), 2),
            "median_ms": round(median(ms), 2),
            "p95_ms": round(sorted_ms[p95_idx], 2),
            "max_ms": round(max(ms), 2),
        }


# ── Singleton tracker ─────────────────────────────────────────────────────────

class TelemetryTracker:
    _instance: Optional["TelemetryTracker"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TelemetryTracker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
        return cls._instance

    def _init(self):
        self._mutex = threading.Lock()
        # Counters
        self.ingestion_count: int = 0
        self.query_count: int = 0
        self.chunks_retrieved_total: int = 0

        # Latency series
        self.ingestion_latency = LatencySeries()
        self.retrieval_latency = LatencySeries()
        self.llm_latency = LatencySeries()
        self.endpoint_latency: dict[str, LatencySeries] = defaultdict(LatencySeries)

    # ── Context managers ──────────────────────────────────────────────────────

    @contextmanager
    def track_ingestion(self, source: str = "") -> Generator[None, None, None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            with self._mutex:
                self.ingestion_count += 1
                self.ingestion_latency.record(elapsed)
            _emit("ingestion", {"source": source, "duration_s": round(elapsed, 3)})

    @contextmanager
    def track_retrieval(self, query: str = "", n_chunks: int = 0) -> Generator[None, None, None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            with self._mutex:
                self.query_count += 1
                self.chunks_retrieved_total += n_chunks
                self.retrieval_latency.record(elapsed)
            _emit("retrieval", {
                "query_prefix": query[:60],
                "chunks": n_chunks,
                "duration_s": round(elapsed, 3),
            })

    @contextmanager
    def track_llm(self, model: str = "") -> Generator[None, None, None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            with self._mutex:
                self.llm_latency.record(elapsed)
            _emit("llm_response", {"model": model, "duration_s": round(elapsed, 3)})

    @contextmanager
    def track_endpoint(self, route: str) -> Generator[None, None, None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            with self._mutex:
                self.endpoint_latency[route].record(elapsed)
            _emit("endpoint", {"route": route, "duration_s": round(elapsed, 3)})

    # ── Metrics snapshot ──────────────────────────────────────────────────────

    def get_metrics(self) -> dict:
        with self._mutex:
            return {
                "counters": {
                    "total_ingestions": self.ingestion_count,
                    "total_queries": self.query_count,
                    "total_chunks_retrieved": self.chunks_retrieved_total,
                },
                "latency": {
                    "ingestion": self.ingestion_latency.stats(),
                    "retrieval": self.retrieval_latency.stats(),
                    "llm": self.llm_latency.stats(),
                },
                "endpoints": {
                    route: series.stats()
                    for route, series in self.endpoint_latency.items()
                },
            }


# ── Module-level singleton access ─────────────────────────────────────────────

telemetry = TelemetryTracker()

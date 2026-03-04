"""Lightweight per-frame timing tracker for runtime profiling."""

from collections import defaultdict
from time import monotonic


class PerfTracker:
    """Aggregate per-frame timings and emit periodic summaries."""

    def __init__(self, *, enabled: bool, report_interval: float = 1.0) -> None:
        """Create a tracker that emits summary logs periodically."""
        self.enabled = enabled
        self.report_interval = report_interval
        self._last_report_time = monotonic()
        self._report_time: float | None = None
        self._durations: dict[str, float] = defaultdict(float)
        self._counts: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}

    def record(self, key: str, duration: float) -> None:
        """Record a duration value under a named key."""
        if not self.enabled:
            return
        self._durations[key] += duration
        self._counts[key] += 1

    def set_gauge(self, key: str, value: float) -> None:
        """Record the latest gauge-style value for a key."""
        if not self.enabled:
            return
        self._gauges[key] = value

    def maybe_report(self) -> None:
        """Emit a summary log line once per interval."""
        if not self.enabled:
            return
        now = monotonic()
        if (now - self._last_report_time) < self.report_interval:
            return
        self._report_time = now
        parts: list[str] = []
        for key in sorted(self._durations.keys()):
            total_ms = self._durations[key] * 1000.0
            calls = self._counts.get(key, 0)
            parts.append(f"{key}={total_ms:.1f}ms/{calls}")
        for key in sorted(self._gauges.keys()):
            value = self._gauges[key]
            if isinstance(value, float):
                parts.append(f"{key}={value:.1f}")
            else:
                parts.append(f"{key}={value}")
        message = "perf: " + " ".join(parts)
        print(message)  # noqa: T201
        self._durations.clear()
        self._counts.clear()
        self._last_report_time = now

    def last_report_time(self) -> float | None:
        """Return the monotonic timestamp of the last report, if any."""
        return self._report_time

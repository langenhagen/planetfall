"""Lightweight per-frame timing tracker for runtime profiling."""

from collections import defaultdict
from time import monotonic


class PerfTracker:  # pylint: disable=too-many-instance-attributes
    # R0902: tracks multiple per-key aggregates for perf summaries.
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
        self._samples: dict[str, list[float]] = defaultdict(list)

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

    def record_sample(self, key: str, value: float) -> None:
        """Record a numeric sample for summary stats."""
        if not self.enabled:
            return
        self._samples[key].append(value)

    def _summarize_samples(self, key: str, samples: list[float]) -> list[str]:
        """Build summary stats strings for a sample list."""
        if not samples:
            return []
        sample_count = len(samples)
        samples_sorted = sorted(samples)
        min_value = samples_sorted[0]
        max_value = samples_sorted[-1]
        mid_index = sample_count // 2
        if sample_count % 2 == 1:
            median = samples_sorted[mid_index]
        else:
            median = 0.5 * (samples_sorted[mid_index - 1] + samples_sorted[mid_index])
        average = sum(samples) / sample_count
        return [
            f"{key}_min={min_value:.1f}",
            f"{key}_med={median:.1f}",
            f"{key}_avg={average:.1f}",
            f"{key}_max={max_value:.1f}",
        ]

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
        for key in sorted(self._samples.keys()):
            parts.extend(self._summarize_samples(key, self._samples[key]))
        message = "perf: " + " ".join(parts)
        print(message)  # noqa: T201
        self._durations.clear()
        self._counts.clear()
        self._samples.clear()
        self._last_report_time = now

    def last_report_time(self) -> float | None:
        """Return the monotonic timestamp of the last report, if any."""
        return self._report_time

"""RIFTWALKER — runtime diagnostics / performance guardrails 0.9.5.

Pure-Python helpers so the diagnostics can be tested without opening Pygame.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import platform
import traceback
from typing import Deque, Dict, Mapping, Optional


@dataclass
class RuntimeDiagnostics:
    window: int = 240
    frame_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=240))
    logic_updates: Deque[int] = field(default_factory=lambda: deque(maxlen=240))
    peak_counts: Dict[str, int] = field(default_factory=dict)
    dropped_effects: Dict[str, int] = field(default_factory=dict)
    last_counts: Dict[str, int] = field(default_factory=dict)

    def record_frame(self, real_dt: float, logic_updates: int, counts: Mapping[str, int]) -> None:
        self.frame_ms.append(max(0.0, float(real_dt) * 1000.0))
        self.logic_updates.append(max(0, int(logic_updates)))
        self.last_counts = {str(k): max(0, int(v)) for k, v in counts.items()}
        for key, value in self.last_counts.items():
            self.peak_counts[key] = max(self.peak_counts.get(key, 0), value)

    def note_drop(self, category: str, amount: int) -> None:
        if amount > 0:
            self.dropped_effects[category] = self.dropped_effects.get(category, 0) + int(amount)

    @property
    def average_frame_ms(self) -> float:
        return sum(self.frame_ms) / len(self.frame_ms) if self.frame_ms else 0.0

    @property
    def worst_frame_ms(self) -> float:
        return max(self.frame_ms) if self.frame_ms else 0.0

    def summary(self) -> Dict[str, object]:
        return {
            "avg_frame_ms": round(self.average_frame_ms, 3),
            "worst_frame_ms": round(self.worst_frame_ms, 3),
            "last_logic_updates": self.logic_updates[-1] if self.logic_updates else 0,
            "peak_counts": dict(self.peak_counts),
            "dropped_effects": dict(self.dropped_effects),
            "last_counts": dict(self.last_counts),
        }


def trim_oldest(items: list, limit: int) -> int:
    """Keep the newest `limit` items. Returns how many were discarded."""
    limit = max(0, int(limit))
    excess = max(0, len(items) - limit)
    if excess:
        del items[:excess]
    return excess


def write_crash_report(directory: str | Path, exc: BaseException, context: Optional[Mapping[str, object]] = None) -> Path:
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = root / f"crash_{stamp}.txt"
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "exception": f"{type(exc).__name__}: {exc}",
        "context": dict(context or {}),
    }
    text = ["RIFTWALKER CRASH REPORT", "=" * 28, json.dumps(payload, ensure_ascii=False, indent=2), "", "TRACEBACK", "-" * 28, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))]
    path.write_text("\n".join(text), encoding="utf-8")
    return path

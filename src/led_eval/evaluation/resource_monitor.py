from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import psutil


@dataclass
class ResourceSnapshot:
    cpu_percent: float
    ram_mb: float


@dataclass
class ResourceMonitor:
    process: psutil.Process = field(default_factory=lambda: psutil.Process(os.getpid()))
    snapshots: list[ResourceSnapshot] = field(default_factory=list)

    def start(self) -> None:
        self.snapshots.clear()
        self.process.cpu_percent(interval=None)

    def sample(self) -> None:
        cpu = self.process.cpu_percent(interval=None)
        ram_mb = self.process.memory_info().rss / (1024 * 1024)
        self.snapshots.append(ResourceSnapshot(cpu_percent=float(cpu), ram_mb=float(ram_mb)))

    def summary(self) -> dict[str, float]:
        if not self.snapshots:
            self.sample()
        cpu_values = [s.cpu_percent for s in self.snapshots]
        ram_values = [s.ram_mb for s in self.snapshots]
        return {
            "mean_cpu_percent": sum(cpu_values) / len(cpu_values),
            "peak_ram_mb": max(ram_values),
            "sample_count": float(len(self.snapshots)),
        }


def now_seconds() -> float:
    return time.perf_counter()

"""RIFTWALKER — FAIR ENCOUNTER / PACING DIRECTOR 0.7"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from narrative_systems import REGIONS


@dataclass(frozen=True)
class UnitBudget:
    archetype: str
    cost: int
    role: str
    min_danger: int = 0


UNITS: Tuple[UnitBudget, ...] = (
    UnitBudget("crawler", 3, "vanguard"),
    UnitBudget("shooter", 5, "ranged", 1),
    UnitBudget("hunter", 6, "hunter", 1),
    UnitBudget("tank", 8, "tank", 2),
    UnitBudget("support", 7, "support", 2),
)


@dataclass
class PerformanceSnapshot:
    hp_ratio: float = 1.0
    recent_deaths: int = 0
    rooms_cleared_fast: int = 0
    healing_used_recently: int = 0
    active_rifts: int = 0


@dataclass
class EncounterPlan:
    threat_budget: int
    units: List[str]
    doctrine: str
    spawn_groups: List[List[str]]
    recovery_after: bool
    superior_chance_bonus: float


DOCTRINES = ("cerco", "fortaleza", "cacada", "isca")


class EncounterDirector:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.recent_doctrines: List[str] = []
        self.recent_compositions: List[Tuple[str, ...]] = []

    @staticmethod
    def fair_adjustment(performance: PerformanceSnapshot) -> float:
        # Ajuste propositalmente pequeno: o jogador nunca deve sentir rubber-band.
        score = 0.0
        if performance.hp_ratio < 0.30:
            score -= 0.08
        elif performance.hp_ratio > 0.85 and performance.rooms_cleared_fast >= 2:
            score += 0.08
        score -= min(0.04, performance.recent_deaths * 0.02)
        score += min(0.04, performance.active_rifts * 0.01)
        return max(-0.12, min(0.12, score))

    def threat_budget(self, region_id: str, depth: int, performance: PerformanceSnapshot) -> int:
        danger = REGIONS[region_id].danger
        base = 10 + danger * 7 + depth * 3 + performance.active_rifts * 4
        return max(8, int(base * (1.0 + self.fair_adjustment(performance))))

    def choose_doctrine(self) -> str:
        pool = [x for x in DOCTRINES if x not in self.recent_doctrines[-2:]] or list(DOCTRINES)
        doctrine = self.rng.choice(pool)
        self.recent_doctrines.append(doctrine)
        self.recent_doctrines = self.recent_doctrines[-6:]
        return doctrine

    def generate(self, region_id: str, depth: int, performance: PerformanceSnapshot) -> EncounterPlan:
        budget = self.threat_budget(region_id, depth, performance)
        danger = REGIONS[region_id].danger
        candidates = [u for u in UNITS if danger >= u.min_danger]
        remaining = budget
        units: List[str] = []
        safety = 0
        while remaining >= min(x.cost for x in candidates) and safety < 80:
            safety += 1
            affordable = [u for u in candidates if u.cost <= remaining]
            if not affordable:
                break
            pick = self.rng.choice(affordable)
            proposed = tuple(sorted(units + [pick.archetype]))
            if proposed in self.recent_compositions[-2:] and len(affordable) > 1:
                continue
            units.append(pick.archetype)
            remaining -= pick.cost
        if not units:
            units = ["crawler", "crawler"]
        self.recent_compositions.append(tuple(sorted(units)))
        self.recent_compositions = self.recent_compositions[-6:]

        # Divide em grupos de 2–4 para entrada escalonada.
        shuffled = list(units)
        self.rng.shuffle(shuffled)
        groups: List[List[str]] = []
        while shuffled:
            size = min(len(shuffled), self.rng.randint(2, 4))
            groups.append(shuffled[:size])
            del shuffled[:size]

        recovery = performance.hp_ratio < 0.38 or performance.recent_deaths >= 2
        superior_bonus = max(0.0, min(0.18, danger * 0.015 + performance.active_rifts * 0.02))
        return EncounterPlan(budget, units, self.choose_doctrine(), groups, recovery, superior_bonus)


def director_summary() -> Dict[str, int]:
    return {"unit_archetypes": len(UNITS), "doctrines": len(DOCTRINES)}

"""RIFTWALKER — STRESS TEST 0.9 RC

Executa validações pesadas que não dependem de Pygame/renderização.
Use antes de abrir a build e sempre que houver mudança grande de conteúdo.
"""
from __future__ import annotations

import tempfile
from collections import deque
from pathlib import Path

import class_kit_systems  # registra skills 0.9 RC
import endgame_systems     # registra bosses finais

from boss_systems import BOSSES, BossDirector
from class_kit_systems import CLASS_KITS
from core_systems import (
    CLASS_REGISTRY,
    SKILL_REGISTRY,
    CharacterIdentity,
    Gender,
    PlayerState,
    SaveManager,
)
from encounter_director_systems import EncounterDirector, PerformanceSnapshot
from narrative_systems import REGIONS
from production_systems import content_metrics, run_content_audit
from profile_systems import ProfileManager
from world_generation_systems import generate_expedition_map, serialize_map, deserialize_map


def assert_path_to_boss(exp_map) -> None:
    queue = deque([exp_map.start_id])
    seen = {exp_map.start_id}
    while queue:
        node_id = queue.popleft()
        if node_id == exp_map.boss_id:
            return
        for nxt in exp_map.nodes[node_id].connections:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    raise AssertionError(f"Mapa seed={exp_map.seed} sem caminho até boss")


def stress_classes() -> None:
    for class_id, kit in CLASS_KITS.items():
        assert class_id in CLASS_REGISTRY
        assert len(kit.recommended_skills) >= 6
        state = PlayerState(
            identity=CharacterIdentity(
                nome=f"Stress_{class_id}",
                genero=Gender.MASCULINO,
                class_id=class_id,
            )
        )
        state.progression.classes_desbloqueadas.add(class_id)
        for skill_id in kit.recommended_skills:
            assert skill_id in SKILL_REGISTRY
            state.learn_skill(skill_id)
            for _ in range(12):
                state.register_skill_use(skill_id, mastery_xp=12)


def stress_world_generation() -> None:
    region_ids = [r for r in REGIONS if r != "refugio_ultima_luz"]
    assert region_ids
    for seed in range(300):
        region_id = region_ids[seed % len(region_ids)]
        difficulty = 1 + seed % 4
        main_length = 7 + seed % 7
        exp_map = generate_expedition_map(region_id, seed, difficulty, main_length)
        assert exp_map.start_id in exp_map.nodes
        assert exp_map.boss_id in exp_map.nodes
        assert_path_to_boss(exp_map)
        raw = serialize_map(exp_map)
        restored = deserialize_map(raw)
        assert restored.seed == seed
        assert restored.region_id == region_id
        assert_path_to_boss(restored)


def stress_encounter_director() -> None:
    region_ids = [r for r in REGIONS if r != "refugio_ultima_luz"]
    director = EncounterDirector(seed=90817)
    snapshots = (
        PerformanceSnapshot(hp_ratio=.12, recent_deaths=4, rooms_cleared_fast=0, healing_used_recently=5, active_rifts=0),
        PerformanceSnapshot(hp_ratio=.95, recent_deaths=0, rooms_cleared_fast=5, healing_used_recently=0, active_rifts=5),
        PerformanceSnapshot(hp_ratio=.55, recent_deaths=1, rooms_cleared_fast=1, healing_used_recently=2, active_rifts=2),
    )
    for i in range(300):
        snap = snapshots[i % len(snapshots)]
        region_id = region_ids[i % len(region_ids)]
        plan = director.generate(region_id, 1 + i % 15, snap)
        assert plan.threat_budget >= 8
        assert plan.units
        assert plan.spawn_groups
        assert plan.doctrine in ("cerco", "fortaleza", "cacada", "isca")
        assert 0.0 <= plan.superior_chance_bonus <= .18
        adjust = director.fair_adjustment(snap)
        assert -.12 <= adjust <= .12


def stress_bosses() -> None:
    state = PlayerState()
    for boss_id, boss in BOSSES.items():
        director = BossDirector(boss_id, state, seed=sum(map(ord, boss_id)))
        expected = {pid for phase in boss.phases for pid in phase.pattern_ids}
        seen = set()
        for hp in (1.0, .85, .65, .50, .30, .15, .05):
            for _ in range(100):
                pattern = director.choose_pattern(hp)
                seen.add(pattern.id)
                assert pattern.id in expected
                assert pattern.telegraph >= 0
                assert pattern.duration > 0
                assert pattern.danger >= 1
        assert seen


def stress_saves() -> None:
    with tempfile.TemporaryDirectory(prefix="riftwalker_stress_") as td:
        root = Path(td)
        for class_id, kit in CLASS_KITS.items():
            state = PlayerState(
                identity=CharacterIdentity(
                    nome=f"P_{class_id}",
                    genero=Gender.FEMININO,
                    class_id=class_id,
                )
            )
            state.progression.classes_desbloqueadas.add(class_id)
            for skill_id in kit.recommended_skills[:4]:
                state.learn_skill(skill_id)
            manager = SaveManager(str(root / f"{class_id}.json"))
            manager.save(state)
            loaded = manager.load()
            assert loaded.identity.class_id == class_id
            assert loaded.owned_skills == state.owned_skills

        profiles = ProfileManager(str(root / "profiles"), slots=3)
        for slot in range(1, 4):
            state = PlayerState(
                identity=CharacterIdentity(
                    nome=f"Slot{slot}",
                    genero=Gender.MASCULINO,
                    class_id="guerreiro",
                )
            )
            for _ in range(12):
                state.stats.nivel += 1
                profiles.save(slot, state)
                loaded = profiles.load(slot)
                assert loaded.stats.nivel == state.stats.nivel
                verify = profiles.verify(slot)
                assert verify["exists"]
                assert verify["checksum_ok"]
                assert verify["load_ok"]


def stress_release_audit() -> None:
    audit = run_content_audit(asset_root=".", require_audio_assets=False)
    assert not audit.blockers, [(x.code, x.message) for x in audit.blockers]


def main() -> None:
    stress_classes()
    print("[OK] 10 class kits / skill learning")
    stress_world_generation()
    print("[OK] 300 procedural maps + connectivity + serialization")
    stress_encounter_director()
    print("[OK] 300 encounter plans + fairness clamp")
    stress_bosses()
    print(f"[OK] {len(BOSSES)} bosses / pattern decks / phases")
    stress_saves()
    print("[OK] save v8 + 3 slots + checksum roundtrips")
    stress_release_audit()
    print("[OK] release audit: zero code/content blockers")
    print("STRESS TEST 0.9 RC: OK")
    print("CONTENT:", content_metrics())


if __name__ == "__main__":
    main()

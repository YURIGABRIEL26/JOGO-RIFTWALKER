"""RIFTWALKER — BOSS PATTERN DECKS / MEMORY ADAPTATION 0.7"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from core_systems import PlayerState


@dataclass(frozen=True)
class BossPattern:
    id: str
    nome: str
    telegraph: float
    duration: float
    danger: int
    tags: Tuple[str, ...]
    counters_styles: Tuple[str, ...] = ()
    voice_line: str = ""


@dataclass(frozen=True)
class BossPhase:
    threshold: float
    nome: str
    pattern_ids: Tuple[str, ...]
    speed_mult: float = 1.0
    damage_mult: float = 1.0
    arena_effect: Optional[str] = None


@dataclass(frozen=True)
class BossDefinition:
    id: str
    nome: str
    title: str
    region_id: str
    phases: Tuple[BossPhase, ...]
    intro_lines: Tuple[str, ...]
    memory_lines: Tuple[str, ...]


PATTERNS: Dict[str, BossPattern] = {
    p.id: p for p in (
        BossPattern("onda_fenda", "Onda de Fenda", 0.8, 1.1, 2, ("area", "rift"), voice_line="O chão se parte."),
        BossPattern("investida_quebrada", "Investida Quebrada", 0.55, 0.9, 3, ("dash", "melee"), ("long_range", "kite_ranged")),
        BossPattern("chuva_eco", "Chuva de Ecos", 1.0, 2.0, 3, ("projectile", "area"), ("agressivo_melee",)),
        BossPattern("finta_guardiao", "Finta do Guardião", 0.65, 1.0, 4, ("feint", "melee"), ("counter_parry",)),
        BossPattern("prisao_carmesim", "Prisão Carmesim", 1.15, 2.2, 4, ("zone", "blood"), ("cauteloso", "long_range")),
        BossPattern("salto_predador", "Salto Predador", 0.45, 0.8, 4, ("leap", "hunter"), ("kite_ranged", "long_range")),
        BossPattern("pulso_silencio", "Pulso de Silêncio", 1.0, 1.8, 3, ("silence", "area"), ("sustain",)),
        BossPattern("eco_atrasado", "Eco Atrasado", 0.75, 2.0, 4, ("delayed", "memory"), ("adaptavel",)),
        BossPattern("campo_temporal", "Campo Temporal", 1.1, 3.0, 4, ("temporal", "slow"), ("agressivo_melee",)),
        BossPattern("corte_instante", "Corte do Instante", 0.35, 0.7, 5, ("temporal", "melee"), ("counter_parry",)),
        BossPattern("espelho_vazio", "Espelho do Vazio", 0.9, 2.4, 5, ("void", "clone"), ("adaptavel",)),
        BossPattern("colapso_final", "Colapso Final", 1.4, 3.0, 6, ("ultimate", "area"), voice_line="Tudo termina aqui."),
    )
}


BOSSES: Dict[str, BossDefinition] = {
    "guardiao_primeira_ruptura": BossDefinition(
        "guardiao_primeira_ruptura", "Guardião da Primeira Ruptura", "Sentinela do Rasgo", "campos_primeira_fenda",
        (
            BossPhase(1.00, "Vigília", ("onda_fenda", "investida_quebrada", "chuva_eco")),
            BossPhase(0.55, "Memória Desperta", ("finta_guardiao", "eco_atrasado", "prisao_carmesim"), 1.08, 1.10, "fendas_no_chao"),
            BossPhase(0.20, "Última Guarda", ("salto_predador", "onda_fenda", "colapso_final"), 1.18, 1.18, "arena_instavel"),
        ),
        ("Você não deveria atravessar.",),
        ("Eu me lembro do seu passo.", "O Véu guardou sua hesitação."),
    ),
    "primeiro_rasgado": BossDefinition(
        "primeiro_rasgado", "O Primeiro Rasgado", "Aquele que Sobreviveu ao Véu", "bastilha_carmesim",
        (
            BossPhase(1.0, "Forma Contida", ("investida_quebrada", "prisao_carmesim", "onda_fenda")),
            BossPhase(0.50, "Corpo Aberto", ("salto_predador", "eco_atrasado", "pulso_silencio"), 1.10, 1.14, "ruptura_carmesim"),
            BossPhase(0.18, "Rasgado Completo", ("espelho_vazio", "colapso_final", "salto_predador"), 1.22, 1.24, "arena_quebrada"),
        ),
        ("Você chama isso de controle?",),
        ("Da última vez você correu.", "Você mudou. Eu também."),
    ),
    "matriarca_sussurrante": BossDefinition(
        "matriarca_sussurrante", "Matriarca Sussurrante", "A Voz Entre as Árvores", "bosque_sussurrante",
        (
            BossPhase(1.0, "Sussurro", ("chuva_eco", "pulso_silencio", "eco_atrasado")),
            BossPhase(0.45, "Coro", ("prisao_carmesim", "espelho_vazio", "salto_predador"), 1.06, 1.12, "raizes_vivas"),
        ),
        ("Eu ouvi seu nome antes de você chegar.",),
        ("Suas mortes têm voz.",),
    ),
    "cronarca_fraturado": BossDefinition(
        "cronarca_fraturado", "Cronarca Fraturado", "O Homem de Muitos Segundos", "observatorio_fraturado",
        (
            BossPhase(1.0, "Agora", ("campo_temporal", "corte_instante", "chuva_eco")),
            BossPhase(0.60, "Antes", ("eco_atrasado", "finta_guardiao", "campo_temporal"), 1.08, 1.08, "tempo_reverso"),
            BossPhase(0.25, "Depois", ("corte_instante", "espelho_vazio", "colapso_final"), 1.20, 1.20, "tempo_fraturado"),
        ),
        ("Já tivemos esta conversa.",),
        ("Na próxima vez você tentará outra coisa. Eu já vi.",),
    ),
}


class BossDirector:
    def __init__(self, boss_id: str, state: PlayerState, seed: int = 0):
        if boss_id not in BOSSES:
            raise ValueError(f"Boss inexistente: {boss_id}")
        self.definition = BOSSES[boss_id]
        self.state = state
        self.rng = random.Random(seed)
        self.history: List[str] = []

    def phase_for_hp(self, hp_ratio: float) -> BossPhase:
        phases = sorted(self.definition.phases, key=lambda x: x.threshold, reverse=True)
        selected = phases[0]
        for phase in phases:
            if hp_ratio <= phase.threshold:
                selected = phase
        return selected

    def player_style(self) -> str:
        memory = self.state.veil_memory.enemies.get(self.definition.id)
        return memory.ultimo_estilo_detectado if memory else "adaptavel"

    def choose_pattern(self, hp_ratio: float) -> BossPattern:
        phase = self.phase_for_hp(hp_ratio)
        style = self.player_style()
        candidates = [PATTERNS[x] for x in phase.pattern_ids]
        weights: List[float] = []
        for pattern in candidates:
            weight = 1.0
            if style in pattern.counters_styles:
                weight *= 1.55
            if pattern.id in self.history[-2:]:
                weight *= 0.20
            weights.append(weight)
        selected = self.rng.choices(candidates, weights=weights, k=1)[0]
        self.history.append(selected.id)
        self.history = self.history[-8:]
        return selected

    def intro_line(self) -> str:
        memory = self.state.veil_memory.enemies.get(self.definition.id)
        if memory and memory.encontros > 1 and self.definition.memory_lines:
            return self.rng.choice(self.definition.memory_lines)
        return self.rng.choice(self.definition.intro_lines)


def boss_summary() -> Dict[str, int]:
    return {"bosses": len(BOSSES), "patterns": len(PATTERNS), "phases": sum(len(x.phases) for x in BOSSES.values())}

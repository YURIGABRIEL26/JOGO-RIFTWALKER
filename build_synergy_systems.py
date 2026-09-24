"""RIFTWALKER — BUILD SYNERGIES / SKILL EVOLUTIONS 0.7"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from core_systems import PlayerState, SKILL_REGISTRY


@dataclass(frozen=True)
class SynergyDefinition:
    id: str
    nome: str
    descricao: str
    required_tags: Tuple[Tuple[str, int], ...]
    class_ids: Tuple[str, ...] = ()
    damage_mult: float = 1.0
    cooldown_mult: float = 1.0
    speed_mult: float = 1.0
    healing_mult: float = 1.0
    special_effects: Tuple[str, ...] = ()


SYNERGIES: Dict[str, SynergyDefinition] = {}


def register_synergy(s: SynergyDefinition) -> None:
    SYNERGIES[s.id] = s


for synergy in (
    SynergyDefinition("caminho_geada", "Caminho da Geada", "Controle gelado começa a encadear entre alvos.", (("ice", 2),), damage_mult=1.05, special_effects=("chill_spread",)),
    SynergyDefinition("coracao_inverno", "Coração do Inverno", "Build de gelo completa ganha congelamento mais confiável.", (("ice", 3), ("control", 2)), damage_mult=1.10, cooldown_mult=0.95, special_effects=("freeze_threshold_down",)),
    SynergyDefinition("incendiario", "Incendiário", "Fogo prolongado aumenta explosões.", (("fire", 2),), damage_mult=1.08, special_effects=("burn_explosion",)),
    SynergyDefinition("predador_sangue", "Predador de Sangue", "Sangramento e execução se fortalecem juntos.", (("bleed", 1), ("execute", 1)), healing_mult=1.10, special_effects=("execute_bleed_bonus",)),
    SynergyDefinition("andarilho_vazio", "Andarilho do Vazio", "Poder do Vazio cresce com risco.", (("rift", 2),), damage_mult=1.10, special_effects=("rift_echo",)),
    SynergyDefinition("corrompido_voluntario", "Corrompido Voluntário", "Duas fontes de corrupção ativam poder instável.", (("corruption", 2),), damage_mult=1.16, healing_mult=0.88, special_effects=("corruption_surge",)),
    SynergyDefinition("mestre_mobilidade", "Mestre da Mobilidade", "Dash e reposicionamento reduzem janelas de vulnerabilidade.", (("mobility", 2),), speed_mult=1.08, cooldown_mult=0.97, special_effects=("dash_afterimage",)),
    SynergyDefinition("contra_perfeito", "Contra Perfeito", "Parry e contra-ataque formam um estilo próprio.", (("parry", 2),), damage_mult=1.08, special_effects=("perfect_counter_window",)),
    SynergyDefinition("engenheiro_fendas", "Engenheiro de Fendas", "Dispositivos podem transmitir efeitos do Véu.", (("deployable", 2), ("rift", 1)), special_effects=("device_link", "rift_device_chain")),
    SynergyDefinition("profeta_condenacao", "Profeta da Condenação", "Marcas e maldições detonam em cadeia.", (("mark", 1), ("curse", 1)), damage_mult=1.09, special_effects=("mark_chain",)),
    SynergyDefinition("tempestade_arcana", "Tempestade Arcana", "Elementos mágicos alternados acumulam Convergência.", (("magic", 2),), damage_mult=1.06, cooldown_mult=0.97, special_effects=("element_rotation",)),
    SynergyDefinition("muralha_viva", "Muralha Viva", "Defesa e barreira convertem bloqueio em poder.", (("defense", 2),), healing_mult=1.08, special_effects=("guard_charge",)),
):
    register_synergy(synergy)


@dataclass(frozen=True)
class SkillEvolution:
    id: str
    nome: str
    base_skill_id: str
    min_mastery: int
    required_owned_skills: Tuple[str, ...] = ()
    required_synergies: Tuple[str, ...] = ()
    description: str = ""
    effects: Tuple[str, ...] = ()


EVOLUTIONS: Dict[str, SkillEvolution] = {
    x.id: x for x in (
        SkillEvolution("sol_negro", "Sol Negro", "bola_de_fogo", 5, required_synergies=("incendiario",), description="Bola de Fogo vira núcleo negro que puxa e incinera.", effects=("vacuum_fireball", "larger_explosion")),
        SkillEvolution("inverno_absoluto", "Inverno Absoluto", "prisao_glacial", 5, required_synergies=("coracao_inverno",), description="Prisão Glacial cria domínio congelante persistente.", effects=("persistent_blizzard",)),
        SkillEvolution("linha_morta", "Linha Morta", "horizonte_partido", 5, required_synergies=("andarilho_vazio",), description="O disparo deixa uma fenda que repete parte do tiro.", effects=("rift_repeat",)),
        SkillEvolution("colheita_final", "Colheita Final", "colheita_sombria", 5, required_owned_skills=("sentenca_final",), description="Roubo de vida passa a preparar execução.", effects=("harvest_execute_mark",)),
        SkillEvolution("coracao_aberto", "Coração Aberto", "fenda_interior", 5, required_synergies=("corrompido_voluntario",), description="Corrupção pode ser liberada em pulso devastador.", effects=("corruption_release",)),
        SkillEvolution("segundo_roubado", "Segundo Roubado", "passo_rebobinado", 5, required_owned_skills=("instante_imovel",), description="Rebobinar deixa um eco temporal atacando.", effects=("temporal_clone",)),
        SkillEvolution("rede_autonoma", "Rede Autônoma", "torreta_do_veu", 5, required_synergies=("engenheiro_fendas",), description="Torretas compartilham alvo e energia.", effects=("turret_network",)),
        SkillEvolution("duelo_impossivel", "Duelo Impossível", "contra_golpe", 5, required_synergies=("contra_perfeito",), description="Parry perfeito reposiciona e zera parte do cooldown.", effects=("counter_reset",)),
        SkillEvolution("sentenca_profetizada", "Sentença Profetizada", "marca_do_pressagio", 5, required_synergies=("profeta_condenacao",), description="Marca prevê dano futuro e detona ao atingir limiar.", effects=("prophecy_threshold",)),
        SkillEvolution("bastiao_eterno", "Bastião Eterno", "barreira_do_veu", 5, required_synergies=("muralha_viva",), description="Barreira absorvida retorna como onda defensiva.", effects=("barrier_retaliation",)),
    )
}


def skill_tag_counts(state: PlayerState) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for skill_id in state.owned_skills:
        skill = SKILL_REGISTRY.get(skill_id)
        if not skill:
            continue
        for tag in skill.tags:
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def active_synergies(state: PlayerState) -> List[SynergyDefinition]:
    counts = skill_tag_counts(state)
    result: List[SynergyDefinition] = []
    for s in SYNERGIES.values():
        if s.class_ids and state.identity.class_id not in s.class_ids:
            continue
        if all(counts.get(tag, 0) >= amount for tag, amount in s.required_tags):
            result.append(s)
    return result


def synergy_modifiers(state: PlayerState) -> Dict[str, object]:
    result = {"damage_mult": 1.0, "cooldown_mult": 1.0, "speed_mult": 1.0, "healing_mult": 1.0, "effects": set()}
    for s in active_synergies(state):
        result["damage_mult"] *= s.damage_mult
        result["cooldown_mult"] *= s.cooldown_mult
        result["speed_mult"] *= s.speed_mult
        result["healing_mult"] *= s.healing_mult
        result["effects"].update(s.special_effects)
    return result


def ensure_build_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("build_system", {})
    root.setdefault("evolved_skills", [])
    root.setdefault("evolution_history", [])
    return root


def available_evolutions(state: PlayerState) -> List[SkillEvolution]:
    active_ids = {x.id for x in active_synergies(state)}
    evolved = set(ensure_build_state(state)["evolved_skills"])
    result: List[SkillEvolution] = []
    for evo in EVOLUTIONS.values():
        if evo.id in evolved or evo.base_skill_id not in state.owned_skills:
            continue
        mastery = state.masteries.get(evo.base_skill_id)
        if not mastery or mastery.nivel < evo.min_mastery:
            continue
        if any(req not in state.owned_skills for req in evo.required_owned_skills):
            continue
        if any(req not in active_ids for req in evo.required_synergies):
            continue
        result.append(evo)
    return result


def evolve_skill(state: PlayerState, evolution_id: str) -> Tuple[bool, str]:
    if evolution_id not in EVOLUTIONS:
        return False, "Evolução inexistente."
    available = {x.id for x in available_evolutions(state)}
    if evolution_id not in available:
        return False, "Requisitos da evolução ainda não foram cumpridos."
    root = ensure_build_state(state)
    root["evolved_skills"].append(evolution_id)
    root["evolution_history"].append({"evolution_id": evolution_id, "base_skill_id": EVOLUTIONS[evolution_id].base_skill_id})
    return True, EVOLUTIONS[evolution_id].nome


def build_summary() -> Dict[str, int]:
    return {"synergies": len(SYNERGIES), "evolutions": len(EVOLUTIONS)}

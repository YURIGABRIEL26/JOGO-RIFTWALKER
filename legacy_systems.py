"""RIFTWALKER — ECHO LEGACY META PROGRESSION 0.7

Progressão permanente deliberadamente moderada: abre possibilidades e pequenos
bônus, sem substituir habilidade do jogador nem transformar morte em grind.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core_systems import PlayerState
from hub_systems import ensure_hub_state


@dataclass(frozen=True)
class LegacyNode:
    id: str
    branch: str
    nome: str
    cost: int
    prerequisite: Optional[str]
    effects: Tuple[Tuple[str, float], ...]


NODES: Dict[str, LegacyNode] = {}


def _reg(node: LegacyNode) -> None:
    NODES[node.id] = node


for node in (
    LegacyNode("vigor_1", "vigor", "Pulso Persistente", 2, None, (("max_hp_mult", 1.02),)),
    LegacyNode("vigor_2", "vigor", "Recuperação de Campo", 4, "vigor_1", (("healing_mult", 1.04),)),
    LegacyNode("vigor_3", "vigor", "Último Fôlego", 7, "vigor_2", (("low_hp_resist", 0.05),)),
    LegacyNode("vigor_4", "vigor", "Corpo do Caminhante", 11, "vigor_3", (("max_hp_mult", 1.03),)),
    LegacyNode("instinto_1", "instinto", "Passo Leve", 2, None, (("speed_mult", 1.015),)),
    LegacyNode("instinto_2", "instinto", "Janela Clara", 4, "instinto_1", (("parry_window_mult", 1.05),)),
    LegacyNode("instinto_3", "instinto", "Rastro Curto", 7, "instinto_2", (("dash_cooldown_mult", 0.97),)),
    LegacyNode("instinto_4", "instinto", "Ritmo Impossível", 11, "instinto_3", (("speed_mult", 1.02),)),
    LegacyNode("conhecimento_1", "conhecimento", "Notas de Campo", 2, None, (("research_mult", 1.05),)),
    LegacyNode("conhecimento_2", "conhecimento", "Olho de Cartógrafo", 4, "conhecimento_1", (("secret_hint", 0.05),)),
    LegacyNode("conhecimento_3", "conhecimento", "Memória Comparada", 7, "conhecimento_2", (("bestiary_gain_mult", 1.08),)),
    LegacyNode("conhecimento_4", "conhecimento", "Arquivo Vivo", 11, "conhecimento_3", (("research_mult", 1.08),)),
    LegacyNode("fortuna_1", "fortuna", "Bolso de Sucata", 2, None, (("material_drop_mult", 1.04),)),
    LegacyNode("fortuna_2", "fortuna", "Olhar Raro", 5, "fortuna_1", (("loot_luck", 0.03),)),
    LegacyNode("fortuna_3", "fortuna", "Retorno Seguro", 8, "fortuna_2", (("gold_return_mult", 1.05),)),
    LegacyNode("fortuna_4", "fortuna", "Eco Valioso", 12, "fortuna_3", (("loot_luck", 0.04),)),
    LegacyNode("veu_1", "veu", "Tolerância à Fenda", 3, None, (("rift_penalty_mult", 0.98),)),
    LegacyNode("veu_2", "veu", "Escolha Extra", 6, "veu_1", (("rift_offer_bonus", 1.0),)),
    LegacyNode("veu_3", "veu", "Eco Controlado", 9, "veu_2", (("corruption_resist", 0.05),)),
    LegacyNode("veu_4", "veu", "Caminhante Verdadeiro", 14, "veu_3", (("rift_reward_mult", 1.06),)),
):
    _reg(node)


def ensure_legacy_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("legacy", {})
    root.setdefault("unlocked_nodes", [])
    root.setdefault("lifetime_echo_spent", 0)
    return root


def available_echoes(state: PlayerState) -> int:
    return int(ensure_hub_state(state).get("ecos", 0))


def can_unlock(state: PlayerState, node_id: str) -> Tuple[bool, str]:
    if node_id not in NODES:
        return False, "Nó inexistente."
    root = ensure_legacy_state(state)
    if node_id in root["unlocked_nodes"]:
        return False, "Nó já desbloqueado."
    node = NODES[node_id]
    if node.prerequisite and node.prerequisite not in root["unlocked_nodes"]:
        return False, "Pré-requisito não cumprido."
    if available_echoes(state) < node.cost:
        return False, "Ecos insuficientes."
    return True, "OK"


def unlock_node(state: PlayerState, node_id: str) -> Tuple[bool, str]:
    ok, reason = can_unlock(state, node_id)
    if not ok:
        return False, reason
    node = NODES[node_id]
    hub = ensure_hub_state(state)
    hub["ecos"] = int(hub.get("ecos", 0)) - node.cost
    root = ensure_legacy_state(state)
    root["unlocked_nodes"].append(node_id)
    root["lifetime_echo_spent"] += node.cost
    return True, node.nome


def legacy_modifiers(state: PlayerState) -> Dict[str, float]:
    result: Dict[str, float] = {
        "max_hp_mult": 1.0, "healing_mult": 1.0, "speed_mult": 1.0,
        "parry_window_mult": 1.0, "dash_cooldown_mult": 1.0,
        "research_mult": 1.0, "bestiary_gain_mult": 1.0,
        "material_drop_mult": 1.0, "gold_return_mult": 1.0,
        "rift_penalty_mult": 1.0, "rift_reward_mult": 1.0,
        "loot_luck": 0.0, "secret_hint": 0.0, "low_hp_resist": 0.0,
        "rift_offer_bonus": 0.0, "corruption_resist": 0.0,
    }
    for node_id in ensure_legacy_state(state)["unlocked_nodes"]:
        node = NODES.get(node_id)
        if not node:
            continue
        for key, value in node.effects:
            if key.endswith("_mult"):
                result[key] *= value
            else:
                result[key] += value
    return result


def legacy_summary() -> Dict[str, int]:
    return {"nodes": len(NODES), "branches": len({x.branch for x in NODES.values()})}

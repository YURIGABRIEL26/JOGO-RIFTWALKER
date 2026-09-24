"""RIFTWALKER — FACTIONS / REPUTATION / CONSEQUENCES 0.7"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core_systems import PlayerState


@dataclass(frozen=True)
class FactionDefinition:
    id: str
    nome: str
    descricao: str
    rival_id: Optional[str]
    reward_flags: Tuple[Tuple[int, str], ...]


FACTIONS: Dict[str, FactionDefinition] = {
    "vigilia": FactionDefinition("vigilia", "Vigília da Última Luz", "Defende o Refúgio e prefere estabilidade.", "filhos_fenda", ((20, "vigilia_supply_discount"), (50, "vigilia_guardian_recipe"), (80, "vigilia_elite_contracts"))),
    "cartografos": FactionDefinition("cartografos", "Cartógrafos do Véu", "Exploram rotas impossíveis e segredos.", None, ((20, "map_secret_hint"), (50, "extra_branch_choice"), (80, "rare_expedition_routes"))),
    "arquivistas": FactionDefinition("arquivistas", "Arquivistas de Nox", "Querem compreender a memória das Rupturas.", None, ((20, "research_bonus_small"), (50, "superior_memory_scan"), (80, "bestiary_mastery_bonus"))),
    "filhos_fenda": FactionDefinition("filhos_fenda", "Filhos da Fenda", "Acreditam que a Ruptura deve ser usada, não fechada.", "vigilia", ((20, "corrupted_offer_bonus"), (50, "void_recipe"), (80, "deep_rift_access"))),
}


@dataclass(frozen=True)
class FactionChoice:
    id: str
    description: str
    changes: Tuple[Tuple[str, int], ...]
    set_flag: str


CHOICES: Dict[str, FactionChoice] = {
    "entregar_fragmento_vigilia": FactionChoice("entregar_fragmento_vigilia", "Entregar fragmento instável à Vigília.", (("vigilia", 12), ("filhos_fenda", -6)), "fragmento_vigilia"),
    "entregar_fragmento_filhos": FactionChoice("entregar_fragmento_filhos", "Entregar fragmento aos Filhos da Fenda.", (("filhos_fenda", 12), ("vigilia", -8)), "fragmento_filhos"),
    "mapa_cartografos": FactionChoice("mapa_cartografos", "Compartilhar rota secreta com Cartógrafos.", (("cartografos", 10),), "rota_compartilhada"),
    "memoria_arquivistas": FactionChoice("memoria_arquivistas", "Entregar eco de memória aos Arquivistas.", (("arquivistas", 10),), "eco_entregue_arquivo"),
}


def ensure_faction_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("factions", {})
    root.setdefault("reputation", {fid: 0 for fid in FACTIONS})
    root.setdefault("choices", [])
    root.setdefault("unlocked_flags", [])
    for fid in FACTIONS:
        root["reputation"].setdefault(fid, 0)
    return root


def reputation(state: PlayerState, faction_id: str) -> int:
    return int(ensure_faction_state(state)["reputation"].get(faction_id, 0))


def reputation_rank(value: int) -> str:
    if value >= 80: return "Aliado"
    if value >= 50: return "Respeitado"
    if value >= 20: return "Conhecido"
    if value <= -50: return "Hostil"
    if value < 0: return "Desconfiado"
    return "Neutro"


def change_reputation(state: PlayerState, faction_id: str, amount: int) -> List[str]:
    if faction_id not in FACTIONS:
        raise ValueError(f"Facção inexistente: {faction_id}")
    root = ensure_faction_state(state)
    rep = root["reputation"]
    rep[faction_id] = max(-100, min(100, int(rep.get(faction_id, 0)) + amount))
    unlocked: List[str] = []
    for threshold, flag in FACTIONS[faction_id].reward_flags:
        if rep[faction_id] >= threshold and flag not in root["unlocked_flags"]:
            root["unlocked_flags"].append(flag)
            unlocked.append(flag)
    return unlocked


def make_faction_choice(state: PlayerState, choice_id: str) -> Tuple[bool, str]:
    if choice_id not in CHOICES:
        return False, "Escolha inexistente."
    root = ensure_faction_state(state)
    if choice_id in root["choices"]:
        return False, "Esta escolha já foi feita."
    choice = CHOICES[choice_id]
    for faction_id, amount in choice.changes:
        change_reputation(state, faction_id, amount)
    root["choices"].append(choice_id)
    if choice.set_flag not in root["unlocked_flags"]:
        root["unlocked_flags"].append(choice.set_flag)
    return True, choice.description


def faction_summary() -> Dict[str, int]:
    return {"factions": len(FACTIONS), "choices": len(CHOICES)}

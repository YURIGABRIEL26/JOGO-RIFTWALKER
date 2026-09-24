"""RIFTWALKER — ENDGAME / ENDINGS / NG+ 0.9 RC

Fecha a campanha em código e fornece pós-jogo sem depender da UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core_systems import PlayerState, SKILL_REGISTRY
from boss_systems import BOSSES, PATTERNS, BossDefinition, BossPattern, BossPhase
from faction_systems import reputation


FINAL_BOSS_ID = "o_nome_apagado"
ECHO_BOSS_ID = "eco_do_riftwalker"


# ---------------------------------------------------------------------------
# Padrões finais registrados no mesmo diretor de bosses existente.
# ---------------------------------------------------------------------------
_EXTRA_PATTERNS = (
    BossPattern("apagamento", "Apagamento", 1.15, 2.2, 6, ("void", "silence", "area"), ("sustain",), "Esqueça."),
    BossPattern("nome_roubado", "Nome Roubado", 0.85, 1.6, 6, ("memory", "mark"), ("adaptavel",), "Seu nome não é seu."),
    BossPattern("fenda_especular", "Fenda Especular", 0.75, 2.0, 7, ("clone", "rift"), ("counter_parry", "agressivo_melee")),
    BossPattern("horizonte_nulo", "Horizonte Nulo", 1.35, 2.8, 7, ("ultimate", "line", "void"), ("long_range", "kite_ranged"), "Não existe depois."),
    BossPattern("memoria_invertida", "Memória Invertida", 0.65, 1.8, 7, ("memory", "feint"), ("counter_parry", "adaptavel")),
    BossPattern("colapso_do_veu", "Colapso do Véu", 1.55, 3.5, 8, ("ultimate", "area", "rift"), (), "O Véu fecha sobre você."),
    BossPattern("eco_perfeito", "Eco Perfeito", 0.55, 1.2, 7, ("copy", "memory"), ("adaptavel",)),
    BossPattern("contra_memoria", "Contra-Memória", 0.42, 0.9, 8, ("counter", "memory"), ("counter_parry", "kite_ranged")),
)

for pattern in _EXTRA_PATTERNS:
    PATTERNS.setdefault(pattern.id, pattern)

BOSSES.setdefault(
    FINAL_BOSS_ID,
    BossDefinition(
        FINAL_BOSS_ID,
        "O Nome Apagado",
        "Aquilo que o Véu recusou lembrar",
        "abismo_sem_nome",
        (
            BossPhase(1.00, "Sem Nome", ("apagamento", "nome_roubado", "espelho_vazio", "onda_fenda"), 1.00, 1.00, "nomes_desaparecem"),
            BossPhase(0.70, "Sem Passado", ("memoria_invertida", "fenda_especular", "eco_atrasado", "horizonte_nulo"), 1.08, 1.10, "memorias_invertidas"),
            BossPhase(0.38, "Sem Futuro", ("horizonte_nulo", "corte_instante", "apagamento", "espelho_vazio"), 1.16, 1.16, "arena_sem_bordas"),
            BossPhase(0.14, "Sem Véu", ("colapso_do_veu", "memoria_invertida", "horizonte_nulo"), 1.24, 1.24, "veu_aberto"),
        ),
        (
            "Você trouxe um nome até um lugar que não aceita nomes.",
            "Tudo que atravessa o Véu deixa algo para trás.",
        ),
        (
            "Eu lembro de todas as formas que você tentou sobreviver.",
            "Outra estratégia. Outro eco. O mesmo fim?",
        ),
    ),
)

BOSSES.setdefault(
    ECHO_BOSS_ID,
    BossDefinition(
        ECHO_BOSS_ID,
        "Eco do Riftwalker",
        "A versão de você que o Véu guardou",
        "abismo_sem_nome",
        (
            BossPhase(1.00, "Imitação", ("eco_perfeito", "investida_quebrada", "chuva_eco", "campo_temporal"), 1.08, 1.08, "espelho_jogador"),
            BossPhase(0.50, "Adaptação", ("contra_memoria", "finta_guardiao", "espelho_vazio", "salto_predador"), 1.16, 1.16, "estilo_roubado"),
            BossPhase(0.18, "Substituição", ("eco_perfeito", "horizonte_nulo", "colapso_final"), 1.25, 1.22, "eco_total"),
        ),
        ("Eu sou o que você ensinou ao Véu.",),
        ("Você mudou. Então eu também.", "Tente algo que nunca tentou."),
    ),
)


@dataclass(frozen=True)
class EndingDefinition:
    id: str
    nome: str
    descricao: str
    epilogo: str
    tone: str


ENDINGS: Dict[str, EndingDefinition] = {
    "selar": EndingDefinition(
        "selar", "A Última Luz",
        "Selar a maior ferida do Véu e preservar o Refúgio.",
        "As Rupturas não desaparecem, mas deixam de crescer. O Riftwalker vira guardião de uma paz que precisa ser mantida.",
        "hopeful",
    ),
    "compreender": EndingDefinition(
        "compreender", "O Arquivo Infinito",
        "Estabilizar a Ruptura e transformar memória em conhecimento.",
        "O Véu passa a ser estudado em vez de apenas temido. Toda expedição futura começa com a pergunta: o que mais ele lembra?",
        "curious",
    ),
    "atravessar": EndingDefinition(
        "atravessar", "Além do Véu",
        "Recusar o fechamento e caminhar para o outro lado.",
        "O Riftwalker desaparece da Última Luz. Novas Rupturas passam a carregar sinais de que alguém continua caminhando do outro lado.",
        "mysterious",
    ),
    "equilibrio": EndingDefinition(
        "equilibrio", "Entre Duas Margens",
        "Manter uma passagem controlada sem entregar o Véu a nenhuma facção.",
        "O mundo não volta a ser o que era. Em vez disso, aprende a viver com portas que exigem respeito.",
        "balanced",
    ),
    "consumir": EndingDefinition(
        "consumir", "O Novo Rasgo",
        "Absorver o núcleo da Ruptura e se tornar parte dela.",
        "O nome do Riftwalker começa a sumir dos registros. Em seu lugar surge uma nova presença nas regiões profundas.",
        "corrupted",
    ),
}


def ensure_endgame_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("endgame", {})
    root.setdefault("final_boss_defeated", False)
    root.setdefault("ending", None)
    root.setdefault("ending_history", [])
    root.setdefault("story_complete", False)
    root.setdefault("ng_plus_cycle", 0)
    root.setdefault("boss_rush_unlocked", False)
    root.setdefault("echo_boss_defeated", False)
    root.setdefault("postgame_flags", [])
    return root


def final_boss_available(state: PlayerState) -> bool:
    flags = set(state.campaign.get("flags", []))
    required_bosses = {
        "guardiao_primeira_ruptura",
        "primeiro_rasgado",
        "matriarca_sussurrante",
        "cronarca_fraturado",
    }
    bosses_ok = required_bosses.issubset(state.progression.bosses_derrotados)
    chapter_ok = int(state.campaign.get("chapter", 1)) >= 4 or "abismo_unlocked" in flags
    return bosses_ok and chapter_ok


def record_final_boss_defeat(state: PlayerState) -> None:
    root = ensure_endgame_state(state)
    root["final_boss_defeated"] = True
    if FINAL_BOSS_ID not in state.progression.bosses_derrotados:
        state.progression.bosses_derrotados.add(FINAL_BOSS_ID)
    flags = state.campaign.setdefault("flags", [])
    for flag in ("final_boss_defeated", "ending_choice_available"):
        if flag not in flags:
            flags.append(flag)


def corruption_score(state: PlayerState) -> int:
    corrupted = sum(
        1 for sid in state.owned_skills
        if sid in SKILL_REGISTRY and SKILL_REGISTRY[sid].corrupted
    )
    rifts = len(state.active_rifts.active_ids)
    children = max(0, reputation(state, "filhos_fenda"))
    return corrupted * 20 + rifts * 5 + children // 5


def eligible_endings(state: PlayerState) -> List[EndingDefinition]:
    root = ensure_endgame_state(state)
    if not root["final_boss_defeated"]:
        return []

    result: List[EndingDefinition] = []
    if reputation(state, "vigilia") >= 0:
        result.append(ENDINGS["selar"])
    if reputation(state, "arquivistas") >= 15:
        result.append(ENDINGS["compreender"])
    if reputation(state, "filhos_fenda") >= 15 or corruption_score(state) >= 45:
        result.append(ENDINGS["atravessar"])
    if reputation(state, "cartografos") >= 15:
        result.append(ENDINGS["equilibrio"])
    if corruption_score(state) >= 80:
        result.append(ENDINGS["consumir"])

    # Nunca trava o final por reputação.
    if not result:
        result.append(ENDINGS["selar"])
    return result


def choose_ending(state: PlayerState, ending_id: str) -> EndingDefinition:
    eligible = {ending.id: ending for ending in eligible_endings(state)}
    if ending_id not in eligible:
        raise ValueError("Final ainda não está disponível para este personagem.")

    root = ensure_endgame_state(state)
    root["ending"] = ending_id
    root["story_complete"] = True
    root["boss_rush_unlocked"] = True
    if ending_id not in root["ending_history"]:
        root["ending_history"].append(ending_id)
    flags = state.campaign.setdefault("flags", [])
    for flag in ("story_complete", "postgame_unlocked"):
        if flag not in flags:
            flags.append(flag)
    return eligible[ending_id]


def postgame_available(state: PlayerState) -> bool:
    return bool(ensure_endgame_state(state)["story_complete"])


def boss_rush_roster(state: PlayerState) -> Tuple[str, ...]:
    roster = [
        "guardiao_primeira_ruptura",
        "matriarca_sussurrante",
        "primeiro_rasgado",
        "cronarca_fraturado",
        FINAL_BOSS_ID,
    ]
    if ensure_endgame_state(state)["ng_plus_cycle"] >= 1:
        roster.append(ECHO_BOSS_ID)
    return tuple(roster)


def ng_plus_modifiers(cycle: int) -> Dict[str, float]:
    cycle = max(0, int(cycle))
    # Cresce, mas sem escala infinita absurda.
    capped = min(cycle, 10)
    return {
        "enemy_hp": 1.0 + capped * 0.10,
        "enemy_damage": 1.0 + capped * 0.075,
        "enemy_speed": 1.0 + capped * 0.018,
        "reward": 1.0 + capped * 0.12,
        "superior_chance_bonus": min(0.18, capped * 0.018),
    }


def start_ng_plus(state: PlayerState) -> int:
    root = ensure_endgame_state(state)
    if not root["story_complete"]:
        raise ValueError("NG+ só é liberado depois de concluir a campanha.")

    root["ng_plus_cycle"] = int(root["ng_plus_cycle"]) + 1
    cycle = int(root["ng_plus_cycle"])

    # Mantém metaprogressão, mas reinicia estado temporário de expedição.
    state.active_rifts.active_ids.clear()
    state.campaign["current_region"] = "refugio_ultima_luz"
    state.campaign["selected_contract"] = None
    flags = state.campaign.setdefault("flags", [])
    marker = f"ng_plus_{cycle}"
    if marker not in flags:
        flags.append(marker)
    return cycle


def record_echo_boss_defeat(state: PlayerState) -> None:
    root = ensure_endgame_state(state)
    root["echo_boss_defeated"] = True
    state.progression.bosses_derrotados.add(ECHO_BOSS_ID)
    if "echo_conquered" not in root["postgame_flags"]:
        root["postgame_flags"].append("echo_conquered")


def endgame_summary() -> Dict[str, int]:
    return {
        "endings": len(ENDINGS),
        "bosses_total": len(BOSSES),
        "patterns_total": len(PATTERNS),
        "postgame_bosses": 1,
    }

"""RIFTWALKER — ACHIEVEMENTS / TRIALS 0.7"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from core_systems import PlayerState


@dataclass(frozen=True)
class AchievementDefinition:
    id: str
    nome: str
    metric: str
    target: int
    reward_echoes: int
    hidden: bool = False


ACHIEVEMENTS: Dict[str, AchievementDefinition] = {
    a.id: a for a in (
        AchievementDefinition("primeiro_passo", "Primeiro Passo", "rooms_cleared", 1, 1),
        AchievementDefinition("dez_salas", "Sem Olhar Para Trás", "rooms_cleared", 10, 2),
        AchievementDefinition("cem_inimigos", "O Véu Conta Corpos", "kills", 100, 4),
        AchievementDefinition("primeiro_boss", "Algo Caiu", "bosses", 1, 3),
        AchievementDefinition("cinco_bosses", "Caçador de Lendas", "bosses", 5, 6),
        AchievementDefinition("superior", "Você Era Diferente", "superiors", 1, 3),
        AchievementDefinition("dez_superiores", "Predador de Predadores", "superiors", 10, 7),
        AchievementDefinition("tres_rupturas", "Mais Fundo", "max_active_rifts", 3, 5),
        AchievementDefinition("cinco_rupturas", "Sem Volta", "max_active_rifts", 5, 9, True),
        AchievementDefinition("mestre_habilidade", "Mão e Magia", "mastery_5", 1, 4),
        AchievementDefinition("descobriu_segredo", "Não Estava no Mapa", "secrets_found", 1, 3),
        AchievementDefinition("dez_segredos", "Cartógrafo Impossível", "secrets_found", 10, 8),
        AchievementDefinition("sem_dano_boss", "Intocável", "boss_no_damage", 1, 8, True),
        AchievementDefinition("morte_dez", "Ainda Aqui", "deaths", 10, 2),
        AchievementDefinition("evolucao", "Além da Técnica", "skill_evolutions", 1, 6),
    )
}


@dataclass(frozen=True)
class TrialDefinition:
    id: str
    nome: str
    description: str
    modifiers: Tuple[str, ...]
    target_rooms: int
    reward_echoes: int


TRIALS: Dict[str, TrialDefinition] = {
    t.id: t for t in (
        TrialDefinition("vidro", "Caminho de Vidro", "Muito dano, pouca vida.", ("player_hp_60", "player_damage_135"), 8, 7),
        TrialDefinition("silencio", "Juramento do Silêncio", "Habilidades especiais têm cooldown maior.", ("skill_cooldown_150",), 7, 6),
        TrialDefinition("predadores", "Temporada de Caça", "Hunters e Superiores aparecem mais.", ("hunter_weight_up", "superior_chance_up"), 8, 8),
        TrialDefinition("fendas", "Cinco Cicatrizes", "Começa com múltiplas Rupturas.", ("start_rifts_3",), 6, 9),
        TrialDefinition("sem_cura", "Sangue Seco", "Sem consumíveis de cura.", ("healing_disabled",), 7, 8),
        TrialDefinition("tempo", "Um Minuto a Menos", "Encontros aceleram gradualmente.", ("pacing_accelerates",), 9, 10),
    )
}


def ensure_challenge_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("challenges", {})
    root.setdefault("metrics", {})
    root.setdefault("unlocked_achievements", [])
    root.setdefault("claimed_achievements", [])
    root.setdefault("active_trial", None)
    root.setdefault("trial_progress", 0)
    root.setdefault("completed_trials", [])
    root.setdefault("pending_echo_rewards", 0)
    return root


def add_metric(state: PlayerState, metric: str, amount: int = 1, absolute_max: bool = False) -> List[str]:
    root = ensure_challenge_state(state)
    metrics = root["metrics"]
    if absolute_max:
        metrics[metric] = max(int(metrics.get(metric, 0)), int(amount))
    else:
        metrics[metric] = int(metrics.get(metric, 0)) + int(amount)
    unlocked: List[str] = []
    for ach in ACHIEVEMENTS.values():
        if ach.id in root["unlocked_achievements"]:
            continue
        if int(metrics.get(ach.metric, 0)) >= ach.target:
            root["unlocked_achievements"].append(ach.id)
            root["pending_echo_rewards"] += ach.reward_echoes
            unlocked.append(ach.id)
    return unlocked


def start_trial(state: PlayerState, trial_id: str) -> Tuple[bool, str]:
    if trial_id not in TRIALS:
        return False, "Provação inexistente."
    root = ensure_challenge_state(state)
    if root["active_trial"]:
        return False, "Já existe uma provação ativa."
    root["active_trial"] = trial_id
    root["trial_progress"] = 0
    return True, TRIALS[trial_id].nome


def progress_trial_room(state: PlayerState) -> Tuple[bool, List[str]]:
    root = ensure_challenge_state(state)
    trial_id = root.get("active_trial")
    if not trial_id:
        return False, []
    trial = TRIALS[trial_id]
    root["trial_progress"] += 1
    if root["trial_progress"] >= trial.target_rooms:
        if trial_id not in root["completed_trials"]:
            root["completed_trials"].append(trial_id)
            root["pending_echo_rewards"] += trial.reward_echoes
        root["active_trial"] = None
        return True, list(trial.modifiers)
    return False, list(trial.modifiers)


def collect_pending_echo_rewards(state: PlayerState) -> int:
    root = ensure_challenge_state(state)
    amount = int(root["pending_echo_rewards"])
    root["pending_echo_rewards"] = 0
    return amount


def challenge_summary() -> Dict[str, int]:
    return {"achievements": len(ACHIEVEMENTS), "trials": len(TRIALS)}

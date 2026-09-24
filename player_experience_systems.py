"""RIFTWALKER — PLAYER EXPERIENCE / SETTINGS / TUTORIAL 0.9 RC

Sistemas independentes de Pygame para dificuldade, acessibilidade,
controles, tutorial e códice. A camada visual apenas renderiza/aplica.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core_systems import PlayerState


@dataclass(frozen=True)
class DifficultyDefinition:
    id: str
    nome: str
    descricao: str
    enemy_hp: float
    enemy_damage: float
    enemy_speed: float
    superior_chance: float
    reward_mult: float
    adaptive_enabled: bool = True


DIFFICULTIES: Dict[str, DifficultyDefinition] = {
    "historia": DifficultyDefinition(
        "historia", "História",
        "Mais espaço para explorar a campanha sem remover as mecânicas.",
        0.78, 0.70, 0.96, -0.02, 0.90, False,
    ),
    "viajante": DifficultyDefinition(
        "viajante", "Viajante",
        "Experiência padrão planejada para a primeira campanha.",
        1.00, 1.00, 1.00, 0.00, 1.00, True,
    ),
    "riftwalker": DifficultyDefinition(
        "riftwalker", "Riftwalker",
        "Inimigos pressionam mais e Superiores aparecem com maior frequência.",
        1.12, 1.15, 1.035, 0.025, 1.15, True,
    ),
    "sem_veu": DifficultyDefinition(
        "sem_veu", "Sem Véu",
        "Modo avançado: erros custam caro e o mundo adapta mais cedo.",
        1.25, 1.30, 1.055, 0.05, 1.30, True,
    ),
}


@dataclass
class AccessibilitySettings:
    subtitles: bool = True
    subtitle_size: int = 100
    subtitle_background: bool = True
    reduced_screen_shake: bool = False
    reduced_flashes: bool = False
    high_contrast_telegraphs: bool = False
    colorblind_mode: str = "off"
    damage_numbers: bool = True
    aim_assist_strength: int = 0
    hold_to_cast: bool = False
    auto_sprint: bool = False
    larger_ui: bool = False


@dataclass
class AudioSettings:
    master: int = 90
    music: int = 75
    sfx: int = 85
    voices: int = 90
    ambience: int = 75
    mute_when_unfocused: bool = True


@dataclass
class VideoSettings:
    resolution: Tuple[int, int] = (1280, 720)
    fullscreen: bool = False
    vsync: bool = False
    fps_cap: int = 144
    show_fps: bool = False


DEFAULT_BINDINGS: Dict[str, str] = {
    "move_up": "W",
    "move_down": "S",
    "move_left": "A",
    "move_right": "D",
    "basic_attack": "MOUSE1",
    "secondary": "MOUSE2",
    "skill_1": "1",
    "skill_2": "2",
    "skill_3": "3",
    "skill_4": "4",
    "defense": "Q",
    "dash": "SPACE",
    "interact": "E",
    "inventory": "I",
    "map": "M",
    "codex": "C",
    "pause": "ESC",
}


@dataclass
class GameSettings:
    difficulty: str = "viajante"
    language: str = "pt-BR"
    accessibility: AccessibilitySettings = field(default_factory=AccessibilitySettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    bindings: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_BINDINGS))

    def validate(self) -> None:
        if self.difficulty not in DIFFICULTIES:
            self.difficulty = "viajante"
        for field_name in ("master", "music", "sfx", "voices", "ambience"):
            value = getattr(self.audio, field_name)
            setattr(self.audio, field_name, max(0, min(100, int(value))))
        self.accessibility.subtitle_size = max(70, min(150, int(self.accessibility.subtitle_size)))
        self.accessibility.aim_assist_strength = max(0, min(100, int(self.accessibility.aim_assist_strength)))
        self.video.fps_cap = max(30, min(360, int(self.video.fps_cap)))
        for action, default in DEFAULT_BINDINGS.items():
            self.bindings.setdefault(action, default)


class SettingsManager:
    def __init__(self, path: str = "settings.json"):
        self.path = Path(path)

    def save(self, settings: GameSettings) -> None:
        settings.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(settings)
        data["video"]["resolution"] = list(settings.video.resolution)
        fd, temp_name = tempfile.mkstemp(prefix="settings_", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def load(self) -> GameSettings:
        if not self.path.exists():
            return GameSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            a = data.get("accessibility", {})
            au = data.get("audio", {})
            v = data.get("video", {})
            resolution = v.get("resolution", [1280, 720])
            settings = GameSettings(
                difficulty=data.get("difficulty", "viajante"),
                language=data.get("language", "pt-BR"),
                accessibility=AccessibilitySettings(**{k: val for k, val in a.items() if k in AccessibilitySettings.__dataclass_fields__}),
                audio=AudioSettings(**{k: val for k, val in au.items() if k in AudioSettings.__dataclass_fields__}),
                video=VideoSettings(
                    resolution=(int(resolution[0]), int(resolution[1])),
                    fullscreen=bool(v.get("fullscreen", False)),
                    vsync=bool(v.get("vsync", False)),
                    fps_cap=int(v.get("fps_cap", 144)),
                    show_fps=bool(v.get("show_fps", False)),
                ),
                bindings=dict(data.get("bindings", DEFAULT_BINDINGS)),
            )
            settings.validate()
            return settings
        except Exception:
            return GameSettings()


# ---------------------------------------------------------------------------
# Tutorial contextual
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TutorialStep:
    id: str
    title: str
    text: str
    trigger: str
    once: bool = True
    priority: int = 1


TUTORIAL_STEPS: Dict[str, TutorialStep] = {
    step.id: step for step in (
        TutorialStep("move", "Movimento", "Use WASD para se mover. O posicionamento importa tanto quanto dano.", "game_started", priority=5),
        TutorialStep("attack", "Ataque", "Use o ataque básico para aprender o ritmo da sua classe.", "first_enemy_seen", priority=5),
        TutorialStep("dash", "Dash", "SPACE executa um dash com uma pequena janela de invulnerabilidade.", "first_damage_taken", priority=4),
        TutorialStep("skills", "Habilidades", "Use 1–4 para ativar habilidades equipadas. Elas ganham maestria com uso.", "first_skill_learned", priority=4),
        TutorialStep("rift", "Rupturas", "Rupturas aumentam risco e recompensa. Aceitar mais de uma pode transformar completamente a expedição.", "first_rift_seen", priority=5),
        TutorialStep("superior", "Superior", "Este inimigo possui mutações e pode guardar memória de encontros.", "first_superior_seen", priority=6),
        TutorialStep("memory", "Memória do Véu", "Algumas ameaças lembram tendências de runs anteriores. Mudar seu estilo pode ser tão importante quanto melhorar atributos.", "memory_rank_observer", priority=6),
        TutorialStep("hub", "Última Luz", "No Refúgio você prepara expedições, pesquisa criaturas, melhora instalações e cria equipamentos.", "first_hub_return", priority=3),
        TutorialStep("mastery", "Maestria", "Usar uma habilidade aperfeiçoa conjuração, custo, cooldown e pode liberar evoluções.", "first_mastery_up", priority=4),
        TutorialStep("corruption", "Corrupção", "Poder Corrompido cobra preço real. Leia o custo antes de aceitar.", "first_corrupted_offer", priority=6),
    )
}


def ensure_tutorial_state(state: PlayerState) -> Dict[str, object]:
    root = state.campaign.setdefault("tutorial", {})
    root.setdefault("seen", [])
    root.setdefault("disabled", False)
    root.setdefault("codex_unlocked", [])
    return root


def tutorial_for_trigger(state: PlayerState, trigger: str) -> Optional[TutorialStep]:
    root = ensure_tutorial_state(state)
    if root.get("disabled"):
        return None
    candidates = [x for x in TUTORIAL_STEPS.values() if x.trigger == trigger]
    candidates.sort(key=lambda x: x.priority, reverse=True)
    for step in candidates:
        if step.once and step.id in root["seen"]:
            continue
        return step
    return None


def mark_tutorial_seen(state: PlayerState, step_id: str) -> None:
    root = ensure_tutorial_state(state)
    if step_id in TUTORIAL_STEPS and step_id not in root["seen"]:
        root["seen"].append(step_id)


# ---------------------------------------------------------------------------
# Códice: explicações curtas que podem ser abertas sem internet.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CodexEntry:
    id: str
    title: str
    category: str
    text: str
    unlock_trigger: str


CODEX: Dict[str, CodexEntry] = {
    e.id: e for e in (
        CodexEntry("veu", "O Véu", "Mundo", "Barreira instável entre regiões e estados de realidade. Ele registra ecos de quem o atravessa.", "game_started"),
        CodexEntry("rupturas", "Rupturas", "Mecânica", "Feridas no Véu que modificam regras, inimigos e recompensas.", "first_rift_seen"),
        CodexEntry("memoria", "Memória do Véu", "Mecânica", "Ameaças especiais podem usar tendências de encontros anteriores para variar sua estratégia.", "memory_rank_observer"),
        CodexEntry("superiores", "Inimigos Superiores", "Combate", "Variantes nomeadas com mutações, loot e memória próprios.", "first_superior_seen"),
        CodexEntry("maestria", "Maestria", "Progressão", "Habilidades ficam mais eficientes conforme são realmente usadas.", "first_mastery_up"),
        CodexEntry("corrupcao", "Corrupção", "Progressão", "Poder do Vazio que troca segurança por força e pode alterar finais.", "first_corrupted_offer"),
        CodexEntry("refugio", "Refúgio da Última Luz", "Mundo", "Base persistente dos Riftwalkers e centro de preparação entre expedições.", "first_hub_return"),
        CodexEntry("faccoes", "Facções", "Mundo", "Grupos com visões diferentes sobre o que fazer com as Rupturas.", "first_faction_choice"),
        CodexEntry("provações", "Provações", "Pós-jogo", "Desafios opcionais com regras especiais e Ecos como recompensa.", "postgame_unlocked"),
        CodexEntry("ngplus", "Ciclos do Véu", "Pós-jogo", "NG+ mantém metaprogressão e aumenta perigo e recompensas gradualmente.", "ng_plus_started"),
    )
}


def unlock_codex_by_trigger(state: PlayerState, trigger: str) -> List[str]:
    root = ensure_tutorial_state(state)
    unlocked: List[str] = []
    for entry in CODEX.values():
        if entry.unlock_trigger == trigger and entry.id not in root["codex_unlocked"]:
            root["codex_unlocked"].append(entry.id)
            unlocked.append(entry.id)
    return unlocked


def experience_summary() -> Dict[str, int]:
    return {
        "difficulties": len(DIFFICULTIES),
        "tutorial_steps": len(TUTORIAL_STEPS),
        "codex_entries": len(CODEX),
        "input_actions": len(DEFAULT_BINDINGS),
    }

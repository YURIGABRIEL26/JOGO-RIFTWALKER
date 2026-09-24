"""RIFTWALKER — AUDIO / MUSIC / SUBTITLE ROUTER 0.9 RC

Não toca áudio diretamente: resolve eventos, prioridades, variações,
cooldowns, música e legendas. A camada Pygame/mixer apenas consome planos.
Isso permite validar toda a lógica sem placa de som ou assets instalados.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class AudioBus(str, Enum):
    MUSIC = "music"
    SFX = "sfx"
    VOICE = "voice"
    AMBIENCE = "ambience"
    UI = "ui"


@dataclass(frozen=True)
class AudioCue:
    id: str
    bus: AudioBus
    paths: Tuple[str, ...]
    volume: float = 1.0
    pitch_variance: float = 0.0
    cooldown: float = 0.0
    max_simultaneous: int = 4
    subtitle: Optional[str] = None
    priority: int = 1


@dataclass(frozen=True)
class PlaybackPlan:
    cue_id: str
    path: Optional[str]
    bus: AudioBus
    volume: float
    pitch: float
    subtitle: Optional[str]
    priority: int
    fallback_only: bool = False


@dataclass(frozen=True)
class MusicState:
    id: str
    path: str
    intensity: int
    fade_seconds: float
    loop: bool = True


CUES: Dict[str, AudioCue] = {}


def register_cue(cue: AudioCue) -> None:
    if cue.id in CUES:
        raise ValueError(f"Cue duplicado: {cue.id}")
    CUES[cue.id] = cue


# UI
for cue in (
    AudioCue("ui_confirm", AudioBus.UI, ("assets/audio/ui/confirm_01.ogg", "assets/audio/ui/confirm_02.ogg"), 0.65, 0.02, 0.05),
    AudioCue("ui_back", AudioBus.UI, ("assets/audio/ui/back.ogg",), 0.60, 0.0, 0.05),
    AudioCue("ui_hover", AudioBus.UI, ("assets/audio/ui/hover.ogg",), 0.35, 0.02, 0.04),
    AudioCue("ui_rare_drop", AudioBus.UI, ("assets/audio/ui/rare_drop.ogg",), 0.85, 0.0, 0.20, priority=3),
    AudioCue("ui_legendary_drop", AudioBus.UI, ("assets/audio/ui/legendary_drop.ogg",), 1.0, 0.0, 0.35, priority=5),
): register_cue(cue)

# Combate / impacto
for cue in (
    AudioCue("sword_swing", AudioBus.SFX, tuple(f"assets/audio/combat/sword_swing_{i:02d}.ogg" for i in range(1, 5)), 0.78, 0.055, 0.025, 6),
    AudioCue("sword_hit", AudioBus.SFX, tuple(f"assets/audio/combat/sword_hit_{i:02d}.ogg" for i in range(1, 5)), 0.90, 0.045, 0.018, 7),
    AudioCue("arrow_shot", AudioBus.SFX, tuple(f"assets/audio/combat/arrow_{i:02d}.ogg" for i in range(1, 4)), 0.75, 0.04, 0.025, 6),
    AudioCue("magic_cast", AudioBus.SFX, tuple(f"assets/audio/combat/magic_cast_{i:02d}.ogg" for i in range(1, 4)), 0.76, 0.035, 0.03, 6),
    AudioCue("fire_impact", AudioBus.SFX, tuple(f"assets/audio/combat/fire_impact_{i:02d}.ogg" for i in range(1, 4)), 0.90, 0.035, 0.04, 6),
    AudioCue("ice_break", AudioBus.SFX, ("assets/audio/combat/ice_break_01.ogg", "assets/audio/combat/ice_break_02.ogg"), 0.92, 0.03, 0.05, 5),
    AudioCue("parry", AudioBus.SFX, ("assets/audio/combat/parry_01.ogg", "assets/audio/combat/parry_02.ogg"), 1.0, 0.02, 0.08, 3, priority=5),
    AudioCue("dash", AudioBus.SFX, ("assets/audio/combat/dash_01.ogg", "assets/audio/combat/dash_02.ogg"), 0.68, 0.05, 0.06, 4),
    AudioCue("footstep", AudioBus.SFX, tuple(f"assets/audio/combat/footstep_{i:02d}.ogg" for i in range(1, 5)), 0.30, 0.04, 0.055, 2),
    AudioCue("player_hurt", AudioBus.SFX, ("assets/audio/combat/player_hurt_01.ogg", "assets/audio/combat/player_hurt_02.ogg"), 0.86, 0.02, 0.15, 2),
    AudioCue("enemy_death", AudioBus.SFX, tuple(f"assets/audio/combat/enemy_death_{i:02d}.ogg" for i in range(1, 4)), 0.70, 0.06, 0.04, 6),
    AudioCue("enemy_step_crawler", AudioBus.SFX, ("assets/audio/enemy/step_crawler.ogg",), 0.22, 0.015, 0.10, 2),
    AudioCue("enemy_step_light", AudioBus.SFX, ("assets/audio/enemy/step_light.ogg",), 0.18, 0.015, 0.10, 2),
    AudioCue("enemy_step_heavy", AudioBus.SFX, ("assets/audio/enemy/step_heavy.ogg",), 0.28, 0.015, 0.16, 2),
    AudioCue("enemy_attack_melee", AudioBus.SFX, ("assets/audio/enemy/attack_melee.ogg",), 0.40, 0.025, 0.08, 3),
    AudioCue("enemy_attack_ranged", AudioBus.SFX, ("assets/audio/enemy/attack_ranged.ogg",), 0.36, 0.025, 0.09, 3),
    AudioCue("enemy_hurt", AudioBus.SFX, ("assets/audio/enemy/hurt.ogg",), 0.28, 0.025, 0.10, 2),
    AudioCue("enemy_roar", AudioBus.SFX, ("assets/audio/enemy/roar.ogg",), 0.52, 0.02, 0.35, 2, priority=4),
    AudioCue("arrow_hit", AudioBus.SFX, ("assets/audio/combat/arrow_hit_01.ogg", "assets/audio/combat/arrow_hit_02.ogg"), 0.72, 0.035, 0.025, 7),
    AudioCue("arcane_impact", AudioBus.SFX, ("assets/audio/combat/arcane_impact_01.ogg", "assets/audio/combat/arcane_impact_02.ogg"), 0.82, 0.025, 0.03, 7),
    AudioCue("lightning_impact", AudioBus.SFX, ("assets/audio/combat/lightning_impact.ogg",), 0.88, 0.0, 0.04, 6),
    AudioCue("void_impact", AudioBus.SFX, ("assets/audio/combat/void_impact.ogg",), 0.88, 0.0, 0.05, 6),
    AudioCue("heal", AudioBus.SFX, ("assets/audio/combat/heal.ogg",), 0.72, 0.0, 0.10, 3),
    AudioCue("rift_open", AudioBus.SFX, ("assets/audio/rift/open.ogg",), 1.0, 0.0, 0.50, 2, priority=5),
    AudioCue("rift_accept", AudioBus.SFX, ("assets/audio/rift/accept.ogg",), 1.0, 0.0, 0.50, 2, priority=5),
    AudioCue("superior_spawn", AudioBus.SFX, ("assets/audio/enemy/superior_spawn.ogg",), 0.95, 0.02, 1.0, 1, priority=5),
    AudioCue("boss_phase", AudioBus.SFX, ("assets/audio/boss/phase_change.ogg",), 1.0, 0.0, 1.0, 1, priority=6),
    AudioCue("boss_death", AudioBus.SFX, ("assets/audio/boss/death.ogg",), 1.0, 0.0, 1.0, 1, priority=7),
): register_cue(cue)

# Ambiente
for cue in (
    AudioCue("amb_hub", AudioBus.AMBIENCE, ("assets/audio/ambience/hub.ogg",), 0.55, max_simultaneous=1),
    AudioCue("amb_fields", AudioBus.AMBIENCE, ("assets/audio/ambience/fields.ogg",), 0.55, max_simultaneous=1),
    AudioCue("amb_forest", AudioBus.AMBIENCE, ("assets/audio/ambience/forest.ogg",), 0.55, max_simultaneous=1),
    AudioCue("amb_bastion", AudioBus.AMBIENCE, ("assets/audio/ambience/bastion.ogg",), 0.55, max_simultaneous=1),
    AudioCue("amb_observatory", AudioBus.AMBIENCE, ("assets/audio/ambience/observatory.ogg",), 0.55, max_simultaneous=1),
    AudioCue("amb_abyss", AudioBus.AMBIENCE, ("assets/audio/ambience/abyss.ogg",), 0.60, max_simultaneous=1),
): register_cue(cue)


MUSIC: Dict[str, MusicState] = {
    "menu": MusicState("menu", "assets/audio/music/menu_theme.ogg", 0, 1.2),
    "hub": MusicState("hub", "assets/audio/music/last_light.ogg", 0, 1.5),
    "exploration": MusicState("exploration", "assets/audio/music/beyond_the_veil.ogg", 1, 1.2),
    "combat": MusicState("combat", "assets/audio/music/rupture_combat.ogg", 2, 0.65),
    "elite": MusicState("elite", "assets/audio/music/superior_hunt.ogg", 3, 0.55),
    "boss": MusicState("boss", "assets/audio/music/boss_veilbreaker.ogg", 4, 0.45),
    "boss_final": MusicState("boss_final", "assets/audio/music/the_nameless.ogg", 5, 0.40),
    "ending": MusicState("ending", "assets/audio/music/after_the_rift.ogg", 0, 2.0, False),
}


@dataclass
class SubtitleLine:
    speaker: str
    text: str
    duration: float
    priority: int
    elapsed: float = 0.0


class SubtitleQueue:
    def __init__(self):
        self.current: Optional[SubtitleLine] = None
        self.pending: List[SubtitleLine] = []

    def push(self, line: SubtitleLine) -> None:
        if self.current is None:
            self.current = line
            return
        if line.priority > self.current.priority:
            self.pending.insert(0, self.current)
            self.current = line
        else:
            self.pending.append(line)
        self.pending = self.pending[:8]

    def update(self, dt: float) -> None:
        if self.current is None:
            if self.pending:
                self.current = self.pending.pop(0)
            return
        self.current.elapsed += max(0.0, dt)
        if self.current.elapsed >= self.current.duration:
            self.current = self.pending.pop(0) if self.pending else None


class AudioRouter:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.cooldowns: Dict[str, float] = {}
        self.active_counts: Dict[str, int] = {}

    def update(self, dt: float) -> None:
        for key in list(self.cooldowns):
            self.cooldowns[key] = max(0.0, self.cooldowns[key] - max(0.0, dt))
            if self.cooldowns[key] <= 0:
                del self.cooldowns[key]

    def resolve(self, cue_id: str, asset_root: str = ".") -> Optional[PlaybackPlan]:
        cue = CUES.get(cue_id)
        if cue is None or cue_id in self.cooldowns:
            return None
        if self.active_counts.get(cue_id, 0) >= cue.max_simultaneous:
            return None

        candidates = list(cue.paths)
        self.rng.shuffle(candidates)
        chosen = next((p for p in candidates if (Path(asset_root) / p).exists()), None)
        fallback = chosen is None
        if chosen is None and candidates:
            chosen = candidates[0]
        pitch = 1.0 + self.rng.uniform(-cue.pitch_variance, cue.pitch_variance)
        if cue.cooldown > 0:
            self.cooldowns[cue_id] = cue.cooldown
        return PlaybackPlan(cue.id, chosen, cue.bus, cue.volume, pitch, cue.subtitle, cue.priority, fallback)

    def mark_started(self, cue_id: str) -> None:
        self.active_counts[cue_id] = self.active_counts.get(cue_id, 0) + 1

    def mark_finished(self, cue_id: str) -> None:
        self.active_counts[cue_id] = max(0, self.active_counts.get(cue_id, 0) - 1)


class MusicDirector:
    def __init__(self):
        self.current: Optional[str] = None

    def desired_state(
        self,
        in_hub: bool = False,
        in_combat: bool = False,
        elite_present: bool = False,
        boss_present: bool = False,
        final_boss: bool = False,
        ending: bool = False,
    ) -> MusicState:
        if ending: return MUSIC["ending"]
        if final_boss: return MUSIC["boss_final"]
        if boss_present: return MUSIC["boss"]
        if elite_present: return MUSIC["elite"]
        if in_combat: return MUSIC["combat"]
        if in_hub: return MUSIC["hub"]
        return MUSIC["exploration"]

    def transition_plan(self, desired: MusicState) -> Optional[Tuple[Optional[str], str, float]]:
        if self.current == desired.id:
            return None
        old = self.current
        self.current = desired.id
        return old, desired.id, desired.fade_seconds


def expected_audio_assets() -> Tuple[str, ...]:
    paths = {p for cue in CUES.values() for p in cue.paths}
    paths.update(state.path for state in MUSIC.values())
    return tuple(sorted(paths))


def audio_summary() -> Dict[str, int]:
    return {
        "cues": len(CUES),
        "music_states": len(MUSIC),
        "expected_assets": len(expected_audio_assets()),
    }

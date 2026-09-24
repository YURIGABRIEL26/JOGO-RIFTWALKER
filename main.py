from __future__ import annotations

import math
import os
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from core_systems import (
    ActiveRiftState,
    AutosaveController,
    AutosaveReason,
    CLASS_REGISTRY,
    CharacterIdentity,
    CombatTelemetry,
    DamageType,
    FixedTimestep,
    Gender,
    MemoryRank,
    PlayerState,
    RARITY_INFO,
    RIFT_REGISTRY,
    Rarity,
    ReactionController,
    ReactionEvent,
    SaveManager,
    SKILL_REGISTRY,
    SkillCategory,
    SkillDefinition,
    SquadDoctrine,
    SQUAD_DOCTRINES,
    choose_squad_doctrine,
    create_new_character,
    generate_skill_offers,
)

from content_systems import (
    EQUIPMENT_REGISTRY,
    EquipmentSlot,
    active_set_bonuses,
    active_unique_effects,
    equip_item,
    equipment_modifiers,
    evaluate_class_unlocks,
    inventory_equipment_ids,
    make_inventory_item,
    roll_equipment_drop,
    rule_for_class,
    transfer_meta_progression,
)

from narrative_systems import (
    CampaignDirector,
    CampaignEvent,
    QUESTS,
    REGIONS,
    chapter_title,
)

from hub_systems import (
    ensure_hub_state,
    reward_boss_materials,
    reward_rift_materials,
    FACILITIES, MATERIALS, upgrade_facility, facility_level,
    material_count, gold, echoes,
)

from creature_systems import (
    CREATURES,
    CreatureTier,
    apply_traits_to_enemy,
    creature_id_for_archetype,
    knowledge_rank,
    mutation_display,
    record_encounter,
    record_kill,
    record_superior_history,
    roll_spawn_traits,
    superior_memory_id,
    record_death_to,
)

# 0.9 RC: estes módulos registram os kits e o conteúdo final no motor.
from class_kit_systems import behavior_for, CLASS_KITS
from boss_systems import BOSSES, BossDirector
from endgame_systems import (
    FINAL_BOSS_ID,
    ECHO_BOSS_ID,
    final_boss_available,
    record_final_boss_defeat,
    record_echo_boss_defeat,
    eligible_endings,
    choose_ending,
)
from combat_status_systems import Element, StatusController, StatusId
from build_synergy_systems import synergy_modifiers, available_evolutions, evolve_skill
from challenge_systems import add_metric, progress_trial_room
from legacy_systems import legacy_modifiers
from encounter_director_systems import EncounterDirector, PerformanceSnapshot
from world_generation_systems import (
    RoomType, begin_generated_expedition, load_active_map, save_active_map, complete_generated_expedition,
)
from profile_systems import ProfileManager
from player_experience_systems import SettingsManager, DIFFICULTIES, CODEX
from pygame_audio_runtime import PygameAudioRuntime
from runtime_diagnostics import RuntimeDiagnostics, trim_oldest, write_crash_report
from environment_systems import EnvironmentRenderer

# ============================================================
# RIFTWALKER — RELEASE CANDIDATE 0.9
# ============================================================
#
# Este arquivo liga o motor de sistemas (core_systems.py) ao
# Pygame e transforma a arquitetura em uma versão jogável.
#
# CONTROLES
# WASD       mover
# Mouse      mirar
# Clique 1   ataque básico
# Clique 2   habilidade contextual / especial da classe
# Q/E/R/F    habilidades equipadas (1..4 também funcionam)
# SHIFT      defesa/parry quando disponível
# Mouse/setas direcionais = mira
# SPACE      dash
# ESC        pausa/voltar
# F3         debug FPS
#
# IMPORTANTE:
# - lógica de jogo usa fixed timestep em 60 Hz;
# - render pode rodar em FPS maior sem alterar gameplay;
# - autosave acontece em pontos seguros, não por frame.
# ============================================================

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

# Em execução .py, saves/settings ficam ao lado do projeto para facilitar a escola e o debug.
# Em um .exe PyInstaller, usamos uma pasta gravável do usuário em vez do diretório temporário _MEIPASS.
if getattr(sys, "frozen", False):
    _appdata = os.environ.get("APPDATA")
    DATA_DIR = (Path(_appdata) if _appdata else Path.home()) / "RIFTWALKER"
else:
    DATA_DIR = Path(__file__).resolve().parent
DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_MANAGER = SettingsManager(str(DATA_DIR / "settings.json"))
GAME_SETTINGS = SETTINGS_MANAGER.load()
WIDTH, HEIGHT = GAME_SETTINGS.video.resolution
RENDER_FPS_CAP = GAME_SETTINGS.video.fps_cap
LOGIC_UPS = 60

_video_flags = pygame.FULLSCREEN if GAME_SETTINGS.video.fullscreen else 0
try:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), _video_flags, vsync=1 if GAME_SETTINGS.video.vsync else 0)
except TypeError:
    screen = pygame.display.set_mode((WIDTH, HEIGHT), _video_flags)
pygame.display.set_caption("RIFTWALKER — Release Candidate 0.9")
clock = pygame.time.Clock()
stepper = FixedTimestep(updates_per_second=LOGIC_UPS)
AUDIO = PygameAudioRuntime(GAME_SETTINGS, str(BASE_DIR))

# ============================================================
# FONTES / CORES
# ============================================================

_UI_SCALE = 1.14 if GAME_SETTINGS.accessibility.larger_ui else 1.0
def _fs(size: int) -> int:
    return max(10, int(size * _UI_SCALE))
FONT_TINY = pygame.font.SysFont("consolas", _fs(13))
FONT_SMALL = pygame.font.SysFont("consolas", _fs(16))
FONT = pygame.font.SysFont("consolas", _fs(20))
FONT_MEDIUM = pygame.font.SysFont("consolas", _fs(28), bold=True)
FONT_BIG = pygame.font.SysFont("consolas", _fs(48), bold=True)
FONT_TITLE = pygame.font.SysFont("consolas", _fs(76), bold=True)

WHITE = (238, 241, 248)
BLACK = (7, 8, 13)
BG = (12, 14, 23)
BG_2 = (18, 21, 33)
PANEL = (29, 33, 48)
PANEL_HOVER = (42, 48, 69)
GRID = (37, 42, 59)
GRAY = (144, 151, 169)
DARK_GRAY = (73, 80, 96)
RED = (232, 72, 78)
GREEN = (73, 214, 127)
BLUE = (82, 151, 245)
CYAN = (69, 225, 235)
PURPLE = (173, 93, 236)
YELLOW = (246, 216, 83)
ORANGE = (246, 140, 52)
PINK = (236, 91, 178)

RARITY_COLORS = {
    Rarity.COMUM: (210, 215, 225),
    Rarity.INCOMUM: (92, 220, 126),
    Rarity.RARA: (80, 152, 245),
    Rarity.EPICA: (175, 92, 238),
    Rarity.LENDARIA: (246, 190, 63),
    Rarity.MITICA: (75, 236, 235),
    Rarity.CORROMPIDA: (235, 62, 95),
}

CLASS_COLORS = {
    "guerreiro": RED,
    "mago": CYAN,
    "arqueiro": YELLOW,
    "ceifador": (177, 74, 164),
    "rasgado": (212, 54, 87),
    "cronista": (79, 188, 210),
    "artifice": ORANGE,
    "duelista": (236, 226, 205),
    "oraculo": PURPLE,
    "guardiao_veu": BLUE,
}

DAMAGE_ELEMENT_MAP = {
    DamageType.FISICO: Element.FISICO,
    DamageType.FOGO: Element.FOGO,
    DamageType.GELO: Element.GELO,
    DamageType.RAIO: Element.RAIO,
    DamageType.SOMBRA: Element.SOMBRA,
    DamageType.VAZIO: Element.VAZIO,
    DamageType.TEMPORAL: Element.TEMPORAL,
    DamageType.ARCANO: Element.ARCANO,
    DamageType.SANGRAMENTO: Element.FISICO,
    DamageType.PURO: Element.ARCANO,
}

# ============================================================
# SKINS / ANIMACAO VISUAL DO JOGADOR
# ============================================================

PLAYER_SKIN_CACHE: Dict[Tuple[str, str], pygame.Surface] = {}

def _gender_asset_key(gender: Gender) -> str:
    return "feminino" if gender == Gender.FEMININO else "masculino"

def get_player_skin(class_id: str, gender: Gender) -> Optional[pygame.Surface]:
    key = (class_id, _gender_asset_key(gender))
    if key in PLAYER_SKIN_CACHE:
        return PLAYER_SKIN_CACHE[key]
    path = BASE_DIR / "assets" / "sprites" / "player" / class_id / f"{key[1]}.png"
    if not path.exists():
        PLAYER_SKIN_CACHE[key] = None
        return None
    try:
        img = pygame.image.load(str(path)).convert_alpha()
        # Failsafe para assets cujo RGB está íntegro, mas o recorte alpha veio
        # quase todo transparente. Evita personagem invisível no runtime.
        area = max(1, img.get_width() * img.get_height())
        coverage = pygame.mask.from_surface(img, 10).count() / area
        if coverage < 0.08:
            opaque = pygame.image.load(str(path)).convert()
            recovered = pygame.Surface(opaque.get_size(), pygame.SRCALPHA)
            recovered.blit(opaque, (0, 0))
            vignette = pygame.Surface(opaque.get_size(), pygame.SRCALPHA)
            inset_x = max(2, int(opaque.get_width() * 0.025))
            inset_y = max(2, int(opaque.get_height() * 0.015))
            rect = pygame.Rect(inset_x, inset_y, opaque.get_width() - inset_x * 2, opaque.get_height() - inset_y * 2)
            pygame.draw.rect(vignette, (255, 255, 255, 255), rect, border_radius=max(10, min(rect.width, rect.height) // 7))
            recovered.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            img = recovered
    except Exception:
        PLAYER_SKIN_CACHE[key] = None
        return None
    PLAYER_SKIN_CACHE[key] = img
    return img

def draw_tinted(surface: pygame.Surface, image: pygame.Surface, pos, tint=(255,255,255), alpha=255):
    frame = image.copy()
    if tint != (255,255,255):
        frame.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
    frame.set_alpha(alpha)
    surface.blit(frame, pos)


# ============================================================
# SPRITES / ANIMACAO VISUAL DOS INIMIGOS
# ============================================================

ENEMY_SKIN_CACHE: Dict[str, Optional[pygame.Surface]] = {}

def get_enemy_skin(kind: str, boss_id: Optional[str] = None) -> Optional[pygame.Surface]:
    # Bosses têm arte própria; inimigos normais usam o arquétipo.
    key = boss_id if boss_id else kind
    if key == "guardian" or not key:
        key = "guardiao_primeira_ruptura"
    if key in ENEMY_SKIN_CACHE:
        return ENEMY_SKIN_CACHE[key]
    path = BASE_DIR / "assets" / "sprites" / "enemies" / f"{key}.png"
    if not path.exists():
        ENEMY_SKIN_CACHE[key] = None
        return None
    try:
        image = pygame.image.load(str(path)).convert_alpha()
    except Exception:
        ENEMY_SKIN_CACHE[key] = None
        return None
    ENEMY_SKIN_CACHE[key] = image
    return image


def enemy_tier_color(tier: str) -> Tuple[int, int, int]:
    raw = str(tier).lower()
    if "super" in raw:
        return (244, 77, 205)
    if "elite" in raw:
        return (246, 190, 63)
    if "boss" in raw:
        return (246, 90, 64)
    return (110, 118, 140)


# Cache geométrico: evita smoothscale/flip/rotate repetidos para os mesmos estados.
# Dimensões e ângulos são quantizados de propósito para limitar memória e manter
# a animação visual suave sem criar milhares de Surfaces diferentes.
SPRITE_TRANSFORM_CACHE: Dict[Tuple[int, int, int, bool, int], pygame.Surface] = {}
SPRITE_TRANSFORM_CACHE_LIMIT = 640

def cached_sprite_transform(image: pygame.Surface, width: int, height: int, flip_x: bool, angle: float) -> pygame.Surface:
    qw = max(2, int(round(width / 2.0) * 2))
    qh = max(2, int(round(height / 2.0) * 2))
    qa = int(round(angle / 2.0) * 2)
    key = (id(image), qw, qh, bool(flip_x), qa)
    cached = SPRITE_TRANSFORM_CACHE.get(key)
    if cached is not None:
        return cached
    frame = pygame.transform.smoothscale(image, (qw, qh))
    if flip_x:
        frame = pygame.transform.flip(frame, True, False)
    if qa:
        frame = pygame.transform.rotate(frame, qa)
    if len(SPRITE_TRANSFORM_CACHE) >= SPRITE_TRANSFORM_CACHE_LIMIT:
        # Limpeza simples e previsível; melhor um pico raro de rebuild do que cache sem limite.
        SPRITE_TRANSFORM_CACHE.clear()
    SPRITE_TRANSFORM_CACHE[key] = frame
    return frame



def elemental_payload_for_skill(skill_id: Optional[str]):
    skill = SKILL_REGISTRY.get(skill_id or "")
    if skill is None:
        return Element.FISICO, ()
    element = DAMAGE_ELEMENT_MAP.get(skill.damage_type, Element.FISICO)
    tags = set(skill.tags)
    applied = []
    if element == Element.FOGO:
        applied.append((StatusId.QUEIMANDO, 1))
    elif element == Element.GELO:
        applied.append((StatusId.RESFRIADO, 1))
        if "control" in tags:
            applied.append((StatusId.RESFRIADO, 1))
    elif element == Element.RAIO:
        applied.append((StatusId.ELETRIZADO, 1))
    elif element == Element.SOMBRA:
        applied.append((StatusId.AMALDICOADO, 1))
    elif element == Element.VAZIO:
        applied.append((StatusId.CORROMPIDO, 1))
    elif element == Element.TEMPORAL:
        applied.append((StatusId.LENTO, 1))
    if "bleed" in tags:
        applied.append((StatusId.SANGRANDO, 1))
    if "mark" in tags:
        applied.append((StatusId.MARCADO, 1))
    return element, tuple(applied)

ROOM = pygame.Rect(55, 78, WIDTH - 110, HEIGHT - 145)

SAVE_DIR = DATA_DIR / "saves"
SAVE_DIR.mkdir(parents=True, exist_ok=True)
SAVE_PATH = SAVE_DIR / "save_riftwalker.json"

# ============================================================
# HELPERS
# ============================================================

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize(v: pygame.Vector2) -> pygame.Vector2:
    if v.length_squared() <= 0.00001:
        return pygame.Vector2(1, 0)
    return v.normalize()


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def draw_text(
    surface: pygame.Surface,
    text: str,
    pos: Tuple[float, float] | pygame.Vector2,
    color=WHITE,
    font=FONT,
    center: bool = False,
):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = (int(pos[0]), int(pos[1]))
    else:
        rect.topleft = (int(pos[0]), int(pos[1]))
    surface.blit(img, rect)
    return rect


def draw_wrapped_text(
    surface: pygame.Surface,
    text: str,
    rect: pygame.Rect,
    color=WHITE,
    font=FONT_SMALL,
    line_spacing: int = 3,
):
    words = text.split()
    lines: List[str] = []
    current = ""

    for word in words:
        test = word if not current else current + " " + word
        if font.size(test)[0] <= rect.width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    y = rect.top
    for line in lines:
        if y + font.get_height() > rect.bottom:
            break
        draw_text(surface, line, (rect.left, y), color, font)
        y += font.get_height() + line_spacing


def draw_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    value: float,
    maximum: float,
    color,
    border_color=WHITE,
):
    pygame.draw.rect(surface, (6, 8, 14), rect.move(0, 3), border_radius=5)
    pygame.draw.rect(surface, (45, 50, 65), rect, border_radius=5)
    ratio = 0.0 if maximum <= 0 else clamp(value / maximum, 0.0, 1.0)
    fill = rect.copy()
    fill.width = int(rect.width * ratio)
    if fill.width > 0:
        pygame.draw.rect(surface, color, fill, border_radius=5)
        pygame.draw.line(surface, tuple(min(255, c + 55) for c in color), (fill.x + 5, fill.y + 2), (max(fill.x + 5, fill.right - 5), fill.y + 2), 1)
    pygame.draw.rect(surface, border_color, rect, 1, border_radius=5)


def draw_ui_panel(surface, rect, accent=CYAN, fill=PANEL, radius=10, glow=False):
    shadow = rect.move(0, 5)
    pygame.draw.rect(surface, (5, 6, 12), shadow, border_radius=radius)
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if glow:
        glow_rect = rect.inflate(6, 6)
        pygame.draw.rect(surface, (*accent, 34), glow_rect, 2, border_radius=radius + 2)
    pygame.draw.rect(surface, accent, rect, 2, border_radius=radius)
    pygame.draw.line(surface, (*accent, 150), (rect.x + 14, rect.y + 2), (rect.right - 14, rect.y + 2), 2)


def point_in_circle(a: pygame.Vector2, b: pygame.Vector2, radius: float) -> bool:
    return a.distance_squared_to(b) <= radius * radius


def circle_collision(
    a_pos: pygame.Vector2,
    a_radius: float,
    b_pos: pygame.Vector2,
    b_radius: float,
) -> bool:
    r = a_radius + b_radius
    return a_pos.distance_squared_to(b_pos) <= r * r


def difficulty_label(value: int) -> str:
    return {
        1: "Fácil",
        2: "Média",
        3: "Difícil",
        4: "Alta",
        5: "Extrema",
    }.get(value, "?")


# ============================================================
# VISUAIS PROCEDURAIS
# ============================================================

@dataclass
class Particle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    color: Tuple[int, int, int]
    life: float
    max_life: float
    radius: float
    drag: float = 0.92
    dead: bool = False

    @classmethod
    def burst(
        cls,
        pos: pygame.Vector2,
        color,
        speed_min=70.0,
        speed_max=240.0,
        life=0.42,
        radius=5.0,
    ) -> "Particle":
        angle = random.uniform(0, math.tau)
        speed = random.uniform(speed_min, speed_max)
        vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
        actual_life = life * random.uniform(0.7, 1.2)
        return cls(
            pos=pygame.Vector2(pos),
            vel=vel,
            color=color,
            life=actual_life,
            max_life=actual_life,
            radius=random.uniform(max(1.0, radius * 0.45), radius),
        )

    def update(self, dt: float):
        self.pos += self.vel * dt
        self.vel *= self.drag
        self.life -= dt
        if self.life <= 0:
            self.dead = True

    def draw(self, surface, offset):
        ratio = clamp(self.life / self.max_life, 0.0, 1.0)
        radius = max(1, int(self.radius * ratio))
        pygame.draw.circle(surface, self.color, self.pos + offset, radius)


@dataclass
class FloatingText:
    pos: pygame.Vector2
    text: str
    color: Tuple[int, int, int]
    life: float = 0.72
    max_life: float = 0.72
    dead: bool = False

    def update(self, dt: float):
        self.pos.y -= 42 * dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True

    def draw(self, surface, offset):
        draw_text(surface, self.text, self.pos + offset, self.color, FONT_SMALL, True)


@dataclass
class SlashVisual:
    pos: pygame.Vector2
    direction: pygame.Vector2
    color: Tuple[int, int, int]
    radius: float
    life: float = 0.13
    max_life: float = 0.13
    width: int = 10
    dead: bool = False

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.dead = True

    def draw(self, surface, offset):
        progress = 1.0 - clamp(self.life / self.max_life, 0.0, 1.0)
        angle = math.atan2(self.direction.y, self.direction.x)
        start = angle - 0.8 + 0.15 * progress
        end = angle + 0.8 + 0.15 * progress
        rect = pygame.Rect(
            self.pos.x - self.radius + offset.x,
            self.pos.y - self.radius + offset.y,
            self.radius * 2,
            self.radius * 2,
        )
        pygame.draw.arc(surface, self.color, rect, start, end, self.width)


@dataclass
class SpeechBubble:
    text: str
    speaker: str
    color: Tuple[int, int, int]
    life: float
    max_life: float
    priority: int = 1
    dead: bool = False

    def update(self, dt):
        self.life -= dt
        if self.life <= 0:
            self.dead = True

    def draw(self, surface):
        alpha = int(220 * clamp(self.life / self.max_life, 0.0, 1.0))
        box = pygame.Surface((760, 68), pygame.SRCALPHA)
        box.fill((9, 11, 18, alpha))
        pygame.draw.rect(box, (*self.color, alpha), box.get_rect(), 2, border_radius=8)
        draw_text(box, self.speaker, (14, 8), self.color, FONT_SMALL)
        draw_text(box, self.text, (14, 31), WHITE, FONT)
        surface.blit(box, (WIDTH // 2 - 380, HEIGHT - 132))


@dataclass
class AreaEffect:
    kind: str
    pos: pygame.Vector2
    radius: float
    duration: float
    owner: str
    damage: float = 0.0
    tick_interval: float = 0.25
    tick_timer: float = 0.0
    delay: float = 0.0
    color: Tuple[int, int, int] = CYAN
    dead: bool = False
    triggered: bool = False

    def update(self, dt, game: "Game"):
        if self.delay > 0:
            self.delay -= dt
            if self.delay <= 0:
                self.triggered = True
                game.add_shake(10, 0.15)
                for _ in range(28):
                    game.particles.append(Particle.burst(self.pos, self.color, 100, 320, 0.5, 7))
            return

        self.triggered = True
        self.duration -= dt
        self.tick_timer -= dt

        if self.tick_timer <= 0:
            self.tick_timer = self.tick_interval

            if self.owner == "player":
                for enemy in game.enemies:
                    if enemy.dead:
                        continue
                    if point_in_circle(enemy.pos, self.pos, self.radius + enemy.radius):
                        if self.kind == "ice_prison":
                            enemy.slow_timer = max(enemy.slow_timer, 0.55)
                            enemy.take_damage(self.damage, game, critical=False)
                        elif self.kind == "arrow_rain":
                            enemy.take_damage(self.damage, game, critical=False)
                        elif self.kind == "singularity":
                            direction = normalize(self.pos - enemy.pos)
                            enemy.pos += direction * 18
                            enemy.take_damage(self.damage, game, critical=False)

        if self.duration <= 0:
            if self.kind == "singularity":
                for enemy in game.enemies:
                    if enemy.dead:
                        continue
                    if point_in_circle(enemy.pos, self.pos, self.radius + enemy.radius):
                        enemy.take_damage(self.damage * 3.4, game, critical=True)
                game.add_shake(16, 0.23)
                game.hit_stop = max(game.hit_stop, 0.08)
            self.dead = True

    def draw(self, surface, offset):
        p = self.pos + offset
        now = pygame.time.get_ticks() * 0.001

        # Telegraph continua legível, mas deixa de ser um círculo vazio genérico.
        if self.delay > 0:
            pulse = 2 + int(abs(math.sin(now * 9.0)) * 3)
            pygame.draw.circle(surface, self.color, p, int(self.radius), pulse)
            inner = max(12, int(self.radius * (0.45 + 0.06 * math.sin(now * 7.0))))
            pygame.draw.circle(surface, (*self.color,), p, inner, 2)
            for a in range(0, 360, 90):
                v1 = pygame.Vector2(1, 0).rotate(a + now * 55) * (self.radius * 0.62)
                v2 = pygame.Vector2(1, 0).rotate(a + now * 55) * (self.radius * 0.86)
                pygame.draw.line(surface, self.color, p + v1, p + v2, 3)
            return

        if self.kind == "singularity":
            # Núcleo negro com anéis em rotação e pequenos braços de distorção.
            pygame.draw.circle(surface, (8, 5, 18), p, int(self.radius))
            for scale, width in ((0.92, 3), (0.68, 2), (0.42, 2)):
                rr = max(8, int(self.radius * scale))
                rect = pygame.Rect(p.x - rr, p.y - rr * 0.55, rr * 2, rr * 1.1)
                pygame.draw.arc(surface, self.color, rect, now * 1.7, now * 1.7 + math.pi * 1.35, width)
            pygame.draw.circle(surface, WHITE, p, 7)
            pygame.draw.circle(surface, self.color, p, 14, 3)
        elif self.kind == "ice_prison":
            # Prisão formada por cristais, não apenas um círculo.
            pygame.draw.circle(surface, self.color, p, int(self.radius), 2)
            for angle in range(0, 360, 45):
                d = pygame.Vector2(1, 0).rotate(angle)
                side = d.rotate(90)
                tip = p + d * self.radius
                base = p + d * (self.radius * 0.58)
                crystal = [tip, base + side * 8, base - side * 8]
                pygame.draw.polygon(surface, self.color, crystal)
                pygame.draw.line(surface, WHITE, base, tip, 2)
        elif self.kind == "arrow_rain":
            # Setas visíveis caindo sobre a área.
            pygame.draw.circle(surface, self.color, p, int(self.radius), 2)
            for i in range(7):
                angle = (i * 137.5 + now * 23.0) % 360
                dist = self.radius * (0.25 + 0.65 * ((i * 0.31 + now * 0.17) % 1.0))
                q = p + pygame.Vector2(1, 0).rotate(angle) * dist
                pygame.draw.line(surface, WHITE, q + (-5, -16), q + (3, 7), 3)
                pygame.draw.line(surface, self.color, q + (3, 7), q + (-3, 1), 2)
                pygame.draw.line(surface, self.color, q + (3, 7), q + (6, 0), 2)
        elif self.kind == "magic_burst":
            # Selo rúnico de explosão.
            pygame.draw.circle(surface, self.color, p, int(self.radius), 3)
            pygame.draw.circle(surface, WHITE, p, max(10, int(self.radius * 0.24)), 2)
            pts = []
            for i in range(6):
                pts.append(p + pygame.Vector2(1, 0).rotate(i * 60 + now * 35) * self.radius * 0.58)
            pygame.draw.polygon(surface, self.color, pts, 2)
            for q in pts[::2]:
                pygame.draw.line(surface, self.color, p, q, 2)
        else:
            # Área genérica com runas rotativas em vez de aro vazio.
            pygame.draw.circle(surface, self.color, p, int(self.radius), 2)
            for a in (0, 120, 240):
                q = p + pygame.Vector2(1, 0).rotate(a + now * 40) * self.radius * 0.72
                pygame.draw.circle(surface, self.color, q, 5, 2)


# ============================================================
# PROJÉTEIS
# ============================================================

@dataclass
class Projectile:
    pos: pygame.Vector2
    vel: pygame.Vector2
    damage: float
    color: Tuple[int, int, int]
    owner: str
    radius: float = 6.0
    life: float = 2.0
    pierce: int = 0
    explosion_radius: float = 0.0
    skill_id: Optional[str] = None
    bleed_damage: float = 0.0
    dead: bool = False
    hit_ids: set = field(default_factory=set)

    def update(self, dt: float, game: "Game"):
        self.pos += self.vel * dt
        self.life -= dt

        if self.life <= 0:
            self.dead = True

        if not ROOM.inflate(150, 150).collidepoint(self.pos):
            self.dead = True

    def explode(self, game: "Game"):
        if self.explosion_radius <= 0:
            return

        game.add_shake(8, 0.13)
        for _ in range(22):
            game.particles.append(
                Particle.burst(self.pos, self.color, 80, 290, 0.45, 7)
            )

        for enemy in game.enemies:
            if enemy.dead:
                continue
            if point_in_circle(enemy.pos, self.pos, self.explosion_radius + enemy.radius):
                enemy.take_damage(self.damage * 0.68, game, critical=False)

    def draw(self, surface, offset):
        p = self.pos + offset
        direction = normalize(self.vel)
        side = direction.rotate(90)
        speed = self.vel.length()
        sid = self.skill_id or ""
        skill = SKILL_REGISTRY.get(sid)
        dtype = skill.damage_type if skill is not None else None
        tags = set(skill.tags) if skill is not None else set()
        now = pygame.time.get_ticks() * 0.001

        def line(a, b, color, width):
            pygame.draw.line(surface, color, a, b, max(1, int(width)))

        def arrow(length=34, width=8, color=None):
            c = color or self.color
            tail = p - direction * length * 0.58
            tip = p + direction * length * 0.55
            line(tail, tip, c, max(2, width // 3))
            line(tail, tip, WHITE, 1)
            head = [tip, tip - direction * width * 1.5 + side * width * 0.75, tip - direction * width * 1.5 - side * width * 0.75]
            pygame.draw.polygon(surface, c, head)
            # penas
            line(tail, tail + direction * width + side * width * 0.65, c, 2)
            line(tail, tail + direction * width - side * width * 0.65, c, 2)

        # Flechas e disparos perfurantes: silhueta longa e reconhecível.
        if sid in {"arrow", "burst_arrow", "ricochet", "horizonte_partido"} or "arrow" in tags:
            if sid == "horizonte_partido":
                for k, w in ((52, 10), (38, 5), (25, 2)):
                    line(p - direction * k, p + direction * 26, CYAN if w > 2 else WHITE, w)
                pygame.draw.polygon(surface, WHITE, [p + direction*34, p + direction*14 + side*9, p + direction*14 - side*9])
            else:
                arrow(46 if sid == "burst_arrow" else 38, 9 if sid == "burst_arrow" else 7, YELLOW if sid != "ricochet" else CYAN)
            return

        # Fogo: cometa com cauda, núcleo e pequenas labaredas.
        if sid == "bola_de_fogo" or dtype == DamageType.FOGO:
            for dist, rr, c in ((30, 7, RED), (20, 9, ORANGE), (10, 10, YELLOW)):
                pygame.draw.circle(surface, c, p - direction * dist, rr)
            pygame.draw.circle(surface, ORANGE, p, int(self.radius + 5))
            pygame.draw.circle(surface, YELLOW, p, max(5, int(self.radius)))
            pygame.draw.circle(surface, WHITE, p + direction * 2, 3)
            return

        # Gelo: estilhaço cristalino em forma de lança.
        if dtype == DamageType.GELO or "ice" in tags:
            tip = p + direction * 18
            back = p - direction * 18
            pts = [tip, p + side * 8, back, p - side * 8]
            pygame.draw.polygon(surface, CYAN, pts)
            pygame.draw.polygon(surface, WHITE, [tip, p + side*2, back], 2)
            line(back - direction*18, back, (110, 200, 255), 4)
            return

        # Raio: zig-zag, não esfera.
        if dtype == DamageType.RAIO or "lightning" in tags:
            points = [p - direction * 34]
            for i in range(1, 5):
                t = i / 5.0
                jitter = side * (7 if i % 2 else -7) * (0.75 + 0.25 * math.sin(now * 20 + i))
                points.append(p - direction * (34 - 68*t) + jitter)
            points.append(p + direction * 34)
            pygame.draw.lines(surface, CYAN, False, points, 5)
            pygame.draw.lines(surface, WHITE, False, points, 2)
            return

        # Temporal: losango/estilhaço com eco atrás.
        if sid == "temporal_shard" or dtype == DamageType.TEMPORAL:
            pts = [p + direction*19, p + side*7, p - direction*16, p - side*7]
            pygame.draw.polygon(surface, CYAN, pts)
            pygame.draw.polygon(surface, WHITE, pts, 2)
            for i in range(1, 4):
                q = p - direction * (i * 13)
                pygame.draw.polygon(surface, (79,188,210), [q+direction*7, q+side*3, q-direction*6, q-side*3], 1)
            return

        # Ruptura/Vazio/Sombra: lâmina crescente com rastro quebrado.
        if sid in {"rasgado_basic", "arkhon_rift"} or dtype in {DamageType.VAZIO, DamageType.SOMBRA} or "rift" in tags:
            length = 32 if sid != "arkhon_rift" else 48
            a = p - direction * length * 0.45
            b = p + direction * length * 0.55
            line(a, b, PURPLE if sid == "arkhon_rift" else RED, 8 if sid == "arkhon_rift" else 6)
            line(a + side*6, b, WHITE, 2)
            for i in range(3):
                q = a - direction * (8 + i*8) + side * ((-1)**i * 5)
                line(q, q + direction*8, PURPLE, 2)
            return

        # Artífice: munição mecânica/energia compacta com estabilizadores.
        if sid in {"artifice_bolt", "artifice_burst", "torreta_do_veu"} or "device" in tags or "artifice" in sid:
            front = p + direction * 13
            back = p - direction * 13
            body = [front + side*4, front - side*4, back - side*6, back + side*6]
            pygame.draw.polygon(surface, ORANGE, body)
            pygame.draw.polygon(surface, WHITE, body, 1)
            line(back + side*6, back - direction*8 + side*10, ORANGE, 2)
            line(back - side*6, back - direction*8 - side*10, ORANGE, 2)
            return

        # Oráculo: selo em losango com "olho" central.
        if sid in {"oracle_mark_bolt", "marca_do_pressagio"} or "mark" in tags or dtype == DamageType.ARCANO:
            r = max(7, int(self.radius + 2))
            diamond = [p + direction*r*1.5, p + side*r, p - direction*r*1.5, p - side*r]
            pygame.draw.polygon(surface, PURPLE if self.color == PURPLE else self.color, diamond, 3)
            pygame.draw.circle(surface, WHITE, p, max(2, r//3))
            line(p - direction*24, p - direction*10, self.color, 3)
            return

        # Inimigos: Shooter dispara espinhos do Véu; bosses disparam fragmentos maiores.
        if self.owner == "enemy":
            if self.radius >= 9 or self.color == ORANGE:
                tip = p + direction * 19
                base = p - direction * 15
                pygame.draw.polygon(surface, ORANGE, [tip, base + side*8, base - side*8])
                pygame.draw.polygon(surface, WHITE, [tip, base + side*2, base - side*2], 1)
                line(base - direction*18, base, RED, 4)
            else:
                tip = p + direction * 16
                base = p - direction * 13
                pygame.draw.polygon(surface, PURPLE, [tip, base + side*6, base - side*6])
                line(base - direction*14, base, (120, 64, 180), 3)
            return

        # Físico genérico: dardo, nunca uma bolinha.
        if dtype in {DamageType.FISICO, DamageType.SANGRAMENTO} or "projectile" in tags:
            arrow(34, 7, self.color)
            return

        # Último fallback ainda tem silhueta de cometa/runa; nenhum projétil vira ponto.
        tail = p - direction * 22
        line(tail, p, self.color, max(3, int(self.radius * 0.7)))
        pygame.draw.polygon(surface, self.color, [p + direction*10, p + side*6, p - direction*8, p - side*6])
        pygame.draw.circle(surface, WHITE, p, 2)


# ============================================================
# INIMIGOS / SQUADS
# ============================================================

@dataclass
class EnemyDeathVisual:
    pos: pygame.Vector2
    kind: str
    boss_id: Optional[str]
    radius: float
    facing_left: bool
    tier: str
    mutation_ids: Tuple[str, ...]
    life: float = 0.62
    max_life: float = 0.62
    dead: bool = False

    def update(self, dt: float):
        self.life -= dt
        if self.life <= 0:
            self.dead = True

    def draw(self, surface: pygame.Surface, offset: pygame.Vector2):
        skin = get_enemy_skin(self.kind, self.boss_id)
        if skin is None:
            return
        p = self.pos + offset
        progress = 1.0 - clamp(self.life / self.max_life, 0.0, 1.0)
        base_h = 122 if self.kind == "guardian" else max(58, int(self.radius * 3.1))
        ratio = base_h / max(1, skin.get_height())
        w = max(28, int(skin.get_width() * ratio * (1.0 + progress * 0.16)))
        h = max(32, int(skin.get_height() * ratio * (1.0 - progress * 0.34)))
        frame = pygame.transform.smoothscale(skin, (w, h))
        if self.facing_left:
            frame = pygame.transform.flip(frame, True, False)
        frame = pygame.transform.rotate(frame, (-34 if self.facing_left else 34) * progress)
        frame.set_alpha(int(255 * (1.0 - progress) ** 0.7))
        rect = frame.get_rect(midbottom=(int(p.x), int(p.y + self.radius + 7 + progress * 7)))
        surface.blit(frame, rect)


class Enemy:
    next_id = 1

    def __init__(
        self,
        pos: pygame.Vector2,
        kind: str,
        difficulty: float,
        squad_id: int,
        doctrine: SquadDoctrine,
        role: str,
    ):
        self.uid = Enemy.next_id
        Enemy.next_id += 1

        self.pos = pygame.Vector2(pos)
        self.velocity = pygame.Vector2()
        self.kind = kind
        self.squad_id = squad_id
        self.doctrine = doctrine
        self.role = role

        self.dead = False
        self.flash_timer = 0.0
        self.contact_cd = 0.0
        self.attack_cd = random.uniform(0.3, 1.0)
        self.slow_timer = 0.0
        self.bleed_timer = 0.0
        self.bleed_tick = 0.0
        self.bleed_damage = 0.0
        self.strategy_hint = doctrine.id

        # Metadados de criatura/mutação são preenchidos por Game.decorate_enemy.
        self.creature_id = creature_id_for_archetype(kind)
        self.creature_tier = CreatureTier.COMUM.value
        self.mutation_ids: List[str] = []
        self.superior_name: Optional[str] = None
        self.mutation_behavior_hints: List[str] = []
        # Bosses usam o mesmo corpo runtime enquanto arte final ainda não existe,
        # mas possuem identidade/diretor/padrões próprios.
        self.boss_id: Optional[str] = None
        self.boss_director: Optional[BossDirector] = None
        self.last_boss_pattern: Optional[str] = None
        self.last_boss_phase_name: Optional[str] = None
        self.statuses = StatusController()

        # Estado visual é separado da IA/hitbox: animações nunca mudam colisão.
        self.visual_time = random.uniform(0.0, 4.0)
        self.visual_state = "idle"
        self.visual_move = pygame.Vector2()
        self.facing_left = False
        self.attack_visual_timer = 0.0
        self.attack_visual_max = 0.0
        self.attack_direction = pygame.Vector2(1, 0)
        self.hurt_visual_timer = 0.0
        self.step_timer = random.uniform(0.0, 0.22)
        self.last_pos = self.pos.copy()

        if kind == "crawler":
            self.radius = 18
            self.max_hp = int(52 * difficulty)
            self.speed = 104 + difficulty * 6
            self.damage = int(10 + difficulty * 1.8)
            self.color = RED
            self.xp = 12
        elif kind == "shooter":
            self.radius = 19
            self.max_hp = int(67 * difficulty)
            self.speed = 78 + difficulty * 4
            self.damage = int(9 + difficulty * 1.6)
            self.color = PURPLE
            self.xp = 18
        elif kind == "tank":
            self.radius = 27
            self.max_hp = int(145 * difficulty)
            self.speed = 55 + difficulty * 2.5
            self.damage = int(15 + difficulty * 2.2)
            self.color = BLUE
            self.xp = 30
        elif kind == "hunter":
            self.radius = 17
            self.max_hp = int(76 * difficulty)
            self.speed = 145 + difficulty * 5
            self.damage = int(12 + difficulty * 2.0)
            self.color = PINK
            self.xp = 24
        else:
            self.radius = 46
            self.max_hp = int(760 * difficulty)
            self.speed = 66
            self.damage = int(20 + difficulty * 3.0)
            self.color = ORANGE
            self.xp = 180

        self.hp = self.max_hp

    def take_damage(
        self,
        amount: float,
        game: "Game",
        knockback: Optional[pygame.Vector2] = None,
        critical: bool = False,
        element: Optional[Element] = None,
        applied_statuses: Sequence[Tuple[StatusId, int]] = (),
    ):
        if self.dead:
            return

        # Equipamentos podem alterar crítico e roubo de vida sem acoplar o inimigo a itens específicos.
        gear = game.player.gear_modifiers()
        if not critical and gear.crit_chance > 0 and random.random() < gear.crit_chance:
            critical = True
            amount *= gear.crit_damage_mult

        if element is not None:
            resolution = self.statuses.resolve_hit(amount, element, applied_statuses)
            amount = resolution.final_damage
            for reaction_id in resolution.reaction_ids[:2]:
                game.floating_texts.append(
                    FloatingText(self.pos + pygame.Vector2(0, -self.radius - 28),
                                 reaction_id.replace("_", " ").upper(), CYAN)
                )
                game.add_shake(5, 0.08)

        if amount > 0:
            self.hp -= amount
            game.player.heal(amount * gear.lifesteal)

        self.hp -= amount
        self.flash_timer = 0.025 if GAME_SETTINGS.accessibility.reduced_flashes else 0.08
        self.hurt_visual_timer = max(self.hurt_visual_timer, 0.24)
        if random.random() < 0.42:
            game.audio.play("enemy_hurt")

        if knockback is not None:
            self.pos += knockback

        if GAME_SETTINGS.accessibility.damage_numbers:
            game.floating_texts.append(
                FloatingText(
                    self.pos + pygame.Vector2(0, -self.radius - 10),
                    str(int(amount)),
                    YELLOW if critical else WHITE,
                )
            )

        for _ in range(12 if critical else 7):
            game.particles.append(
                Particle.burst(
                    self.pos,
                    YELLOW if critical else self.color,
                    70,
                    240 if critical else 180,
                    0.34,
                    6,
                )
            )

        game.add_shake(7 if critical else 3, 0.12 if critical else 0.07)
        game.hit_stop = max(game.hit_stop, 0.05 if critical else 0.018)
        game.telemetry.dano_causado += amount

        if self.hp <= 0:
            self.die(game)

    def die(self, game: "Game"):
        if self.dead:
            return
        game.enemy_deaths.append(EnemyDeathVisual(
            pos=self.pos.copy(),
            kind=self.kind,
            boss_id=self.boss_id,
            radius=self.radius,
            facing_left=self.facing_left,
            tier=str(self.creature_tier),
            mutation_ids=tuple(self.mutation_ids),
        ))
        self.dead = True
        if self.kind != "guardian":
            game.audio.play("enemy_death")

        game.award_xp(self.xp)

        for _ in range(20):
            game.particles.append(Particle.burst(self.pos, self.color, 80, 290, 0.45, 7))

        if "sangue_do_veu" in game.player_state.owned_skills:
            game.player.heal(max(2, int(game.player.max_hp * 0.018)))

        if random.random() < 0.14:
            game.heals.append(self.pos.copy())

        game.try_equipment_drop(self)
        game.on_enemy_killed(self)

        if self.kind == "guardian":
            game.on_boss_defeated(self)

    def apply_bleed(self, damage: float, duration: float = 3.0):
        self.bleed_damage = max(self.bleed_damage, damage)
        self.bleed_timer = max(self.bleed_timer, duration)
        self.bleed_tick = min(self.bleed_tick, 0.35)

    def update_status(self, dt: float, game: "Game"):
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.contact_cd = max(0.0, self.contact_cd - dt)
        self.attack_cd = max(0.0, self.attack_cd - dt)
        self.slow_timer = max(0.0, self.slow_timer - dt)

        if self.bleed_timer > 0:
            self.bleed_timer -= dt
            self.bleed_tick -= dt
            if self.bleed_tick <= 0:
                self.bleed_tick = 0.55
                self.take_damage(self.bleed_damage, game, critical=False)

        status_update = self.statuses.update(dt)
        if status_update.periodic_damage > 0:
            self.take_damage(status_update.periodic_damage, game, critical=False)

    def speed_multiplier(self) -> float:
        base = 0.52 if self.slow_timer > 0 else 1.0
        return base * self.statuses.movement_multiplier()

    def doctrine_vector(self, game: "Game", base_direction: pygame.Vector2) -> pygame.Vector2:
        player = game.player
        to_player = player.pos - self.pos
        distance = max(0.001, to_player.length())
        direction = to_player / distance

        if self.doctrine.id == "cerco":
            if self.role.lower() == "flanker":
                side = -1 if self.uid % 2 else 1
                return normalize(direction + direction.rotate(90) * 0.72 * side)
            return direction

        if self.doctrine.id == "fortaleza":
            squad_center = game.squad_center(self.squad_id)
            if self.role.lower() in ("tank", "vanguard"):
                guard_point = pygame.Vector2.lerp(squad_center, player.pos, 0.42)
                return normalize(guard_point - self.pos)
            if distance < 250:
                return -direction
            if distance > 360:
                return direction
            return direction.rotate(90 if self.uid % 2 else -90)

        if self.doctrine.id == "cacada":
            if self.role.lower() == "hunter" and player.dash_cooldown > 0.55:
                return direction
            return normalize(direction + direction.rotate(90) * (0.18 if self.uid % 2 else -0.18))

        if self.doctrine.id == "isca":
            if self.role.lower() == "vanguard":
                return direction
            if distance < 210:
                return -direction
            return direction.rotate(90 if self.uid % 2 else -90)

        return base_direction

    def update(self, dt: float, game: "Game"):
        if self.dead:
            return

        self.last_pos = self.pos.copy()
        self.visual_time += dt
        self.attack_visual_timer = max(0.0, self.attack_visual_timer - dt)
        self.hurt_visual_timer = max(0.0, self.hurt_visual_timer - dt)
        self.step_timer = max(0.0, self.step_timer - dt)

        self.update_status(dt, game)

        p = game.player
        delta = p.pos - self.pos
        distance = max(delta.length(), 0.001)
        direction = delta / distance
        move_direction = self.doctrine_vector(game, direction)
        speed = self.speed * self.speed_multiplier()

        # Modificadores de Ruptura são aplicados dinamicamente.
        rmods = game.player_state.active_rifts.cumulative_modifiers()
        speed *= rmods["enemy_speed_multiplier"]
        effective_damage = self.damage * rmods["enemy_damage_multiplier"] * self.statuses.outgoing_damage_multiplier()
        desired_velocity = pygame.Vector2()

        if self.kind == "crawler":
            desired_velocity = move_direction * speed

        elif self.kind == "tank":
            desired_velocity = move_direction * speed
            if distance < 100 and self.attack_cd <= 0:
                self.attack_cd = 1.6
                self.attack_visual_timer = 0.38
                self.attack_visual_max = self.attack_visual_timer
                self.attack_direction = direction.copy()
                if random.random() < 0.22:
                    game.speak_enemy("Colosso", "O Véu fecha sobre você.", ORANGE, priority=1, duration=1.4, cooldown_key="enemy_attack_voice")
                game.audio.play("enemy_attack_melee")
                p.take_damage(effective_damage * 1.25, game)
                p.pos += direction * 38
                game.add_shake(9, 0.14)

        elif self.kind == "hunter":
            desired_velocity = move_direction * speed
            if distance < 90 and self.attack_cd <= 0:
                self.attack_cd = 1.05
                self.attack_visual_timer = 0.30
                self.attack_visual_max = self.attack_visual_timer
                self.attack_direction = direction.copy()
                if random.random() < 0.18:
                    game.speak_enemy("Caçador", "Eu conheço seus passos.", PINK, priority=1, duration=1.4, cooldown_key="enemy_attack_voice")
                game.audio.play("enemy_attack_melee")
                if p.try_parry(self, game):
                    self.pos -= direction * 60
                else:
                    p.take_damage(effective_damage, game)

        elif self.kind == "shooter":
            ideal = 300
            if distance > ideal + 55:
                desired_velocity = move_direction * speed
            elif distance < ideal - 55:
                desired_velocity = -direction * speed
            else:
                desired_velocity = direction.rotate(90 if self.uid % 2 else -90) * speed * 0.46

            if self.attack_cd <= 0 and distance < 570:
                self.attack_cd = random.uniform(1.0, 1.45)
                self.attack_visual_timer = 0.36
                self.attack_visual_max = self.attack_visual_timer
                self.attack_direction = direction.copy()
                if random.random() < 0.16:
                    game.speak_enemy("Atirador", "Você chama isso de controle?", PURPLE, priority=1, duration=1.4, cooldown_key="enemy_attack_voice")
                game.audio.play("enemy_attack_ranged")
                game.projectiles.append(
                    Projectile(
                        pos=self.pos.copy(),
                        vel=direction * 335,
                        damage=effective_damage,
                        color=PURPLE,
                        owner="enemy",
                        radius=8,
                        life=2.3,
                    )
                )

        else:  # guardian
            self.update_guardian(dt, game, direction, distance, speed, effective_damage)

        if self.kind != "guardian":
            response = 10.0 if desired_velocity.length_squared() > 0 else 15.0
            self.velocity = self.velocity.lerp(desired_velocity, min(1.0, response * dt))
            self.pos += self.velocity * dt

        self.pos.x = clamp(self.pos.x, ROOM.left + self.radius, ROOM.right - self.radius)
        self.pos.y = clamp(self.pos.y, ROOM.top + self.radius, ROOM.bottom - self.radius)

        delta_move = self.pos - self.last_pos
        moved = delta_move.length_squared() > 0.02
        if moved:
            self.visual_move = normalize(delta_move)
            if abs(self.visual_move.x) > 0.08:
                self.facing_left = self.visual_move.x < 0
            if self.step_timer <= 0 and self.kind != "guardian":
                if self.kind == "crawler":
                    game.audio.play("enemy_step_crawler")
                    self.step_timer = 0.29
                elif self.kind == "tank":
                    game.audio.play("enemy_step_heavy")
                    self.step_timer = 0.44
                else:
                    game.audio.play("enemy_step_light")
                    self.step_timer = 0.34
        else:
            self.visual_move *= max(0.0, 1.0 - 8.0 * dt)

        if self.hurt_visual_timer > 0:
            self.visual_state = "hurt"
        elif self.attack_visual_timer > 0:
            self.visual_state = "attack"
        elif moved:
            self.visual_state = "run" if self.kind == "hunter" else "walk"
        else:
            self.visual_state = "idle"

        if self.kind in ("crawler",) and distance < self.radius + p.radius + 4:
            if self.contact_cd <= 0:
                self.contact_cd = 0.72
                self.attack_visual_timer = 0.26
                self.attack_visual_max = self.attack_visual_timer
                self.attack_direction = direction.copy()
                if random.random() < 0.12:
                    game.speak_enemy("Rastejante", "Esqueça.", RED, priority=1, duration=1.1, cooldown_key="enemy_attack_voice")
                game.audio.play("enemy_attack_melee")
                if p.try_parry(self, game):
                    self.pos -= direction * 55
                else:
                    p.take_damage(effective_damage, game)
                    self.pos -= direction * 24

    def update_guardian(
        self,
        dt: float,
        game: "Game",
        direction: pygame.Vector2,
        distance: float,
        speed: float,
        effective_damage: float,
    ):
        boss_id = self.boss_id or "guardiao_primeira_ruptura"
        memory = game.player_state.veil_memory.get(boss_id)
        strategy = game.current_boss_strategy
        director = self.boss_director
        hp_ratio = self.hp / max(1.0, self.max_hp)

        phase_speed = 1.0
        phase_damage = 1.0
        if director is not None:
            phase = director.phase_for_hp(hp_ratio)
            if self.last_boss_phase_name is None:
                self.last_boss_phase_name = phase.nome
            elif phase.nome != self.last_boss_phase_name:
                self.last_boss_phase_name = phase.nome
                game.audio.play("boss_phase")
                game.queue_banner("NOVA FASE", phase.nome, ORANGE)
            phase_speed = phase.speed_mult
            phase_damage = phase.damage_mult
        speed *= phase_speed
        effective_damage *= phase_damage

        if strategy in ("fechar_distancia", "salto_de_aproximacao", "pressao_continua"):
            if distance > 125:
                self.pos += direction * speed * 1.32 * dt
        elif strategy in ("flanquear_ranged", "flanco", "cortar_rota_fuga"):
            self.pos += normalize(direction + direction.rotate(90) * 0.7) * speed * dt
        else:
            if distance > 165:
                self.pos += direction * speed * dt

        if self.attack_cd > 0:
            return

        self.attack_visual_timer = 0.52
        self.attack_visual_max = self.attack_visual_timer
        self.attack_direction = direction.copy()
        game.audio.play("enemy_roar")

        # O boss real usa o deck 0.7/0.8. Caso seja um save antigo sem diretor,
        # cai no padrão radial seguro.
        if director is not None:
            pattern = director.choose_pattern(hp_ratio)
            self.last_boss_pattern = pattern.id
            danger = pattern.danger
            tags = set(pattern.tags)
            self.attack_cd = max(0.55, pattern.telegraph + pattern.duration * 0.25)

            if pattern.voice_line:
                game.speak_enemy(
                    BOSSES[boss_id].nome,
                    pattern.voice_line,
                    ORANGE,
                    priority=4,
                    duration=max(1.2, pattern.telegraph + 0.4),
                )

            # Padrões de aproximação/corpo a corpo têm uma resposta diferente
            # de chuva radial, mas todos mantêm telegraph e contra-jogo.
            if "melee" in tags or "dash" in tags or "leap" in tags:
                self.pos += direction * (80 + danger * 12)
                if distance < 145:
                    if game.player.try_parry(self, game):
                        self.pos -= direction * 70
                    else:
                        game.player.take_damage(effective_damage * (0.75 + danger * 0.06), game)
                game.add_shake(5 + danger, 0.10)
                return

            if "line" in tags:
                count = 5 + max(0, danger - 5)
                spread = 34 + danger * 2
                for i in range(count):
                    t = 0.5 if count == 1 else i / (count - 1)
                    d = direction.rotate(-spread / 2 + spread * t)
                    game.projectiles.append(
                        Projectile(self.pos.copy(), d * (335 + danger * 18),
                                   effective_damage * 0.86, ORANGE, "enemy",
                                   radius=9, life=2.4)
                    )
                game.add_shake(6 + danger, 0.12)
                return

            count = 8 + danger * 2
            if "ultimate" in tags:
                count += 4
            offset = math.pi / count if "feint" in tags or "delayed" in tags else 0.0
            for i in range(count):
                angle = math.tau * i / count + offset
                v = pygame.Vector2(math.cos(angle), math.sin(angle))
                game.projectiles.append(
                    Projectile(
                        pos=self.pos.copy(),
                        vel=v * (230 + danger * 19),
                        damage=effective_damage * (0.70 if count > 16 else 0.80),
                        color=ORANGE,
                        owner="enemy",
                        radius=8 if danger < 7 else 10,
                        life=2.8,
                    )
                )
            if danger >= 6:
                game.add_shake(7 + danger, 0.15)
            return

        # Compatibilidade: boss sem diretor.
        self.attack_cd = 1.25
        for i in range(12):
            angle = math.tau * i / 12
            v = pygame.Vector2(math.cos(angle), math.sin(angle))
            game.projectiles.append(
                Projectile(self.pos.copy(), v * 275, effective_damage * 0.80,
                           ORANGE, "enemy", radius=8, life=2.7)
            )

    def draw(self, surface, offset):
        p = self.pos + offset
        skin = get_enemy_skin(self.kind, self.boss_id if self.kind == "guardian" else None)

        # Sombra ancora o monstro no chão. A hitbox real continua sendo self.radius.
        shadow_w = int(self.radius * (2.0 if self.kind != "guardian" else 2.5))
        pygame.draw.ellipse(surface, (4, 5, 8),
                            (p.x - shadow_w/2, p.y + self.radius*0.55, shadow_w, max(8, self.radius*0.55)))

        if skin is not None:
            state = self.visual_state
            t = self.visual_time
            bob = 0.0
            angle = 0.0
            sx = sy = 1.0
            tint = (255, 255, 255)

            if state == "idle":
                bob = math.sin(t * (2.4 if self.kind == "tank" else 3.8)) * 1.4
                sx = 1.0 + math.sin(t * 2.7) * 0.012
                sy = 1.0 - math.sin(t * 2.7) * 0.010
            elif state == "walk":
                freq = 7.2 if self.kind == "tank" else (12.0 if self.kind == "crawler" else 9.5)
                phase = math.sin(t * freq)
                bob = -abs(phase) * (2.3 if self.kind == "tank" else 3.3)
                angle = phase * (1.4 if self.kind == "tank" else 3.0)
                sx = 1.0 + abs(phase) * 0.025
                sy = 1.0 - abs(phase) * 0.025
            elif state == "run":
                phase = math.sin(t * 15.0)
                bob = -abs(phase) * 4.4
                angle = (-7.0 if not self.facing_left else 7.0) + phase * 2.4
                sx, sy = 1.07, 0.94
            elif state == "attack":
                phase = 1.0 - clamp(self.attack_visual_timer / (0.52 if self.kind == "guardian" else 0.38), 0.0, 1.0)
                impulse = math.sin(clamp(phase, 0.0, 1.0) * math.pi)
                sx = 1.0 + impulse * (0.15 if self.kind == "tank" else 0.10)
                sy = 1.0 - impulse * 0.06
                angle = (10.0 if self.facing_left else -10.0) * impulse
                bob = -3.0 * impulse
            elif state == "hurt":
                phase = clamp(self.hurt_visual_timer / 0.24, 0.0, 1.0)
                angle = (8.0 if self.facing_left else -8.0) * phase
                sx, sy = 0.96, 1.04
                tint = (255, 150, 150)

            if self.kind == "guardian":
                base_h = 126
            else:
                base_h = max(58, min(94, int(self.radius * 3.2)))
            ratio = base_h / max(1, skin.get_height())
            w = max(28, int(skin.get_width() * ratio * sx))
            h = max(34, int(skin.get_height() * ratio * sy))
            frame = cached_sprite_transform(skin, w, h, self.facing_left, angle)
            if tint != (255,255,255):
                frame = frame.copy()
                frame.fill((*tint,255), special_flags=pygame.BLEND_RGBA_MULT)
            if self.flash_timer > 0:
                frame = frame.copy()
                frame.fill((150,150,150,150), special_flags=pygame.BLEND_RGBA_ADD)

            # Hunter ganha um pequeno afterimage em corrida, reforçando a função de perseguidor.
            if self.kind == "hunter" and state == "run" and self.visual_move.length_squared() > 0:
                ghost = frame.copy(); ghost.set_alpha(68)
                gp = p - self.visual_move * 18
                grect = ghost.get_rect(midbottom=(int(gp.x), int(gp.y + self.radius + 9 + bob)))
                surface.blit(ghost, grect)

            rect = frame.get_rect(midbottom=(int(p.x), int(p.y + self.radius + 9 + bob)))
            surface.blit(frame, rect)
        else:
            # Fallback: se um asset faltar, o inimigo continua jogável.
            color = WHITE if self.flash_timer > 0 else self.color
            pygame.draw.circle(surface, color, p, int(self.radius))
            pygame.draw.circle(surface, BLACK, p, int(self.radius), 3)

        if self.attack_visual_timer > 0 and self.attack_visual_max > 0:
            progress = 1.0 - clamp(self.attack_visual_timer / self.attack_visual_max, 0.0, 1.0)
            direction = normalize(self.attack_direction)
            side = pygame.Vector2(-direction.y, direction.x)
            reach = self.radius + 30 + progress * (34 if self.kind != "guardian" else 58)
            width = max(7, int(9 + progress * 10))
            color = (255, 116, 72) if progress < 0.55 else (255, 220, 112)
            base = p + direction * (self.radius * 0.25)
            tip = p + direction * reach
            pygame.draw.polygon(surface, color, [base + side * width, tip, base - side * width], 2)
            if self.kind == "shooter":
                pygame.draw.line(surface, color, p + direction * self.radius, tip, width)

        # Elite/Superior e mutações deixam marcas visuais legíveis sem aumentar a hitbox.
        tier_color = enemy_tier_color(str(self.creature_tier))
        tier_raw = str(self.creature_tier).lower()
        if "elite" in tier_raw or "super" in tier_raw or self.kind == "guardian":
            pulse = 2 + int(abs(math.sin(self.visual_time * 4.0)) * 3)
            pygame.draw.circle(surface, tier_color, p, int(self.radius + 8 + pulse), 2)
        if self.mutation_ids:
            orbit = self.radius + 13
            for i, _mid in enumerate(self.mutation_ids[:3]):
                ang = self.visual_time * (1.4 + i * 0.2) + i * math.tau / 3
                q = p + pygame.Vector2(math.cos(ang), math.sin(ang)) * orbit
                pygame.draw.circle(surface, tier_color, q, 3 + (i % 2))

        bar = pygame.Rect(int(p.x - 28), int(p.y - self.radius - 22), 56, 7)
        draw_bar(surface, bar, self.hp, self.max_hp, GREEN)

        if self.bleed_timer > 0:
            pygame.draw.circle(surface, RED, p, int(self.radius + 5), 2)

        if self.superior_name and "super" in tier_raw:
            draw_text(surface, self.superior_name[:28], (p.x, p.y - self.radius - 37), tier_color, FONT_TINY, True)


# ============================================================
# PLAYER RUNTIME
# ============================================================

@dataclass
class PendingCast:
    skill_id: str
    timer: float
    target: pygame.Vector2
    aim: pygame.Vector2
    incantation_spoken: bool = False


class PlayerAvatar:
    def __init__(self, state: PlayerState):
        self.state = state
        self.pos = pygame.Vector2(WIDTH / 2, HEIGHT / 2)
        self.prev_pos = self.pos.copy()
        self.radius = 21
        self.velocity = pygame.Vector2()

        self.max_hp = self.effective_max_hp()
        self.hp = float(self.max_hp)
        self.resource_max = float(state.class_definition().recurso_maximo)

        # Guerreiro acumula Fadiga e Rasgado acumula Corrupção.
        if state.identity.class_id in ("guerreiro", "rasgado"):
            self.resource = 0.0
        else:
            self.resource = self.resource_max

        self.attack_cooldown = 0.0
        self.special_cooldown = 0.0
        self.dash_cooldown = 0.0
        self.invuln = 0.0
        self.parry_window = 0.0
        self.parry_cooldown = 0.0
        self.shield_timer = 0.0
        self.attack_counter = 0
        self.pending_cast: Optional[PendingCast] = None
        self.last_dash_direction = pygame.Vector2()
        self.low_hp_pulse_cd = 0.0
        self.position_history: List[pygame.Vector2] = []
        self.position_history_timer = 0.0
        self.duelist_combo = 0

        # Animacao visual: a hitbox continua sendo o circulo logico; a skin e apenas render.
        self.visual_time = 0.0
        self.visual_state = "idle"
        self.visual_move = pygame.Vector2()
        self.dash_visual_timer = 0.0
        self.hurt_visual_timer = 0.0
        self.attack_visual_timer = 0.0
        self.footstep_timer = 0.0
        self.skin = get_player_skin(self.class_id, self.state.identity.genero)

        # Mira independente do movimento. Mouse atualiza normalmente; setas direcionais
        # permitem mirar sem tirar a mão do teclado. Ataques sempre usam esta direção.
        self.aim_dir = pygame.Vector2(1, 0)
        self.aim_target = self.pos + self.aim_dir * 320

        # Buffs genéricos usados pelos kits 0.8. A chave é semântica e o valor é tempo restante.
        self.active_buffs: Dict[str, float] = {}

        self.active_slots: List[str] = []
        self.refresh_skill_slots()

    @property
    def class_id(self) -> str:
        return self.state.identity.class_id

    @property
    def color(self):
        return CLASS_COLORS.get(self.class_id, WHITE)

    def gear_modifiers(self):
        return equipment_modifiers(self.state)

    def effective_max_hp(self) -> int:
        mods = self.gear_modifiers()
        legacy = legacy_modifiers(self.state)
        return max(1, int((self.state.max_hp() + mods.hp_flat) * mods.hp_mult * legacy["max_hp_mult"]))

    def combat_damage(self) -> float:
        mods = self.gear_modifiers()
        value = (self.state.damage_base() + mods.damage_flat) * mods.damage_mult
        value *= float(synergy_modifiers(self.state)["damage_mult"])

        # Rasgado cresce com a própria corrupção acumulada.
        if self.class_id == "rasgado":
            value *= 1.0 + (self.resource / max(1.0, self.resource_max)) * 0.55

        # Buffs de kit 0.8: bônus deliberadamente moderados para manter leitura e balanceamento.
        if self.active_buffs.get("hunter_step", 0) > 0:
            value *= 1.18
        if self.active_buffs.get("future_echo", 0) > 0:
            value *= 1.15
        if self.active_buffs.get("torn_apotheosis", 0) > 0:
            value *= 1.45
        if self.active_buffs.get("war_oath", 0) > 0:
            value *= 1.12
        if self.active_buffs.get("final_citadel", 0) > 0:
            value *= 1.08

        return value

    def refresh_from_state(self):
        old_max = self.max_hp
        self.max_hp = self.effective_max_hp()
        if self.max_hp > old_max:
            self.hp += self.max_hp - old_max
        self.hp = min(self.hp, self.max_hp)
        self.refresh_skill_slots()

    def refresh_skill_slots(self):
        available: List[str] = []
        for skill_id in sorted(self.state.owned_skills):
            definition = SKILL_REGISTRY[skill_id]
            if definition.categoria == SkillCategory.PASSIVA:
                continue
            available.append(skill_id)

        # Preserva a ordem já equipada. Aprender uma habilidade nova não deve
        # embaralhar Q/E/R/F só porque o ID dela vem antes alfabeticamente.
        saved = self.state.campaign.get("skill_loadout", []) if isinstance(self.state.campaign, dict) else []
        preferred = list(self.active_slots) if self.active_slots else list(saved)
        slots = [skill_id for skill_id in preferred if skill_id in available]
        for skill_id in available:
            if skill_id not in slots and len(slots) < 4:
                slots.append(skill_id)
        self.active_slots = slots[:4]
        if isinstance(self.state.campaign, dict):
            self.state.campaign["skill_loadout"] = list(self.active_slots)

    def movement_speed(self) -> float:
        mods = self.gear_modifiers()
        synergy = synergy_modifiers(self.state)
        legacy = legacy_modifiers(self.state)
        return (self.state.movement_speed() + mods.speed_flat) * mods.speed_mult * float(synergy["speed_mult"]) * legacy["speed_mult"]

    def heal(self, amount: float):
        mods = self.gear_modifiers()
        synergy = synergy_modifiers(self.state)
        legacy = legacy_modifiers(self.state)
        healing = amount * mods.healing_mult * float(synergy["healing_mult"]) * legacy["healing_mult"]
        self.hp = min(self.max_hp, self.hp + healing)

    def take_damage(self, amount: float, game: "Game"):
        if self.invuln > 0:
            return

        if self.shield_timer > 0:
            amount *= 0.35
        if self.active_buffs.get("funeral_mantle", 0) > 0:
            amount *= 0.72
        if self.active_buffs.get("protective_chain", 0) > 0:
            amount *= 0.70
        if self.active_buffs.get("final_citadel", 0) > 0:
            amount *= 0.52

        self.hp -= amount
        self.hurt_visual_timer = 0.28
        game.audio.play("player_hurt")
        if self.class_id == "duelista":
            self.duelist_combo = 0
        self.invuln = 0.52
        game.telemetry.dano_recebido += amount
        game.add_shake(11, 0.18)
        game.hit_stop = max(game.hit_stop, 0.04)
        if GAME_SETTINGS.accessibility.damage_numbers:
            game.floating_texts.append(
                FloatingText(self.pos + pygame.Vector2(0, -34), f"-{int(amount)}", RED)
            )

        for _ in range(14):
            game.particles.append(Particle.burst(self.pos, RED, 70, 260, 0.4, 6))

        # Pulso de Sobrevivência (passiva universal)
        if (
            "pulso_de_sobrevivencia" in self.state.owned_skills
            and self.hp / max(1, self.max_hp) <= 0.25
            and self.low_hp_pulse_cd <= 0
        ):
            self.low_hp_pulse_cd = 18.0
            for enemy in game.enemies:
                dist = enemy.pos.distance_to(self.pos)
                if dist < 150:
                    enemy.pos += normalize(enemy.pos - self.pos) * 55
                    enemy.take_damage(20, game)
            game.speak_player("NÃO AINDA!", priority=2)

    def start_parry(self, game: "Game"):
        if self.class_id not in ("guerreiro", "duelista"):
            return
        if self.parry_cooldown > 0:
            return

        legacy = legacy_modifiers(self.state)
        self.parry_window = 0.22 * legacy["parry_window_mult"]
        self.parry_cooldown = 1.1
        game.speak_player(random.choice(("VENHA!", "AGORA.")), priority=1, cooldown_key="parry")

    def try_parry(self, enemy: Enemy, game: "Game") -> bool:
        if self.parry_window <= 0:
            return False

        self.parry_window = 0
        self.invuln = 0.24
        game.audio.play("parry")
        game.telemetry.parries += 1
        game.add_shake(15, 0.21)
        game.hit_stop = max(game.hit_stop, 0.075)

        damage = self.combat_damage() * 1.6
        enemy.take_damage(
            damage,
            game,
            knockback=normalize(enemy.pos - self.pos) * 62,
            critical=True,
        )

        game.slashes.append(
            SlashVisual(self.pos.copy(), enemy.pos - self.pos, CYAN, 98, 0.17, 12)
        )
        game.speak_player("MINHA VEZ!", priority=3, cooldown_key="perfect_parry")
        return True

    def dash(self, game: "Game"):
        if self.dash_cooldown > 0 or self.pending_cast is not None:
            return

        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(
            keys[pygame.K_d] - keys[pygame.K_a],
            keys[pygame.K_s] - keys[pygame.K_w],
        )

        if direction.length_squared() == 0:
            direction = pygame.Vector2(pygame.mouse.get_pos()) - self.pos

        direction = normalize(direction)
        self.last_dash_direction = direction.copy()
        self.dash_visual_timer = 0.24
        self.prev_pos = self.pos.copy()
        game.audio.play("dash")
        self.pos += direction * 122
        self.dash_cooldown = 0.95 * legacy_modifiers(self.state)["dash_cooldown_mult"]
        self.invuln = 0.24

        game.telemetry.dashes_total += 1
        nearest = game.nearest_enemy(self.pos)
        if nearest is not None:
            to_enemy = normalize(nearest.pos - self.pos)
            # Se o dash aponta para longe do inimigo, conta como para trás.
            if direction.dot(to_enemy) < -0.25:
                game.telemetry.dashes_para_tras += 1

        for _ in range(16):
            game.particles.append(Particle.burst(self.prev_pos, self.color, 45, 150, 0.34, 5))

        # Passo Fantasma cria eco puramente visual + pequena desorientação.
        if "passo_fantasma" in self.state.owned_skills:
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.prev_pos) < 125:
                    enemy.attack_cd += 0.25

    def basic_attack(self, game: "Game"):
        if self.attack_cooldown > 0 or self.pending_cast is not None:
            return

        aim = normalize(self.aim_dir)
        damage = self.combat_damage()
        self.attack_visual_timer = max(self.attack_visual_timer, 0.24)

        if self.class_id == "guerreiro":
            if self.resource >= 92:
                return
            self.resource += 12
            if random.random() < 0.08:
                game.speak_player("ABRAM CAMINHO!", priority=1, cooldown_key="basic_warrior_voice", duration=1.0)
            game.audio.play("sword_swing")
            self.attack_cooldown = 0.34
            self.attack_counter += 1
            critical = self.attack_counter % 10 == 0

            game.telemetry.ataques_melee += 1
            game.slashes.append(
                SlashVisual(
                    self.pos.copy(),
                    aim,
                    YELLOW if critical else WHITE,
                    92 if not critical else 112,
                    0.13 if not critical else 0.17,
                    10 if not critical else 14,
                )
            )

            hit_any = False
            for enemy in game.enemies:
                delta = enemy.pos - self.pos
                if delta.length() <= 98 + enemy.radius:
                    direction = normalize(delta)
                    if direction.dot(aim) > 0.30:
                        enemy.take_damage(
                            damage * (1.9 if critical else 1.0),
                            game,
                            knockback=aim * (34 if critical else 16),
                            critical=critical,
                        )
                        hit_any = True

            if critical:
                game.add_shake(12, 0.16)
                game.hit_stop = max(game.hit_stop, 0.08)
                game.speak_player("DÉCIMO IMPACTO!", priority=3, cooldown_key="tenth_hit")
                if "arkhon_tenth_rift" in active_unique_effects(self.state):
                    game.projectiles.append(Projectile(self.pos + aim * 30, aim * 720, damage * 1.05, PURPLE, "player", radius=10, life=1.0, pierce=2, skill_id="arkhon_rift"))
            elif hit_any:
                game.audio.play("sword_hit")
                game.add_shake(2.5, 0.06)

        elif self.class_id == "mago":
            if self.resource < 7:
                return
            self.resource -= 7
            if random.random() < 0.06:
                game.speak_player("EXPLODA!", priority=1, cooldown_key="basic_mage_voice", duration=1.0)
            game.audio.play("magic_cast")
            self.attack_cooldown = 0.26
            game.telemetry.ataques_magicos += 1
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 28,
                    aim * 520,
                    damage * 0.78,
                    CYAN,
                    "player",
                    radius=7,
                    life=1.8,
                    pierce=0,
                    skill_id="arcane_bolt",
                )
            )

        elif self.class_id == "arqueiro":
            if self.resource < 5:
                return
            self.resource -= 5
            if random.random() < 0.06:
                game.speak_player("RAJADA!", priority=1, cooldown_key="basic_archer_voice", duration=1.0)
            game.audio.play("arrow_shot")
            self.attack_cooldown = 0.205
            game.telemetry.ataques_ranged += 1

            bleed = 0.0
            if "flecha_serrilhada" in self.state.owned_skills:
                bleed = 5.0

            effects = active_unique_effects(self.state)
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 28,
                    aim * 690,
                    damage * 0.88,
                    YELLOW,
                    "player",
                    radius=5,
                    life=1.55,
                    pierce=1 if "horizon_pierce" in effects else 0,
                    skill_id="arrow",
                    bleed_damage=bleed,
                )
            )

        elif self.class_id == "ceifador":
            game.audio.play("sword_swing")
            self.attack_cooldown = 0.29
            game.telemetry.ataques_melee += 1
            game.slashes.append(SlashVisual(self.pos.copy(), aim, PINK, 108, 0.15, 12))
            hit = 0
            for enemy in game.enemies:
                delta = enemy.pos - self.pos
                if delta.length() <= 112 + enemy.radius and normalize(delta).dot(aim) > 0.05:
                    enemy.take_damage(damage * 0.96, game, knockback=aim * 18)
                    hit += 1
            if hit:
                self.heal(damage * 0.025 * hit)

        elif self.class_id == "rasgado":
            game.audio.play("magic_cast")
            if self.resource >= 98:
                return
            self.resource = min(100.0, self.resource + 6.0)
            self.attack_cooldown = 0.28
            game.telemetry.ataques_magicos += 1
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 28,
                    aim * 585,
                    damage * 0.90,
                    RED,
                    "player",
                    radius=8,
                    life=1.7,
                    skill_id="rasgado_basic",
                )
            )

        elif self.class_id == "cronista":
            game.audio.play("magic_cast")
            self.attack_cooldown = 0.235
            game.telemetry.ataques_magicos += 1
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 28,
                    aim * 610,
                    damage * 0.78,
                    CYAN,
                    "player",
                    radius=6,
                    life=1.55,
                    skill_id="temporal_shard",
                )
            )

        elif self.class_id == "artifice":
            game.audio.play("arrow_shot")
            self.attack_cooldown = 0.22
            game.telemetry.ataques_ranged += 1
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 28,
                    aim * 650,
                    damage * 0.80,
                    ORANGE,
                    "player",
                    radius=6,
                    life=1.55,
                    skill_id="artifice_bolt",
                )
            )

        elif self.class_id == "duelista":
            game.audio.play("sword_swing")
            self.attack_cooldown = max(0.13, 0.22 - min(0.07, self.duelist_combo * 0.006))
            self.duelist_combo = min(12, self.duelist_combo + 1)
            game.telemetry.ataques_melee += 1
            game.slashes.append(SlashVisual(self.pos.copy(), aim, WHITE, 92, 0.11, 8))
            for enemy in game.enemies:
                delta = enemy.pos - self.pos
                if delta.length() <= 94 + enemy.radius and normalize(delta).dot(aim) > 0.18:
                    enemy.take_damage(damage * (0.82 + self.duelist_combo * 0.025), game, knockback=aim * 10)

        elif self.class_id == "oraculo":
            game.audio.play("magic_cast")
            self.attack_cooldown = 0.30
            game.telemetry.ataques_magicos += 1
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 28,
                    aim * 540,
                    damage * 0.88,
                    PURPLE,
                    "player",
                    radius=7,
                    life=1.9,
                    skill_id="oracle_mark_bolt",
                )
            )

        elif self.class_id == "guardiao_veu":
            game.audio.play("sword_swing")
            self.attack_cooldown = 0.38
            game.telemetry.ataques_melee += 1
            game.slashes.append(SlashVisual(self.pos.copy(), aim, BLUE, 100, 0.15, 13))
            for enemy in game.enemies:
                delta = enemy.pos - self.pos
                if delta.length() <= 105 + enemy.radius and normalize(delta).dot(aim) > 0.10:
                    enemy.take_damage(damage * 0.92, game, knockback=aim * 34)

        else:
            self.attack_cooldown = 0.30

    def use_secondary(self, game: "Game"):
        # Especial base rápido por classe inicial.
        if self.special_cooldown > 0 or self.pending_cast is not None:
            return

        aim = normalize(self.aim_dir)
        damage = self.combat_damage()

        if self.class_id == "guerreiro":
            self.special_cooldown = 4.2
            game.speak_player("ABRAM CAMINHO!", priority=2, cooldown_key="warrior_spin")
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 160:
                    enemy.take_damage(
                        damage * 1.8,
                        game,
                        normalize(enemy.pos - self.pos) * 48,
                        critical=True,
                    )
            game.add_shake(13, 0.19)

        elif self.class_id == "mago":
            if self.resource < 32:
                return
            self.resource -= 32
            self.special_cooldown = 4.8
            game.speak_player("EXPLODA!", priority=2, cooldown_key="mage_burst")
            game.area_effects.append(
                AreaEffect(
                    "magic_burst",
                    mouse,
                    120,
                    duration=0.05,
                    owner="player",
                    damage=damage * 1.9,
                    delay=0.3,
                    color=CYAN,
                )
            )
            # magic_burst usa gatilho manual no update do jogo.

        elif self.class_id == "arqueiro":
            if self.resource < 25:
                return
            self.resource -= 25
            self.special_cooldown = 3.6
            game.speak_player("RAJADA!", priority=2, cooldown_key="archer_burst")
            for angle in (-8, -4, 0, 4, 8):
                d = aim.rotate(angle)
                game.projectiles.append(
                    Projectile(
                        self.pos + d * 28,
                        d * 760,
                        damage * 1.05,
                        YELLOW,
                        "player",
                        radius=5,
                        life=1.5,
                        pierce=1,
                        skill_id="burst_arrow",
                    )
                )

        elif self.class_id == "ceifador":
            if self.resource < 28:
                return
            self.resource -= 28
            self.special_cooldown = 4.4
            game.speak_player("COLHEITA!", priority=2, cooldown_key="reaper_secondary")
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 150:
                    dealt = damage * (1.35 if enemy.hp / max(1, enemy.max_hp) > 0.25 else 2.1)
                    enemy.take_damage(dealt, game, knockback=normalize(enemy.pos - self.pos) * 30)
                    self.heal(dealt * 0.025)

        elif self.class_id == "rasgado":
            if self.resource < 32:
                return
            power = 1.0 + self.resource / 100.0
            self.resource = max(0.0, self.resource - 32.0)
            self.special_cooldown = 4.7
            self.hp = max(1.0, self.hp - self.max_hp * 0.05)
            game.speak_player("RASGUE!", priority=3, cooldown_key="torn_secondary")
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 185:
                    enemy.take_damage(damage * 1.15 * power, game, critical=power > 1.65)
            game.add_shake(12, 0.18)

        elif self.class_id == "cronista":
            if self.resource < 26:
                return
            self.resource -= 26
            self.special_cooldown = 5.2
            if self.position_history:
                self.pos = self.position_history[0].copy()
            self.invuln = max(self.invuln, 0.28)
            game.speak_player("VOLTE.", priority=2, cooldown_key="chronist_secondary")

        elif self.class_id == "artifice":
            if self.resource < 30:
                return
            self.resource -= 30
            self.special_cooldown = 4.2
            game.speak_player("SISTEMA: SOBRECARGA!", priority=2, cooldown_key="artifice_secondary")
            for angle in (-18, -9, 0, 9, 18):
                d = aim.rotate(angle)
                game.projectiles.append(Projectile(self.pos + d * 25, d * 700, damage * 0.72, ORANGE, "player", radius=5, life=1.3, skill_id="artifice_burst"))

        elif self.class_id == "duelista":
            self.special_cooldown = 3.0
            self.invuln = max(self.invuln, 0.16)
            self.pos += aim * 95
            game.speak_player("MINHA VEZ.", priority=2, cooldown_key="duelist_secondary")
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 92:
                    enemy.take_damage(damage * 1.45, game, knockback=aim * 22, critical=self.duelist_combo >= 6)

        elif self.class_id == "oraculo":
            if self.resource < 30:
                return
            self.resource -= 30
            self.special_cooldown = 5.0
            game.speak_player("EU JÁ VI ESTE MOMENTO.", priority=2, cooldown_key="oracle_secondary")
            game.area_effects.append(AreaEffect("magic_burst", mouse, 135, 0.05, "player", damage=damage * 1.65, delay=0.55, color=PURPLE))

        elif self.class_id == "guardiao_veu":
            if self.resource < 24:
                return
            self.resource -= 24
            self.special_cooldown = 4.8
            self.shield_timer = max(self.shield_timer, 3.2)
            self.parry_window = max(self.parry_window, 0.32)
            game.speak_player("ATRÁS DE MIM!", priority=2, cooldown_key="guardian_secondary")

    def use_skill_slot(self, index: int, game: "Game"):
        if index < 0 or index >= len(self.active_slots):
            return
        self.use_skill(self.active_slots[index], game)

    def use_skill(self, skill_id: str, game: "Game"):
        if skill_id not in self.state.owned_skills:
            return
        if self.pending_cast is not None:
            return

        skill = SKILL_REGISTRY[skill_id]
        mastery = self.state.masteries.get(skill_id)
        if mastery is None:
            return

        # Cooldowns por habilidade ficam no Game.
        if game.skill_cooldowns.get(skill_id, 0.0) > 0:
            return

        mods = self.gear_modifiers()
        cost = mastery.effective_resource_cost() * mods.resource_cost_mult

        if self.class_id in ("guerreiro", "rasgado"):
            # Fadiga/Corrupção crescem em vez de consumir pool tradicional.
            if self.resource + cost > 100:
                return
            self.resource += cost
        else:
            if self.resource < cost:
                return
            self.resource -= cost

        target = pygame.Vector2(self.aim_target)
        aim = normalize(self.aim_dir)
        base_cast = self.base_cast_time(skill_id)
        cast_time = mastery.effective_cast_time(base_cast)

        incantation = mastery.choose_incantation(self.state.identity.genero)
        if incantation and cast_time > 0.05:
            game.speak_player(
                incantation,
                priority=2,
                cooldown_key=f"incant_{skill_id}",
                duration=max(1.0, cast_time + 0.25),
            )

        if cast_time > 0.05:
            self.pending_cast = PendingCast(skill_id, cast_time, target, aim, bool(incantation))
        else:
            self.execute_skill(skill_id, target, aim, game)

    def base_cast_time(self, skill_id: str) -> float:
        return {
            "bola_de_fogo": 0.75,
            "prisao_glacial": 0.42,
            "singularidade_arcana": 0.85,
            "fim_da_linha_temporal": 1.0,
            "corte_crescente": 0.0,
            "muralha_de_aco": 0.0,
            "ruptura_da_lamina": 0.22,
            "chuva_de_flechas": 0.35,
            "horizonte_partido": 0.75,
        }.get(skill_id, 0.10)

    def update_pending_cast(self, dt: float, game: "Game"):
        if self.pending_cast is None:
            return

        self.pending_cast.timer -= dt
        if self.pending_cast.timer <= 0:
            cast = self.pending_cast
            self.pending_cast = None
            self.execute_skill(cast.skill_id, cast.target, cast.aim, game)

    def execute_skill(
        self,
        skill_id: str,
        target: pygame.Vector2,
        aim: pygame.Vector2,
        game: "Game",
    ):
        game.play_skill_audio(skill_id)
        skill = SKILL_REGISTRY[skill_id]
        mastery = self.state.masteries[skill_id]
        damage = mastery.effective_damage()
        mods = self.gear_modifiers()
        damage = (damage + mods.damage_flat) * mods.damage_mult
        cooldown = mastery.effective_cooldown() * mods.cooldown_mult * float(synergy_modifiers(self.state)["cooldown_mult"])
        game.skill_cooldowns[skill_id] = cooldown

        leveled = self.state.register_skill_use(skill_id, mastery_xp=6)
        if leveled:
            stage = self.state.masteries[skill_id].stage()
            game.campaign.record(
                CampaignEvent.SKILL_MASTERY,
                target_id=skill_id,
                value=stage.nivel,
            )
            game.process_campaign_rewards()
            game.queue_banner(
                f"MAESTRIA {stage.nivel} — {stage.nome}",
                f"{skill.nome} foi aperfeiçoada.",
                RARITY_COLORS[skill.raridade],
            )
            if stage.nivel >= 5:
                add_metric(self.state, "mastery_5", 1)
            # Evoluções são marcos de build; quando requisitos completos convergem,
            # o primeiro caminho válido evolui automaticamente nesta build sem UI extra.
            matching = [e for e in available_evolutions(self.state) if e.base_skill_id == skill_id]
            if matching:
                ok, evo_name = evolve_skill(self.state, matching[0].id)
                if ok:
                    add_metric(self.state, "skill_evolutions", 1)
                    game.queue_banner("HABILIDADE EVOLUÍDA", evo_name, PURPLE)
            game.autosave.request(AutosaveReason.DESBLOQUEIO_IMPORTANTE)

        line = mastery.choose_voice_line(self.state.identity.genero)
        if line:
            game.speak_player(line, priority=3, cooldown_key=f"skill_voice_{skill_id}")

        if skill_id == "corte_crescente":
            game.telemetry.ataques_melee += 1
            game.slashes.append(SlashVisual(self.pos.copy(), aim, WHITE, 120, 0.17, 14))
            for enemy in game.enemies:
                delta = enemy.pos - self.pos
                if delta.length() <= 125 + enemy.radius and normalize(delta).dot(aim) > 0.10:
                    enemy.take_damage(damage, game, aim * 36)

        elif skill_id == "muralha_de_aco":
            self.shield_timer = 2.6
            self.parry_window = max(self.parry_window, 0.42)
            game.add_shake(3, 0.08)

        elif skill_id == "ruptura_da_lamina":
            game.telemetry.ataques_melee += 1
            game.slashes.append(SlashVisual(self.pos.copy(), aim, PURPLE, 150, 0.20, 16))
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 35,
                    aim * 610,
                    damage,
                    PURPLE,
                    "player",
                    radius=11,
                    life=1.2,
                    pierce=3,
                    skill_id=skill_id,
                )
            )

        elif skill_id == "bola_de_fogo":
            game.telemetry.ataques_magicos += 1
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 32,
                    aim * 535,
                    damage,
                    ORANGE,
                    "player",
                    radius=11,
                    life=2.0,
                    explosion_radius=95,
                    skill_id=skill_id,
                )
            )

        elif skill_id == "prisao_glacial":
            game.telemetry.ataques_magicos += 1
            game.area_effects.append(
                AreaEffect(
                    "ice_prison",
                    target,
                    125,
                    duration=2.2,
                    owner="player",
                    damage=damage * 0.18,
                    tick_interval=0.42,
                    color=CYAN,
                )
            )

        elif skill_id == "singularidade_arcana":
            game.telemetry.ataques_magicos += 1
            game.area_effects.append(
                AreaEffect(
                    "singularity",
                    target,
                    145,
                    duration=2.35,
                    owner="player",
                    damage=damage * 0.12,
                    tick_interval=0.25,
                    color=PURPLE,
                )
            )

        elif skill_id == "fim_da_linha_temporal":
            game.telemetry.ataques_magicos += 1
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 390:
                    enemy.slow_timer = max(enemy.slow_timer, 2.5)
                    enemy.take_damage(damage * 0.65, game, critical=True)
            game.add_shake(18, 0.28)
            game.hit_stop = max(game.hit_stop, 0.11)

        elif skill_id == "chuva_de_flechas":
            game.telemetry.ataques_ranged += 1
            game.area_effects.append(
                AreaEffect(
                    "arrow_rain",
                    target,
                    135,
                    duration=2.0,
                    owner="player",
                    damage=damage * 0.20,
                    tick_interval=0.22,
                    delay=0.55,
                    color=YELLOW,
                )
            )

        elif skill_id == "horizonte_partido":
            game.telemetry.ataques_ranged += 1
            game.add_shake(14, 0.20)
            game.projectiles.append(
                Projectile(
                    self.pos + aim * 32,
                    aim * 1050,
                    damage,
                    CYAN,
                    "player",
                    radius=12,
                    life=1.05,
                    pierce=999,
                    skill_id=skill_id,
                )
            )

        elif skill_id == "colheita_sombria":
            hit = 0
            game.slashes.append(SlashVisual(self.pos.copy(), aim, PINK, 132, 0.18, 15))
            for enemy in game.enemies:
                delta = enemy.pos - self.pos
                if delta.length() <= 135 + enemy.radius and normalize(delta).dot(aim) > -0.05:
                    enemy.take_damage(damage, game, knockback=aim * 22)
                    hit += 1
            if hit:
                self.heal(damage * 0.07 * hit)

        elif skill_id == "sentenca_final":
            candidates = [e for e in game.enemies if not e.dead]
            if candidates:
                target_enemy = min(candidates, key=lambda e: e.pos.distance_squared_to(target))
                ratio = target_enemy.hp / max(1, target_enemy.max_hp)
                target_enemy.take_damage(damage * (2.4 if ratio <= 0.22 and target_enemy.kind != "guardian" else 1.0), game, critical=ratio <= 0.22)

        elif skill_id == "fenda_interior":
            self.hp = max(1.0, self.hp - self.max_hp * 0.10)
            self.resource = min(100.0, self.resource + 38.0)
            game.add_shake(9, 0.14)

        elif skill_id == "passo_rebobinado":
            if self.position_history:
                self.pos = self.position_history[0].copy()
            self.invuln = max(self.invuln, 0.30)

        elif skill_id == "instante_imovel":
            game.area_effects.append(AreaEffect("ice_prison", target, 150, 2.4, "player", damage=damage * 0.12, tick_interval=0.32, color=CYAN))

        elif skill_id == "torreta_do_veu":
            # Primeira versão funcional: um núcleo estacionário dispara uma rajada radial.
            for angle in range(0, 360, 30):
                d = pygame.Vector2(1, 0).rotate(angle)
                game.projectiles.append(Projectile(target.copy(), d * 430, damage * 0.50, ORANGE, "player", radius=5, life=1.5, skill_id=skill_id))

        elif skill_id == "mina_de_fenda":
            game.area_effects.append(AreaEffect("magic_burst", target, 125, 0.05, "player", damage=damage, delay=0.80, color=PURPLE))

        elif skill_id == "contra_golpe":
            self.parry_window = max(self.parry_window, 0.48)
            self.invuln = max(self.invuln, 0.12)

        elif skill_id == "danca_de_laminas":
            game.add_shake(10, 0.15)
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 170:
                    enemy.take_damage(damage * 0.72, game, critical=True)
                    enemy.take_damage(damage * 0.38, game, critical=False)

        elif skill_id == "marca_do_pressagio":
            game.projectiles.append(Projectile(self.pos + aim * 28, aim * 560, damage, PURPLE, "player", radius=8, life=1.8, skill_id=skill_id))

        elif skill_id == "destino_condenado":
            for enemy in game.enemies:
                if enemy.pos.distance_to(self.pos) < 330:
                    enemy.take_damage(damage * 0.82, game, critical=True)

        elif skill_id == "barreira_do_veu":
            self.shield_timer = max(self.shield_timer, 4.0)
            self.parry_window = max(self.parry_window, 0.36)

        else:
            # Executor genérico 0.8. Novas skills declaram comportamento em
            # class_kit_systems.py; isso evita um bloco gigante por habilidade.
            behavior = behavior_for(skill_id)
            if behavior is None:
                game.projectiles.append(
                    Projectile(self.pos + aim * 28, aim * 550, damage, self.color,
                               "player", radius=8, life=1.7, skill_id=skill_id)
                )
            elif behavior.mode == "projectile":
                speed = behavior.projectile_speed or 600
                game.projectiles.append(
                    Projectile(
                        self.pos + aim * 28, aim * speed, damage * behavior.power_scale,
                        self.color, "player", radius=8, life=max(1.2, behavior.range / max(1.0, speed)),
                        pierce=behavior.pierce, skill_id=skill_id,
                        explosion_radius=behavior.radius if behavior.radius > 0 else 0,
                    )
                )
            elif behavior.mode == "multi_projectile":
                count = max(1, behavior.projectile_count)
                spread = behavior.spread
                for i in range(count):
                    t = 0.0 if count == 1 else i / (count - 1)
                    angle = -spread / 2 + spread * t
                    d = aim.rotate(angle)
                    game.projectiles.append(
                        Projectile(
                            self.pos + d * 28, d * (behavior.projectile_speed or 560),
                            damage * behavior.power_scale, self.color, "player", radius=7,
                            life=1.8, pierce=behavior.pierce, skill_id=skill_id,
                        )
                    )
            elif behavior.mode in ("aoe_self", "cone"):
                radius = behavior.radius or 150
                for enemy in game.enemies:
                    delta = enemy.pos - self.pos
                    if delta.length() > radius + enemy.radius:
                        continue
                    if behavior.mode == "cone" and normalize(delta).dot(aim) < 0.05:
                        continue
                    enemy.take_damage(
                        damage * behavior.power_scale, game,
                        knockback=normalize(delta) * behavior.knockback if behavior.knockback else None,
                    )
                game.add_shake(8 if behavior.radius < 220 else 12, 0.14)
            elif behavior.mode in ("area", "delayed_aoe"):
                kind = "magic_burst" if behavior.mode == "delayed_aoe" else "ice_prison"
                game.area_effects.append(
                    AreaEffect(
                        kind, target, behavior.radius or 135,
                        max(0.12, behavior.duration if behavior.mode == "area" else 0.08),
                        "player", damage=damage * max(0.1, behavior.power_scale),
                        tick_interval=0.35,
                        delay=behavior.duration if behavior.mode == "delayed_aoe" else 0.0,
                        color=self.color,
                    )
                )
            elif behavior.mode == "dash_strike":
                self.pos += aim * (behavior.dash_distance or 120)
                self.invuln = max(self.invuln, 0.16)
                for enemy in game.enemies:
                    delta = enemy.pos - self.pos
                    if delta.length() <= (behavior.radius or 80) + enemy.radius:
                        enemy.take_damage(
                            damage * behavior.power_scale, game,
                            knockback=normalize(delta) * behavior.knockback if behavior.knockback else None,
                        )
            elif behavior.mode == "dash_buff":
                self.pos += aim * (behavior.dash_distance or 110)
                self.invuln = max(self.invuln, 0.22)
                if behavior.status:
                    self.active_buffs[behavior.status] = max(self.active_buffs.get(behavior.status, 0), behavior.duration or 2.0)
            elif behavior.mode == "self_buff":
                if behavior.status:
                    self.active_buffs[behavior.status] = max(self.active_buffs.get(behavior.status, 0), behavior.duration or 3.0)
                if behavior.status == "soul_feast":
                    self.heal(self.max_hp * 0.18)
                    self.resource = min(self.resource_max, self.resource + 25)
                elif behavior.status in ("protective_chain", "final_citadel"):
                    self.shield_timer = max(self.shield_timer, behavior.duration or 3.0)
            elif behavior.mode == "passive":
                # Passivas não deveriam ser acionadas manualmente, mas não causam erro
                # caso um save antigo as coloque em slot.
                return
            else:
                game.projectiles.append(
                    Projectile(self.pos + aim * 28, aim * 550, damage, self.color,
                               "player", radius=8, life=1.7, skill_id=skill_id)
                )

    def update(self, dt: float, game: "Game"):
        self.prev_pos = self.pos.copy()

        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        self.special_cooldown = max(0.0, self.special_cooldown - dt)
        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.parry_window = max(0.0, self.parry_window - dt)
        self.parry_cooldown = max(0.0, self.parry_cooldown - dt)
        self.shield_timer = max(0.0, self.shield_timer - dt)
        self.low_hp_pulse_cd = max(0.0, self.low_hp_pulse_cd - dt)
        self.dash_visual_timer = max(0.0, self.dash_visual_timer - dt)
        self.hurt_visual_timer = max(0.0, self.hurt_visual_timer - dt)
        self.attack_visual_timer = max(0.0, self.attack_visual_timer - dt)
        self.footstep_timer = max(0.0, self.footstep_timer - dt)
        self.visual_time += dt

        for buff_id in list(self.active_buffs):
            self.active_buffs[buff_id] = max(0.0, self.active_buffs[buff_id] - dt)
            if self.active_buffs[buff_id] <= 0:
                del self.active_buffs[buff_id]

        # Apoteose Rasgada troca vida por poder enquanto permanece ativa.
        if self.active_buffs.get("torn_apotheosis", 0) > 0:
            self.hp = max(1.0, self.hp - self.max_hp * 0.006 * dt)
        if self.active_buffs.get("final_citadel", 0) > 0:
            self.shield_timer = max(self.shield_timer, 0.15)

        self.position_history_timer -= dt
        if self.position_history_timer <= 0:
            self.position_history_timer = 0.08
            self.position_history.append(self.pos.copy())
            if len(self.position_history) > 20:
                self.position_history.pop(0)

        self.update_pending_cast(dt, game)

        keys = pygame.key.get_pressed()

        # Mira: mouse por padrão; setas têm prioridade quando pressionadas.
        keyboard_aim = pygame.Vector2(
            keys[pygame.K_RIGHT] - keys[pygame.K_LEFT],
            keys[pygame.K_DOWN] - keys[pygame.K_UP],
        )
        if keyboard_aim.length_squared() > 0:
            self.aim_dir = keyboard_aim.normalize()
            self.aim_target = self.pos + self.aim_dir * 320
        else:
            # Converte mouse de coordenada de tela para coordenada do mundo,
            # compensando o screen shake usado no desenho.
            mouse_target = pygame.Vector2(pygame.mouse.get_pos()) - game.current_camera_offset
            mouse_delta = mouse_target - self.pos
            if mouse_delta.length_squared() > 36:
                self.aim_dir = mouse_delta.normalize()
                self.aim_target = mouse_target

        movement = pygame.Vector2(
            keys[pygame.K_d] - keys[pygame.K_a],
            keys[pygame.K_s] - keys[pygame.K_w],
        )

        # Durante encantamentos maiores o Mago se move mais devagar, mas não trava totalmente.
        cast_move_mult = 0.42 if self.pending_cast else 1.0

        target_velocity = pygame.Vector2()
        if movement.length_squared() > 0:
            movement = movement.normalize()
            target_velocity = movement * self.movement_speed() * cast_move_mult
            game.telemetry.tempo_movendo += dt
            if self.footstep_timer <= 0 and self.dash_visual_timer <= 0:
                game.audio.play("footstep")
                self.footstep_timer = 0.31

        # Aceleração curta e frenagem macia deixam o movimento mais controlável
        # sem tirar precisão do combate ou alterar a hitbox.
        response = 16.0 if target_velocity.length_squared() > 0 else 21.0
        self.velocity = self.velocity.lerp(target_velocity, min(1.0, response * dt))
        self.pos += self.velocity * dt
        if self.velocity.length_squared() > 4:
            self.visual_move = self.velocity.normalize()
        else:
            self.visual_move *= max(0.0, 1.0 - 12.0 * dt)

        if self.hurt_visual_timer > 0:
            self.visual_state = "hurt"
        elif self.dash_visual_timer > 0:
            self.visual_state = "run"
        elif self.parry_window > 0 or self.shield_timer > 0:
            self.visual_state = "parry"
        elif self.attack_visual_timer > 0 or self.attack_cooldown > 0.08:
            self.visual_state = "attack"
        elif self.velocity.length_squared() > 180:
            self.visual_state = "walk"
        else:
            self.visual_state = "idle"

        mods = self.gear_modifiers()
        if self.class_id == "guerreiro":
            self.resource = max(0.0, self.resource - 18.0 * mods.resource_regen_mult * dt)
        elif self.class_id == "rasgado":
            self.resource = max(0.0, self.resource - 4.2 * dt)
        else:
            self.resource = min(self.resource_max, self.resource + 9.25 * mods.resource_regen_mult * dt)

        self.pos.x = clamp(self.pos.x, ROOM.left + self.radius, ROOM.right - self.radius)
        self.pos.y = clamp(self.pos.y, ROOM.top + self.radius, ROOM.bottom - self.radius)

        if self.hp / max(1, self.max_hp) <= 0.25:
            game.telemetry.tempo_baixa_vida += dt

    def draw(self, surface, offset):
        p = self.pos + offset
        blink = self.invuln > 0 and int(self.invuln * 22) % 2 == 0
        color = WHITE if blink else self.color

        # A hitbox continua circular e invisivel. A sombra ancora os pes no chao.
        pygame.draw.ellipse(surface, (5, 6, 10), (p.x - 24, p.y + 18, 48, 13))

        aim_world = normalize(self.aim_dir)
        facing_left = aim_world.x < 0

        if self.skin is not None:
            state = self.visual_state
            t = self.visual_time
            bob = 0.0
            angle = 0.0
            sx = 1.0
            sy = 1.0
            alpha = 255
            tint = (255, 255, 255)

            if state == "idle":
                bob = math.sin(t * 3.2) * 1.6
                sx = 1.0 + math.sin(t * 3.2) * 0.012
                sy = 1.0 - math.sin(t * 3.2) * 0.008
            elif state == "walk":
                phase = math.sin(t * 11.5)
                stride = abs(phase)
                bob = -stride * 3.8
                angle = phase * 3.6
                sx = 1.0 + stride * 0.028
                sy = 1.0 - stride * 0.035
            elif state == "run":
                phase = math.sin(t * 15.5)
                bob = abs(phase) * -4.2
                angle = (-5.0 if self.visual_move.x >= 0 else 5.0) + phase * 1.8
                sx, sy = 1.055, 0.965
            elif state == "attack":
                phase = 1.0 - clamp(self.attack_visual_timer / 0.24, 0.0, 1.0)
                angle = lerp(-9.0, 10.0, phase) * (-1 if facing_left else 1)
                sx = 1.0 + math.sin(phase * math.pi) * 0.08
                sy = 1.0 - math.sin(phase * math.pi) * 0.035
                bob = -2.0
            elif state == "parry":
                sy = 0.95
                sx = 1.045
                angle = -3.0 if facing_left else 3.0
                bob = 2.0
            elif state == "hurt":
                phase = clamp(self.hurt_visual_timer / 0.28, 0.0, 1.0)
                angle = (7.0 if facing_left else -7.0) * phase
                tint = (255, 155, 155)
                bob = 2.0

            # Normaliza toda skin para uma altura de gameplay legivel sem mudar a hitbox.
            base_h = 78
            ratio = base_h / max(1, self.skin.get_height())
            w = max(24, int(self.skin.get_width() * ratio * sx))
            h = max(38, int(self.skin.get_height() * ratio * sy))
            frame = cached_sprite_transform(self.skin, w, h, facing_left, angle)

            if blink:
                flash = frame.copy()
                flash.fill((255,255,255,150), special_flags=pygame.BLEND_RGBA_ADD)
                frame = flash
            elif tint != (255,255,255):
                frame = frame.copy()
                frame.fill((*tint,255), special_flags=pygame.BLEND_RGBA_MULT)

            # Dash: duas imagens fantasmas deixam o movimento claramente animado.
            if self.dash_visual_timer > 0 and self.last_dash_direction.length_squared() > 0:
                for dist, a in ((24, 70), (13, 120)):
                    ghost = frame.copy(); ghost.set_alpha(a)
                    gpos = p - self.last_dash_direction * dist
                    grect = ghost.get_rect(midbottom=(int(gpos.x), int(gpos.y + 31 + bob)))
                    surface.blit(ghost, grect)

            rect = frame.get_rect(midbottom=(int(p.x), int(p.y + 31 + bob)))
            surface.blit(frame, rect)
        else:
            # Fallback seguro se um asset faltar: nunca quebra a partida.
            pygame.draw.circle(surface, color, p, self.radius)
            pygame.draw.circle(surface, BLACK, p, self.radius, 3)
            pygame.draw.line(surface, WHITE, p, p + aim_world * 32, 4)

        if self.parry_window > 0:
            pygame.draw.circle(surface, CYAN, p, self.radius + 13, 4)
        if self.shield_timer > 0:
            pygame.draw.circle(surface, BLUE, p, self.radius + 18, 3)

        if self.pending_cast:
            ratio = clamp(self.pending_cast.timer / max(0.001, self.base_cast_time(self.pending_cast.skill_id)), 0, 1)
            pygame.draw.circle(surface, PURPLE, p, self.radius + 26, 3)
            pygame.draw.arc(
                surface,
                WHITE,
                pygame.Rect(p.x - 32, p.y - 32, 64, 64),
                -math.pi / 2,
                -math.pi / 2 + math.tau * (1 - ratio),
                5,
            )


# ============================================================
# UI: BOTÕES / CARDS
# ============================================================

class Button:
    def __init__(self, rect: pygame.Rect, text: str, accent=WHITE):
        self.rect = rect
        self.text = text
        self.accent = accent

    def draw(self, surface, mouse):
        hover = self.rect.collidepoint(mouse)
        draw_ui_panel(
            surface,
            self.rect,
            self.accent,
            PANEL_HOVER if hover else PANEL,
            radius=9,
            glow=hover,
        )
        marker_x = self.rect.x + 18
        pygame.draw.circle(surface, self.accent, (marker_x, self.rect.centery), 4 if hover else 3)
        draw_text(surface, self.text, (self.rect.centerx + 8, self.rect.centery), self.accent if hover else WHITE, FONT, True)

    def clicked(self, event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )


# ============================================================
# MENU / CRIAÇÃO
# ============================================================

class Frontend:
    def __init__(self, profile_manager: ProfileManager):
        self.profile_manager = profile_manager
        self.selected_slot = 1
        self.save_manager = SaveManager(str(self.profile_manager.save_path(self.selected_slot)))
        self.mode = "title"
        self.name_input = ""
        self.gender = Gender.MASCULINO
        self.class_id = "guerreiro"
        self.message = ""
        self.scroll = 0
        self.meta_state: Optional[PlayerState] = None
        self.unlocked_classes = {"guerreiro", "mago", "arqueiro"}
        self.refresh_slot_context()

    def refresh_slot_context(self):
        self.save_manager = SaveManager(str(self.profile_manager.save_path(self.selected_slot)))
        self.meta_state = None
        self.unlocked_classes = {"guerreiro", "mago", "arqueiro"}
        if self.profile_manager.save_path(self.selected_slot).exists():
            self.meta_state = self.save_manager.load()
            self.unlocked_classes = set(self.meta_state.progression.classes_desbloqueadas)

    def select_slot(self, slot: int):
        if 1 <= slot <= self.profile_manager.slots:
            self.selected_slot = slot
            self.refresh_slot_context()
            self.message = ""

    def slot_rects(self):
        width = 205
        gap = 18
        total = width * self.profile_manager.slots + gap * (self.profile_manager.slots - 1)
        start = WIDTH // 2 - total // 2
        return [pygame.Rect(start + i * (width + gap), 292, width, 76) for i in range(self.profile_manager.slots)]

    def run(self) -> PlayerState:
        AUDIO.set_music("menu", force=True)
        while True:
            dt = clock.tick(RENDER_FPS_CAP) / 1000.0
            AUDIO.router.update(dt)
            mouse = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

                if self.mode == "title":
                    result = self.handle_title_event(event)
                    if result is not None:
                        return result
                elif self.mode == "create":
                    result = self.handle_create_event(event)
                    if result is not None:
                        return result
                elif self.mode == "settings":
                    self.handle_front_settings_event(event)
                elif self.mode == "credits":
                    self.handle_credits_event(event)

            if self.mode == "title":
                self.draw_title(mouse)
            elif self.mode == "create":
                self.draw_create(mouse)
            elif self.mode == "settings":
                self.draw_front_settings()
            else:
                self.draw_credits()

            pygame.display.flip()

    def handle_title_event(self, event):
        new_btn = Button(pygame.Rect(WIDTH // 2 - 170, 382, 340, 46), "NOVO JOGO", PURPLE)
        continue_btn = Button(pygame.Rect(WIDTH // 2 - 170, 434, 340, 46), "CONTINUAR", CYAN)
        settings_btn = Button(pygame.Rect(WIDTH // 2 - 170, 486, 340, 46), "CONFIGURAÇÕES", WHITE)
        credits_btn = Button(pygame.Rect(WIDTH // 2 - 170, 538, 340, 46), "CRÉDITOS", YELLOW)
        quit_btn = Button(pygame.Rect(WIDTH // 2 - 170, 590, 340, 46), "SAIR", RED)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.slot_rects(), start=1):
                if rect.collidepoint(event.pos):
                    AUDIO.play("ui_confirm")
                    self.select_slot(i)
                    return None

        if new_btn.clicked(event):
            AUDIO.play("ui_confirm")
            self.mode = "create"
            return None

        if continue_btn.clicked(event):
            if self.profile_manager.save_path(self.selected_slot).exists():
                AUDIO.play("ui_confirm")
                return self.save_manager.load()
            self.message = f"Slot {self.selected_slot} está vazio."

        if settings_btn.clicked(event):
            AUDIO.play("ui_confirm")
            self.mode = "settings"
            return None

        if credits_btn.clicked(event):
            AUDIO.play("ui_confirm")
            self.mode = "credits"
            return None

        if quit_btn.clicked(event):
            AUDIO.play("ui_back")
            pygame.quit()
            raise SystemExit

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.select_slot(event.key - pygame.K_1 + 1)
            elif event.key == pygame.K_n:
                self.mode = "create"
            elif event.key == pygame.K_c and self.profile_manager.save_path(self.selected_slot).exists():
                return self.save_manager.load()
            elif event.key == pygame.K_o:
                self.mode = "settings"
            elif event.key == pygame.K_F1:
                self.mode = "credits"

        return None

    def handle_create_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                AUDIO.play("ui_back")
                self.mode = "title"
                return None
            if event.key == pygame.K_BACKSPACE:
                self.name_input = self.name_input[:-1]
            elif event.key == pygame.K_RETURN:
                return self.try_create()
            elif event.unicode and event.unicode.isprintable() and len(self.name_input) < 24:
                self.name_input += event.unicode

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            male_rect = pygame.Rect(120, 205, 180, 46)
            female_rect = pygame.Rect(315, 205, 180, 46)
            if male_rect.collidepoint(event.pos):
                AUDIO.play("ui_confirm")
                self.gender = Gender.MASCULINO
            elif female_rect.collidepoint(event.pos):
                AUDIO.play("ui_confirm")
                self.gender = Gender.FEMININO

            cards = self.class_card_rects()
            for class_id, rect in cards:
                if rect.collidepoint(event.pos):
                    if class_id in self.unlocked_classes:
                        AUDIO.play("ui_confirm")
                        self.class_id = class_id
                        self.message = ""
                    else:
                        rule = rule_for_class(class_id)
                        self.message = rule.descricao if rule else f"{CLASS_REGISTRY[class_id].nome} está bloqueada."

            start_rect = pygame.Rect(WIDTH - 305, HEIGHT - 72, 245, 48)
            if start_rect.collidepoint(event.pos):
                AUDIO.play("ui_confirm")
                return self.try_create()

        return None

    def try_create(self):
        name = self.name_input.strip() or "Viajante"
        state = create_new_character(name, self.gender, self.class_id)
        if self.meta_state is not None:
            state = transfer_meta_progression(self.meta_state, state)
        self.profile_manager.save(self.selected_slot, state, playtime_seconds=0)
        self.refresh_slot_context()
        return state

    def draw_title(self, mouse):
        screen.fill(BG)
        self.draw_rift_background()

        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((5, 6, 13, 92))
        screen.blit(veil, (0, 0))

        title_panel = pygame.Rect(WIDTH // 2 - 340, 55, 680, 215)
        draw_ui_panel(screen, title_panel, PURPLE, (16, 17, 30), radius=18, glow=True)
        pygame.draw.circle(screen, (255, 255, 255, 22), (WIDTH // 2, 132), 108, 2)

        draw_text(screen, "RIFTWALKER", (WIDTH // 2, 100), PURPLE, FONT_TITLE, True)
        draw_text(screen, "RELEASE CANDIDATE 0.9", (WIDTH // 2, 168), GRAY, FONT, True)
        draw_text(screen, "O Véu se lembra.", (WIDTH // 2, 215), WHITE, FONT_MEDIUM, True)
        draw_text(screen, "Escolha um slot", (WIDTH // 2, 262), GRAY, FONT_SMALL, True)

        for slot, rect in enumerate(self.slot_rects(), start=1):
            selected = slot == self.selected_slot
            meta = self.profile_manager.slot_meta(slot)
            draw_ui_panel(screen, rect, CYAN if selected else DARK_GRAY, PANEL_HOVER if selected else PANEL, radius=9, glow=selected)
            draw_text(screen, f"SLOT {slot}", (rect.centerx, rect.y + 16), CYAN if selected else WHITE, FONT_SMALL, True)
            if meta.exists:
                cls = CLASS_REGISTRY.get(meta.class_id)
                label = f"{meta.character_name} • Nv.{meta.level}"
                draw_text(screen, label, (rect.centerx, rect.y + 40), WHITE, FONT_TINY, True)
                draw_text(screen, cls.nome if cls else meta.class_id, (rect.centerx, rect.y + 58), GRAY, FONT_TINY, True)
            else:
                draw_text(screen, "VAZIO", (rect.centerx, rect.y + 48), DARK_GRAY, FONT_TINY, True)

        buttons = [
            Button(pygame.Rect(WIDTH // 2 - 170, 382, 340, 46), "NOVO JOGO", PURPLE),
            Button(pygame.Rect(WIDTH // 2 - 170, 434, 340, 46), "CONTINUAR", CYAN),
            Button(pygame.Rect(WIDTH // 2 - 170, 486, 340, 46), "CONFIGURAÇÕES", WHITE),
            Button(pygame.Rect(WIDTH // 2 - 170, 538, 340, 46), "CRÉDITOS", YELLOW),
            Button(pygame.Rect(WIDTH // 2 - 170, 590, 340, 46), "SAIR", RED),
        ]
        for btn in buttons:
            btn.draw(screen, mouse)

        if not self.profile_manager.save_path(self.selected_slot).exists():
            draw_text(screen, "Slot selecionado sem save", (WIDTH // 2, 590), DARK_GRAY, FONT_TINY, True)
        if self.message:
            draw_text(screen, self.message, (WIDTH // 2, 615), YELLOW, FONT_SMALL, True)

        draw_text(screen, "1/2/3 slot • N novo • C continuar • O opções • F1 créditos", (WIDTH // 2, HEIGHT - 38), GRAY, FONT_TINY, True)
        draw_text(screen, "Python + Pygame | lógica 60 Hz independente do FPS", (WIDTH // 2, HEIGHT - 19), DARK_GRAY, FONT_TINY, True)

    def handle_front_settings_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_o):
            AUDIO.play("ui_back")
            self.mode = "title"
            return
        changed = False
        if event.key == pygame.K_1:
            GAME_SETTINGS.accessibility.subtitles = not GAME_SETTINGS.accessibility.subtitles; changed = True
        elif event.key == pygame.K_2:
            GAME_SETTINGS.accessibility.reduced_screen_shake = not GAME_SETTINGS.accessibility.reduced_screen_shake; changed = True
        elif event.key == pygame.K_3:
            GAME_SETTINGS.accessibility.reduced_flashes = not GAME_SETTINGS.accessibility.reduced_flashes; changed = True
        elif event.key == pygame.K_4:
            GAME_SETTINGS.accessibility.damage_numbers = not GAME_SETTINGS.accessibility.damage_numbers; changed = True
        elif event.key == pygame.K_5:
            ids = list(DIFFICULTIES.keys())
            cur = ids.index(GAME_SETTINGS.difficulty) if GAME_SETTINGS.difficulty in ids else 0
            GAME_SETTINGS.difficulty = ids[(cur + 1) % len(ids)]; changed = True
        elif event.key == pygame.K_6:
            GAME_SETTINGS.audio.music = max(0, GAME_SETTINGS.audio.music - 10); changed = True
        elif event.key == pygame.K_7:
            GAME_SETTINGS.audio.music = min(100, GAME_SETTINGS.audio.music + 10); changed = True
        elif event.key == pygame.K_8:
            GAME_SETTINGS.audio.sfx = max(0, GAME_SETTINGS.audio.sfx - 10); changed = True
        elif event.key == pygame.K_9:
            GAME_SETTINGS.audio.sfx = min(100, GAME_SETTINGS.audio.sfx + 10); changed = True
        if changed:
            SETTINGS_MANAGER.save(GAME_SETTINGS)
            AUDIO.refresh_volumes()
            AUDIO.play("ui_confirm")

    def draw_front_settings(self):
        screen.fill(BG)
        draw_text(screen, "CONFIGURAÇÕES", (WIDTH // 2, 75), WHITE, FONT_BIG, True)
        draw_text(screen, "1–9 altera • O/ESC volta", (WIDTH // 2, 122), GRAY, FONT_SMALL, True)
        a = GAME_SETTINGS.accessibility
        au = GAME_SETTINGS.audio
        diff = DIFFICULTIES[GAME_SETTINGS.difficulty]
        rows = [
            ("1", "Legendas", "ON" if a.subtitles else "OFF"),
            ("2", "Screen shake reduzido", "ON" if a.reduced_screen_shake else "OFF"),
            ("3", "Flashes reduzidos", "ON" if a.reduced_flashes else "OFF"),
            ("4", "Números de dano", "ON" if a.damage_numbers else "OFF"),
            ("5", "Dificuldade", diff.nome),
            ("6", "Música -10", f"{au.music}%"),
            ("7", "Música +10", f"{au.music}%"),
            ("8", "SFX -10", f"{au.sfx}%"),
            ("9", "SFX +10", f"{au.sfx}%"),
        ]
        y=175
        for key,label,value in rows:
            rect=pygame.Rect(WIDTH//2-380,y,760,44)
            draw_ui_panel(screen, rect, CYAN if key == "5" else DARK_GRAY, PANEL, radius=7, glow=False)
            draw_text(screen,f"{key}. {label}",(rect.x+18,rect.y+11),WHITE,FONT_SMALL)
            draw_text(screen,value,(rect.right-160,rect.y+11),CYAN,FONT_SMALL)
            y+=51
        draw_wrapped_text(screen,diff.descricao,pygame.Rect(WIDTH//2-380,y+10,760,70),GRAY,FONT_SMALL)

    def handle_credits_event(self, event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_F1):
            AUDIO.play("ui_back")
            self.mode = "title"

    def draw_credits(self):
        screen.fill(BG)
        self.draw_rift_background()
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((5, 6, 13, 128))
        screen.blit(veil, (0, 0))
        draw_ui_panel(screen, pygame.Rect(90, 42, WIDTH - 180, HEIGHT - 105), PURPLE, (14, 16, 27), radius=16, glow=True)
        draw_text(screen,"RIFTWALKER",(WIDTH//2,72),PURPLE,FONT_TITLE,True)
        draw_text(screen,"CRÉDITOS DA RELEASE CANDIDATE",(WIDTH//2,142),WHITE,FONT_MEDIUM,True)
        lines=[
            "Projeto: RIFTWALKER — Python + Pygame",
            "Sistemas: classes, Rupturas, IA, Memória do Véu, campanha, Refúgio e progressão",
            "Áudio/músicas: geração procedural própria desta RC",
            "Voz provisória: síntese local com eSpeak + pós-processamento FFmpeg",
            "Ícone: geração procedural do projeto",
            "Assets externos incorporados nesta RC: nenhum",
            "",
            "As vozes sintéticas são provisórias e podem ser substituídas por dublagem final.",
            "O arquivo CREDITS.txt mantém as informações de produção/licença.",
        ]
        y=230
        for line in lines:
            draw_text(screen,line,(WIDTH//2,y),GRAY if line else WHITE,FONT_SMALL,True)
            y+=38
        draw_text(screen,"F1 ou ESC para voltar",(WIDTH//2,HEIGHT-60),YELLOW,FONT_SMALL,True)

    def draw_rift_background(self):
        center = pygame.Vector2(WIDTH // 2, HEIGHT // 2)
        ticks = pygame.time.get_ticks() * 0.001
        for i in range(18):
            angle = i / 18 * math.tau + ticks * 0.06
            length = 260 + math.sin(ticks * 1.5 + i) * 28
            start = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * 115
            end = center + pygame.Vector2(math.cos(angle), math.sin(angle)) * length
            pygame.draw.line(screen, (40, 24, 65), start, end, 2)

    def class_card_rects(self):
        ids = list(CLASS_REGISTRY.keys())
        rects = []
        columns = 5
        card_w = 215
        card_h = 140
        gap = 14
        start_x = 70
        start_y = 305
        for i, class_id in enumerate(ids):
            col = i % columns
            row = i // columns
            rect = pygame.Rect(
                start_x + col * (card_w + gap),
                start_y + row * (card_h + gap),
                card_w,
                card_h,
            )
            rects.append((class_id, rect))
        return rects

    def draw_create(self, mouse):
        screen.fill(BG)
        self.draw_rift_background()
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill((7, 8, 15, 118))
        screen.blit(veil, (0, 0))
        draw_text(screen, "CRIAR RIFTWALKER", (55, 38), WHITE, FONT_BIG)
        pygame.draw.line(screen, PURPLE, (55, 92), (WIDTH - 55, 92), 2)

        draw_text(screen, "Nome", (70, 115), GRAY, FONT_SMALL)
        name_rect = pygame.Rect(70, 140, 430, 48)
        draw_ui_panel(screen, name_rect, PURPLE, PANEL, radius=8, glow=True)
        name_display = self.name_input + ("|" if pygame.time.get_ticks() // 450 % 2 == 0 else "")
        draw_text(screen, name_display or "", (84, 152), WHITE, FONT)

        draw_text(screen, "Gênero / voz", (120, 183), GRAY, FONT_TINY)
        male_rect = pygame.Rect(120, 205, 180, 46)
        female_rect = pygame.Rect(315, 205, 180, 46)
        for rect, gender, label in (
            (male_rect, Gender.MASCULINO, "HOMEM"),
            (female_rect, Gender.FEMININO, "MULHER"),
        ):
            selected = self.gender == gender
            draw_ui_panel(screen, rect, CYAN if selected else DARK_GRAY, PANEL_HOVER if selected else PANEL, radius=7, glow=selected)
            draw_text(screen, label, rect.center, WHITE, FONT_SMALL, True)

        # Preview vivo da skin selecionada: usa exatamente class_id + genero.
        selected_skin = get_player_skin(self.class_id, self.gender)
        if selected_skin is not None:
            target_h = 145
            ratio = target_h / max(1, selected_skin.get_height())
            preview = pygame.transform.smoothscale(selected_skin, (max(45, int(selected_skin.get_width()*ratio)), target_h))
            bob = math.sin(pygame.time.get_ticks() * 0.0032) * 2
            prect = preview.get_rect(midbottom=(WIDTH - 180, 272 + int(bob)))
            screen.blit(preview, prect)
            draw_text(screen, CLASS_REGISTRY[self.class_id].nome, (WIDTH - 180, 278), CLASS_COLORS.get(self.class_id, WHITE), FONT_SMALL, True)

        draw_text(screen, "Classes", (70, 272), WHITE, FONT_MEDIUM)
        draw_text(
            screen,
            "As 3 primeiras estão disponíveis. As outras existem no sistema e serão desbloqueadas.",
            (225, 280),
            GRAY,
            FONT_SMALL,
        )

        for class_id, rect in self.class_card_rects():
            definition = CLASS_REGISTRY[class_id]
            unlocked = class_id in self.unlocked_classes
            selected = class_id == self.class_id
            accent = CLASS_COLORS.get(class_id, WHITE)

            hovered = rect.collidepoint(mouse)
            draw_ui_panel(
                screen,
                rect,
                accent if unlocked else DARK_GRAY,
                PANEL_HOVER if (hovered or selected) else PANEL,
                radius=10,
                glow=selected,
            )
            pygame.draw.circle(screen, accent if unlocked else DARK_GRAY, (rect.right - 17, rect.y + 17), 4)

            draw_text(screen, definition.nome, (rect.x + 12, rect.y + 10), accent if unlocked else GRAY, FONT_SMALL)
            draw_text(
                screen,
                f"Dificuldade: {difficulty_label(definition.dificuldade)}",
                (rect.x + 12, rect.y + 34),
                GRAY,
                FONT_TINY,
            )
            draw_wrapped_text(
                screen,
                definition.identidade,
                pygame.Rect(rect.x + 12, rect.y + 56, rect.width - 24, 58),
                WHITE if unlocked else DARK_GRAY,
                FONT_TINY,
            )
            if not unlocked:
                draw_text(screen, "BLOQUEADA", (rect.centerx, rect.bottom - 14), RED, FONT_TINY, True)
            elif class_id not in ("guerreiro", "mago", "arqueiro"):
                draw_text(screen, "DESBLOQUEADA", (rect.centerx, rect.bottom - 14), GREEN, FONT_TINY, True)

        start_rect = pygame.Rect(WIDTH - 305, HEIGHT - 72, 245, 48)
        draw_ui_panel(screen, start_rect, GREEN, PANEL_HOVER if start_rect.collidepoint(mouse) else PANEL, radius=8, glow=start_rect.collidepoint(mouse))
        draw_text(screen, "ENTRAR NO VÉU", start_rect.center, GREEN, FONT_SMALL, True)

        if self.message:
            draw_text(screen, self.message, (70, HEIGHT - 55), YELLOW, FONT_SMALL)


# ============================================================
# JOGO PRINCIPAL
# ============================================================

class Game:
    def __init__(self, player_state: PlayerState, save_path: Path = SAVE_PATH):
        self.player_state = player_state
        self.player = PlayerAvatar(player_state)
        self.audio = AUDIO
        self.difficulty = DIFFICULTIES.get(GAME_SETTINGS.difficulty, DIFFICULTIES["viajante"])
        self.meta_panel: Optional[str] = None
        self.meta_message = ""

        # Campanha roda separada da renderização e reage a eventos reais do jogo.
        self.campaign = CampaignDirector(self.player_state)
        self.hub = ensure_hub_state(self.player_state)
        if self.campaign.current_region().id == "refugio_ultima_luz":
            self.campaign.enter_region("campos_primeira_fenda")

        self.encounter_director = EncounterDirector(seed=random.randint(1, 2_000_000_000))
        self.environment = EnvironmentRenderer()
        self.diagnostics = RuntimeDiagnostics()
        self.transition_alpha = 170.0

        self.save_path = Path(save_path)
        self.save_manager = SaveManager(str(self.save_path))
        self.autosave = AutosaveController(self.save_manager, minimum_interval=1.5)

        self.enemies: List[Enemy] = []
        self.enemy_deaths: List[EnemyDeathVisual] = []
        self.projectiles: List[Projectile] = []
        self.particles: List[Particle] = []
        self.floating_texts: List[FloatingText] = []
        self.slashes: List[SlashVisual] = []
        self.area_effects: List[AreaEffect] = []
        self.heals: List[pygame.Vector2] = []
        self.speech: Optional[SpeechBubble] = None
        self.reaction_controller = ReactionController()

        self.wave = 0
        self.rooms_cleared = 0
        self.score = 0
        self.paused = False
        self.pause_selection = 0
        self.abandon_confirm = False
        self.return_to_menu_requested = False
        self.game_over = False
        self.debug = False
        self.inventory_open = False
        self.inventory_message = ""
        self.hit_stop = 0.0
        self.shake_power = 0.0
        self.shake_timer = 0.0
        self.camera_shake_offset = pygame.Vector2()
        self.current_camera_offset = pygame.Vector2()
        self.logic_updates_last_frame = 0

        self.skill_cooldowns: Dict[str, float] = {}
        self.telemetry = CombatTelemetry()

        self.offer_mode: Optional[str] = None
        self.skill_offers: List[SkillDefinition] = []
        self.rift_offers: List[str] = []
        self.ending_offers = []
        self.banner_title = ""
        self.banner_subtitle = ""
        self.banner_color = WHITE
        self.banner_timer = 0.0
        self.banner_queue: List[Tuple[str, str, Tuple[int, int, int]]] = []

        self.current_boss_strategy = "variacao_tatica"
        self.boss_spawn_line_shown = False
        self.magic_burst_triggered_ids = set()

        self.pending_level_ups = 0
        self.xp_needed = self.calculate_xp_needed(self.player_state.stats.nivel)

        self.spawn_next_room()

    # --------------------------------------------------------
    # PERFORMANCE / GUARDRAILS
    # --------------------------------------------------------

    def enforce_runtime_budgets(self):
        # Limites altos o bastante para não amputar a fantasia visual, mas impedem
        # uma combinação extrema de Rupturas/bosses de crescer sem controle.
        budgets = (
            ("particles", self.particles, 520),
            ("floating_texts", self.floating_texts, 140),
            ("slashes", self.slashes, 140),
            ("projectiles", self.projectiles, 420),
            ("area_effects", self.area_effects, 120),
            ("enemy_deaths", self.enemy_deaths, 80),
        )
        for name, collection, limit in budgets:
            dropped = trim_oldest(collection, limit)
            self.diagnostics.note_drop(name, dropped)

    def diagnostic_counts(self):
        return {
            "enemies": len(self.enemies),
            "projectiles": len(self.projectiles),
            "particles": len(self.particles),
            "areas": len(self.area_effects),
            "texts": len(self.floating_texts),
        }

    # --------------------------------------------------------
    # PROGRESSÃO
    # --------------------------------------------------------

    @staticmethod
    def calculate_xp_needed(level: int) -> int:
        return int(70 * (1.25 ** max(0, level - 1)))

    def process_campaign_rewards(self):
        """Entrega automática temporária até o Refúgio/NPCs terem UI própria."""
        claimed = self.campaign.claim_ready_quests()
        for quest_id in claimed:
            quest = QUESTS[quest_id]
            self.queue_banner(
                "MISSÃO CONCLUÍDA",
                f"{quest.nome} — recompensas recebidas",
                GREEN,
            )
            self.autosave.request(AutosaveReason.EVENTO_HISTORIA)

    def award_xp(self, amount: int):
        mult = self.player_state.active_rifts.cumulative_modifiers()["xp_multiplier"]
        gained = max(1, int(amount * mult * self.difficulty.reward_mult))
        self.player_state.stats.xp += gained
        self.score += gained

        while self.player_state.stats.xp >= self.xp_needed:
            self.player_state.stats.xp -= self.xp_needed
            self.player_state.stats.nivel += 1
            self.pending_level_ups += 1
            self.xp_needed = self.calculate_xp_needed(self.player_state.stats.nivel)

    def open_skill_offer(self):
        self.skill_offers = generate_skill_offers(
            class_id=self.player_state.identity.class_id,
            owned_skill_ids=self.player_state.owned_skills,
            amount=3,
            luck=min(0.55, self.player_state.stats.nivel * 0.025),
            allow_corrupted=self.rooms_cleared >= 2,
        )
        if self.skill_offers:
            self.offer_mode = "skill"
        else:
            self.pending_level_ups = max(0, self.pending_level_ups - 1)

    def choose_skill_offer(self, index: int):
        if self.offer_mode != "skill" or index >= len(self.skill_offers):
            return

        skill = self.skill_offers[index]
        learned = self.player_state.learn_skill(skill.id)
        self.player.refresh_skill_slots()

        if learned:
            if skill.raridade in (Rarity.LENDARIA, Rarity.MITICA, Rarity.CORROMPIDA):
                self.audio.play("ui_legendary_drop")
            elif skill.raridade in (Rarity.RARA, Rarity.EPICA):
                self.audio.play("ui_rare_drop")
            else:
                self.audio.play("ui_confirm")
            self.queue_banner(
                skill.raridade.value.upper(),
                f"{skill.nome} aprendida",
                RARITY_COLORS[skill.raridade],
            )
            self.campaign.record(CampaignEvent.SKILL_LEARNED, target_id=skill.id)
            self.process_campaign_rewards()
        else:
            # Se no futuro permitirmos duplicatas, aqui pode evoluir a habilidade.
            self.player_state.register_skill_use(skill.id, mastery_xp=30)

        self.pending_level_ups = max(0, self.pending_level_ups - 1)
        self.offer_mode = None
        self.autosave.request(AutosaveReason.DESBLOQUEIO_IMPORTANTE)
        self.evaluate_unlocks()

        if self.pending_level_ups > 0:
            self.open_skill_offer()

    def open_rift_offer(self):
        self.audio.play("rift_open")
        ids = list(RIFT_REGISTRY.keys())
        self.rift_offers = random.sample(ids, min(3, len(ids)))
        self.offer_mode = "rift"

    def choose_rift_offer(self, index: int):
        if self.offer_mode != "rift" or index >= len(self.rift_offers):
            return

        rift_id = self.rift_offers[index]
        self.audio.play("rift_accept")
        rift = RIFT_REGISTRY[rift_id]
        self.player_state.active_rifts.add(rift_id)
        self.player_state.progression.rupturas_descobertas.add(rift_id)
        self.campaign.record(CampaignEvent.RIFT_DISCOVERED, target_id=rift_id)
        add_metric(self.player_state, "max_active_rifts", len(self.player_state.active_rifts.active_ids), absolute_max=True)
        self.process_campaign_rewards()
        self.player.refresh_from_state()

        self.queue_banner(rift.nome.upper(), rift.descricao, PURPLE)
        self.offer_mode = None
        self.autosave.request(AutosaveReason.RUPTURA_CONCLUIDA)
        self.evaluate_unlocks()
        self.spawn_next_room()

    def choose_ending_offer(self, index: int):
        if self.offer_mode != "ending" or index < 0 or index >= len(self.ending_offers):
            return
        ending = choose_ending(self.player_state, self.ending_offers[index].id)
        self.offer_mode = None
        self.ending_offers = []
        self.queue_banner(ending.nome.upper(), ending.epilogo, CYAN if ending.tone != "corrupted" else RED)
        self.autosave.save_now(self.player_state, AutosaveReason.EVENTO_HISTORIA)

    # --------------------------------------------------------
    # SPAWN / SQUADS
    # --------------------------------------------------------

    def random_edge_spawn(self):
        side = random.choice(("top", "bottom", "left", "right"))
        if side == "top":
            return pygame.Vector2(random.randint(ROOM.left + 40, ROOM.right - 40), ROOM.top + 35)
        if side == "bottom":
            return pygame.Vector2(random.randint(ROOM.left + 40, ROOM.right - 40), ROOM.bottom - 35)
        if side == "left":
            return pygame.Vector2(ROOM.left + 35, random.randint(ROOM.top + 40, ROOM.bottom - 40))
        return pygame.Vector2(ROOM.right - 35, random.randint(ROOM.top + 40, ROOM.bottom - 40))

    def next_story_boss_id(self) -> str:
        defeated = self.player_state.progression.bosses_derrotados
        order = (
            "guardiao_primeira_ruptura",
            "matriarca_sussurrante",
            "primeiro_rasgado",
            "cronarca_fraturado",
            FINAL_BOSS_ID,
        )
        for boss_id in order:
            if boss_id not in defeated:
                return boss_id
        # Pós-jogo: o Eco só entra depois que o boss final caiu; caso contrário,
        # rematches usam o Guardião como ciclo de treinamento.
        if FINAL_BOSS_ID in defeated and ECHO_BOSS_ID not in defeated:
            return ECHO_BOSS_ID
        return "guardiao_primeira_ruptura"

    def spawn_next_room(self):
        self.transition_alpha = max(self.transition_alpha, 155.0)
        self.wave += 1
        difficulty = 1.0 + self.wave * 0.09

        if self.wave % 5 == 0:
            boss_id = self.next_story_boss_id()
            definition = BOSSES[boss_id]
            memory = self.player_state.veil_memory.get(boss_id)
            self.current_boss_strategy = memory.choose_strategy() if memory.encontros > 0 else "variacao_tatica"
            boss = Enemy(
                self.random_edge_spawn(),
                "guardian",
                difficulty,
                squad_id=999,
                doctrine=choose_squad_doctrine(()),
                role="Boss",
            )
            boss.boss_id = boss_id
            boss.boss_director = BossDirector(boss_id, self.player_state, seed=self.wave * 997 + self.rooms_cleared)
            self.decorate_enemy(boss, boss=True)
            self.enemies.append(boss)
            self.boss_spawn_line_shown = False

            # No modo arena/tournament, a progressão de boss também registra a
            # região correspondente para a campanha não ficar desconectada.
            campaign_state = self.player_state.campaign
            unlocked_regions = set(campaign_state.setdefault("unlocked_regions", ["refugio_ultima_luz", "campos_primeira_fenda"]))
            unlocked_regions.add(definition.region_id)
            campaign_state["unlocked_regions"] = sorted(unlocked_regions)
            self.campaign.enter_region(definition.region_id)

            self.queue_banner(definition.nome.upper(), definition.title, ORANGE)
            intro = boss.boss_director.intro_line()
            if intro:
                self.speak_enemy(definition.nome, intro, ORANGE, priority=5, duration=2.8)
            return

        region_id = self.campaign.current_region().id
        if region_id not in REGIONS or region_id == "refugio_ultima_luz":
            region_id = "campos_primeira_fenda"
        performance = PerformanceSnapshot(
            hp_ratio=self.player.hp / max(1, self.player.max_hp),
            recent_deaths=min(3, int(self.player_state.campaign.get("recent_deaths", 0))),
            rooms_cleared_fast=1 if self.rooms_cleared >= 3 and self.player.hp / max(1, self.player.max_hp) > 0.80 else 0,
            healing_used_recently=min(4, self.telemetry.curas_usadas),
            active_rifts=len(self.player_state.active_rifts.active_ids),
        )
        plan = self.encounter_director.generate(region_id, self.wave, performance)
        doctrine = SQUAD_DOCTRINES.get(plan.doctrine, choose_squad_doctrine(()))

        for squad_id, group in enumerate(plan.spawn_groups):
            for archetype in group:
                kind = "shooter" if archetype == "support" else archetype
                role = "Support" if archetype == "support" else archetype.title()
                enemy = Enemy(
                    self.random_edge_spawn(),
                    kind,
                    difficulty,
                    squad_id=squad_id,
                    doctrine=doctrine,
                    role=role,
                )
                force_superior = random.random() < max(0.0, plan.superior_chance_bonus + self.difficulty.superior_chance)
                self.decorate_enemy(
                    enemy,
                    elite=kind in ("tank", "hunter"),
                    force_superior=force_superior,
                )
                self.enemies.append(enemy)

        if plan.recovery_after:
            self.queue_banner("O VÉU HESITA", "A próxima pressão foi reduzida pelo Diretor de Encontros.", CYAN)

    def decorate_enemy(self, enemy: Enemy, elite: bool = False, boss: bool = False, force_superior: bool = False):
        creature_id = creature_id_for_archetype(enemy.kind)
        traits = roll_spawn_traits(
            creature_id=creature_id,
            wave=self.wave,
            active_rift_ids=self.player_state.active_rifts.active_ids,
            elite=elite,
            boss=boss,
            force_superior=force_superior,
        )
        apply_traits_to_enemy(enemy, traits)
        enemy.max_hp = max(1, int(enemy.max_hp * self.difficulty.enemy_hp))
        enemy.hp = enemy.max_hp
        enemy.damage = max(1, int(enemy.damage * self.difficulty.enemy_damage))
        enemy.speed *= self.difficulty.enemy_speed
        enemy.memory_id = superior_memory_id(traits)
        before, after = record_encounter(
            self.player_state,
            creature_id,
            traits.mutation_ids,
        )
        if before != after:
            self.queue_banner(
                "ARQUIVO DO VÉU",
                f"{CREATURES[creature_id].nome}: conhecimento {after.value}.",
                CYAN,
            )
        if traits.tier == CreatureTier.SUPERIOR:
            self.audio.play("superior_spawn")
            subtitle = mutation_display(traits.mutation_ids) or "Sem mutação catalogada"
            self.queue_banner(
                "INIMIGO SUPERIOR",
                f"{traits.superior_name} — {subtitle}",
                ORANGE,
            )

    @staticmethod
    def kind_for_role(role: str) -> str:
        role_lower = role.lower()
        if role_lower == "tank":
            return "tank"
        if role_lower == "ranged" or role_lower == "support":
            return "shooter"
        if role_lower in ("hunter", "flanker"):
            return "hunter"
        return "crawler"

    def squad_center(self, squad_id: int) -> pygame.Vector2:
        members = [e for e in self.enemies if e.squad_id == squad_id and not e.dead]
        if not members:
            return self.player.pos.copy()
        total = pygame.Vector2()
        for enemy in members:
            total += enemy.pos
        return total / len(members)

    def nearest_enemy(self, pos: pygame.Vector2) -> Optional[Enemy]:
        live = [e for e in self.enemies if not e.dead]
        if not live:
            return None
        return min(live, key=lambda e: e.pos.distance_squared_to(pos))

    # --------------------------------------------------------
    # BOSS / MEMÓRIA
    # --------------------------------------------------------

    def on_boss_defeated(self, enemy: Enemy):
        self.audio.play("boss_death")
        boss_id = getattr(enemy, "boss_id", None) or "guardiao_primeira_ruptura"
        memory = self.player_state.veil_memory.get(boss_id)
        memory.register_encounter(self.telemetry, player_died=False)
        self.player_state.progression.bosses_derrotados.add(boss_id)
        reward_boss_materials(self.player_state, boss_id)
        self.campaign.record(CampaignEvent.BOSS_DEFEATED, target_id=boss_id)
        add_metric(self.player_state, "bosses", 1)

        if boss_id == FINAL_BOSS_ID:
            record_final_boss_defeat(self.player_state)
            self.ending_offers = eligible_endings(self.player_state)
            self.offer_mode = "ending" if self.ending_offers else None
            self.queue_banner("O VÉU CEDEU", "O fim agora depende da sua escolha.", PURPLE)
        elif boss_id == ECHO_BOSS_ID:
            record_echo_boss_defeat(self.player_state)
            self.queue_banner("ECO SUPERADO", "O Véu não pode mais imitar tudo que você é.", CYAN)

        self.process_campaign_rewards()
        self.autosave.request(AutosaveReason.BOSS_DERROTADO)
        boss_name = BOSSES.get(boss_id).nome if boss_id in BOSSES else boss_id
        self.queue_banner("MEMÓRIA QUEBRADA", f"{boss_name}: memória {memory.rank().value}", GREEN)
        self.evaluate_unlocks()

    def register_death_memory(self):
        guardians = [e for e in self.enemies if e.kind == "guardian" and not e.dead]
        if guardians:
            boss_enemy = guardians[0]
            boss_id = getattr(boss_enemy, "boss_id", None) or "guardiao_primeira_ruptura"
            memory = self.player_state.veil_memory.get(boss_id)
            memory.register_encounter(self.telemetry, player_died=True)

        superiors = [
            e for e in self.enemies
            if not e.dead and getattr(e, "creature_tier", "") == CreatureTier.SUPERIOR.value
        ]
        if superiors:
            culprit = min(
                superiors,
                key=lambda e: e.pos.distance_squared_to(self.player.pos),
            )
            creature_id = getattr(culprit, "creature_id", creature_id_for_archetype(culprit.kind))
            mutation_ids = list(getattr(culprit, "mutation_ids", []))
            record_death_to(self.player_state, creature_id, mutation_ids)
            memory_id = getattr(culprit, "memory_id", creature_id)
            self.player_state.veil_memory.get(memory_id).register_encounter(
                self.telemetry,
                player_died=True,
            )

        if guardians or superiors:
            self.autosave.request(AutosaveReason.CHECKPOINT)

    # --------------------------------------------------------
    # BESTIÁRIO / SUPERIORES
    # --------------------------------------------------------

    def on_enemy_killed(self, enemy: Enemy):
        creature_id = getattr(enemy, "creature_id", creature_id_for_archetype(enemy.kind))
        mutation_ids = list(getattr(enemy, "mutation_ids", []))
        superior = getattr(enemy, "creature_tier", "") == CreatureTier.SUPERIOR.value
        add_metric(self.player_state, "kills", 1)
        if superior:
            add_metric(self.player_state, "superiors", 1)
        before, after = record_kill(
            self.player_state,
            creature_id,
            mutation_ids=mutation_ids,
            superior=superior,
            superior_name=getattr(enemy, "superior_name", None),
        )
        if superior:
            traits = roll_spawn_traits(creature_id, self.wave, force_superior=True)
            traits.mutation_ids = mutation_ids
            traits.superior_name = getattr(enemy, "superior_name", None)
            record_superior_history(self.player_state, traits, defeated=True)
            memory_id = getattr(enemy, "memory_id", superior_memory_id(traits))
            self.player_state.veil_memory.get(memory_id).register_encounter(
                self.telemetry,
                player_died=False,
            )
            self.autosave.request(AutosaveReason.DESBLOQUEIO_IMPORTANTE)
        if before != after:
            self.queue_banner(
                "CONHECIMENTO AMPLIADO",
                f"{CREATURES[creature_id].nome}: {after.value}.",
                CYAN,
            )

    # --------------------------------------------------------
    # EQUIPAMENTOS / DESBLOQUEIOS
    # --------------------------------------------------------

    def try_equipment_drop(self, enemy: Enemy):
        elite = enemy.kind in ("tank", "hunter")
        boss = enemy.kind == "guardian"
        luck = min(0.75, self.player_state.stats.nivel * 0.018 + len(self.player_state.active_rifts.active_ids) * 0.025)
        item = roll_equipment_drop(self.player_state, elite=elite, boss=boss, luck=luck)
        if item is None:
            return

        self.player_state.inventory.append(make_inventory_item(item.id, source=enemy.kind))
        if item.raridade in (Rarity.LENDARIA, Rarity.MITICA, Rarity.CORROMPIDA):
            self.audio.play("ui_legendary_drop")
        elif item.raridade in (Rarity.RARA, Rarity.EPICA):
            self.audio.play("ui_rare_drop")
        else:
            self.audio.play("ui_confirm")
        self.campaign.record(CampaignEvent.EQUIPMENT_COLLECTED, target_id=item.id)
        self.process_campaign_rewards()
        self.queue_banner(item.raridade.value.upper(), f"Equipamento obtido: {item.nome}", RARITY_COLORS[item.raridade])
        self.autosave.request(AutosaveReason.ITEM_IMPORTANTE)
        self.evaluate_unlocks()

    def equip_inventory_index(self, index: int):
        ids = inventory_equipment_ids(self.player_state)
        if index < 0 or index >= len(ids):
            self.inventory_message = "Sem item neste espaço."
            return

        item_id = ids[index]
        ok, message = equip_item(self.player_state, item_id)
        self.inventory_message = message
        if ok:
            self.player.refresh_from_state()
            self.autosave.request(AutosaveReason.ITEM_IMPORTANTE)

    def evaluate_unlocks(self):
        unlocked = evaluate_class_unlocks(self.player_state)
        for class_id in unlocked:
            definition = CLASS_REGISTRY[class_id]
            self.campaign.record(CampaignEvent.CLASS_UNLOCKED, target_id=class_id)
            self.process_campaign_rewards()
            self.queue_banner("NOVA CLASSE", f"{definition.nome} desbloqueado para novos personagens.", GREEN)
            self.autosave.request(AutosaveReason.DESBLOQUEIO_IMPORTANTE)

    def play_skill_audio(self, skill_id: str):
        skill = SKILL_REGISTRY.get(skill_id)
        if skill is None:
            self.audio.play("magic_cast")
            return
        tags = set(skill.tags)
        if "arrow" in tags or "ranged" in tags and self.player.class_id in ("arqueiro", "artifice"):
            self.audio.play("arrow_shot")
        elif "melee" in tags or "slash" in tags or "scythe" in tags:
            self.audio.play("sword_swing")
        else:
            self.audio.play("magic_cast")

    # --------------------------------------------------------
    # VOZ / REAÇÕES
    # --------------------------------------------------------

    def speak_player(
        self,
        text: str,
        priority: int = 1,
        cooldown_key: Optional[str] = None,
        duration: float = 1.45,
    ):
        event = ReactionEvent(
            event_type="player_voice",
            priority=priority,
            line=text,
            cooldown_key=cooldown_key,
            cooldown=2.2 if cooldown_key else 0.0,
        )
        if self.reaction_controller.play(event):
            self.audio.play_voice(text, self.player_state.identity.genero)
            if GAME_SETTINGS.accessibility.subtitles:
                self.speech = SpeechBubble(
                    text=text,
                    speaker=self.player_state.identity.nome,
                    color=self.player.color,
                    life=duration,
                    max_life=duration,
                    priority=priority,
                )

    def speak_enemy(
        self,
        speaker: str,
        text: str,
        color=ORANGE,
        priority=3,
        duration=2.2,
        cooldown_key: Optional[str] = None,
    ):
        if self.speech and not self.speech.dead and self.speech.priority > priority:
            return
        event = ReactionEvent(
            event_type="enemy_voice",
            priority=priority,
            line=text,
            cooldown_key=cooldown_key,
            cooldown=4.5 if cooldown_key else 0.0,
        )
        if not self.reaction_controller.play(event):
            return
        self.audio.play_enemy_voice(text)
        if GAME_SETTINGS.accessibility.subtitles:
            self.speech = SpeechBubble(text, speaker, color, duration, duration, priority)

    # --------------------------------------------------------
    # FEEDBACK
    # --------------------------------------------------------

    def queue_banner(self, title: str, subtitle: str, color=WHITE):
        entry = (str(title), str(subtitle), tuple(color))
        if self.banner_timer > 0:
            # Agora é fila de verdade: avisos de boss, missão, loot e conhecimento
            # não se sobrescrevem no mesmo frame. Limite evita spam infinito.
            if len(self.banner_queue) < 12:
                self.banner_queue.append(entry)
            return
        self.banner_title, self.banner_subtitle, self.banner_color = entry
        self.banner_timer = 3.0

    def _advance_banner_queue(self):
        if self.banner_timer > 0 or not self.banner_queue:
            return
        self.banner_title, self.banner_subtitle, self.banner_color = self.banner_queue.pop(0)
        self.banner_timer = 3.0

    def add_shake(self, power: float, duration: float):
        if GAME_SETTINGS.accessibility.reduced_screen_shake:
            power *= 0.30
            duration *= 0.70
        self.shake_power = max(self.shake_power, power)
        self.shake_timer = max(self.shake_timer, duration)

    def camera_offset(self):
        target = pygame.Vector2()
        if self.shake_timer > 0:
            target = pygame.Vector2(
                random.uniform(-self.shake_power, self.shake_power),
                random.uniform(-self.shake_power, self.shake_power),
            )
        self.camera_shake_offset = self.camera_shake_offset.lerp(target, 0.34)
        return self.camera_shake_offset.copy()

    # --------------------------------------------------------
    # PAUSA / SAÍDA DA RUN
    # --------------------------------------------------------

    def pause_option_rects(self):
        width = 390
        height = 54
        gap = 12
        x = WIDTH // 2 - width // 2
        y0 = HEIGHT // 2 - 90
        return [pygame.Rect(x, y0 + i * (height + gap), width, height) for i in range(4)]

    def abandon_run_to_hub(self):
        # Abandono é diferente de morte: registra a run, limpa Rupturas ativas e retorna
        # ao Refúgio sem incrementar contador de mortes.
        try:
            self.campaign.append_run_history(
                result="abandoned",
                rooms=self.rooms_cleared,
                region_id=self.campaign.current_region().id,
                boss_defeated=False,
                style=self.telemetry.classify_style(),
                active_rifts=list(self.player_state.active_rifts.active_ids),
            )
        except Exception:
            pass
        self.player_state.active_rifts.active_ids.clear()
        try:
            self.campaign.enter_region("refugio_ultima_luz")
        except Exception:
            self.player_state.campaign["current_region"] = "refugio_ultima_luz"
        self.autosave.save_now(self.player_state, AutosaveReason.CHECKPOINT)
        self.return_to_menu_requested = True

    def activate_pause_option(self, index: int):
        index = max(0, min(3, int(index)))
        if index == 0:
            self.paused = False
            self.abandon_confirm = False
            self.audio.play("ui_back")
        elif index == 1:
            if not self.abandon_confirm:
                self.abandon_confirm = True
                self.audio.play("ui_back")
            else:
                self.audio.play("ui_confirm")
                self.abandon_run_to_hub()
        elif index == 2:
            self.audio.play("ui_confirm")
            self.autosave.save_now(self.player_state, AutosaveReason.CHECKPOINT)
            self.return_to_menu_requested = True
        else:
            self.autosave.save_now(self.player_state, AutosaveReason.SAIDA_DO_JOGO)
            self.audio.stop_all()
            pygame.quit()
            raise SystemExit

    # --------------------------------------------------------
    # INPUT
    # --------------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.autosave.save_now(self.player_state, AutosaveReason.SAIDA_DO_JOGO)
            self.audio.stop_all()
            pygame.quit()
            raise SystemExit

        if event.type != pygame.KEYDOWN and event.type != pygame.MOUSEBUTTONDOWN:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F3:
                self.debug = not self.debug
                return

            if self.paused:
                if event.key == pygame.K_ESCAPE:
                    self.paused = False
                    self.abandon_confirm = False
                    self.audio.play("ui_back")
                elif event.key in (pygame.K_UP, pygame.K_w):
                    self.pause_selection = (self.pause_selection - 1) % 4
                    self.abandon_confirm = False
                    self.audio.play("ui_move")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.pause_selection = (self.pause_selection + 1) % 4
                    self.abandon_confirm = False
                    self.audio.play("ui_move")
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.activate_pause_option(self.pause_selection)
                return

            if self.meta_panel is not None:
                panel_close_key = {"codex": pygame.K_c, "quests": pygame.K_j, "hub": pygame.K_h, "settings": pygame.K_o}.get(self.meta_panel)
                if event.key == pygame.K_ESCAPE or (panel_close_key is not None and event.key == panel_close_key):
                    self.audio.play("ui_back")
                    self.meta_panel = None
                    self.meta_message = ""
                    return
                if self.meta_panel == "hub" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                    facility_ids = list(FACILITIES.keys())
                    idx = event.key - pygame.K_1
                    if idx < len(facility_ids):
                        ok, msg = upgrade_facility(self.player_state, facility_ids[idx])
                        self.meta_message = msg
                        self.audio.play("ui_confirm" if ok else "ui_back")
                        if ok:
                            self.autosave.request(AutosaveReason.DESBLOQUEIO_IMPORTANTE)
                    return
                if self.meta_panel == "settings":
                    changed = False
                    if event.key == pygame.K_1:
                        GAME_SETTINGS.accessibility.subtitles = not GAME_SETTINGS.accessibility.subtitles; changed = True
                    elif event.key == pygame.K_2:
                        GAME_SETTINGS.accessibility.reduced_screen_shake = not GAME_SETTINGS.accessibility.reduced_screen_shake; changed = True
                    elif event.key == pygame.K_3:
                        GAME_SETTINGS.accessibility.reduced_flashes = not GAME_SETTINGS.accessibility.reduced_flashes; changed = True
                    elif event.key == pygame.K_4:
                        GAME_SETTINGS.accessibility.damage_numbers = not GAME_SETTINGS.accessibility.damage_numbers; changed = True
                    elif event.key == pygame.K_5:
                        GAME_SETTINGS.accessibility.high_contrast_telegraphs = not GAME_SETTINGS.accessibility.high_contrast_telegraphs; changed = True
                    elif event.key == pygame.K_6:
                        ids = list(DIFFICULTIES.keys())
                        current = ids.index(GAME_SETTINGS.difficulty) if GAME_SETTINGS.difficulty in ids else 0
                        GAME_SETTINGS.difficulty = ids[(current + 1) % len(ids)]
                        self.difficulty = DIFFICULTIES[GAME_SETTINGS.difficulty]
                        changed = True
                    elif event.key == pygame.K_7:
                        GAME_SETTINGS.audio.music = max(0, GAME_SETTINGS.audio.music - 10); changed = True
                    elif event.key == pygame.K_8:
                        GAME_SETTINGS.audio.music = min(100, GAME_SETTINGS.audio.music + 10); changed = True
                    elif event.key == pygame.K_9:
                        GAME_SETTINGS.audio.sfx = 0 if GAME_SETTINGS.audio.sfx > 0 else 85; changed = True
                    if changed:
                        SETTINGS_MANAGER.save(GAME_SETTINGS)
                        self.audio.refresh_volumes()
                        self.audio.play("ui_confirm")
                        self.meta_message = "Configuração salva."
                    return
                return

            if not self.offer_mode and not self.game_over and not self.inventory_open:
                if event.key == pygame.K_c:
                    self.meta_panel = "codex"; self.audio.play("ui_confirm"); return
                if event.key == pygame.K_j:
                    self.meta_panel = "quests"; self.audio.play("ui_confirm"); return
                if event.key == pygame.K_h:
                    self.meta_panel = "hub"; self.audio.play("ui_confirm"); return
                if event.key == pygame.K_o:
                    self.meta_panel = "settings"; self.audio.play("ui_confirm"); return

            if event.key == pygame.K_i and not self.offer_mode and not self.game_over:
                self.inventory_open = not self.inventory_open
                self.inventory_message = ""
                return

            if self.inventory_open:
                if event.key == pygame.K_ESCAPE:
                    self.inventory_open = False
                    return
                number_keys = (
                    pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
                    pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9,
                )
                if event.key in number_keys:
                    index = number_keys.index(event.key)
                    self.equip_inventory_index(index)
                return

            if event.key == pygame.K_ESCAPE:
                if self.offer_mode:
                    return
                self.paused = True
                self.pause_selection = 0
                self.abandon_confirm = False
                self.audio.play("ui_confirm")
                return

            if self.game_over:
                if event.key == pygame.K_r:
                    self.restart_run()
                return

            if self.offer_mode == "skill":
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self.choose_skill_offer(event.key - pygame.K_1)
                return

            if self.offer_mode == "rift":
                if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self.choose_rift_offer(event.key - pygame.K_1)
                return

            if self.offer_mode == "ending":
                ending_keys = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)
                if event.key in ending_keys:
                    self.choose_ending_offer(ending_keys.index(event.key))
                return

            if self.paused:
                return

            if event.key == pygame.K_SPACE:
                self.player.dash(self)
            elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.player.start_parry(self)
            elif event.key in (pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_f):
                skill_keys = (pygame.K_q, pygame.K_e, pygame.K_r, pygame.K_f)
                self.player.use_skill_slot(skill_keys.index(event.key), self)
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                self.player.use_skill_slot(event.key - pygame.K_1, self)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.paused:
                if event.button == 1:
                    for idx, rect in enumerate(self.pause_option_rects()):
                        if rect.collidepoint(event.pos):
                            self.pause_selection = idx
                            self.activate_pause_option(idx)
                            return
                return
            if self.game_over or self.offer_mode or self.inventory_open or self.meta_panel:
                return
            if event.button == 1:
                self.player.basic_attack(self)
            elif event.button == 3:
                self.player.use_secondary(self)

    # --------------------------------------------------------
    # UPDATE FIXO
    # --------------------------------------------------------

    def fixed_update(self, dt: float):
        self.reaction_controller.update(dt)
        self.audio.update_game(
            dt,
            region_id=self.campaign.current_region().id,
            enemies=self.enemies,
            ending=(self.offer_mode == "ending"),
        )

        if self.speech:
            self.speech.update(dt)
            if self.speech.dead:
                self.speech = None

        if self.banner_timer > 0:
            self.banner_timer = max(0.0, self.banner_timer - dt)
        self._advance_banner_queue()
        if self.transition_alpha > 0:
            self.transition_alpha = max(0.0, self.transition_alpha - dt * 430.0)

        if self.shake_timer > 0:
            self.shake_timer -= dt
            if self.shake_timer <= 0:
                self.shake_power = 0

        for skill_id in list(self.skill_cooldowns.keys()):
            self.skill_cooldowns[skill_id] = max(0.0, self.skill_cooldowns[skill_id] - dt)

        for collection in (self.particles, self.floating_texts, self.slashes):
            for item in collection:
                item.update(dt)

        self.particles = [x for x in self.particles if not x.dead]
        self.floating_texts = [x for x in self.floating_texts if not x.dead]
        self.slashes = [x for x in self.slashes if not x.dead]
        self.enforce_runtime_budgets()

        if self.paused or self.game_over or self.offer_mode or self.inventory_open or self.meta_panel:
            self.autosave.update(self.player_state, safe_to_save=True)
            return

        if self.hit_stop > 0:
            self.hit_stop -= dt
            return

        self.telemetry.tempo_combate += dt
        self.player.update(dt, self)

        nearest = self.nearest_enemy(self.player.pos)
        if nearest:
            self.telemetry.register_distance_sample(nearest.pos.distance_to(self.player.pos))

        # Segurar clique esquerdo.
        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0]:
            self.player.basic_attack(self)

        # Boss fala ao lembrar do jogador.
        if not self.boss_spawn_line_shown:
            bosses = [e for e in self.enemies if e.kind == "guardian" and not e.dead]
            if bosses:
                boss_enemy = bosses[0]
                boss_id = getattr(boss_enemy, "boss_id", None) or "guardiao_primeira_ruptura"
                memory = self.player_state.veil_memory.get(boss_id)
                line = memory.contextual_line(self.player_state.identity.nome)
                if line:
                    boss_name = BOSSES[boss_id].nome if boss_id in BOSSES else "Guardião"
                    self.speak_enemy(boss_name, line, ORANGE, priority=4, duration=2.8)
                self.boss_spawn_line_shown = True

        for enemy in self.enemies:
            enemy.update(dt, self)

        for projectile in self.projectiles:
            projectile.update(dt, self)
            self.resolve_projectile_collision(projectile)

        for effect in self.area_effects:
            # burst mágico especial é um efeito de detonação única.
            if effect.kind == "magic_burst":
                effect.delay -= dt
                if effect.delay <= 0 and not effect.triggered:
                    effect.triggered = True
                    for enemy in self.enemies:
                        if enemy.pos.distance_to(effect.pos) < effect.radius + enemy.radius:
                            enemy.take_damage(effect.damage, self, critical=True)
                    for _ in range(28):
                        self.particles.append(Particle.burst(effect.pos, CYAN, 100, 340, 0.5, 7))
                    self.add_shake(12, 0.18)
                    effect.dead = True
            else:
                effect.update(dt, self)

        for death_visual in self.enemy_deaths:
            death_visual.update(dt)
        self.enemy_deaths = [d for d in self.enemy_deaths if not d.dead]

        self.projectiles = [p for p in self.projectiles if not p.dead]
        self.area_effects = [e for e in self.area_effects if not e.dead]
        self.enemies = [e for e in self.enemies if not e.dead]
        self.enforce_runtime_budgets()

        self.resolve_heals()

        if self.player.hp <= 0 and not self.game_over:
            self.game_over = True
            self.register_death_memory()
            self.campaign.record(CampaignEvent.PLAYER_DIED)
            add_metric(self.player_state, "deaths", 1)
            self.campaign.append_run_history(
                result="death",
                rooms=self.rooms_cleared,
                region_id=self.campaign.current_region().id,
                boss_defeated="guardiao_primeira_ruptura" in self.player_state.progression.bosses_derrotados,
                style=self.telemetry.classify_style(),
                active_rifts=self.player_state.active_rifts.active_ids,
            )
            self.autosave.save_now(self.player_state, AutosaveReason.CHECKPOINT)

        if not self.enemies and not self.game_over and self.offer_mode is None:
            self.rooms_cleared += 1
            self.campaign.record(CampaignEvent.ROOM_CLEARED, amount=1)
            add_metric(self.player_state, "rooms_cleared", 1)
            trial_finished, _trial_modifiers = progress_trial_room(self.player_state)
            if trial_finished:
                self.queue_banner("PROVAÇÃO CONCLUÍDA", "Ecos do Véu foram conquistados.", CYAN)
            if self.player_state.active_rifts.active_ids:
                reward_rift_materials(
                    self.player_state,
                    self.player_state.active_rifts.active_ids[-1],
                    elite=(self.wave % 5 == 0),
                )
            self.process_campaign_rewards()
            # Primeiro resolve level-ups. Depois escolha de Ruptura.
            if self.pending_level_ups > 0:
                self.open_skill_offer()
            else:
                self.open_rift_offer()

        self.autosave.update(self.player_state, safe_to_save=True)

    def resolve_projectile_collision(self, projectile: Projectile):
        if projectile.dead:
            return

        if projectile.owner == "player":
            for enemy in self.enemies:
                if enemy.dead or enemy.uid in projectile.hit_ids:
                    continue
                if circle_collision(projectile.pos, projectile.radius, enemy.pos, enemy.radius):
                    element, applied_statuses = elemental_payload_for_skill(projectile.skill_id)
                    enemy.take_damage(
                        projectile.damage,
                        self,
                        knockback=normalize(projectile.vel) * 10,
                        critical=False,
                        element=element,
                        applied_statuses=applied_statuses,
                    )
                    if projectile.skill_id in ("arrow", "burst_arrow", "ricochet"):
                        self.audio.play("arrow_hit")
                    elif element == Element.FOGO:
                        self.audio.play("fire_impact")
                    elif element == Element.GELO:
                        self.audio.play("ice_break")
                    elif element == Element.RAIO:
                        self.audio.play("lightning_impact")
                    elif element == Element.VAZIO:
                        self.audio.play("void_impact")
                    elif element in (Element.ARCANO, Element.TEMPORAL, Element.SOMBRA):
                        self.audio.play("arcane_impact")
                    projectile.hit_ids.add(enemy.uid)

                    if projectile.bleed_damage > 0:
                        enemy.apply_bleed(projectile.bleed_damage)

                    # Tiro Ricochete: uma chance de gerar novo disparo para outro alvo.
                    if (
                        projectile.skill_id in ("arrow", "burst_arrow")
                        and "tiro_ricochete" in self.player_state.owned_skills
                        and random.random() < 0.35
                    ):
                        candidates = [
                            e for e in self.enemies
                            if not e.dead and e.uid != enemy.uid and e.uid not in projectile.hit_ids
                            and e.pos.distance_to(enemy.pos) < 260
                        ]
                        if candidates:
                            target = min(candidates, key=lambda e: e.pos.distance_squared_to(enemy.pos))
                            direction = normalize(target.pos - enemy.pos)
                            self.projectiles.append(
                                Projectile(
                                    enemy.pos.copy(),
                                    direction * 620,
                                    projectile.damage * 0.72,
                                    YELLOW,
                                    "player",
                                    radius=5,
                                    life=0.8,
                                    skill_id="ricochet",
                                )
                            )

                    if projectile.explosion_radius > 0:
                        projectile.explode(self)

                    if projectile.pierce > 0:
                        projectile.pierce -= 1
                    else:
                        projectile.dead = True
                        break

        else:
            if circle_collision(projectile.pos, projectile.radius, self.player.pos, self.player.radius):
                if self.player.parry_window > 0 and self.player.class_id in ("guerreiro", "duelista"):
                    self.player.parry_window = 0
                    self.telemetry.parries += 1
                    self.audio.play("parry")
                    projectile.owner = "player"
                    projectile.vel *= -1.32
                    projectile.damage *= 1.55
                    projectile.color = CYAN
                    self.add_shake(12, 0.17)
                    self.hit_stop = max(self.hit_stop, 0.055)
                    self.speak_player("DEVOLVIDO!", priority=3, cooldown_key="reflect")
                else:
                    self.player.take_damage(projectile.damage, self)
                    projectile.dead = True

    def resolve_heals(self):
        for heal in self.heals[:]:
            if self.player.pos.distance_to(heal) < 30:
                self.player.heal(28)
                self.audio.play("heal")
                self.telemetry.curas_usadas += 1
                self.heals.remove(heal)

    def restart_run(self):
        # Mantém progresso persistente e reinicia apenas a expedição.
        self.player_state.active_rifts = ActiveRiftState()
        self.player = PlayerAvatar(self.player_state)
        self.enemies.clear()
        self.projectiles.clear()
        self.area_effects.clear()
        self.heals.clear()
        self.particles.clear()
        self.floating_texts.clear()
        self.slashes.clear()
        self.wave = 0
        self.rooms_cleared = 0
        self.game_over = False
        self.offer_mode = None
        self.telemetry = CombatTelemetry()
        self.skill_cooldowns.clear()
        self.spawn_next_room()

    # --------------------------------------------------------
    # DRAW
    # --------------------------------------------------------

    def draw_world(self, surface, offset=None):
        if offset is None:
            offset = self.current_camera_offset
        region_id = self.campaign.current_region().id
        boss_active = any((enemy.boss_id is not None) or enemy.kind == "guardian" for enemy in self.enemies if not enemy.dead)
        rift_count = len(self.player_state.active_rifts.active_ids)
        now_s = pygame.time.get_ticks() / 1000.0

        # Cenário 0.9.3: cada região possui chão, bordas, props, partículas e
        # arena de boss próprios. A colisão continua separada da arte.
        self.environment.draw_base(
            surface, ROOM, region_id, self.wave, rift_count, boss_active, now_s, offset
        )

        mods = self.player_state.active_rifts.cumulative_modifiers()

        for heal in self.heals:
            p = heal + offset
            pygame.draw.circle(surface, GREEN, p, 11)
            pygame.draw.line(surface, WHITE, p + (-5, 0), p + (5, 0), 3)
            pygame.draw.line(surface, WHITE, p + (0, -5), p + (0, 5), 3)

        for effect in self.area_effects:
            effect.draw(surface, offset)
        for projectile in self.projectiles:
            projectile.draw(surface, offset)
        for slash in self.slashes:
            slash.draw(surface, offset)
        for death_visual in self.enemy_deaths:
            death_visual.draw(surface, offset)
        for enemy in self.enemies:
            enemy.draw(surface, offset)
        self.player.draw(surface, offset)
        for particle in self.particles:
            particle.draw(surface, offset)
        for text in self.floating_texts:
            text.draw(surface, offset)

        self.environment.draw_foreground(surface, ROOM, region_id, now_s, offset, self.player.pos)

        # Névoa do Vazio por cima do mundo, abaixo da UI.
        visibility = mods["visibility_multiplier"]
        if visibility < 0.95:
            alpha = int((1.0 - visibility) * 155)
            fog = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fog.fill((6, 3, 12, alpha))
            pygame.draw.circle(fog, (0, 0, 0, 0), self.player.pos + offset, int(310 * visibility + 120))
            surface.blit(fog, (0, 0))

    def draw_hud(self, surface):
        state = self.player_state
        p = self.player
        class_def = state.class_definition()

        top = pygame.Rect(0, 0, WIDTH, 62)
        pygame.draw.rect(surface, (8, 10, 17), top)
        pygame.draw.line(surface, PURPLE, (18, 60), (WIDTH - 18, 60), 2)
        pygame.draw.line(surface, (50, 55, 78), (18, 61), (WIDTH - 18, 61), 1)

        pygame.draw.polygon(surface, PURPLE, [(22, 11), (29, 20), (22, 29), (15, 20)], 2)
        draw_text(surface, f"RUPTURA {self.wave}", (42, 14), PURPLE, FONT_MEDIUM)
        draw_text(surface, class_def.nome, (210, 20), p.color, FONT)
        draw_text(surface, f"Nv. {state.stats.nivel}", (380, 20), WHITE, FONT)
        draw_text(surface, f"Salas: {self.rooms_cleared}", (475, 20), GRAY, FONT_SMALL)
        draw_text(surface, chapter_title(self.campaign.chapter), (600, 20), DARK_GRAY, FONT_TINY)

        live_bosses = [e for e in self.enemies if e.kind == "guardian" and not e.dead]
        memory_boss_id = (getattr(live_bosses[0], "boss_id", None) if live_bosses else None) or self.next_story_boss_id()
        memory = state.veil_memory.get(memory_boss_id)
        memory_name = BOSSES[memory_boss_id].nome if memory_boss_id in BOSSES else "Boss"
        draw_text(
            surface,
            f"Memória — {memory_name}: {memory.rank().value}",
            (WIDTH - 390, 20),
            ORANGE if memory.rank() != MemoryRank.DESCONHECIDO else GRAY,
            FONT_TINY,
        )

        gear_ids = [x for x in (state.equipment.arma, state.equipment.armadura) if x]
        gear_label = " | ".join(EQUIPMENT_REGISTRY[x].nome for x in gear_ids if x in EQUIPMENT_REGISTRY)
        draw_text(surface, f"I: Equipamentos{(' | ' + gear_label) if gear_label else ''}", (24, 50), GRAY, FONT_TINY)

        hud_panel = pygame.Rect(14, HEIGHT - 82, WIDTH - 28, 70)
        pygame.draw.rect(surface, (7, 9, 16), hud_panel, border_radius=12)
        pygame.draw.rect(surface, (47, 53, 74), hud_panel, 1, border_radius=12)
        pygame.draw.line(surface, PURPLE, (hud_panel.x + 14, hud_panel.y + 2), (hud_panel.x + 145, hud_panel.y + 2), 2)

        # Vida / recurso / XP
        draw_bar(surface, pygame.Rect(24, HEIGHT - 44, 270, 16), p.hp, p.max_hp, RED)
        draw_text(surface, f"HP {int(p.hp)}/{p.max_hp}", (30, HEIGHT - 65), WHITE, FONT_TINY)

        resource_color = ORANGE if p.class_id == "guerreiro" else (RED if p.class_id == "rasgado" else CYAN)
        draw_bar(
            surface,
            pygame.Rect(315, HEIGHT - 44, 235, 16),
            p.resource,
            p.resource_max,
            resource_color,
        )
        draw_text(
            surface,
            f"{class_def.recurso_nome}: {int(p.resource)}",
            (321, HEIGHT - 65),
            WHITE,
            FONT_TINY,
        )

        draw_bar(
            surface,
            pygame.Rect(570, HEIGHT - 44, 230, 16),
            state.stats.xp,
            self.xp_needed,
            PURPLE,
        )
        draw_text(
            surface,
            f"XP {state.stats.xp}/{self.xp_needed}",
            (576, HEIGHT - 65),
            WHITE,
            FONT_TINY,
        )

        # Skills
        start_x = 820
        for i in range(4):
            rect = pygame.Rect(start_x + i * 105, HEIGHT - 67, 95, 48)
            pygame.draw.rect(surface, PANEL, rect, border_radius=7)
            if i < len(p.active_slots):
                skill_id = p.active_slots[i]
                skill = SKILL_REGISTRY[skill_id]
                color = RARITY_COLORS[skill.raridade]
                pygame.draw.rect(surface, color, rect, 2, border_radius=7)
                skill_key = ("Q", "E", "R", "F")[i]
                draw_text(surface, f"{skill_key}/{i + 1}", (rect.x + 7, rect.y + 5), color, FONT_TINY)
                draw_wrapped_text(
                    surface,
                    skill.nome,
                    pygame.Rect(rect.x + 22, rect.y + 4, rect.width - 26, 29),
                    WHITE,
                    FONT_TINY,
                    0,
                )
                cd = self.skill_cooldowns.get(skill_id, 0.0)
                if cd > 0:
                    overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 135))
                    surface.blit(overlay, rect.topleft)
                    draw_text(surface, f"{cd:.1f}", rect.center, WHITE, FONT_SMALL, True)
            else:
                pygame.draw.rect(surface, DARK_GRAY, rect, 1, border_radius=7)
                draw_text(surface, ("Q", "E", "R", "F")[i], rect.center, DARK_GRAY, FONT_SMALL, True)

        if p.pending_cast:
            skill = SKILL_REGISTRY[p.pending_cast.skill_id]
            draw_text(
                surface,
                f"Conjurando: {skill.nome}",
                (WIDTH // 2, 82),
                RARITY_COLORS[skill.raridade],
                FONT_SMALL,
                True,
            )

        if self.debug:
            fps = clock.get_fps()
            diag = self.diagnostics.summary()
            lines = [
                (f"FPS render: {fps:.1f} | frame médio: {diag['avg_frame_ms']:.2f} ms | pior: {diag['worst_frame_ms']:.2f} ms", GREEN),
                (f"Lógica: {LOGIC_UPS} Hz | updates/frame: {self.logic_updates_last_frame}", GREEN),
                (f"Entidades E/P/VFX: {len(self.enemies)}/{len(self.projectiles)}/{len(self.particles)} | áreas {len(self.area_effects)}", CYAN),
                (f"Região: {self.campaign.current_region().id} | wave {self.wave} | salas {self.rooms_cleared}", CYAN),
                (f"Estilo: {self.telemetry.classify_style()} | Rupturas: {len(self.player_state.active_rifts.active_ids)}", PURPLE),
                (f"Cache sprites: {len(SPRITE_TRANSFORM_CACHE)}/{SPRITE_TRANSFORM_CACHE_LIMIT} | drops VFX: {sum(diag['dropped_effects'].values())}", YELLOW),
            ]
            for i, (text_line, color_line) in enumerate(lines):
                draw_text(surface, text_line, (12, 72 + i * 17), color_line, FONT_TINY)

    def draw_offer(self, surface):
        if self.offer_mode is None:
            return

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        surface.blit(overlay, (0, 0))

        if self.offer_mode == "skill":
            draw_text(surface, "ESCOLHA UMA HABILIDADE", (WIDTH // 2, 95), WHITE, FONT_BIG, True)
            draw_text(
                surface,
                "Raridade muda poder e, em alguns casos, a própria mecânica.",
                (WIDTH // 2, 145),
                GRAY,
                FONT_SMALL,
                True,
            )

            cards = self.offer_card_rects(len(self.skill_offers))
            for i, (skill, rect) in enumerate(zip(self.skill_offers, cards)):
                color = RARITY_COLORS[skill.raridade]
                pygame.draw.rect(surface, PANEL, rect, border_radius=12)
                pygame.draw.rect(surface, color, rect, 3, border_radius=12)
                draw_text(surface, f"{i + 1}", (rect.x + 16, rect.y + 14), color, FONT_MEDIUM)
                draw_text(surface, skill.raridade.value.upper(), (rect.centerx, rect.y + 24), color, FONT_SMALL, True)
                draw_text(surface, skill.nome, (rect.centerx, rect.y + 62), WHITE, FONT_MEDIUM, True)
                draw_wrapped_text(
                    surface,
                    skill.descricao,
                    pygame.Rect(rect.x + 22, rect.y + 105, rect.width - 44, 95),
                    WHITE,
                    FONT_SMALL,
                )
                draw_text(
                    surface,
                    f"Tipo: {skill.categoria.value}",
                    (rect.x + 22, rect.bottom - 60),
                    GRAY,
                    FONT_TINY,
                )
                if skill.corrupted:
                    draw_text(surface, "PODER COM PREÇO", (rect.centerx, rect.bottom - 30), RED, FONT_SMALL, True)
                elif skill.allowed_classes:
                    draw_text(surface, "EXCLUSIVA / RESTRITA", (rect.centerx, rect.bottom - 30), color, FONT_TINY, True)

        elif self.offer_mode == "rift":
            draw_text(surface, "A RUPTURA EXIGE UMA ESCOLHA", (WIDTH // 2, 95), PURPLE, FONT_BIG, True)
            draw_text(surface, "Mais risco. Mais poder.", (WIDTH // 2, 145), GRAY, FONT, True)

            cards = self.offer_card_rects(len(self.rift_offers))
            for i, (rift_id, rect) in enumerate(zip(self.rift_offers, cards)):
                rift = RIFT_REGISTRY[rift_id]
                pygame.draw.rect(surface, PANEL, rect, border_radius=12)
                pygame.draw.rect(surface, PURPLE, rect, 3, border_radius=12)
                draw_text(surface, f"{i + 1}", (rect.x + 16, rect.y + 14), PURPLE, FONT_MEDIUM)
                draw_text(surface, rift.nome, (rect.centerx, rect.y + 58), PURPLE, FONT_MEDIUM, True)
                draw_wrapped_text(
                    surface,
                    rift.descricao,
                    pygame.Rect(rect.x + 22, rect.y + 105, rect.width - 44, 90),
                    WHITE,
                    FONT_SMALL,
                )
                draw_text(
                    surface,
                    f"Perigo: {'◆' * rift.danger}",
                    (rect.centerx, rect.bottom - 70),
                    ORANGE,
                    FONT_SMALL,
                    True,
                )
                draw_text(
                    surface,
                    f"Recompensas x{rift.reward_multiplier:.2f}",
                    (rect.centerx, rect.bottom - 38),
                    GREEN,
                    FONT_SMALL,
                    True,
                )

        elif self.offer_mode == "ending":
            draw_text(surface, "O QUE SERÁ DO VÉU?", (WIDTH // 2, 82), CYAN, FONT_BIG, True)
            draw_text(surface, "Sua campanha, reputação e corrupção determinaram estas possibilidades.",
                      (WIDTH // 2, 132), GRAY, FONT_SMALL, True)
            cards = self.offer_card_rects(len(self.ending_offers))
            for i, (ending, rect) in enumerate(zip(self.ending_offers, cards)):
                accent = RED if ending.tone == "corrupted" else CYAN if ending.tone == "mysterious" else PURPLE
                pygame.draw.rect(surface, PANEL, rect, border_radius=12)
                pygame.draw.rect(surface, accent, rect, 3, border_radius=12)
                draw_text(surface, f"{i + 1}", (rect.x + 16, rect.y + 14), accent, FONT_MEDIUM)
                draw_text(surface, ending.nome, (rect.centerx, rect.y + 58), accent, FONT_MEDIUM, True)
                draw_wrapped_text(surface, ending.descricao,
                                  pygame.Rect(rect.x + 22, rect.y + 105, rect.width - 44, 90),
                                  WHITE, FONT_SMALL)
                draw_text(surface, "FINAL", (rect.centerx, rect.bottom - 38), accent, FONT_SMALL, True)

    @staticmethod
    def offer_card_rects(count: int):
        width = 330
        height = 390
        gap = 28
        total = count * width + (count - 1) * gap
        start = WIDTH // 2 - total // 2
        return [pygame.Rect(start + i * (width + gap), 205, width, height) for i in range(count)]

    def draw_inventory(self, surface):
        if not self.inventory_open:
            return

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 215))
        surface.blit(overlay, (0, 0))

        draw_text(surface, "EQUIPAMENTOS", (WIDTH // 2, 62), WHITE, FONT_BIG, True)
        draw_text(surface, "1–9 equipa | I ou ESC fecha", (WIDTH // 2, 108), GRAY, FONT_SMALL, True)

        eq = self.player_state.equipment
        equipped = [
            ("Arma", eq.arma),
            ("Armadura", eq.armadura),
            ("Acessório 1", eq.acessorio_1),
            ("Acessório 2", eq.acessorio_2),
        ]

        y = 145
        for label, item_id in equipped:
            name = EQUIPMENT_REGISTRY[item_id].nome if item_id in EQUIPMENT_REGISTRY else "—"
            draw_text(surface, f"{label}: {name}", (80, y), CYAN if item_id else GRAY, FONT_SMALL)
            y += 28

        bonuses = active_set_bonuses(self.player_state)
        if bonuses:
            draw_text(surface, "SINERGIAS ATIVAS", (80, y + 10), YELLOW, FONT_SMALL)
            y += 38
            for item_set, bonus in bonuses[:4]:
                draw_text(surface, f"{item_set.nome} ({bonus.pieces}) — {bonus.nome}", (95, y), GREEN, FONT_TINY)
                y += 22

        ids = inventory_equipment_ids(self.player_state)
        start_x = 520
        draw_text(surface, f"INVENTÁRIO ({len(ids)})", (start_x, 145), WHITE, FONT_MEDIUM)

        for i, item_id in enumerate(ids[:9]):
            item = EQUIPMENT_REGISTRY[item_id]
            color = RARITY_COLORS[item.raridade]
            rect = pygame.Rect(start_x, 195 + i * 48, 675, 40)
            pygame.draw.rect(surface, PANEL, rect, border_radius=6)
            pygame.draw.rect(surface, color, rect, 2, border_radius=6)
            draw_text(surface, f"{i + 1}. {item.nome}", (rect.x + 12, rect.y + 8), color, FONT_SMALL)
            draw_text(surface, item.slot.value.upper(), (rect.right - 135, rect.y + 10), GRAY, FONT_TINY)

        if len(ids) > 9:
            draw_text(surface, f"+ {len(ids) - 9} itens (paginação entra depois)", (start_x, 640), GRAY, FONT_TINY)

        if self.inventory_message:
            draw_text(surface, self.inventory_message, (WIDTH // 2, HEIGHT - 42), YELLOW, FONT_SMALL, True)

    def draw_meta_panel(self, surface):
        if self.meta_panel is None:
            return
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 222))
        surface.blit(overlay, (0, 0))
        box = pygame.Rect(55, 52, WIDTH - 110, HEIGHT - 104)
        pygame.draw.rect(surface, BG_2, box, border_radius=12)
        pygame.draw.rect(surface, PURPLE, box, 2, border_radius=12)

        if self.meta_panel == "codex":
            draw_text(surface, "CÓDICE / BESTIÁRIO", (85, 76), CYAN, FONT_BIG)
            draw_text(surface, "C ou ESC fecha", (WIDTH - 240, 88), GRAY, FONT_TINY)
            tutorial_root = self.player_state.campaign.get("tutorial", {})
            unlocked = set(tutorial_root.get("codex_unlocked", []))
            y = 145
            for entry in CODEX.values():
                color = WHITE if entry.id in unlocked else DARK_GRAY
                label = entry.title if entry.id in unlocked else "???"
                draw_text(surface, f"[{entry.category}] {label}", (90, y), color, FONT_SMALL)
                if entry.id in unlocked:
                    draw_wrapped_text(surface, entry.text, pygame.Rect(310, y - 2, 430, 38), GRAY, FONT_TINY)
                y += 46
                if y > HEIGHT - 110:
                    break
            bx = 785
            draw_text(surface, "CRIATURAS", (bx, 145), YELLOW, FONT_MEDIUM)
            by = 190
            for creature_id, creature in list(CREATURES.items())[:10]:
                rank = knowledge_rank(self.player_state, creature_id)
                draw_text(surface, f"{creature.nome}: {rank.value}", (bx, by), WHITE if rank.value != "Desconhecido" else DARK_GRAY, FONT_TINY)
                by += 28

        elif self.meta_panel == "quests":
            draw_text(surface, "MISSÕES", (85, 76), GREEN, FONT_BIG)
            draw_text(surface, f"Capítulo {self.campaign.chapter}: {chapter_title(self.campaign.chapter)}", (88, 125), PURPLE, FONT_SMALL)
            y = 175
            active = self.campaign.active_quests()
            if not active:
                draw_text(surface, "Nenhuma missão ativa.", (90, y), GRAY, FONT)
            for quest in active[:5]:
                draw_text(surface, quest.nome, (90, y), YELLOW, FONT_MEDIUM)
                y += 34
                for line in self.campaign.quest_progress_text(quest.id):
                    draw_text(surface, line, (112, y), WHITE, FONT_SMALL)
                    y += 26
                y += 18
            draw_text(surface, "J ou ESC fecha", (WIDTH - 240, 88), GRAY, FONT_TINY)

        elif self.meta_panel == "hub":
            draw_text(surface, "REFÚGIO DA ÚLTIMA LUZ", (85, 76), ORANGE, FONT_BIG)
            draw_text(surface, f"Ouro: {gold(self.player_state)}   Ecos: {echoes(self.player_state)}", (90, 130), YELLOW, FONT)
            draw_text(surface, "1–5 tenta melhorar instalação | H ou ESC fecha", (WIDTH - 520, 88), GRAY, FONT_TINY)
            y = 185
            for i, (facility_id, facility) in enumerate(FACILITIES.items(), start=1):
                level = facility_level(self.player_state, facility_id)
                current = facility.levels[level - 1]
                next_text = "MÁXIMO" if level >= len(facility.levels) else f"Próx.: {facility.levels[level].gold_cost} ouro"
                draw_text(surface, f"{i}. {facility.nome} — Nv.{level}", (90, y), CYAN, FONT_SMALL)
                draw_text(surface, current.effect_text, (115, y + 24), GRAY, FONT_TINY)
                draw_text(surface, next_text, (610, y + 12), GREEN if next_text != "MÁXIMO" else YELLOW, FONT_TINY)
                y += 78
            draw_text(surface, "MATERIAIS", (830, 175), WHITE, FONT_MEDIUM)
            my = 220
            for material_id, material in MATERIALS.items():
                draw_text(surface, f"{material.nome}: {material_count(self.player_state, material_id)}", (830, my), GRAY, FONT_TINY)
                my += 27

        elif self.meta_panel == "settings":
            draw_text(surface, "CONFIGURAÇÕES", (85, 76), WHITE, FONT_BIG)
            draw_text(surface, "1–9 altera | O ou ESC fecha", (WIDTH - 300, 88), GRAY, FONT_TINY)
            a = GAME_SETTINGS.accessibility
            au = GAME_SETTINGS.audio
            diff = DIFFICULTIES[GAME_SETTINGS.difficulty]
            rows = [
                ("1", "Legendas", "ON" if a.subtitles else "OFF"),
                ("2", "Screen shake reduzido", "ON" if a.reduced_screen_shake else "OFF"),
                ("3", "Flashes reduzidos", "ON" if a.reduced_flashes else "OFF"),
                ("4", "Números de dano", "ON" if a.damage_numbers else "OFF"),
                ("5", "Telegraphs alto contraste", "ON" if a.high_contrast_telegraphs else "OFF"),
                ("6", "Dificuldade", diff.nome),
                ("7", "Música -10", f"{au.music}%"),
                ("8", "Música +10", f"{au.music}%"),
                ("9", "SFX mute/unmute", f"{au.sfx}%"),
            ]
            y = 170
            for key, label, value in rows:
                rect = pygame.Rect(105, y, WIDTH - 210, 46)
                pygame.draw.rect(surface, PANEL, rect, border_radius=7)
                draw_text(surface, f"{key}. {label}", (130, y + 12), WHITE, FONT_SMALL)
                draw_text(surface, value, (rect.right - 175, y + 12), CYAN, FONT_SMALL)
                y += 55
            draw_wrapped_text(surface, diff.descricao, pygame.Rect(105, y + 8, WIDTH - 210, 70), GRAY, FONT_SMALL)

        if self.meta_message:
            draw_text(surface, self.meta_message, (WIDTH // 2, HEIGHT - 78), YELLOW, FONT_SMALL, True)

    def draw_overlay_states(self, surface):
        if self.banner_timer > 0:
            alpha = int(255 * min(1.0, self.banner_timer / 0.35))
            banner = pygame.Surface((720, 94), pygame.SRCALPHA)
            banner.fill((5, 6, 11, min(220, alpha)))
            pygame.draw.rect(banner, (*self.banner_color, alpha), banner.get_rect(), 2, border_radius=10)
            draw_text(banner, self.banner_title, (360, 24), self.banner_color, FONT_MEDIUM, True)
            draw_text(banner, self.banner_subtitle, (360, 61), WHITE, FONT_SMALL, True)
            surface.blit(banner, (WIDTH // 2 - 360, 95))

        if self.speech:
            self.speech.draw(surface)

        if self.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 205))
            surface.blit(overlay, (0, 0))
            draw_text(surface, "PAUSADO", (WIDTH // 2, HEIGHT // 2 - 160), WHITE, FONT_BIG, True)
            draw_text(surface, "W/S ou ↑/↓ para escolher • ENTER ou clique para confirmar", (WIDTH // 2, HEIGHT // 2 - 116), GRAY, FONT_TINY, True)
            labels = ["CONTINUAR", "ABANDONAR RUN → REFÚGIO", "VOLTAR AO MENU", "SAIR DO JOGO"]
            mouse = pygame.mouse.get_pos()
            for idx, rect in enumerate(self.pause_option_rects()):
                selected = idx == self.pause_selection or rect.collidepoint(mouse)
                pygame.draw.rect(surface, PANEL_HOVER if selected else PANEL, rect, border_radius=9)
                border = CYAN if selected else DARK_GRAY
                pygame.draw.rect(surface, border, rect, 2, border_radius=9)
                text = labels[idx]
                color = RED if idx == 3 else (YELLOW if idx == 1 else WHITE)
                draw_text(surface, text, rect.center, color, FONT_SMALL, True)
            if self.abandon_confirm:
                draw_text(surface, "CONFIRMAR ABANDONO? Selecione ABANDONAR novamente e confirme.", (WIDTH // 2, HEIGHT // 2 + 205), RED, FONT_SMALL, True)
            else:
                draw_text(surface, "ESC retoma imediatamente", (WIDTH // 2, HEIGHT // 2 + 205), GRAY, FONT_TINY, True)

        if self.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 215))
            surface.blit(overlay, (0, 0))
            draw_text(surface, "VOCÊ CAIU NA RUPTURA", (WIDTH // 2, 245), RED, FONT_BIG, True)
            style = self.telemetry.classify_style()
            draw_text(
                surface,
                f"O Véu registrou seu estilo: {style}",
                (WIDTH // 2, 320),
                PURPLE,
                FONT,
                True,
            )
            draw_text(
                surface,
                "Alguns inimigos superiores podem se lembrar disso.",
                (WIDTH // 2, 355),
                WHITE,
                FONT_SMALL,
                True,
            )
            draw_text(surface, "R = nova expedição", (WIDTH // 2, 430), GREEN, FONT, True)

    def draw(self):
        # Um único offset por frame mantém mundo, névoa e mira perfeitamente alinhados.
        self.current_camera_offset = self.camera_offset()
        self.draw_world(screen, self.current_camera_offset)
        if self.transition_alpha > 0:
            fade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            fade.fill((7, 8, 13, int(clamp(self.transition_alpha, 0, 210))))
            screen.blit(fade, (0, 0))

        # Mira visível: mostra exatamente onde ataque/skill será direcionado.
        if not self.paused and not self.game_over and not self.offer_mode:
            target = pygame.Vector2(self.player.aim_target) + self.current_camera_offset
            if target.x < 0 or target.x > WIDTH or target.y < 0 or target.y > HEIGHT:
                target = self.player.pos + self.player.aim_dir * 170 + self.current_camera_offset
            pygame.draw.circle(screen, CYAN, (int(target.x), int(target.y)), 11, 2)
            pygame.draw.line(screen, CYAN, (int(target.x)-16, int(target.y)), (int(target.x)-6, int(target.y)), 2)
            pygame.draw.line(screen, CYAN, (int(target.x)+6, int(target.y)), (int(target.x)+16, int(target.y)), 2)
            pygame.draw.line(screen, CYAN, (int(target.x), int(target.y)-16), (int(target.x), int(target.y)-6), 2)
            pygame.draw.line(screen, CYAN, (int(target.x), int(target.y)+6), (int(target.x), int(target.y)+16), 2)
        self.draw_hud(screen)
        self.draw_offer(screen)
        self.draw_inventory(screen)
        self.draw_meta_panel(screen)
        self.draw_overlay_states(screen)


# ============================================================
# LOOP
# ============================================================

def main():
    profile_manager = ProfileManager(str(SAVE_DIR), slots=3)

    while True:
        frontend = Frontend(profile_manager)
        state = frontend.run()
        active_path = profile_manager.save_path(frontend.selected_slot)
        game = Game(state, save_path=active_path)

        try:
            while True:
                real_dt = min(clock.tick(RENDER_FPS_CAP) / 1000.0, 0.25)

                for event in pygame.event.get():
                    game.handle_event(event)

                if game.return_to_menu_requested:
                    game.audio.stop_all()
                    break

                updates = 0
                for fixed_dt in stepper.consume(real_dt):
                    game.fixed_update(fixed_dt)
                    updates += 1
                game.logic_updates_last_frame = updates
                game.diagnostics.record_frame(real_dt, updates, game.diagnostic_counts())

                game.draw()
                pygame.display.flip()
        except SystemExit:
            raise
        except Exception as exc:
            context = {
                "wave": game.wave,
                "rooms_cleared": game.rooms_cleared,
                "region": game.campaign.current_region().id,
                "class_id": game.player_state.identity.class_id,
                "diagnostics": game.diagnostics.summary(),
            }
            report = write_crash_report(DATA_DIR / "logs", exc, context)
            print(f"\nRIFTWALKER encontrou um erro. Relatório salvo em: {report}\n")
            try:
                game.autosave.save_now(game.player_state, AutosaveReason.CHECKPOINT)
            except Exception:
                pass
            try:
                game.audio.stop_all()
                pygame.quit()
            except Exception:
                pass
            raise


if __name__ == "__main__":
    main()

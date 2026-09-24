"""
RIFTWALKER — CORE SYSTEMS 0.3
=============================

Base de arquitetura para:
- classes expansíveis
- habilidades com raridade
- habilidades exclusivas / universais / corrompidas
- maestria de habilidade
- criação de personagem
- telemetria do estilo de combate
- Memória do Véu
- modificadores de Ruptura
- autosave seguro
- save versionado
- fixed timestep / lógica independente do FPS

Este arquivo foi pensado para ser integrado ao jogo principal em Pygame.
Ele usa apenas a biblioteca padrão do Python para que a lógica fique
independente da renderização.

Projeto: RIFTWALKER
Build de sistemas: 0.3
"""

from __future__ import annotations

import copy
import json
import os
import random
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


# ============================================================
# VERSÃO / CONSTANTES
# ============================================================

SAVE_VERSION = 8
DEFAULT_SAVE_FILE = "save_riftwalker.json"

BASE_STARTING_CLASSES = {
    "guerreiro",
    "mago",
    "arqueiro",
}


# ============================================================
# ENUMS
# ============================================================

class Rarity(str, Enum):
    COMUM = "Comum"
    INCOMUM = "Incomum"
    RARA = "Rara"
    EPICA = "Épica"
    LENDARIA = "Lendária"
    MITICA = "Mítica"
    CORROMPIDA = "Corrompida"


class SkillCategory(str, Enum):
    BASICA = "Básica"
    ATIVA = "Ativa"
    PASSIVA = "Passiva"
    MOBILIDADE = "Mobilidade"
    DEFENSIVA = "Defensiva"
    SUPREMA = "Suprema"
    RUPTURA = "Ruptura"


class DamageType(str, Enum):
    FISICO = "Físico"
    ARCANO = "Arcano"
    FOGO = "Fogo"
    GELO = "Gelo"
    RAIO = "Raio"
    SOMBRA = "Sombra"
    VAZIO = "Vazio"
    SANGRAMENTO = "Sangramento"
    TEMPORAL = "Temporal"
    PURO = "Puro"


class Gender(str, Enum):
    MASCULINO = "Masculino"
    FEMININO = "Feminino"


class AutosaveReason(str, Enum):
    REFUGIO_ENTRADA = "entrada_refugio"
    REFUGIO_SAIDA = "saida_refugio"
    RUPTURA_CONCLUIDA = "ruptura_concluida"
    BOSS_DERROTADO = "boss_derrotado"
    DESBLOQUEIO_IMPORTANTE = "desbloqueio_importante"
    EVENTO_HISTORIA = "evento_historia"
    ITEM_IMPORTANTE = "item_importante"
    SAIDA_DO_JOGO = "saida_do_jogo"
    CHECKPOINT = "checkpoint"


class MemoryRank(str, Enum):
    DESCONHECIDO = "Desconhecido"
    OBSERVADOR = "Observador"
    ADAPTADO = "Adaptado"
    PREDADOR = "Predador"


# ============================================================
# RARIDADE
# ============================================================

@dataclass(frozen=True)
class RarityInfo:
    weight: float
    power_multiplier: float
    display_order: int
    color_name: str


RARITY_INFO: Dict[Rarity, RarityInfo] = {
    Rarity.COMUM: RarityInfo(
        weight=52.0,
        power_multiplier=1.00,
        display_order=1,
        color_name="cinza_claro",
    ),
    Rarity.INCOMUM: RarityInfo(
        weight=25.0,
        power_multiplier=1.10,
        display_order=2,
        color_name="verde",
    ),
    Rarity.RARA: RarityInfo(
        weight=12.0,
        power_multiplier=1.22,
        display_order=3,
        color_name="azul",
    ),
    Rarity.EPICA: RarityInfo(
        weight=6.0,
        power_multiplier=1.38,
        display_order=4,
        color_name="roxo",
    ),
    Rarity.LENDARIA: RarityInfo(
        weight=3.0,
        power_multiplier=1.60,
        display_order=5,
        color_name="dourado",
    ),
    Rarity.MITICA: RarityInfo(
        weight=1.2,
        power_multiplier=1.90,
        display_order=6,
        color_name="ciano_intenso",
    ),
    Rarity.CORROMPIDA: RarityInfo(
        weight=0.8,
        power_multiplier=2.25,
        display_order=7,
        color_name="vermelho_vazio",
    ),
}


# ============================================================
# DEFINIÇÕES DE CLASSE
# ============================================================

@dataclass(frozen=True)
class ClassDefinition:
    id: str
    nome: str
    descricao: str
    recurso_nome: str
    hp_base: int
    recurso_maximo: int
    velocidade_base: float
    dano_base: float
    dificuldade: int
    desbloqueada_inicialmente: bool
    tags: Tuple[str, ...]
    identidade: str
    passiva_inata: str


CLASS_REGISTRY: Dict[str, ClassDefinition] = {}


def register_class(definition: ClassDefinition) -> ClassDefinition:
    if definition.id in CLASS_REGISTRY:
        raise ValueError(f"Classe duplicada: {definition.id}")
    CLASS_REGISTRY[definition.id] = definition
    return definition


register_class(
    ClassDefinition(
        id="guerreiro",
        nome="Guerreiro",
        descricao="Combate corpo a corpo, parry, escudo e pressão constante.",
        recurso_nome="Fadiga",
        hp_base=180,
        recurso_maximo=100,
        velocidade_base=220.0,
        dano_base=34.0,
        dificuldade=2,
        desbloqueada_inicialmente=True,
        tags=("melee", "parry", "tank", "combo"),
        identidade="Domina o espaço curto e transforma ritmo de combate em força.",
        passiva_inata="Décimo Impacto: a cada 10 ataques, o próximo golpe é fortalecido.",
    )
)

register_class(
    ClassDefinition(
        id="mago",
        nome="Mago",
        descricao="Magias elementais, controle de área e domínio de mana.",
        recurso_nome="Mana",
        hp_base=120,
        recurso_maximo=100,
        velocidade_base=230.0,
        dano_base=29.0,
        dificuldade=3,
        desbloqueada_inicialmente=True,
        tags=("ranged", "magic", "elemental", "area"),
        identidade="Troca resistência por controle, explosão e adaptação elemental.",
        passiva_inata="Convergência Arcana: alternar elementos aumenta eficiência mágica.",
    )
)

register_class(
    ClassDefinition(
        id="arqueiro",
        nome="Arqueiro",
        descricao="Precisão, mobilidade, perfuração e domínio de distância.",
        recurso_nome="Energia",
        hp_base=140,
        recurso_maximo=100,
        velocidade_base=245.0,
        dano_base=27.0,
        dificuldade=2,
        desbloqueada_inicialmente=True,
        tags=("ranged", "mobility", "precision", "critical"),
        identidade="Quanto melhor o posicionamento e a precisão, maior a pressão.",
        passiva_inata="Mira Crescente: acertos consecutivos aumentam precisão e crítico.",
    )
)

register_class(
    ClassDefinition(
        id="ceifador",
        nome="Ceifador",
        descricao="Foice, roubo de vida, marcas e execuções.",
        recurso_nome="Essência",
        hp_base=145,
        recurso_maximo=100,
        velocidade_base=235.0,
        dano_base=32.0,
        dificuldade=4,
        desbloqueada_inicialmente=False,
        tags=("melee", "lifesteal", "execute", "shadow"),
        identidade="Transforma inimigos feridos em combustível para continuar lutando.",
        passiva_inata="Último Suspiro: inimigos abaixo de um limite podem ser executados.",
    )
)

register_class(
    ClassDefinition(
        id="rasgado",
        nome="Rasgado",
        descricao="Usa energia da própria Ruptura em troca de corrupção.",
        recurso_nome="Corrupção",
        hp_base=155,
        recurso_maximo=100,
        velocidade_base=228.0,
        dano_base=36.0,
        dificuldade=5,
        desbloqueada_inicialmente=False,
        tags=("corruption", "risk", "void", "hybrid"),
        identidade="Quanto mais perto do limite, maior seu poder e maior o risco.",
        passiva_inata="Fenda Interior: corrupção aumenta dano, mas altera segurança.",
    )
)

register_class(
    ClassDefinition(
        id="cronista",
        nome="Cronista",
        descricao="Manipula ritmo, posição e ecos do tempo.",
        recurso_nome="Fluxo",
        hp_base=125,
        recurso_maximo=100,
        velocidade_base=238.0,
        dano_base=27.0,
        dificuldade=5,
        desbloqueada_inicialmente=False,
        tags=("temporal", "control", "rewind", "utility"),
        identidade="Não vence apenas por dano: vence escolhendo quando cada coisa acontece.",
        passiva_inata="Eco Recente: registra estados curtos que podem ser revisitados.",
    )
)

register_class(
    ClassDefinition(
        id="artifice",
        nome="Artífice",
        descricao="Torretas, minas, drones e dispositivos do Véu.",
        recurso_nome="Carga",
        hp_base=135,
        recurso_maximo=100,
        velocidade_base=225.0,
        dano_base=25.0,
        dificuldade=4,
        desbloqueada_inicialmente=False,
        tags=("deployable", "technology", "trap", "control"),
        identidade="Constrói vantagem no terreno em vez de depender só do ataque direto.",
        passiva_inata="Rede de Dispositivos: engenhocas próximas podem interagir entre si.",
    )
)

register_class(
    ClassDefinition(
        id="duelista",
        nome="Duelista",
        descricao="Mobilidade extrema, contra-ataque e combos de precisão.",
        recurso_nome="Ímpeto",
        hp_base=130,
        recurso_maximo=100,
        velocidade_base=260.0,
        dano_base=31.0,
        dificuldade=4,
        desbloqueada_inicialmente=False,
        tags=("melee", "mobility", "parry", "combo"),
        identidade="Fica mais perigoso quanto mais tempo luta sem ser atingido.",
        passiva_inata="Ritmo Perfeito: esquivas e parries alimentam Ímpeto.",
    )
)

register_class(
    ClassDefinition(
        id="oraculo",
        nome="Oráculo",
        descricao="Marcas, maldições, previsão e explosões atrasadas.",
        recurso_nome="Visão",
        hp_base=118,
        recurso_maximo=100,
        velocidade_base=232.0,
        dano_base=28.0,
        dificuldade=5,
        desbloqueada_inicialmente=False,
        tags=("curse", "mark", "control", "ranged"),
        identidade="Prepara o futuro da luta e faz inimigos pagarem por decisões anteriores.",
        passiva_inata="Presságio: alvos marcados revelam oportunidades especiais.",
    )
)

register_class(
    ClassDefinition(
        id="guardiao_veu",
        nome="Guardião do Véu",
        descricao="Barreiras, controle de ameaça e sobrevivência pesada.",
        recurso_nome="Guarda",
        hp_base=220,
        recurso_maximo=100,
        velocidade_base=205.0,
        dano_base=27.0,
        dificuldade=3,
        desbloqueada_inicialmente=False,
        tags=("tank", "barrier", "control", "defense"),
        identidade="Converte defesa e posicionamento em controle do campo.",
        passiva_inata="Muralha Viva: bloquear dano fortalece a próxima resposta defensiva.",
    )
)


# ============================================================
# HABILIDADES
# ============================================================

@dataclass(frozen=True)
class MasteryStage:
    nivel: int
    nome: str
    usos_necessarios: int
    xp_necessaria: int
    cast_time_multiplier: float = 1.0
    cooldown_multiplier: float = 1.0
    damage_multiplier: float = 1.0
    resource_multiplier: float = 1.0
    remove_incantation: bool = False
    descricao: str = ""


DEFAULT_MASTERY_STAGES: Tuple[MasteryStage, ...] = (
    MasteryStage(
        nivel=1,
        nome="Aprendiz",
        usos_necessarios=0,
        xp_necessaria=0,
        descricao="Execução normal da habilidade.",
    ),
    MasteryStage(
        nivel=2,
        nome="Praticante",
        usos_necessarios=25,
        xp_necessaria=120,
        cast_time_multiplier=0.92,
        cooldown_multiplier=0.97,
        descricao="Movimentos ficam mais naturais.",
    ),
    MasteryStage(
        nivel=3,
        nome="Adepto",
        usos_necessarios=75,
        xp_necessaria=420,
        cast_time_multiplier=0.82,
        cooldown_multiplier=0.93,
        damage_multiplier=1.05,
        descricao="A execução ganha velocidade e confiança.",
    ),
    MasteryStage(
        nivel=4,
        nome="Especialista",
        usos_necessarios=180,
        xp_necessaria=1100,
        cast_time_multiplier=0.68,
        cooldown_multiplier=0.88,
        damage_multiplier=1.10,
        resource_multiplier=0.94,
        descricao="A habilidade passa a exigir menos preparação.",
    ),
    MasteryStage(
        nivel=5,
        nome="Mestre",
        usos_necessarios=400,
        xp_necessaria=2800,
        cast_time_multiplier=0.45,
        cooldown_multiplier=0.82,
        damage_multiplier=1.18,
        resource_multiplier=0.88,
        remove_incantation=True,
        descricao="A técnica foi incorporada ao estilo do personagem.",
    ),
)


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    nome: str
    descricao: str
    raridade: Rarity
    categoria: SkillCategory
    damage_type: DamageType
    base_damage: float
    cooldown: float
    resource_cost: float
    allowed_classes: Tuple[str, ...] = ()
    forbidden_classes: Tuple[str, ...] = ()
    required_tags: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()
    unique: bool = False
    corrupted: bool = False
    mastery_stages: Tuple[MasteryStage, ...] = DEFAULT_MASTERY_STAGES
    voice_lines_male: Tuple[str, ...] = ()
    voice_lines_female: Tuple[str, ...] = ()
    incantations_male: Tuple[str, ...] = ()
    incantations_female: Tuple[str, ...] = ()
    gameplay_notes: str = ""


SKILL_REGISTRY: Dict[str, SkillDefinition] = {}


def register_skill(skill: SkillDefinition) -> SkillDefinition:
    if skill.id in SKILL_REGISTRY:
        raise ValueError(f"Habilidade duplicada: {skill.id}")

    for class_id in skill.allowed_classes:
        if class_id not in CLASS_REGISTRY:
            raise ValueError(
                f"Habilidade {skill.id} referencia classe inexistente: {class_id}"
            )

    SKILL_REGISTRY[skill.id] = skill
    return skill


# ------------------------------------------------------------
# GUERREIRO
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="corte_crescente",
        nome="Corte Crescente",
        descricao="Golpe amplo de espada que empurra inimigos próximos.",
        raridade=Rarity.COMUM,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.FISICO,
        base_damage=38,
        cooldown=1.3,
        resource_cost=13,
        allowed_classes=("guerreiro", "duelista"),
        tags=("melee", "slash", "knockback"),
        voice_lines_male=("ABRA CAMINHO!", "AGORA!", "CORTE!"),
        voice_lines_female=("ABRA CAMINHO!", "AGORA!", "CORTE!"),
        gameplay_notes="Arco frontal largo. Deve usar efeito de corte, nunca projétil genérico.",
    )
)

register_skill(
    SkillDefinition(
        id="muralha_de_aco",
        nome="Muralha de Aço",
        descricao="Assume postura defensiva e fortalece o próximo parry.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.DEFENSIVA,
        damage_type=DamageType.FISICO,
        base_damage=0,
        cooldown=6.5,
        resource_cost=8,
        allowed_classes=("guerreiro", "guardiao_veu"),
        tags=("defense", "parry", "barrier"),
        voice_lines_male=("TENTE PASSAR!", "VENHA!"),
        voice_lines_female=("TENTE PASSAR!", "VENHA!"),
        gameplay_notes="Aumenta janela de parry e dá contra-ataque.",
    )
)

register_skill(
    SkillDefinition(
        id="ruptura_da_lamina",
        nome="Ruptura da Lâmina",
        descricao="O golpe abre uma fenda curta que replica parte do dano.",
        raridade=Rarity.LENDARIA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.VAZIO,
        base_damage=72,
        cooldown=7.0,
        resource_cost=24,
        allowed_classes=("guerreiro",),
        tags=("melee", "rift", "slash"),
        unique=True,
        voice_lines_male=("RUPTURA DA LÂMINA!",),
        voice_lines_female=("RUPTURA DA LÂMINA!",),
        gameplay_notes="Exclusiva do Guerreiro. Golpe físico + eco do Véu.",
    )
)


# ------------------------------------------------------------
# MAGO
# ------------------------------------------------------------

FIREBALL_MASTERY: Tuple[MasteryStage, ...] = (
    MasteryStage(
        1,
        "Aprendiz",
        0,
        0,
        cast_time_multiplier=1.0,
        descricao="Encantamento completo antes do disparo.",
    ),
    MasteryStage(
        2,
        "Praticante",
        20,
        110,
        cast_time_multiplier=0.88,
        descricao="O encantamento começa a encurtar.",
    ),
    MasteryStage(
        3,
        "Adepto",
        65,
        360,
        cast_time_multiplier=0.72,
        cooldown_multiplier=0.95,
        damage_multiplier=1.06,
        descricao="A bola de fogo se forma com menos movimentos.",
    ),
    MasteryStage(
        4,
        "Especialista",
        150,
        950,
        cast_time_multiplier=0.55,
        cooldown_multiplier=0.90,
        damage_multiplier=1.12,
        resource_multiplier=0.94,
        descricao="Quase não há pausa entre gesto e lançamento.",
    ),
    MasteryStage(
        5,
        "Mestre",
        360,
        2500,
        cast_time_multiplier=0.30,
        cooldown_multiplier=0.84,
        damage_multiplier=1.20,
        resource_multiplier=0.88,
        remove_incantation=True,
        descricao="A magia nasce imediatamente. O grito principal continua.",
    ),
)

register_skill(
    SkillDefinition(
        id="bola_de_fogo",
        nome="Bola de Fogo",
        descricao="Conjura uma esfera flamejante que explode no impacto.",
        raridade=Rarity.COMUM,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.FOGO,
        base_damage=42,
        cooldown=1.25,
        resource_cost=14,
        allowed_classes=("mago",),
        tags=("magic", "fire", "projectile", "explosion"),
        mastery_stages=FIREBALL_MASTERY,
        voice_lines_male=("BOLA DE FOGO!", "INCINERAR!", "QUEIME!"),
        voice_lines_female=("BOLA DE FOGO!", "INCINERAR!", "QUEIME!"),
        incantations_male=(
            "Chamas, respondam ao meu chamado...",
            "Fogo do Véu, reúna-se...",
        ),
        incantations_female=(
            "Chamas, respondam ao meu chamado...",
            "Fogo do Véu, reúna-se...",
        ),
        gameplay_notes="No nível máximo de maestria remove encantamento longo, mas mantém vocalização.",
    )
)

register_skill(
    SkillDefinition(
        id="prisao_glacial",
        nome="Prisão Glacial",
        descricao="Congela uma área e prende inimigos por curto período.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.GELO,
        base_damage=32,
        cooldown=6.0,
        resource_cost=28,
        allowed_classes=("mago", "oraculo"),
        tags=("magic", "ice", "control", "area"),
        voice_lines_male=("CONGELE!", "PRISÃO GLACIAL!"),
        voice_lines_female=("CONGELE!", "PRISÃO GLACIAL!"),
        gameplay_notes="Controle de área; bosses sofrem slow em vez de stun completo.",
    )
)

register_skill(
    SkillDefinition(
        id="singularidade_arcana",
        nome="Singularidade Arcana",
        descricao="Cria um núcleo que puxa inimigos e explode após alguns segundos.",
        raridade=Rarity.LENDARIA,
        categoria=SkillCategory.SUPREMA,
        damage_type=DamageType.ARCANO,
        base_damage=130,
        cooldown=18.0,
        resource_cost=62,
        allowed_classes=("mago",),
        tags=("magic", "area", "pull", "ultimate"),
        unique=True,
        voice_lines_male=("SINGULARIDADE ARCANA!",),
        voice_lines_female=("SINGULARIDADE ARCANA!",),
        incantations_male=("Que o espaço se dobre diante de mim...",),
        incantations_female=("Que o espaço se dobre diante de mim...",),
        gameplay_notes="Exclusiva do Mago; deve ter telegraph visual forte.",
    )
)

register_skill(
    SkillDefinition(
        id="fim_da_linha_temporal",
        nome="Fim da Linha Temporal",
        descricao="Interrompe brevemente o fluxo ao redor e libera um colapso mágico.",
        raridade=Rarity.MITICA,
        categoria=SkillCategory.SUPREMA,
        damage_type=DamageType.TEMPORAL,
        base_damage=180,
        cooldown=28.0,
        resource_cost=80,
        allowed_classes=("mago", "cronista"),
        tags=("magic", "temporal", "ultimate", "control"),
        unique=True,
        voice_lines_male=("O TEMPO ACABA AQUI!",),
        voice_lines_female=("O TEMPO ACABA AQUI!",),
        gameplay_notes="Mago usa como colapso ofensivo; Cronista ganha variante de controle.",
    )
)


# ------------------------------------------------------------
# ARQUEIRO
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="flecha_serrilhada",
        nome="Flecha Serrilhada",
        descricao="Acertos aplicam sangramento por alguns segundos.",
        raridade=Rarity.COMUM,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.SANGRAMENTO,
        base_damage=6,
        cooldown=0,
        resource_cost=0,
        allowed_classes=("arqueiro",),
        tags=("ranged", "bleed", "arrow"),
        gameplay_notes="Modificador para ataques de flecha.",
    )
)

register_skill(
    SkillDefinition(
        id="tiro_ricochete",
        nome="Tiro Ricochete",
        descricao="Flechas podem saltar para outro alvo próximo.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.FISICO,
        base_damage=0,
        cooldown=0,
        resource_cost=0,
        allowed_classes=("arqueiro",),
        tags=("ranged", "arrow", "ricochet"),
        gameplay_notes="Chance e número de ricochetes podem crescer com maestria.",
    )
)

register_skill(
    SkillDefinition(
        id="chuva_de_flechas",
        nome="Chuva de Flechas",
        descricao="Marca uma área e cobre o local com múltiplos disparos.",
        raridade=Rarity.EPICA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.FISICO,
        base_damage=95,
        cooldown=9.0,
        resource_cost=38,
        allowed_classes=("arqueiro",),
        tags=("ranged", "area", "arrow"),
        voice_lines_male=("CHUVA DE FLECHAS!", "DO ALTO!"),
        voice_lines_female=("CHUVA DE FLECHAS!", "DO ALTO!"),
        gameplay_notes="Área deve ser anunciada antes da queda para manter leitura.",
    )
)

register_skill(
    SkillDefinition(
        id="horizonte_partido",
        nome="Horizonte Partido",
        descricao="Disparo carregado atravessa a arena e deixa uma cicatriz do Véu.",
        raridade=Rarity.MITICA,
        categoria=SkillCategory.SUPREMA,
        damage_type=DamageType.VAZIO,
        base_damage=210,
        cooldown=22.0,
        resource_cost=70,
        allowed_classes=("arqueiro",),
        tags=("ranged", "pierce", "rift", "ultimate"),
        unique=True,
        voice_lines_male=("HORIZONTE... PARTIDO!",),
        voice_lines_female=("HORIZONTE... PARTIDO!",),
        gameplay_notes="Exclusiva do Arqueiro. Alto telegraph e alto impacto.",
    )
)


# ------------------------------------------------------------
# CEIFADOR
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="colheita_sombria",
        nome="Colheita Sombria",
        descricao="Golpe de foice que cura parte do dano causado.",
        raridade=Rarity.INCOMUM,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.SOMBRA,
        base_damage=50,
        cooldown=2.2,
        resource_cost=16,
        allowed_classes=("ceifador",),
        tags=("melee", "lifesteal", "scythe"),
        voice_lines_male=("SUA ESSÊNCIA É MINHA!", "COLHEITA!"),
        voice_lines_female=("SUA ESSÊNCIA É MINHA!", "COLHEITA!"),
    )
)

register_skill(
    SkillDefinition(
        id="sentenca_final",
        nome="Sentença Final",
        descricao="Executa inimigos comuns muito feridos e causa dano elevado em elites.",
        raridade=Rarity.LENDARIA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.PURO,
        base_damage=120,
        cooldown=10.0,
        resource_cost=34,
        allowed_classes=("ceifador",),
        tags=("execute", "melee", "shadow"),
        unique=True,
        voice_lines_male=("ACABOU.", "SENTENÇA FINAL!"),
        voice_lines_female=("ACABOU.", "SENTENÇA FINAL!"),
    )
)


# ------------------------------------------------------------
# RASGADO
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="fenda_interior",
        nome="Fenda Interior",
        descricao="Converte parte da própria vida em energia de Ruptura.",
        raridade=Rarity.EPICA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.VAZIO,
        base_damage=0,
        cooldown=8.0,
        resource_cost=0,
        allowed_classes=("rasgado",),
        tags=("corruption", "risk", "self_damage"),
        voice_lines_male=("ABRA-SE!", "EU AGUENTO!"),
        voice_lines_female=("ABRA-SE!", "EU AGUENTO!"),
    )
)

register_skill(
    SkillDefinition(
        id="coracao_da_ruptura",
        nome="Coração da Ruptura",
        descricao="+80% dano, mas reduz drasticamente a vida máxima durante a expedição.",
        raridade=Rarity.CORROMPIDA,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.VAZIO,
        base_damage=0,
        cooldown=0,
        resource_cost=0,
        allowed_classes=("rasgado",),
        tags=("corruption", "risk", "power"),
        unique=True,
        corrupted=True,
        gameplay_notes="Poder enorme com custo real. Não remover durante a expedição.",
    )
)


# ------------------------------------------------------------
# CRONISTA
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="passo_rebobinado",
        nome="Passo Rebobinado",
        descricao="Retorna à posição registrada alguns instantes antes.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.MOBILIDADE,
        damage_type=DamageType.TEMPORAL,
        base_damage=0,
        cooldown=8.0,
        resource_cost=26,
        allowed_classes=("cronista",),
        tags=("temporal", "rewind", "mobility"),
        voice_lines_male=("VOLTE.", "AINDA NÃO."),
        voice_lines_female=("VOLTE.", "AINDA NÃO."),
    )
)

register_skill(
    SkillDefinition(
        id="instante_imovel",
        nome="Instante Imóvel",
        descricao="Cria uma zona que desacelera fortemente projéteis e inimigos.",
        raridade=Rarity.EPICA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.TEMPORAL,
        base_damage=18,
        cooldown=12.0,
        resource_cost=42,
        allowed_classes=("cronista",),
        tags=("temporal", "area", "control"),
        voice_lines_male=("PARE.", "INSTANTE IMÓVEL!"),
        voice_lines_female=("PARE.", "INSTANTE IMÓVEL!"),
    )
)


# ------------------------------------------------------------
# ARTÍFICE
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="torreta_do_veu",
        nome="Torreta do Véu",
        descricao="Instala uma torreta temporária que prioriza alvos marcados.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.ARCANO,
        base_damage=22,
        cooldown=10.0,
        resource_cost=35,
        allowed_classes=("artifice",),
        tags=("deployable", "turret", "technology"),
        voice_lines_male=("UNIDADE ATIVA!", "MIRA NELES!"),
        voice_lines_female=("UNIDADE ATIVA!", "MIRA NELES!"),
    )
)

register_skill(
    SkillDefinition(
        id="mina_de_fenda",
        nome="Mina de Fenda",
        descricao="Arma uma mina que abre uma micro-Ruptura ao ser ativada.",
        raridade=Rarity.EPICA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.VAZIO,
        base_damage=88,
        cooldown=7.0,
        resource_cost=28,
        allowed_classes=("artifice",),
        tags=("deployable", "trap", "rift"),
    )
)


# ------------------------------------------------------------
# DUELISTA
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="contra_golpe",
        nome="Contra-Golpe",
        descricao="Parry perfeito permite resposta imediata e reposicionamento.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.DEFENSIVA,
        damage_type=DamageType.FISICO,
        base_damage=64,
        cooldown=5.5,
        resource_cost=18,
        allowed_classes=("duelista",),
        tags=("parry", "counter", "mobility"),
        voice_lines_male=("MINHA VEZ.", "ERROU."),
        voice_lines_female=("MINHA VEZ.", "ERROU."),
    )
)

register_skill(
    SkillDefinition(
        id="danca_de_laminas",
        nome="Dança de Lâminas",
        descricao="Sequência veloz de cortes que cresce enquanto o jogador não é atingido.",
        raridade=Rarity.LENDARIA,
        categoria=SkillCategory.SUPREMA,
        damage_type=DamageType.FISICO,
        base_damage=145,
        cooldown=16.0,
        resource_cost=58,
        allowed_classes=("duelista",),
        tags=("combo", "melee", "mobility", "ultimate"),
        voice_lines_male=("ACOMPANHE SE PUDER!",),
        voice_lines_female=("ACOMPANHE SE PUDER!",),
    )
)


# ------------------------------------------------------------
# ORÁCULO
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="marca_do_pressagio",
        nome="Marca do Presságio",
        descricao="Marca um inimigo; ações futuras acumulam uma explosão atrasada.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.ATIVA,
        damage_type=DamageType.ARCANO,
        base_damage=18,
        cooldown=5.0,
        resource_cost=22,
        allowed_classes=("oraculo",),
        tags=("mark", "curse", "delayed"),
        voice_lines_male=("EU JÁ VI SEU FIM.", "MARCADO."),
        voice_lines_female=("EU JÁ VI SEU FIM.", "MARCADO."),
    )
)

register_skill(
    SkillDefinition(
        id="destino_condenado",
        nome="Destino Condenado",
        descricao="Amplifica todas as marcas e detona maldições simultaneamente.",
        raridade=Rarity.LENDARIA,
        categoria=SkillCategory.SUPREMA,
        damage_type=DamageType.PURO,
        base_damage=130,
        cooldown=20.0,
        resource_cost=64,
        allowed_classes=("oraculo",),
        tags=("curse", "mark", "ultimate"),
        voice_lines_male=("O DESTINO FOI ESCRITO!",),
        voice_lines_female=("O DESTINO FOI ESCRITO!",),
    )
)


# ------------------------------------------------------------
# GUARDIÃO DO VÉU
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="barreira_do_veu",
        nome="Barreira do Véu",
        descricao="Ergue uma barreira que absorve dano frontal.",
        raridade=Rarity.INCOMUM,
        categoria=SkillCategory.DEFENSIVA,
        damage_type=DamageType.ARCANO,
        base_damage=0,
        cooldown=6.0,
        resource_cost=22,
        allowed_classes=("guardiao_veu",),
        tags=("barrier", "tank", "defense"),
        voice_lines_male=("ATRÁS DE MIM!", "SEGUREM!"),
        voice_lines_female=("ATRÁS DE MIM!", "SEGUREM!"),
    )
)


# ------------------------------------------------------------
# UNIVERSAIS
# ------------------------------------------------------------

register_skill(
    SkillDefinition(
        id="sangue_do_veu",
        nome="Sangue do Véu",
        descricao="Eliminar inimigos recupera uma pequena quantidade de vida.",
        raridade=Rarity.RARA,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.VAZIO,
        base_damage=0,
        cooldown=0,
        resource_cost=0,
        tags=("universal", "healing", "rift"),
    )
)

register_skill(
    SkillDefinition(
        id="passo_fantasma",
        nome="Passo Fantasma",
        descricao="Dash deixa um eco que confunde inimigos brevemente.",
        raridade=Rarity.EPICA,
        categoria=SkillCategory.MOBILIDADE,
        damage_type=DamageType.VAZIO,
        base_damage=0,
        cooldown=0,
        resource_cost=0,
        tags=("universal", "dash", "decoy"),
    )
)

register_skill(
    SkillDefinition(
        id="pulso_de_sobrevivencia",
        nome="Pulso de Sobrevivência",
        descricao="Ao ficar com pouca vida, libera uma onda que afasta inimigos.",
        raridade=Rarity.INCOMUM,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.PURO,
        base_damage=20,
        cooldown=18.0,
        resource_cost=0,
        tags=("universal", "survival", "knockback"),
    )
)

register_skill(
    SkillDefinition(
        id="eco_predador",
        nome="Eco Predador",
        descricao="Elites derrotados fortalecem temporariamente o dano contra elites.",
        raridade=Rarity.EPICA,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.PURO,
        base_damage=0,
        cooldown=0,
        resource_cost=0,
        tags=("universal", "elite", "memory"),
    )
)

register_skill(
    SkillDefinition(
        id="pacto_do_vazio",
        nome="Pacto do Vazio",
        descricao="Grande poder ofensivo, mas cura recebida é reduzida.",
        raridade=Rarity.CORROMPIDA,
        categoria=SkillCategory.PASSIVA,
        damage_type=DamageType.VAZIO,
        base_damage=0,
        cooldown=0,
        resource_cost=0,
        tags=("universal", "corruption", "risk"),
        corrupted=True,
    )
)


# ============================================================
# ESTADO DE MAESTRIA
# ============================================================

@dataclass
class SkillMasteryState:
    skill_id: str
    usos: int = 0
    xp: int = 0
    nivel: int = 1

    def definition(self) -> SkillDefinition:
        return SKILL_REGISTRY[self.skill_id]

    def stage(self) -> MasteryStage:
        definition = self.definition()
        stages = definition.mastery_stages
        valid = [s for s in stages if s.nivel <= self.nivel]
        return max(valid, key=lambda s: s.nivel)

    def recalculate_level(self) -> int:
        definition = self.definition()
        new_level = 1

        for stage in definition.mastery_stages:
            if self.usos >= stage.usos_necessarios and self.xp >= stage.xp_necessaria:
                new_level = max(new_level, stage.nivel)

        self.nivel = new_level
        return self.nivel

    def register_use(self, mastery_xp: int = 5) -> bool:
        previous = self.nivel
        self.usos += 1
        self.xp += max(0, mastery_xp)
        self.recalculate_level()
        return self.nivel > previous

    def effective_cast_time(self, base_cast_time: float) -> float:
        return base_cast_time * self.stage().cast_time_multiplier

    def effective_cooldown(self) -> float:
        definition = self.definition()
        return definition.cooldown * self.stage().cooldown_multiplier

    def effective_resource_cost(self) -> float:
        definition = self.definition()
        return definition.resource_cost * self.stage().resource_multiplier

    def effective_damage(self) -> float:
        definition = self.definition()
        rarity_mult = RARITY_INFO[definition.raridade].power_multiplier
        return (
            definition.base_damage
            * rarity_mult
            * self.stage().damage_multiplier
        )

    def choose_voice_line(self, gender: Gender) -> Optional[str]:
        definition = self.definition()

        if gender == Gender.FEMININO:
            pool = definition.voice_lines_female
        else:
            pool = definition.voice_lines_male

        return random.choice(pool) if pool else None

    def choose_incantation(self, gender: Gender) -> Optional[str]:
        if self.stage().remove_incantation:
            return None

        definition = self.definition()

        if gender == Gender.FEMININO:
            pool = definition.incantations_female
        else:
            pool = definition.incantations_male

        return random.choice(pool) if pool else None


# ============================================================
# CRIAÇÃO / PERFIL DO PERSONAGEM
# ============================================================

@dataclass
class CharacterIdentity:
    nome: str = "Viajante"
    genero: Gender = Gender.MASCULINO
    class_id: str = "guerreiro"
    voice_pack: str = "default"

    def validate(self) -> None:
        self.nome = self.nome.strip() or "Viajante"

        if len(self.nome) > 24:
            self.nome = self.nome[:24]

        if self.class_id not in CLASS_REGISTRY:
            raise ValueError(f"Classe inválida: {self.class_id}")


@dataclass
class CharacterStats:
    nivel: int = 1
    xp: int = 0
    ouro: int = 0
    vida_maxima_bonus: int = 0
    dano_bonus: float = 0.0
    velocidade_bonus: float = 0.0


@dataclass
class EquipmentState:
    arma: Optional[str] = None
    armadura: Optional[str] = None
    acessorio_1: Optional[str] = None
    acessorio_2: Optional[str] = None


@dataclass
class ProgressionState:
    classes_desbloqueadas: Set[str] = field(
        default_factory=lambda: set(BASE_STARTING_CLASSES)
    )
    bosses_derrotados: Set[str] = field(default_factory=set)
    rupturas_descobertas: Set[str] = field(default_factory=set)
    eventos_concluidos: Set[str] = field(default_factory=set)
    itens_importantes: Set[str] = field(default_factory=set)
    bestiario: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ============================================================
# TELEMETRIA DE COMBATE
# ============================================================

@dataclass
class CombatTelemetry:
    tempo_combate: float = 0.0

    ataques_melee: int = 0
    ataques_ranged: int = 0
    ataques_magicos: int = 0

    dashes_total: int = 0
    dashes_para_tras: int = 0
    parries: int = 0
    curas_usadas: int = 0

    dano_causado: float = 0.0
    dano_recebido: float = 0.0

    soma_distancia_inimigo: float = 0.0
    amostras_distancia: int = 0

    tempo_baixa_vida: float = 0.0
    tempo_movendo: float = 0.0

    def register_distance_sample(self, distance: float) -> None:
        self.soma_distancia_inimigo += max(0.0, distance)
        self.amostras_distancia += 1

    def distance_average(self) -> float:
        if self.amostras_distancia <= 0:
            return 0.0
        return self.soma_distancia_inimigo / self.amostras_distancia

    def total_attacks(self) -> int:
        return self.ataques_melee + self.ataques_ranged + self.ataques_magicos

    def ranged_ratio(self) -> float:
        total = self.total_attacks()
        if total <= 0:
            return 0.0
        return (self.ataques_ranged + self.ataques_magicos) / total

    def melee_ratio(self) -> float:
        total = self.total_attacks()
        if total <= 0:
            return 0.0
        return self.ataques_melee / total

    def backward_dash_ratio(self) -> float:
        if self.dashes_total <= 0:
            return 0.0
        return self.dashes_para_tras / self.dashes_total

    def aggression_score(self) -> float:
        total_damage = self.dano_causado + self.dano_recebido

        if total_damage <= 0:
            return 0.5

        offense = self.dano_causado / total_damage
        close_bonus = min(0.25, self.melee_ratio() * 0.25)
        return max(0.0, min(1.0, offense + close_bonus))

    def healing_dependency(self) -> float:
        minutes = max(1.0, self.tempo_combate / 60.0)
        value = self.curas_usadas / (minutes * 4.0)
        return max(0.0, min(1.0, value))

    def profile(self) -> Dict[str, float]:
        return {
            "agressividade": round(self.aggression_score(), 3),
            "distancia_media": round(self.distance_average(), 2),
            "uso_melee": round(self.melee_ratio(), 3),
            "uso_distancia": round(self.ranged_ratio(), 3),
            "uso_dash": round(min(1.0, self.dashes_total / max(1.0, self.tempo_combate / 3.0)), 3),
            "dash_para_tras": round(self.backward_dash_ratio(), 3),
            "dependencia_cura": round(self.healing_dependency(), 3),
            "parries_por_minuto": round(
                self.parries / max(1.0, self.tempo_combate / 60.0),
                3,
            ),
        }

    def classify_style(self) -> str:
        p = self.profile()

        if p["uso_distancia"] >= 0.72 and p["dash_para_tras"] >= 0.55:
            return "kite_ranged"

        if p["uso_melee"] >= 0.72 and p["agressividade"] >= 0.68:
            return "agressivo_melee"

        if p["parries_por_minuto"] >= 2.2:
            return "counter_parry"

        if p["dependencia_cura"] >= 0.62:
            return "sustain"

        if p["distancia_media"] >= 320:
            return "long_range"

        if p["agressividade"] <= 0.38:
            return "cauteloso"

        return "adaptavel"


# ============================================================
# MEMÓRIA DO VÉU
# ============================================================

COUNTER_STRATEGIES: Dict[str, Tuple[str, ...]] = {
    "kite_ranged": (
        "flanquear_ranged",
        "fechar_distancia",
        "cortar_rota_fuga",
        "forcar_centro",
    ),
    "agressivo_melee": (
        "isca_contra_ataque",
        "zona_de_negacao",
        "recuo_tatico",
        "punir_combo_longo",
    ),
    "counter_parry": (
        "ataque_atrasado",
        "finta",
        "golpe_multiplo",
        "agarrar",
    ),
    "sustain": (
        "interromper_cura",
        "pressao_continua",
        "marcar_recuperacao",
    ),
    "long_range": (
        "salto_de_aproximacao",
        "flanco",
        "parede_projetil",
        "invocar_perseguidor",
    ),
    "cauteloso": (
        "controle_de_area",
        "avanco_coordenado",
        "limitar_espaco",
    ),
    "adaptavel": (
        "variacao_tatica",
        "troca_de_ritmo",
        "formacao_mista",
    ),
}


@dataclass
class EnemyMemory:
    enemy_id: str
    encontros: int = 0
    mortes_do_jogador: int = 0
    derrotas_do_inimigo: int = 0
    memory_points: int = 0
    ultimo_estilo_detectado: str = "desconhecido"
    estrategias_ja_usadas: List[str] = field(default_factory=list)
    ultimo_perfil: Dict[str, float] = field(default_factory=dict)

    def rank(self) -> MemoryRank:
        if self.memory_points >= 9:
            return MemoryRank.PREDADOR
        if self.memory_points >= 5:
            return MemoryRank.ADAPTADO
        if self.memory_points >= 2:
            return MemoryRank.OBSERVADOR
        return MemoryRank.DESCONHECIDO

    def register_encounter(
        self,
        telemetry: CombatTelemetry,
        player_died: bool,
    ) -> None:
        self.encontros += 1
        self.ultimo_estilo_detectado = telemetry.classify_style()
        self.ultimo_perfil = telemetry.profile()

        if player_died:
            self.mortes_do_jogador += 1
            self.memory_points += 2
        else:
            self.derrotas_do_inimigo += 1
            self.memory_points = max(0, self.memory_points - 1)

    def choose_strategy(self) -> str:
        style = self.ultimo_estilo_detectado
        candidates = list(COUNTER_STRATEGIES.get(style, ("variacao_tatica",)))

        # Não repetir a estratégia imediatamente se houver alternativas.
        fresh = [x for x in candidates if x not in self.estrategias_ja_usadas[-2:]]

        if fresh:
            chosen = random.choice(fresh)
        else:
            chosen = random.choice(candidates)

        self.estrategias_ja_usadas.append(chosen)

        if len(self.estrategias_ja_usadas) > 8:
            self.estrategias_ja_usadas = self.estrategias_ja_usadas[-8:]

        return chosen

    def contextual_line(self, player_name: str = "Riftwalker") -> Optional[str]:
        rank = self.rank()

        if self.encontros <= 1:
            return None

        if rank == MemoryRank.OBSERVADOR:
            return random.choice(
                (
                    "Você voltou.",
                    "Eu me lembro.",
                    f"Outra vez, {player_name}.",
                )
            )

        if rank == MemoryRank.ADAPTADO:
            return random.choice(
                (
                    "O mesmo ritmo... não funcionará de novo.",
                    "Eu conheço seus passos.",
                    "Sua estratégia deixou marcas no Véu.",
                )
            )

        if rank == MemoryRank.PREDADOR:
            return random.choice(
                (
                    "Eu aprendi cada fuga sua.",
                    "O Véu me mostrou como você morre.",
                    "Mude... ou repita seu fim.",
                )
            )

        return None


@dataclass
class VeilMemoryState:
    enemies: Dict[str, EnemyMemory] = field(default_factory=dict)

    def get(self, enemy_id: str) -> EnemyMemory:
        if enemy_id not in self.enemies:
            self.enemies[enemy_id] = EnemyMemory(enemy_id=enemy_id)
        return self.enemies[enemy_id]


# ============================================================
# RUPTURAS
# ============================================================

@dataclass(frozen=True)
class RiftDefinition:
    id: str
    nome: str
    descricao: str
    danger: int
    reward_multiplier: float
    enemy_damage_multiplier: float = 1.0
    enemy_speed_multiplier: float = 1.0
    player_damage_multiplier: float = 1.0
    player_speed_multiplier: float = 1.0
    xp_multiplier: float = 1.0
    max_hp_multiplier: float = 1.0
    visibility_multiplier: float = 1.0
    tags: Tuple[str, ...] = ()


RIFT_REGISTRY: Dict[str, RiftDefinition] = {}


def register_rift(definition: RiftDefinition) -> RiftDefinition:
    if definition.id in RIFT_REGISTRY:
        raise ValueError(f"Ruptura duplicada: {definition.id}")
    RIFT_REGISTRY[definition.id] = definition
    return definition


register_rift(
    RiftDefinition(
        id="carmesim",
        nome="Ruptura Carmesim",
        descricao="Mais dano dos dois lados. Recompensas ofensivas aumentadas.",
        danger=2,
        reward_multiplier=1.28,
        enemy_damage_multiplier=1.25,
        player_damage_multiplier=1.18,
        tags=("blood", "damage", "risk"),
    )
)

register_rift(
    RiftDefinition(
        id="temporal",
        nome="Ruptura Temporal",
        descricao="O ritmo do campo acelera e a experiência recebida aumenta.",
        danger=3,
        reward_multiplier=1.34,
        enemy_speed_multiplier=1.18,
        player_speed_multiplier=1.05,
        xp_multiplier=1.35,
        tags=("temporal", "speed", "xp"),
    )
)

register_rift(
    RiftDefinition(
        id="vazio",
        nome="Ruptura do Vazio",
        descricao="Visibilidade reduzida e poder ofensivo aumentado.",
        danger=4,
        reward_multiplier=1.48,
        player_damage_multiplier=1.28,
        max_hp_multiplier=0.88,
        visibility_multiplier=0.70,
        tags=("void", "darkness", "risk"),
    )
)

register_rift(
    RiftDefinition(
        id="vital",
        nome="Ruptura Vital",
        descricao="Criaturas ficam mais agressivas, mas ecos de cura aparecem com frequência.",
        danger=2,
        reward_multiplier=1.20,
        enemy_damage_multiplier=1.12,
        tags=("healing", "life", "pressure"),
    )
)

register_rift(
    RiftDefinition(
        id="instavel",
        nome="Ruptura Instável",
        descricao="Velocidade e comportamento ficam menos previsíveis.",
        danger=3,
        reward_multiplier=1.38,
        enemy_speed_multiplier=1.12,
        player_speed_multiplier=1.08,
        player_damage_multiplier=1.10,
        tags=("chaos", "speed", "variance"),
    )
)


@dataclass
class ActiveRiftState:
    active_ids: List[str] = field(default_factory=list)

    def add(self, rift_id: str) -> None:
        if rift_id not in RIFT_REGISTRY:
            raise ValueError(f"Ruptura desconhecida: {rift_id}")
        self.active_ids.append(rift_id)

    def cumulative_modifiers(self) -> Dict[str, float]:
        result = {
            "reward_multiplier": 1.0,
            "enemy_damage_multiplier": 1.0,
            "enemy_speed_multiplier": 1.0,
            "player_damage_multiplier": 1.0,
            "player_speed_multiplier": 1.0,
            "xp_multiplier": 1.0,
            "max_hp_multiplier": 1.0,
            "visibility_multiplier": 1.0,
        }

        for rift_id in self.active_ids:
            rift = RIFT_REGISTRY[rift_id]

            for key in result:
                result[key] *= getattr(rift, key)

        return result


# ============================================================
# POOL / SORTEIO DE HABILIDADES
# ============================================================

def class_can_use_skill(class_id: str, skill: SkillDefinition) -> bool:
    if class_id not in CLASS_REGISTRY:
        return False

    if class_id in skill.forbidden_classes:
        return False

    if skill.allowed_classes and class_id not in skill.allowed_classes:
        return False

    class_tags = set(CLASS_REGISTRY[class_id].tags)

    if skill.required_tags and not set(skill.required_tags).issubset(class_tags):
        return False

    return True


def eligible_skills(
    class_id: str,
    owned_skill_ids: Iterable[str] = (),
    allow_corrupted: bool = True,
) -> List[SkillDefinition]:
    owned = set(owned_skill_ids)
    result = []

    for skill in SKILL_REGISTRY.values():
        if not class_can_use_skill(class_id, skill):
            continue

        if skill.unique and skill.id in owned:
            continue

        if skill.corrupted and not allow_corrupted:
            continue

        result.append(skill)

    return result


def weighted_skill_choice(
    skills: Sequence[SkillDefinition],
    luck: float = 0.0,
) -> SkillDefinition:
    if not skills:
        raise ValueError("Nenhuma habilidade disponível para sorteio.")

    weights = []

    for skill in skills:
        info = RARITY_INFO[skill.raridade]

        # Luck positiva beneficia raridades mais altas.
        rarity_bonus = 1.0 + max(0.0, luck) * (info.display_order - 1) * 0.18
        weights.append(info.weight * rarity_bonus)

    return random.choices(skills, weights=weights, k=1)[0]


def generate_skill_offers(
    class_id: str,
    owned_skill_ids: Iterable[str],
    amount: int = 3,
    luck: float = 0.0,
    allow_corrupted: bool = True,
) -> List[SkillDefinition]:
    pool = eligible_skills(
        class_id=class_id,
        owned_skill_ids=owned_skill_ids,
        allow_corrupted=allow_corrupted,
    )

    if len(pool) <= amount:
        return list(pool)

    offers: List[SkillDefinition] = []
    local_pool = list(pool)

    while local_pool and len(offers) < amount:
        chosen = weighted_skill_choice(local_pool, luck=luck)
        offers.append(chosen)
        local_pool.remove(chosen)

    return offers


# ============================================================
# ESTADO DO JOGADOR
# ============================================================

@dataclass
class PlayerState:
    identity: CharacterIdentity = field(default_factory=CharacterIdentity)
    stats: CharacterStats = field(default_factory=CharacterStats)
    equipment: EquipmentState = field(default_factory=EquipmentState)
    progression: ProgressionState = field(default_factory=ProgressionState)

    owned_skills: Set[str] = field(default_factory=set)
    masteries: Dict[str, SkillMasteryState] = field(default_factory=dict)

    active_rifts: ActiveRiftState = field(default_factory=ActiveRiftState)
    veil_memory: VeilMemoryState = field(default_factory=VeilMemoryState)

    inventory: List[Dict[str, Any]] = field(default_factory=list)

    # Estado flexível da campanha/narrativa. Mantido como dicionário para
    # permitir expansão sem criar dependência circular com narrative_systems.
    campaign: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.identity.validate()

    def class_definition(self) -> ClassDefinition:
        return CLASS_REGISTRY[self.identity.class_id]

    def unlock_class(self, class_id: str) -> bool:
        if class_id not in CLASS_REGISTRY:
            raise ValueError(f"Classe desconhecida: {class_id}")

        previous = class_id in self.progression.classes_desbloqueadas
        self.progression.classes_desbloqueadas.add(class_id)
        return not previous

    def learn_skill(self, skill_id: str) -> bool:
        if skill_id not in SKILL_REGISTRY:
            raise ValueError(f"Habilidade desconhecida: {skill_id}")

        skill = SKILL_REGISTRY[skill_id]

        if not class_can_use_skill(self.identity.class_id, skill):
            raise ValueError(
                f"{self.class_definition().nome} não pode usar {skill.nome}."
            )

        already = skill_id in self.owned_skills

        self.owned_skills.add(skill_id)

        if skill_id not in self.masteries:
            self.masteries[skill_id] = SkillMasteryState(skill_id=skill_id)

        return not already

    def register_skill_use(self, skill_id: str, mastery_xp: int = 5) -> bool:
        if skill_id not in self.masteries:
            self.masteries[skill_id] = SkillMasteryState(skill_id=skill_id)

        return self.masteries[skill_id].register_use(mastery_xp=mastery_xp)

    def max_hp(self) -> int:
        base = self.class_definition().hp_base
        rift_mult = self.active_rifts.cumulative_modifiers()["max_hp_multiplier"]
        return max(
            1,
            int((base + self.stats.vida_maxima_bonus) * rift_mult),
        )

    def damage_base(self) -> float:
        base = self.class_definition().dano_base + self.stats.dano_bonus
        rift_mult = self.active_rifts.cumulative_modifiers()["player_damage_multiplier"]
        return base * rift_mult

    def movement_speed(self) -> float:
        base = self.class_definition().velocidade_base + self.stats.velocidade_bonus
        rift_mult = self.active_rifts.cumulative_modifiers()["player_speed_multiplier"]
        return base * rift_mult


# ============================================================
# SERIALIZAÇÃO
# ============================================================

def _serialize_enum(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value

    if isinstance(value, set):
        return sorted(_serialize_enum(x) for x in value)

    if isinstance(value, list):
        return [_serialize_enum(x) for x in value]

    if isinstance(value, tuple):
        return [_serialize_enum(x) for x in value]

    if isinstance(value, dict):
        return {
            str(k): _serialize_enum(v)
            for k, v in value.items()
        }

    return value


def player_state_to_dict(state: PlayerState) -> Dict[str, Any]:
    masteries = {
        skill_id: {
            "skill_id": mastery.skill_id,
            "usos": mastery.usos,
            "xp": mastery.xp,
            "nivel": mastery.nivel,
        }
        for skill_id, mastery in state.masteries.items()
    }

    veil_memory = {
        enemy_id: {
            "enemy_id": memory.enemy_id,
            "encontros": memory.encontros,
            "mortes_do_jogador": memory.mortes_do_jogador,
            "derrotas_do_inimigo": memory.derrotas_do_inimigo,
            "memory_points": memory.memory_points,
            "ultimo_estilo_detectado": memory.ultimo_estilo_detectado,
            "estrategias_ja_usadas": list(memory.estrategias_ja_usadas),
            "ultimo_perfil": dict(memory.ultimo_perfil),
        }
        for enemy_id, memory in state.veil_memory.enemies.items()
    }

    data = {
        "save_version": SAVE_VERSION,

        "identity": {
            "nome": state.identity.nome,
            "genero": state.identity.genero.value,
            "class_id": state.identity.class_id,
            "voice_pack": state.identity.voice_pack,
        },

        "stats": asdict(state.stats),

        "equipment": asdict(state.equipment),

        "progression": {
            "classes_desbloqueadas": sorted(state.progression.classes_desbloqueadas),
            "bosses_derrotados": sorted(state.progression.bosses_derrotados),
            "rupturas_descobertas": sorted(state.progression.rupturas_descobertas),
            "eventos_concluidos": sorted(state.progression.eventos_concluidos),
            "itens_importantes": sorted(state.progression.itens_importantes),
            "bestiario": copy.deepcopy(state.progression.bestiario),
        },

        "owned_skills": sorted(state.owned_skills),

        "masteries": masteries,

        "active_rifts": list(state.active_rifts.active_ids),

        "veil_memory": veil_memory,

        "inventory": copy.deepcopy(state.inventory),

        "campaign": copy.deepcopy(state.campaign),
    }

    return _serialize_enum(data)


def player_state_from_dict(data: Dict[str, Any]) -> PlayerState:
    version = int(data.get("save_version", 1))

    if version > SAVE_VERSION:
        raise ValueError(
            f"Save versão {version} é mais novo que o jogo suporta ({SAVE_VERSION})."
        )

    identity_data = data.get("identity", {})
    stats_data = data.get("stats", {})
    equipment_data = data.get("equipment", {})
    progression_data = data.get("progression", {})

    gender_raw = identity_data.get("genero", Gender.MASCULINO.value)

    try:
        gender = Gender(gender_raw)
    except ValueError:
        gender = Gender.MASCULINO

    identity = CharacterIdentity(
        nome=identity_data.get("nome", "Viajante"),
        genero=gender,
        class_id=identity_data.get("class_id", "guerreiro"),
        voice_pack=identity_data.get("voice_pack", "default"),
    )

    if identity.class_id not in CLASS_REGISTRY:
        identity.class_id = "guerreiro"

    stats = CharacterStats(
        nivel=int(stats_data.get("nivel", 1)),
        xp=int(stats_data.get("xp", 0)),
        ouro=int(stats_data.get("ouro", 0)),
        vida_maxima_bonus=int(stats_data.get("vida_maxima_bonus", 0)),
        dano_bonus=float(stats_data.get("dano_bonus", 0.0)),
        velocidade_bonus=float(stats_data.get("velocidade_bonus", 0.0)),
    )

    equipment = EquipmentState(
        arma=equipment_data.get("arma"),
        armadura=equipment_data.get("armadura"),
        acessorio_1=equipment_data.get("acessorio_1"),
        acessorio_2=equipment_data.get("acessorio_2"),
    )

    progression = ProgressionState(
        classes_desbloqueadas=set(
            progression_data.get(
                "classes_desbloqueadas",
                list(BASE_STARTING_CLASSES),
            )
        ),
        bosses_derrotados=set(progression_data.get("bosses_derrotados", [])),
        rupturas_descobertas=set(progression_data.get("rupturas_descobertas", [])),
        eventos_concluidos=set(progression_data.get("eventos_concluidos", [])),
        itens_importantes=set(progression_data.get("itens_importantes", [])),
        bestiario=dict(progression_data.get("bestiario", {})),
    )

    state = PlayerState(
        identity=identity,
        stats=stats,
        equipment=equipment,
        progression=progression,
    )

    state.owned_skills = {
        skill_id
        for skill_id in data.get("owned_skills", [])
        if skill_id in SKILL_REGISTRY
    }

    for skill_id, mastery_data in data.get("masteries", {}).items():
        if skill_id not in SKILL_REGISTRY:
            continue

        mastery = SkillMasteryState(
            skill_id=skill_id,
            usos=int(mastery_data.get("usos", 0)),
            xp=int(mastery_data.get("xp", 0)),
            nivel=int(mastery_data.get("nivel", 1)),
        )

        mastery.recalculate_level()
        state.masteries[skill_id] = mastery

    for rift_id in data.get("active_rifts", []):
        if rift_id in RIFT_REGISTRY:
            state.active_rifts.active_ids.append(rift_id)

    for enemy_id, memory_data in data.get("veil_memory", {}).items():
        memory = EnemyMemory(
            enemy_id=enemy_id,
            encontros=int(memory_data.get("encontros", 0)),
            mortes_do_jogador=int(memory_data.get("mortes_do_jogador", 0)),
            derrotas_do_inimigo=int(memory_data.get("derrotas_do_inimigo", 0)),
            memory_points=int(memory_data.get("memory_points", 0)),
            ultimo_estilo_detectado=memory_data.get(
                "ultimo_estilo_detectado",
                "desconhecido",
            ),
            estrategias_ja_usadas=list(
                memory_data.get("estrategias_ja_usadas", [])
            ),
            ultimo_perfil=dict(memory_data.get("ultimo_perfil", {})),
        )

        state.veil_memory.enemies[enemy_id] = memory

    state.inventory = list(data.get("inventory", []))
    campaign = data.get("campaign", {})
    state.campaign = copy.deepcopy(campaign) if isinstance(campaign, dict) else {}

    return state


# ============================================================
# SAVE MANAGER ROBUSTO
# ============================================================

class SaveManager:
    """
    Save JSON com:
    - escrita atômica
    - backup
    - versionamento
    - recuperação de backup
    """

    def __init__(
        self,
        filename: str = DEFAULT_SAVE_FILE,
        backup_suffix: str = ".backup",
    ):
        self.path = Path(filename)
        self.backup_path = Path(str(self.path) + backup_suffix)
        self.last_load_source = "none"
        self.last_error: Optional[str] = None

    def save(self, state: PlayerState) -> None:
        data = player_state_to_dict(state)

        self.path.parent.mkdir(parents=True, exist_ok=True)

        temp_path: Optional[Path] = None

        try:
            fd, temp_name = tempfile.mkstemp(
                prefix=self.path.stem + "_",
                suffix=".tmp",
                dir=str(self.path.parent),
            )

            temp_path = Path(temp_name)

            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(
                    data,
                    file,
                    indent=4,
                    ensure_ascii=False,
                )
                file.flush()
                os.fsync(file.fileno())

            # Mantém backup apenas quando o save principal anterior é realmente válido.
            # Se acabamos de recuperar pelo .backup, copiar o principal corrompido por cima
            # dele destruiria a única cópia boa.
            previous_primary_valid = False
            if self.path.exists() and self.last_load_source != "backup":
                try:
                    with self.path.open("r", encoding="utf-8") as previous_file:
                        previous_data = json.load(previous_file)
                    player_state_from_dict(previous_data)
                    previous_primary_valid = True
                except Exception:
                    previous_primary_valid = False

            if previous_primary_valid:
                shutil.copy2(self.path, self.backup_path)

            os.replace(temp_path, self.path)
            temp_path = None

            # Depois de uma recuperação por backup, o novo principal já é íntegro;
            # ele também vira a nova cópia de recuperação.
            if self.last_load_source == "backup":
                shutil.copy2(self.path, self.backup_path)
                self.last_load_source = "primary_repaired"

        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def load(self) -> PlayerState:
        self.last_error = None
        if not self.path.exists():
            # Um principal ausente ainda pode ser recuperado pelo backup.
            if self.backup_path.exists():
                try:
                    with self.backup_path.open("r", encoding="utf-8") as file:
                        data = json.load(file)
                    state = player_state_from_dict(data)
                    self.last_load_source = "backup"
                    return state
                except Exception as backup_exc:
                    self.last_error = f"backup: {type(backup_exc).__name__}: {backup_exc}"
                    self.last_load_source = "new_after_error"
                    return PlayerState()
            self.last_load_source = "new"
            return PlayerState()

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            state = player_state_from_dict(data)
            self.last_load_source = "primary"
            return state

        except Exception as exc:
            self.last_error = f"primary: {type(exc).__name__}: {exc}"
            # Se o save principal falhar, tenta backup sem apagar evidência do arquivo corrompido.
            if self.backup_path.exists():
                try:
                    with self.backup_path.open("r", encoding="utf-8") as file:
                        data = json.load(file)
                    state = player_state_from_dict(data)
                    self.last_load_source = "backup"
                    return state
                except Exception as backup_exc:
                    self.last_error += f" | backup: {type(backup_exc).__name__}: {backup_exc}"

            self.last_load_source = "new_after_error"
            return PlayerState()


# ============================================================
# AUTOSAVE
# ============================================================

@dataclass
class AutosaveController:
    manager: SaveManager
    minimum_interval: float = 2.0
    last_save_time: float = 0.0
    pending_reason: Optional[AutosaveReason] = None

    def request(self, reason: AutosaveReason) -> None:
        self.pending_reason = reason

    def update(
        self,
        state: PlayerState,
        safe_to_save: bool = True,
        force: bool = False,
    ) -> bool:
        if self.pending_reason is None:
            return False

        if not safe_to_save and not force:
            return False

        now = time.monotonic()

        if not force and now - self.last_save_time < self.minimum_interval:
            return False

        self.manager.save(state)

        self.last_save_time = now
        self.pending_reason = None

        return True

    def save_now(
        self,
        state: PlayerState,
        reason: AutosaveReason = AutosaveReason.CHECKPOINT,
    ) -> None:
        self.pending_reason = reason
        self.update(
            state,
            safe_to_save=True,
            force=True,
        )


# ============================================================
# FIXED TIMESTEP
# ============================================================

class FixedTimestep:
    """
    Separação entre tempo de render e lógica.

    Uso típico no Pygame:

        dt_real = clock.tick(render_fps) / 1000.0

        for fixed_dt in stepper.consume(dt_real):
            game.fixed_update(fixed_dt)

        game.draw(interpolation=stepper.alpha)

    A lógica continua em frequência fixa mesmo com FPS de render variando.
    """

    def __init__(
        self,
        updates_per_second: int = 60,
        max_frame_time: float = 0.25,
    ):
        if updates_per_second <= 0:
            raise ValueError("updates_per_second deve ser maior que zero.")

        self.fixed_dt = 1.0 / updates_per_second
        self.max_frame_time = max_frame_time
        self.accumulator = 0.0

    def consume(self, real_dt: float) -> Iterable[float]:
        real_dt = max(0.0, min(real_dt, self.max_frame_time))
        self.accumulator += real_dt

        steps = 0
        max_steps = 12

        while self.accumulator >= self.fixed_dt and steps < max_steps:
            self.accumulator -= self.fixed_dt
            steps += 1
            yield self.fixed_dt

        # Evita espiral de morte em travamentos grandes.
        if steps >= max_steps:
            self.accumulator = min(self.accumulator, self.fixed_dt)

    @property
    def alpha(self) -> float:
        return max(0.0, min(1.0, self.accumulator / self.fixed_dt))


# ============================================================
# REAÇÕES / VOZ
# ============================================================

@dataclass
class ReactionEvent:
    event_type: str
    priority: int
    line: Optional[str] = None
    animation: Optional[str] = None
    movement_hint: Optional[str] = None
    cooldown_key: Optional[str] = None
    cooldown: float = 0.0


class ReactionController:
    """
    Evita spam de voz e ajuda a sincronizar:
    estado -> movimento -> animação -> fala.
    """

    def __init__(self):
        self.cooldowns: Dict[str, float] = {}
        self.current_priority = -1

    def update(self, dt: float) -> None:
        expired = []

        for key in self.cooldowns:
            self.cooldowns[key] = max(0.0, self.cooldowns[key] - dt)

            if self.cooldowns[key] <= 0:
                expired.append(key)

        for key in expired:
            del self.cooldowns[key]

        self.current_priority = -1

    def can_play(self, event: ReactionEvent) -> bool:
        if event.priority < self.current_priority:
            return False

        if event.cooldown_key and event.cooldown_key in self.cooldowns:
            return False

        return True

    def play(self, event: ReactionEvent) -> Optional[ReactionEvent]:
        if not self.can_play(event):
            return None

        self.current_priority = event.priority

        if event.cooldown_key and event.cooldown > 0:
            self.cooldowns[event.cooldown_key] = event.cooldown

        return event


# ============================================================
# SQUADS / PAPÉIS TÁTICOS
# ============================================================

class SquadRole(str, Enum):
    VANGUARD = "Vanguard"
    FLANKER = "Flanker"
    SUPPORT = "Support"
    HUNTER = "Hunter"
    TANK = "Tank"
    RANGED = "Ranged"


@dataclass(frozen=True)
class SquadDoctrine:
    id: str
    nome: str
    descricao: str
    preferred_roles: Tuple[SquadRole, ...]
    behaviors: Tuple[str, ...]


SQUAD_DOCTRINES: Dict[str, SquadDoctrine] = {
    "cerco": SquadDoctrine(
        id="cerco",
        nome="Cerco",
        descricao="Abre formação e tenta reduzir rotas de fuga.",
        preferred_roles=(
            SquadRole.VANGUARD,
            SquadRole.FLANKER,
            SquadRole.FLANKER,
            SquadRole.HUNTER,
        ),
        behaviors=(
            "cortar_rota",
            "flanquear",
            "forcar_centro",
        ),
    ),
    "fortaleza": SquadDoctrine(
        id="fortaleza",
        nome="Fortaleza",
        descricao="Forma compacta ao redor de unidades importantes.",
        preferred_roles=(
            SquadRole.TANK,
            SquadRole.TANK,
            SquadRole.SUPPORT,
            SquadRole.RANGED,
        ),
        behaviors=(
            "proteger_ranged",
            "segurar_posicao",
            "contra_atacar",
        ),
    ),
    "cacada": SquadDoctrine(
        id="cacada",
        nome="Caçada",
        descricao="Pressão constante e perseguição coordenada.",
        preferred_roles=(
            SquadRole.HUNTER,
            SquadRole.FLANKER,
            SquadRole.VANGUARD,
        ),
        behaviors=(
            "punir_dash",
            "seguir_alvo",
            "alternar_agressor",
        ),
    ),
    "isca": SquadDoctrine(
        id="isca",
        nome="Isca",
        descricao="Um membro chama atenção enquanto os demais preparam resposta.",
        preferred_roles=(
            SquadRole.VANGUARD,
            SquadRole.FLANKER,
            SquadRole.RANGED,
            SquadRole.HUNTER,
        ),
        behaviors=(
            "atrair",
            "esperar_compromisso",
            "contra_golpe",
        ),
    ),
}


def choose_squad_doctrine(
    previous_ids: Sequence[str] = (),
) -> SquadDoctrine:
    options = [
        doctrine
        for doctrine_id, doctrine in SQUAD_DOCTRINES.items()
        if doctrine_id not in previous_ids[-2:]
    ]

    if not options:
        options = list(SQUAD_DOCTRINES.values())

    return random.choice(options)


# ============================================================
# FUNÇÕES DE APOIO / DEBUG DE DESIGN
# ============================================================

def describe_class(class_id: str) -> str:
    definition = CLASS_REGISTRY[class_id]

    return (
        f"{definition.nome} | HP {definition.hp_base} | "
        f"{definition.recurso_nome} {definition.recurso_maximo} | "
        f"Dano {definition.dano_base} | Vel {definition.velocidade_base}"
    )


def rarity_distribution_summary() -> Dict[str, float]:
    total = sum(info.weight for info in RARITY_INFO.values())

    return {
        rarity.value: round((info.weight / total) * 100.0, 2)
        for rarity, info in RARITY_INFO.items()
    }


def create_new_character(
    nome: str,
    genero: Gender,
    class_id: str,
) -> PlayerState:
    if class_id not in CLASS_REGISTRY:
        raise ValueError(f"Classe desconhecida: {class_id}")

    state = PlayerState(
        identity=CharacterIdentity(
            nome=nome,
            genero=genero,
            class_id=class_id,
        )
    )

    # Cada classe recebe uma habilidade que já apresenta sua identidade.
    # O bloqueio de classes é responsabilidade da progressão/UI, não desta fábrica.
    starter_skills = {
        "guerreiro": "corte_crescente",
        "mago": "bola_de_fogo",
        "arqueiro": "flecha_serrilhada",
        "ceifador": "colheita_sombria",
        "rasgado": "fenda_interior",
        "cronista": "passo_rebobinado",
        "artifice": "torreta_do_veu",
        "duelista": "contra_golpe",
        "oraculo": "marca_do_pressagio",
        "guardiao_veu": "barreira_do_veu",
    }

    starter = starter_skills.get(class_id)
    if starter:
        state.learn_skill(starter)

    return state


# ============================================================
# EXEMPLO DE INTEGRAÇÃO
# ============================================================

def integration_example() -> None:
    """
    Não é o jogo final.
    É apenas uma referência de como o main.py poderá conversar
    com estes sistemas.
    """

    player = create_new_character(
        nome="Riftwalker",
        genero=Gender.MASCULINO,
        class_id="mago",
    )

    # Aprende uma habilidade rara.
    player.learn_skill("prisao_glacial")

    # Usa Bola de Fogo várias vezes -> ganha maestria.
    for _ in range(30):
        leveled = player.register_skill_use(
            "bola_de_fogo",
            mastery_xp=6,
        )

        if leveled:
            mastery = player.masteries["bola_de_fogo"]
            print(
                "Maestria subiu:",
                mastery.nivel,
                mastery.stage().nome,
            )

    mastery = player.masteries["bola_de_fogo"]

    print("Incantação:", mastery.choose_incantation(player.identity.genero))
    print("Fala:", mastery.choose_voice_line(player.identity.genero))
    print("Dano efetivo:", round(mastery.effective_damage(), 2))

    # Ruptura.
    player.active_rifts.add("temporal")

    print("Velocidade:", round(player.movement_speed(), 2))

    # Perfil de combate.
    telemetry = CombatTelemetry(
        tempo_combate=120,
        ataques_ranged=70,
        ataques_magicos=50,
        dashes_total=24,
        dashes_para_tras=18,
        dano_causado=4200,
        dano_recebido=850,
        soma_distancia_inimigo=33000,
        amostras_distancia=100,
    )

    print("Estilo:", telemetry.classify_style())

    boss_memory = player.veil_memory.get("primeiro_rasgado")
    boss_memory.register_encounter(
        telemetry=telemetry,
        player_died=True,
    )

    print("Memória:", boss_memory.rank().value)
    print("Estratégia futura:", boss_memory.choose_strategy())

    # Save.
    save_manager = SaveManager("save_riftwalker.json")
    autosave = AutosaveController(save_manager)

    autosave.request(AutosaveReason.BOSS_DERROTADO)

    # No jogo real, isso seria chamado no update quando for seguro.
    # autosave.update(player, safe_to_save=True)


if __name__ == "__main__":
    print("RIFTWALKER — Core Systems 0.3")
    print(f"Classes registradas: {len(CLASS_REGISTRY)}")
    print(f"Habilidades registradas: {len(SKILL_REGISTRY)}")
    print(f"Rupturas registradas: {len(RIFT_REGISTRY)}")
    print("Distribuição base de raridade:", rarity_distribution_summary())
    print()
    integration_example()

"""
RIFTWALKER — CONTENT SYSTEMS 0.3
================================

Conteúdo expansível separado do motor principal:
- equipamentos e raridades
- conjuntos e sinergias
- modificadores de atributos
- geração de loot
- requisitos de equipamento
- desbloqueios de classes
- preservação de progressão entre personagens

A intenção é permitir adicionar centenas de itens e novas regras sem
entupir main.py nem core_systems.py com condicionais específicas.
"""

from __future__ import annotations

import copy
import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core_systems import (
    CLASS_REGISTRY,
    RARITY_INFO,
    RIFT_REGISTRY,
    Rarity,
    PlayerState,
    SKILL_REGISTRY,
)


# ============================================================
# EQUIPAMENTOS
# ============================================================

class EquipmentSlot(str, Enum):
    ARMA = "arma"
    ARMADURA = "armadura"
    ACESSORIO = "acessorio"


@dataclass(frozen=True)
class EquipmentModifiers:
    hp_flat: int = 0
    hp_mult: float = 1.0
    damage_flat: float = 0.0
    damage_mult: float = 1.0
    speed_flat: float = 0.0
    speed_mult: float = 1.0
    cooldown_mult: float = 1.0
    resource_regen_mult: float = 1.0
    resource_cost_mult: float = 1.0
    crit_chance: float = 0.0
    crit_damage_mult: float = 1.0
    lifesteal: float = 0.0
    healing_mult: float = 1.0
    corruption_gain_mult: float = 1.0

    def merged(self, other: "EquipmentModifiers") -> "EquipmentModifiers":
        return EquipmentModifiers(
            hp_flat=self.hp_flat + other.hp_flat,
            hp_mult=self.hp_mult * other.hp_mult,
            damage_flat=self.damage_flat + other.damage_flat,
            damage_mult=self.damage_mult * other.damage_mult,
            speed_flat=self.speed_flat + other.speed_flat,
            speed_mult=self.speed_mult * other.speed_mult,
            cooldown_mult=self.cooldown_mult * other.cooldown_mult,
            resource_regen_mult=self.resource_regen_mult * other.resource_regen_mult,
            resource_cost_mult=self.resource_cost_mult * other.resource_cost_mult,
            crit_chance=self.crit_chance + other.crit_chance,
            crit_damage_mult=self.crit_damage_mult * other.crit_damage_mult,
            lifesteal=self.lifesteal + other.lifesteal,
            healing_mult=self.healing_mult * other.healing_mult,
            corruption_gain_mult=self.corruption_gain_mult * other.corruption_gain_mult,
        )


@dataclass(frozen=True)
class EquipmentDefinition:
    id: str
    nome: str
    descricao: str
    slot: EquipmentSlot
    raridade: Rarity
    modifiers: EquipmentModifiers = EquipmentModifiers()
    allowed_classes: Tuple[str, ...] = ()
    forbidden_classes: Tuple[str, ...] = ()
    set_id: Optional[str] = None
    unique_effect: Optional[str] = None
    tags: Tuple[str, ...] = ()
    min_level: int = 1


@dataclass(frozen=True)
class SetBonus:
    pieces: int
    nome: str
    descricao: str
    modifiers: EquipmentModifiers = EquipmentModifiers()
    effect_id: Optional[str] = None


@dataclass(frozen=True)
class EquipmentSet:
    id: str
    nome: str
    descricao: str
    bonuses: Tuple[SetBonus, ...]


EQUIPMENT_REGISTRY: Dict[str, EquipmentDefinition] = {}
EQUIPMENT_SETS: Dict[str, EquipmentSet] = {}


def register_equipment(item: EquipmentDefinition) -> EquipmentDefinition:
    if item.id in EQUIPMENT_REGISTRY:
        raise ValueError(f"Equipamento duplicado: {item.id}")

    for class_id in item.allowed_classes + item.forbidden_classes:
        if class_id not in CLASS_REGISTRY:
            raise ValueError(f"Equipamento {item.id} referencia classe inválida: {class_id}")

    EQUIPMENT_REGISTRY[item.id] = item
    return item


def register_set(item_set: EquipmentSet) -> EquipmentSet:
    if item_set.id in EQUIPMENT_SETS:
        raise ValueError(f"Conjunto duplicado: {item_set.id}")
    EQUIPMENT_SETS[item_set.id] = item_set
    return item_set


# ============================================================
# CONJUNTOS
# ============================================================

register_set(
    EquipmentSet(
        id="sentinela",
        nome="Sentinela da Primeira Fenda",
        descricao="Equipamento criado para sobreviver às primeiras Rupturas.",
        bonuses=(
            SetBonus(
                2,
                "Postura da Sentinela",
                "+12% vida e recuperação de recurso melhorada.",
                EquipmentModifiers(hp_mult=1.12, resource_regen_mult=1.10),
            ),
            SetBonus(
                3,
                "Juramento da Fenda",
                "Ao sofrer dano pesado, a próxima habilidade recebe bônus de dano.",
                EquipmentModifiers(damage_mult=1.08),
                effect_id="sentinel_retaliation",
            ),
        ),
    )
)

register_set(
    EquipmentSet(
        id="cinzas",
        nome="Cinzas Arcanas",
        descricao="Relíquias de conjuradores consumidos por magia elemental.",
        bonuses=(
            SetBonus(
                2,
                "Chama Persistente",
                "+14% dano e -6% custo de recurso.",
                EquipmentModifiers(damage_mult=1.14, resource_cost_mult=0.94),
            ),
            SetBonus(
                3,
                "Núcleo Arcano",
                "Magias elementais podem deixar um eco secundário.",
                EquipmentModifiers(cooldown_mult=0.93),
                effect_id="arcane_echo",
            ),
        ),
    )
)

register_set(
    EquipmentSet(
        id="cacador_veu",
        nome="Caçador do Véu",
        descricao="Construído para perseguir criaturas através de terreno instável.",
        bonuses=(
            SetBonus(
                2,
                "Passo do Caçador",
                "+22 velocidade e +6% crítico.",
                EquipmentModifiers(speed_flat=22, crit_chance=0.06),
            ),
            SetBonus(
                3,
                "Predador de Rupturas",
                "Dashes fortalecem temporariamente ataques à distância.",
                EquipmentModifiers(damage_mult=1.07),
                effect_id="rift_hunter_dash_power",
            ),
        ),
    )
)

register_set(
    EquipmentSet(
        id="relogio_partido",
        nome="Relógio Partido",
        descricao="Fragmentos de uma linha temporal que não deveria existir.",
        bonuses=(
            SetBonus(
                2,
                "Segundo Roubado",
                "Cooldowns 9% menores e +10 velocidade.",
                EquipmentModifiers(cooldown_mult=0.91, speed_flat=10),
            ),
            SetBonus(
                3,
                "Tempo Emprestado",
                "Uma esquiva perfeita pode devolver parte do cooldown mais longo.",
                effect_id="borrowed_time",
            ),
        ),
    )
)

register_set(
    EquipmentSet(
        id="abismo",
        nome="Vestígios do Abismo",
        descricao="Itens que carregam uma presença do outro lado do Véu.",
        bonuses=(
            SetBonus(
                2,
                "Sussurro do Vazio",
                "+19% dano, porém -8% vida máxima.",
                EquipmentModifiers(damage_mult=1.19, hp_mult=0.92),
            ),
            SetBonus(
                3,
                "O Abismo Responde",
                "Baixa vida aumenta o poder de habilidades Corrompidas.",
                effect_id="abyss_answers",
            ),
        ),
    )
)

register_set(
    EquipmentSet(
        id="duelo",
        nome="Juramento do Duelo",
        descricao="Relíquias de combatentes que tratavam cada luta como uma sentença.",
        bonuses=(
            SetBonus(
                2,
                "Sem Recuo",
                "+8% dano e +8% velocidade.",
                EquipmentModifiers(damage_mult=1.08, speed_mult=1.08),
            ),
            SetBonus(
                3,
                "Perfeição Cruel",
                "Parries e esquivas perfeitas acumulam dano crítico.",
                EquipmentModifiers(crit_damage_mult=1.18),
                effect_id="duelist_perfection",
            ),
        ),
    )
)


# ============================================================
# ITENS — ARMAS
# ============================================================

register_equipment(
    EquipmentDefinition(
        id="espada_sentinela",
        nome="Espada da Sentinela",
        descricao="Lâmina equilibrada feita para patrulheiros das Rupturas.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.INCOMUM,
        modifiers=EquipmentModifiers(damage_flat=6, hp_flat=8),
        allowed_classes=("guerreiro", "duelista", "guardiao_veu"),
        set_id="sentinela",
        tags=("sword", "melee"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="fenda_de_arkhon",
        nome="Fenda de Arkhon",
        descricao="A cada décimo impacto, a lâmina tenta rasgar o espaço.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.LENDARIA,
        modifiers=EquipmentModifiers(damage_flat=14, damage_mult=1.12, crit_chance=0.04),
        allowed_classes=("guerreiro", "duelista"),
        unique_effect="arkhon_tenth_rift",
        tags=("sword", "rift", "melee"),
        min_level=6,
    )
)

register_equipment(
    EquipmentDefinition(
        id="bastao_cinzas",
        nome="Bastão das Cinzas Arcanas",
        descricao="Conduz magia elemental com eficiência incomum.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(damage_flat=8, resource_cost_mult=0.94),
        allowed_classes=("mago", "oraculo", "cronista"),
        set_id="cinzas",
        tags=("staff", "magic", "elemental"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="cetro_estrela_morta",
        nome="Cetro da Estrela Morta",
        descricao="Sua ponta contém uma pequena massa arcana instável.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.MITICA,
        modifiers=EquipmentModifiers(damage_mult=1.27, cooldown_mult=0.91, resource_cost_mult=1.07),
        allowed_classes=("mago",),
        unique_effect="dead_star_overload",
        tags=("staff", "magic", "ultimate"),
        min_level=10,
    )
)

register_equipment(
    EquipmentDefinition(
        id="arco_cacador",
        nome="Arco do Caçador do Véu",
        descricao="Leve e silencioso, feito para perseguir alvos entre fendas.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(damage_flat=7, speed_flat=10, crit_chance=0.05),
        allowed_classes=("arqueiro",),
        set_id="cacador_veu",
        tags=("bow", "ranged", "precision"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="arco_horizonte_morto",
        nome="Horizonte Morto",
        descricao="Flechas disparadas por ele parecem desaparecer antes do impacto.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.LENDARIA,
        modifiers=EquipmentModifiers(damage_mult=1.17, crit_chance=0.09, crit_damage_mult=1.12),
        allowed_classes=("arqueiro",),
        unique_effect="horizon_pierce",
        tags=("bow", "rift", "pierce"),
        min_level=7,
    )
)

register_equipment(
    EquipmentDefinition(
        id="foice_ultimo_suspiro",
        nome="Foice do Último Suspiro",
        descricao="Vibra quando uma criatura próxima está à beira da morte.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.LENDARIA,
        modifiers=EquipmentModifiers(damage_mult=1.15, lifesteal=0.05),
        allowed_classes=("ceifador",),
        unique_effect="execution_threshold_up",
        tags=("scythe", "execute", "shadow"),
        min_level=6,
    )
)

register_equipment(
    EquipmentDefinition(
        id="fragmento_rasgado",
        nome="Fragmento Rasgado",
        descricao="Não parece uma arma. Ainda assim, reage à corrupção do portador.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.CORROMPIDA,
        modifiers=EquipmentModifiers(damage_mult=1.32, hp_mult=0.86, corruption_gain_mult=1.15),
        allowed_classes=("rasgado",),
        unique_effect="corruption_edge",
        tags=("void", "corruption", "risk"),
        min_level=5,
    )
)

register_equipment(
    EquipmentDefinition(
        id="agulha_segundo_perdido",
        nome="Agulha do Segundo Perdido",
        descricao="Uma lâmina curta que parece chegar ao alvo antes do movimento terminar.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(speed_flat=18, cooldown_mult=0.91, damage_flat=6),
        allowed_classes=("cronista", "duelista"),
        set_id="relogio_partido",
        tags=("temporal", "blade", "speed"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="nucleo_artifice",
        nome="Núcleo de Combate Mk.III",
        descricao="Centraliza energia para dispositivos e armas experimentais.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(damage_flat=9, cooldown_mult=0.90, resource_regen_mult=1.16),
        allowed_classes=("artifice",),
        unique_effect="deployable_overclock",
        tags=("technology", "deployable"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="lamina_juramento",
        nome="Lâmina do Juramento",
        descricao="Uma arma sem ornamentos. Cada marca nela representa um duelo vencido.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(damage_flat=9, crit_chance=0.07, speed_flat=8),
        allowed_classes=("duelista",),
        set_id="duelo",
        tags=("blade", "duel", "critical"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="olho_fendido",
        nome="Olho Fendido",
        descricao="Foco ritual usado para transformar presságios em ataques reais.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(damage_mult=1.13, cooldown_mult=0.94),
        allowed_classes=("oraculo",),
        unique_effect="marks_last_longer",
        tags=("curse", "mark", "focus"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="escudo_primeiro_veu",
        nome="Escudo do Primeiro Véu",
        descricao="Parte de uma barreira antiga convertida em arma defensiva.",
        slot=EquipmentSlot.ARMA,
        raridade=Rarity.LENDARIA,
        modifiers=EquipmentModifiers(hp_flat=28, hp_mult=1.08, damage_flat=5),
        allowed_classes=("guardiao_veu", "guerreiro"),
        unique_effect="barrier_retaliation",
        tags=("shield", "barrier", "tank"),
    )
)


# ============================================================
# ARMADURAS
# ============================================================

register_equipment(
    EquipmentDefinition(
        id="couraça_sentinela",
        nome="Couraça da Sentinela",
        descricao="Proteção reforçada contra impactos de criaturas de Ruptura.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(hp_flat=35, hp_mult=1.06, speed_flat=-5),
        set_id="sentinela",
        tags=("armor", "defense"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="manto_cinzas",
        nome="Manto das Cinzas Arcanas",
        descricao="Fibras queimadas por magia ainda carregam energia residual.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(hp_flat=12, resource_regen_mult=1.16, cooldown_mult=0.97),
        allowed_classes=("mago", "oraculo", "cronista"),
        set_id="cinzas",
        tags=("robe", "magic"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="manto_cacador",
        nome="Manto do Caçador do Véu",
        descricao="Quase não produz som mesmo durante movimentos bruscos.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(speed_flat=20, hp_flat=14),
        allowed_classes=("arqueiro", "duelista", "ceifador"),
        set_id="cacador_veu",
        tags=("light_armor", "mobility"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="casaco_relogio_partido",
        nome="Casaco do Relógio Partido",
        descricao="A barra do tecido oscila em ritmos diferentes do ambiente.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(speed_mult=1.06, cooldown_mult=0.95, hp_flat=10),
        allowed_classes=("cronista", "duelista"),
        set_id="relogio_partido",
        tags=("temporal", "mobility"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="pele_abismo",
        nome="Pele do Abismo",
        descricao="Não há certeza se isso ainda pode ser chamado de armadura.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.CORROMPIDA,
        modifiers=EquipmentModifiers(hp_mult=0.90, damage_mult=1.22, healing_mult=0.82),
        set_id="abismo",
        unique_effect="low_hp_void_aura",
        tags=("void", "corruption"),
        min_level=6,
    )
)

register_equipment(
    EquipmentDefinition(
        id="traje_duelo",
        nome="Traje do Juramento",
        descricao="Proteção mínima para não sacrificar movimento e leitura corporal.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(speed_mult=1.09, crit_chance=0.04, hp_flat=8),
        allowed_classes=("duelista",),
        set_id="duelo",
        tags=("duel", "mobility"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="bastiao_movel",
        nome="Bastião Móvel",
        descricao="Placas pesadas que respondem à energia de barreira.",
        slot=EquipmentSlot.ARMADURA,
        raridade=Rarity.LENDARIA,
        modifiers=EquipmentModifiers(hp_flat=55, hp_mult=1.13, speed_mult=0.92),
        allowed_classes=("guardiao_veu", "guerreiro"),
        unique_effect="barrier_hp_conversion",
        tags=("heavy_armor", "barrier"),
        min_level=7,
    )
)


# ============================================================
# ACESSÓRIOS
# ============================================================

register_equipment(
    EquipmentDefinition(
        id="selo_sentinela",
        nome="Selo da Sentinela",
        descricao="Marca de quem sobreviveu ao primeiro contato com o Véu.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.INCOMUM,
        modifiers=EquipmentModifiers(hp_flat=12, damage_flat=3),
        set_id="sentinela",
        tags=("relic",),
    )
)

register_equipment(
    EquipmentDefinition(
        id="brasas_arcanas",
        nome="Brasas Arcanas",
        descricao="Pequeno recipiente que nunca deixa a chama interna morrer.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(damage_mult=1.07, resource_regen_mult=1.10),
        allowed_classes=("mago", "oraculo", "cronista"),
        set_id="cinzas",
        tags=("magic", "fire"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="olho_cacador",
        nome="Olho do Caçador",
        descricao="Uma lente que destaca movimentos frágeis na postura do alvo.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(crit_chance=0.07, crit_damage_mult=1.08),
        set_id="cacador_veu",
        tags=("precision", "critical"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="ponteiro_quebrado",
        nome="Ponteiro Quebrado",
        descricao="Ainda se move mesmo sem relógio ao redor.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.RARA,
        modifiers=EquipmentModifiers(cooldown_mult=0.96, speed_flat=9),
        set_id="relogio_partido",
        tags=("temporal",),
    )
)

register_equipment(
    EquipmentDefinition(
        id="dente_abismo",
        nome="Dente do Abismo",
        descricao="Um fragmento orgânico que pulsa quando o portador está ferido.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.CORROMPIDA,
        modifiers=EquipmentModifiers(damage_mult=1.16, lifesteal=0.035, hp_mult=0.94),
        set_id="abismo",
        tags=("void", "lifesteal", "corruption"),
        min_level=5,
    )
)

register_equipment(
    EquipmentDefinition(
        id="moeda_duelista",
        nome="Moeda do Último Duelo",
        descricao="Uma face representa vitória. A outra nunca foi encontrada.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.EPICA,
        modifiers=EquipmentModifiers(crit_chance=0.06, speed_flat=8),
        set_id="duelo",
        tags=("duel", "critical"),
    )
)

register_equipment(
    EquipmentDefinition(
        id="fragmento_primeira_ruptura",
        nome="Fragmento da Primeira Ruptura",
        descricao="Relíquia extremamente rara que reage a qualquer classe.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.MITICA,
        modifiers=EquipmentModifiers(
            hp_mult=1.08,
            damage_mult=1.13,
            speed_mult=1.05,
            resource_regen_mult=1.10,
        ),
        unique_effect="first_rift_resonance",
        tags=("rift", "mythic", "universal"),
        min_level=9,
    )
)

register_equipment(
    EquipmentDefinition(
        id="coroa_sem_rei",
        nome="Coroa Sem Rei",
        descricao="O Véu não reconhece o dono original desta relíquia.",
        slot=EquipmentSlot.ACESSORIO,
        raridade=Rarity.LENDARIA,
        modifiers=EquipmentModifiers(damage_mult=1.10, hp_flat=18, cooldown_mult=0.95),
        unique_effect="elite_memory_bonus",
        tags=("memory", "elite", "universal"),
        min_level=8,
    )
)


# ============================================================
# INVENTÁRIO / INSTÂNCIAS
# ============================================================

def make_inventory_item(equipment_id: str, source: str = "loot") -> Dict[str, object]:
    if equipment_id not in EQUIPMENT_REGISTRY:
        raise ValueError(f"Equipamento inexistente: {equipment_id}")

    return {
        "instance_id": uuid.uuid4().hex[:12],
        "equipment_id": equipment_id,
        "source": source,
    }


def inventory_equipment_ids(state: PlayerState) -> List[str]:
    result: List[str] = []

    for entry in state.inventory:
        equipment_id = entry.get("equipment_id") if isinstance(entry, dict) else None
        if equipment_id in EQUIPMENT_REGISTRY:
            result.append(str(equipment_id))

    return result


def equipped_ids(state: PlayerState) -> List[str]:
    ids = [
        state.equipment.arma,
        state.equipment.armadura,
        state.equipment.acessorio_1,
        state.equipment.acessorio_2,
    ]
    return [item_id for item_id in ids if item_id in EQUIPMENT_REGISTRY]


def can_equip(state: PlayerState, equipment_id: str) -> Tuple[bool, str]:
    if equipment_id not in EQUIPMENT_REGISTRY:
        return False, "Equipamento desconhecido."

    item = EQUIPMENT_REGISTRY[equipment_id]
    class_id = state.identity.class_id

    if item.allowed_classes and class_id not in item.allowed_classes:
        return False, f"{CLASS_REGISTRY[class_id].nome} não pode usar este item."

    if class_id in item.forbidden_classes:
        return False, f"{CLASS_REGISTRY[class_id].nome} não pode usar este item."

    if state.stats.nivel < item.min_level:
        return False, f"Requer nível {item.min_level}."

    return True, "OK"


def equip_item(state: PlayerState, equipment_id: str) -> Tuple[bool, str]:
    allowed, reason = can_equip(state, equipment_id)
    if not allowed:
        return False, reason

    if equipment_id not in inventory_equipment_ids(state):
        return False, "O item não está no inventário."

    item = EQUIPMENT_REGISTRY[equipment_id]

    if item.slot == EquipmentSlot.ARMA:
        state.equipment.arma = equipment_id

    elif item.slot == EquipmentSlot.ARMADURA:
        state.equipment.armadura = equipment_id

    else:
        # Primeiro espaço livre; se ambos ocupados, substitui o primeiro.
        if not state.equipment.acessorio_1:
            state.equipment.acessorio_1 = equipment_id
        elif not state.equipment.acessorio_2:
            state.equipment.acessorio_2 = equipment_id
        elif state.equipment.acessorio_1 == equipment_id or state.equipment.acessorio_2 == equipment_id:
            return True, "Já equipado."
        else:
            state.equipment.acessorio_1 = equipment_id

    return True, f"{item.nome} equipado."


def unequip_slot(state: PlayerState, slot_name: str) -> bool:
    if not hasattr(state.equipment, slot_name):
        return False
    setattr(state.equipment, slot_name, None)
    return True


# ============================================================
# BÔNUS / SINERGIAS DE EQUIPAMENTO
# ============================================================

def active_set_counts(state: PlayerState) -> Dict[str, int]:
    counts: Dict[str, int] = {}

    for item_id in equipped_ids(state):
        item = EQUIPMENT_REGISTRY[item_id]
        if item.set_id:
            counts[item.set_id] = counts.get(item.set_id, 0) + 1

    return counts


def active_set_bonuses(state: PlayerState) -> List[Tuple[EquipmentSet, SetBonus]]:
    counts = active_set_counts(state)
    result: List[Tuple[EquipmentSet, SetBonus]] = []

    for set_id, count in counts.items():
        item_set = EQUIPMENT_SETS.get(set_id)
        if not item_set:
            continue

        for bonus in item_set.bonuses:
            if count >= bonus.pieces:
                result.append((item_set, bonus))

    return result


def equipment_modifiers(state: PlayerState) -> EquipmentModifiers:
    total = EquipmentModifiers()

    for item_id in equipped_ids(state):
        total = total.merged(EQUIPMENT_REGISTRY[item_id].modifiers)

    for _, bonus in active_set_bonuses(state):
        total = total.merged(bonus.modifiers)

    return total


def active_unique_effects(state: PlayerState) -> Set[str]:
    result: Set[str] = set()

    for item_id in equipped_ids(state):
        effect = EQUIPMENT_REGISTRY[item_id].unique_effect
        if effect:
            result.add(effect)

    for _, bonus in active_set_bonuses(state):
        if bonus.effect_id:
            result.add(bonus.effect_id)

    return result


# ============================================================
# LOOT
# ============================================================

def rarity_loot_weight(rarity: Rarity, luck: float, elite: bool, boss: bool) -> float:
    base = RARITY_INFO[rarity].weight
    order = RARITY_INFO[rarity].display_order

    # Para loot, elites e bosses deslocam peso em direção ao topo.
    multiplier = 1.0 + max(0.0, luck) * max(0, order - 1) * 0.23

    if elite:
        multiplier *= 1.0 + max(0, order - 2) * 0.12

    if boss:
        multiplier *= 1.0 + max(0, order - 1) * 0.28

    # Reduz Comum em boss para não gerar recompensa anticlimática.
    if boss and rarity == Rarity.COMUM:
        multiplier *= 0.08
    elif boss and rarity == Rarity.INCOMUM:
        multiplier *= 0.35

    return max(0.001, base * multiplier)


def eligible_equipment(state: PlayerState) -> List[EquipmentDefinition]:
    result = []

    for item in EQUIPMENT_REGISTRY.values():
        allowed, _ = can_equip(state, item.id)
        if allowed:
            result.append(item)

    return result


def roll_equipment_drop(
    state: PlayerState,
    *,
    elite: bool = False,
    boss: bool = False,
    luck: float = 0.0,
) -> Optional[EquipmentDefinition]:
    pool = eligible_equipment(state)
    if not pool:
        return None

    # Chance de um inimigo gerar equipamento.
    chance = 0.035
    if elite:
        chance = 0.18
    if boss:
        chance = 1.0

    chance *= 1.0 + max(0.0, luck) * 0.35

    if random.random() > chance:
        return None

    weights = [
        rarity_loot_weight(item.raridade, luck, elite, boss)
        for item in pool
    ]

    return random.choices(pool, weights=weights, k=1)[0]


# ============================================================
# DESBLOQUEIO DE CLASSES
# ============================================================

@dataclass(frozen=True)
class ClassUnlockRule:
    class_id: str
    titulo: str
    descricao: str

    def check(self, state: PlayerState) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class BossUnlockRule(ClassUnlockRule):
    boss_id: str = ""

    def check(self, state: PlayerState) -> bool:
        return self.boss_id in state.progression.bosses_derrotados


@dataclass(frozen=True)
class RiftUnlockRule(ClassUnlockRule):
    required_rifts: Tuple[str, ...] = ()
    minimum_level: int = 1

    def check(self, state: PlayerState) -> bool:
        return (
            state.stats.nivel >= self.minimum_level
            and set(self.required_rifts).issubset(state.progression.rupturas_descobertas)
        )


@dataclass(frozen=True)
class SkillUnlockRule(ClassUnlockRule):
    required_skill_ids: Tuple[str, ...] = ()
    minimum_mastery: int = 1
    required_rifts: Tuple[str, ...] = ()

    def check(self, state: PlayerState) -> bool:
        if not set(self.required_skill_ids).issubset(state.owned_skills):
            return False

        if not set(self.required_rifts).issubset(state.progression.rupturas_descobertas):
            return False

        for skill_id in self.required_skill_ids:
            mastery = state.masteries.get(skill_id)
            if mastery is None or mastery.nivel < self.minimum_mastery:
                return False

        return True


@dataclass(frozen=True)
class CorruptionUnlockRule(ClassUnlockRule):
    minimum_level: int = 1
    void_required: bool = True

    def check(self, state: PlayerState) -> bool:
        corrupted_owned = any(
            skill_id in SKILL_REGISTRY and SKILL_REGISTRY[skill_id].corrupted
            for skill_id in state.owned_skills
        )

        has_void = (
            not self.void_required
            or "vazio" in state.progression.rupturas_descobertas
        )

        return state.stats.nivel >= self.minimum_level and corrupted_owned and has_void


@dataclass(frozen=True)
class CollectionUnlockRule(ClassUnlockRule):
    minimum_equipment: int = 0
    minimum_rifts: int = 0
    minimum_level: int = 1

    def check(self, state: PlayerState) -> bool:
        return (
            state.stats.nivel >= self.minimum_level
            and len(set(inventory_equipment_ids(state))) >= self.minimum_equipment
            and len(state.progression.rupturas_descobertas) >= self.minimum_rifts
        )


CLASS_UNLOCK_RULES: Tuple[ClassUnlockRule, ...] = (
    BossUnlockRule(
        class_id="ceifador",
        titulo="O ÚLTIMO SUSPIRO",
        descricao="Derrote o Guardião da Primeira Ruptura.",
        boss_id="guardiao_primeira_ruptura",
    ),
    CorruptionUnlockRule(
        class_id="rasgado",
        titulo="DEIXE O VÉU ENTRAR",
        descricao="Descubra a Ruptura do Vazio e carregue uma habilidade Corrompida.",
        minimum_level=5,
    ),
    RiftUnlockRule(
        class_id="cronista",
        titulo="UM SEGUNDO QUE NÃO EXISTIU",
        descricao="Alcance nível 6 após descobrir a Ruptura Temporal.",
        required_rifts=("temporal",),
        minimum_level=6,
    ),
    CollectionUnlockRule(
        class_id="artifice",
        titulo="ENGENHARIA DO IMPOSSÍVEL",
        descricao="Colete 6 equipamentos diferentes e descubra 2 Rupturas.",
        minimum_equipment=6,
        minimum_rifts=2,
        minimum_level=5,
    ),
    SkillUnlockRule(
        class_id="duelista",
        titulo="SEM UM PASSO EM FALSO",
        descricao="Eleve Corte Crescente a maestria 3 e derrote o primeiro Guardião.",
        required_skill_ids=("corte_crescente",),
        minimum_mastery=3,
    ),
    RiftUnlockRule(
        class_id="oraculo",
        titulo="VOCÊ JÁ VIU DEMAIS",
        descricao="Descubra 4 tipos diferentes de Ruptura e alcance nível 7.",
        required_rifts=("carmesim", "temporal", "vazio", "instavel"),
        minimum_level=7,
    ),
    CollectionUnlockRule(
        class_id="guardiao_veu",
        titulo="A MURALHA RESPONDE",
        descricao="Alcance nível 10, derrote o primeiro Guardião e reúna 8 equipamentos.",
        minimum_equipment=8,
        minimum_rifts=1,
        minimum_level=10,
    ),
)


def rule_for_class(class_id: str) -> Optional[ClassUnlockRule]:
    for rule in CLASS_UNLOCK_RULES:
        if rule.class_id == class_id:
            return rule
    return None


def evaluate_class_unlocks(state: PlayerState) -> List[str]:
    newly_unlocked: List[str] = []

    for rule in CLASS_UNLOCK_RULES:
        if rule.class_id in state.progression.classes_desbloqueadas:
            continue

        extra_ok = True
        if rule.class_id == "duelista":
            extra_ok = "guardiao_primeira_ruptura" in state.progression.bosses_derrotados
        elif rule.class_id == "guardiao_veu":
            extra_ok = "guardiao_primeira_ruptura" in state.progression.bosses_derrotados

        if extra_ok and rule.check(state):
            state.unlock_class(rule.class_id)
            newly_unlocked.append(rule.class_id)

    return newly_unlocked


# ============================================================
# PROGRESSÃO ENTRE PERSONAGENS
# ============================================================

def transfer_meta_progression(previous: PlayerState, new_state: PlayerState) -> PlayerState:
    """
    Novo personagem mantém descobertas e desbloqueios globais,
    mas não herda build, inventário equipado, maestrias ou Memória do Véu.
    """

    new_state.progression.classes_desbloqueadas = set(
        previous.progression.classes_desbloqueadas
    )
    new_state.progression.bosses_derrotados = set(
        previous.progression.bosses_derrotados
    )
    new_state.progression.rupturas_descobertas = set(
        previous.progression.rupturas_descobertas
    )
    new_state.progression.eventos_concluidos = set(
        previous.progression.eventos_concluidos
    )
    new_state.progression.itens_importantes = set(
        previous.progression.itens_importantes
    )
    new_state.progression.bestiario = copy.deepcopy(
        previous.progression.bestiario
    )

    # Campanha, regiões, NPCs e missões são metaprogressão do mundo.
    # Um novo personagem volta ao Refúgio sem herdar um contrato ativo.
    new_state.campaign = copy.deepcopy(previous.campaign)
    if isinstance(new_state.campaign, dict):
        new_state.campaign["current_region"] = "refugio_ultima_luz"
        new_state.campaign["selected_contract"] = None

    return new_state


# ============================================================
# DEBUG / TESTES
# ============================================================

def content_summary() -> Dict[str, int]:
    return {
        "equipment": len(EQUIPMENT_REGISTRY),
        "sets": len(EQUIPMENT_SETS),
        "unlock_rules": len(CLASS_UNLOCK_RULES),
    }

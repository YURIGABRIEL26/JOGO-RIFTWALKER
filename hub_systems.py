"""
RIFTWALKER — HUB / ECONOMY SYSTEMS 0.5
======================================

Camada independente de renderização para:
- Refúgio da Última Luz
- moedas e materiais
- consumíveis
- lojas e estoque rotativo
- compra / venda / desmontagem
- crafting
- instalações e upgrades do Refúgio
- preparação de expedições
- contratos e regiões
- registro de transações

Objetivo de arquitetura:
O Refúgio precisa ser um sistema estratégico do Action RPG, não apenas um
menu de +5 dano. Toda função abaixo pode ser testada sem abrir Pygame.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core_systems import PlayerState, Rarity
from content_systems import (
    EQUIPMENT_REGISTRY,
    EquipmentDefinition,
    EquipmentSlot,
    inventory_equipment_ids,
    make_inventory_item,
)
from narrative_systems import CampaignDirector, CONTRACTS, REGIONS, ensure_campaign_state


# ============================================================
# ENUMS / MODELOS
# ============================================================

class Currency(str, Enum):
    OURO = "ouro"
    ECOS = "ecos"


class VendorType(str, Enum):
    FERREIRO = "ferreiro"
    BOTICARIA = "boticaria"
    CARTOGRAFO = "cartografo"
    RELIQUIARIO = "reliquiario"


class FacilityId(str, Enum):
    FORJA = "forja"
    ENFERMARIA = "enfermaria"
    ARQUIVO = "arquivo"
    CARTOGRAFIA = "cartografia"
    ESTABILIZADOR = "estabilizador"


class TransactionType(str, Enum):
    COMPRA = "compra"
    VENDA = "venda"
    CRAFT = "craft"
    DESMONTAGEM = "desmontagem"
    UPGRADE_REFUGIO = "upgrade_refugio"
    RECOMPENSA = "recompensa"
    EXPEDICAO = "expedicao"


class CraftOutputType(str, Enum):
    EQUIPMENT = "equipment"
    CONSUMABLE = "consumable"
    MATERIAL = "material"


# ============================================================
# MATERIAIS
# ============================================================

@dataclass(frozen=True)
class MaterialDefinition:
    id: str
    nome: str
    descricao: str
    valor_base: int
    rarity_hint: str
    tags: Tuple[str, ...] = ()


MATERIALS: Dict[str, MaterialDefinition] = {}


def register_material(definition: MaterialDefinition) -> MaterialDefinition:
    if definition.id in MATERIALS:
        raise ValueError(f"Material duplicado: {definition.id}")
    MATERIALS[definition.id] = definition
    return definition


register_material(MaterialDefinition(
    "po_do_veu", "Pó do Véu",
    "Resíduo comum deixado por criaturas tocadas por Rupturas.",
    8, "Comum", ("veil", "basic"),
))
register_material(MaterialDefinition(
    "fragmento_carmesim", "Fragmento Carmesim",
    "Cristal quente formado em Rupturas violentas.",
    24, "Incomum", ("carmesim", "offense"),
))
register_material(MaterialDefinition(
    "fibra_temporal", "Fibra Temporal",
    "Matéria que parece chegar um instante antes de ser tocada.",
    32, "Rara", ("temporal", "cooldown"),
))
register_material(MaterialDefinition(
    "cinza_arcana", "Cinza Arcana",
    "Restos de magia condensada após colapso elemental.",
    28, "Rara", ("arcane", "magic"),
))
register_material(MaterialDefinition(
    "nucleo_instavel", "Núcleo Instável",
    "Concentração perigosa de energia de Ruptura.",
    55, "Épica", ("rift", "unstable"),
))
register_material(MaterialDefinition(
    "eco_predador", "Eco Predador",
    "Memória solidificada de uma criatura superior.",
    80, "Lendária", ("memory", "elite"),
))
register_material(MaterialDefinition(
    "vidro_do_vazio", "Vidro do Vazio",
    "Superfície negra que reflete lugares que não existem.",
    95, "Lendária", ("void", "rare"),
))
register_material(MaterialDefinition(
    "coracao_fraturado", "Coração Fraturado",
    "Núcleo raríssimo arrancado de uma Ruptura estabilizada.",
    180, "Mítica", ("rift", "mythic"),
))


# ============================================================
# CONSUMÍVEIS
# ============================================================

@dataclass(frozen=True)
class ConsumableDefinition:
    id: str
    nome: str
    descricao: str
    preco_base: int
    max_stack: int
    expedition_only: bool = True
    tags: Tuple[str, ...] = ()


CONSUMABLES: Dict[str, ConsumableDefinition] = {}


def register_consumable(definition: ConsumableDefinition) -> ConsumableDefinition:
    if definition.id in CONSUMABLES:
        raise ValueError(f"Consumível duplicado: {definition.id}")
    CONSUMABLES[definition.id] = definition
    return definition


register_consumable(ConsumableDefinition(
    "frasco_vital", "Frasco Vital",
    "Recupera parte da vida durante uma expedição.", 55, 5,
    tags=("healing",),
))
register_consumable(ConsumableDefinition(
    "tonico_fluxo", "Tônico de Fluxo",
    "Acelera regeneração do recurso da classe por curto período.", 62, 5,
    tags=("resource",),
))
register_consumable(ConsumableDefinition(
    "sal_estabilizador", "Sal Estabilizador",
    "Reduz temporariamente um efeito negativo de Ruptura.", 90, 3,
    tags=("rift", "defense"),
))
register_consumable(ConsumableDefinition(
    "sinalizador_eco", "Sinalizador de Eco",
    "Aumenta a chance de encontrar evento ou elite especial.", 110, 3,
    tags=("exploration", "elite"),
))
register_consumable(ConsumableDefinition(
    "pedra_retorno", "Pedra de Retorno",
    "Permite abandonar uma expedição em ponto seguro sem perder tudo.", 160, 1,
    tags=("escape", "rare"),
))
register_consumable(ConsumableDefinition(
    "oleo_carmesim", "Óleo Carmesim",
    "Aumenta dano por pouco tempo, mas também dano recebido.", 75, 3,
    tags=("risk", "damage"),
))
register_consumable(ConsumableDefinition(
    "agulha_temporal", "Agulha Temporal",
    "Reduz imediatamente parte do maior cooldown ativo.", 135, 2,
    tags=("temporal", "cooldown"),
))
register_consumable(ConsumableDefinition(
    "selo_memoria", "Selo de Memória",
    "Protege uma recompensa escolhida contra perda em uma morte.", 220, 1,
    tags=("memory", "insurance"),
))


# ============================================================
# ESTADO DO REFÚGIO
# ============================================================

DEFAULT_HUB_STATE: Dict[str, Any] = {
    "ecos": 0,
    "materials": {},
    "consumables": {},
    "facilities": {
        FacilityId.FORJA.value: 1,
        FacilityId.ENFERMARIA.value: 1,
        FacilityId.ARQUIVO.value: 1,
        FacilityId.CARTOGRAFIA.value: 1,
        FacilityId.ESTABILIZADOR.value: 1,
    },
    "vendor_reputation": {},
    "market_cycle": 0,
    "market_seed": 731947,
    "shop_stock": {},
    "craft_counts": {},
    "transaction_log": [],
    "prepared_expedition": None,
    "expedition_history": [],
    "lifetime_gold_spent": 0,
    "lifetime_gold_earned": 0,
    "lifetime_salvaged": 0,
}


def ensure_hub_state(state: PlayerState) -> Dict[str, Any]:
    campaign = ensure_campaign_state(state)
    hub = campaign.get("hub")

    if not isinstance(hub, dict):
        hub = {}
        campaign["hub"] = hub

    for key, default in DEFAULT_HUB_STATE.items():
        if key in hub:
            continue
        if isinstance(default, dict):
            hub[key] = dict(default)
        elif isinstance(default, list):
            hub[key] = list(default)
        else:
            hub[key] = default

    for key in ("materials", "consumables", "facilities", "vendor_reputation", "shop_stock", "craft_counts"):
        if not isinstance(hub.get(key), dict):
            hub[key] = {}

    for key in ("transaction_log", "expedition_history"):
        if not isinstance(hub.get(key), list):
            hub[key] = []

    for material_id in MATERIALS:
        hub["materials"].setdefault(material_id, 0)

    for consumable_id in CONSUMABLES:
        hub["consumables"].setdefault(consumable_id, 0)

    for facility in FacilityId:
        hub["facilities"].setdefault(facility.value, 1)

    return hub


# ============================================================
# WALLET / LEDGER
# ============================================================

def gold(state: PlayerState) -> int:
    return max(0, int(state.stats.ouro))


def echoes(state: PlayerState) -> int:
    return max(0, int(ensure_hub_state(state).get("ecos", 0)))


def add_gold(state: PlayerState, amount: int, source: str = "system") -> int:
    amount = max(0, int(amount))
    state.stats.ouro = gold(state) + amount
    hub = ensure_hub_state(state)
    hub["lifetime_gold_earned"] = int(hub.get("lifetime_gold_earned", 0)) + amount
    _log_transaction(state, TransactionType.RECOMPENSA, amount, source)
    return state.stats.ouro


def spend_gold(state: PlayerState, amount: int, reason: str = "purchase") -> bool:
    amount = max(0, int(amount))
    if gold(state) < amount:
        return False
    state.stats.ouro -= amount
    hub = ensure_hub_state(state)
    hub["lifetime_gold_spent"] = int(hub.get("lifetime_gold_spent", 0)) + amount
    return True


def add_echoes(state: PlayerState, amount: int) -> int:
    hub = ensure_hub_state(state)
    hub["ecos"] = max(0, int(hub.get("ecos", 0)) + int(amount))
    return int(hub["ecos"])


def material_count(state: PlayerState, material_id: str) -> int:
    if material_id not in MATERIALS:
        return 0
    return max(0, int(ensure_hub_state(state)["materials"].get(material_id, 0)))


def add_material(state: PlayerState, material_id: str, amount: int) -> int:
    if material_id not in MATERIALS:
        raise ValueError(f"Material desconhecido: {material_id}")
    hub = ensure_hub_state(state)
    hub["materials"][material_id] = max(
        0,
        int(hub["materials"].get(material_id, 0)) + int(amount),
    )
    return int(hub["materials"][material_id])


def spend_materials(state: PlayerState, costs: Dict[str, int]) -> bool:
    for material_id, amount in costs.items():
        if material_count(state, material_id) < int(amount):
            return False

    hub = ensure_hub_state(state)
    for material_id, amount in costs.items():
        hub["materials"][material_id] -= int(amount)
    return True


def consumable_count(state: PlayerState, consumable_id: str) -> int:
    if consumable_id not in CONSUMABLES:
        return 0
    return max(0, int(ensure_hub_state(state)["consumables"].get(consumable_id, 0)))


def add_consumable(state: PlayerState, consumable_id: str, amount: int = 1) -> int:
    if consumable_id not in CONSUMABLES:
        raise ValueError(f"Consumível desconhecido: {consumable_id}")

    definition = CONSUMABLES[consumable_id]
    hub = ensure_hub_state(state)
    new_value = min(
        definition.max_stack,
        consumable_count(state, consumable_id) + max(0, int(amount)),
    )
    hub["consumables"][consumable_id] = new_value
    return new_value


def consume_consumable(state: PlayerState, consumable_id: str, amount: int = 1) -> bool:
    amount = max(1, int(amount))
    if consumable_count(state, consumable_id) < amount:
        return False
    hub = ensure_hub_state(state)
    hub["consumables"][consumable_id] -= amount
    return True


def _log_transaction(
    state: PlayerState,
    transaction_type: TransactionType,
    amount: int,
    detail: str,
) -> None:
    hub = ensure_hub_state(state)
    log = hub["transaction_log"]
    log.append({
        "type": transaction_type.value,
        "amount": int(amount),
        "detail": str(detail),
        "cycle": int(hub.get("market_cycle", 0)),
    })
    if len(log) > 80:
        del log[:-80]


# ============================================================
# INSTALAÇÕES DO REFÚGIO
# ============================================================

@dataclass(frozen=True)
class FacilityLevel:
    level: int
    gold_cost: int
    material_costs: Tuple[Tuple[str, int], ...]
    description: str

    def costs_dict(self) -> Dict[str, int]:
        return dict(self.material_costs)


@dataclass(frozen=True)
class FacilityDefinition:
    id: FacilityId
    nome: str
    descricao: str
    levels: Tuple[FacilityLevel, ...]


FACILITIES: Dict[str, FacilityDefinition] = {}


def register_facility(definition: FacilityDefinition) -> FacilityDefinition:
    FACILITIES[definition.id.value] = definition
    return definition


register_facility(FacilityDefinition(
    FacilityId.FORJA,
    "Forja da Última Luz",
    "Crafting, desmontagem e manutenção de equipamentos.",
    (
        FacilityLevel(1, 0, (), "Permite crafting básico e desmontagem."),
        FacilityLevel(2, 450, (("po_do_veu", 18), ("fragmento_carmesim", 4)), "-6% custo de crafting em ouro."),
        FacilityLevel(3, 1100, (("po_do_veu", 35), ("cinza_arcana", 10), ("nucleo_instavel", 2)), "Desbloqueia receitas Épicas e +10% material de desmontagem."),
        FacilityLevel(4, 2600, (("nucleo_instavel", 8), ("eco_predador", 3)), "Desbloqueia receitas Lendárias e reforja especial."),
        FacilityLevel(5, 6000, (("coracao_fraturado", 2), ("vidro_do_vazio", 6)), "Permite projetos Míticos e reduz custo total em 15%."),
    ),
))

register_facility(FacilityDefinition(
    FacilityId.ENFERMARIA,
    "Enfermaria do Refúgio",
    "Recuperação, consumíveis e preparação de sobrevivência.",
    (
        FacilityLevel(1, 0, (), "3 espaços de suprimentos por expedição."),
        FacilityLevel(2, 380, (("po_do_veu", 16),), "4 espaços de suprimentos."),
        FacilityLevel(3, 900, (("po_do_veu", 28), ("cinza_arcana", 6)), "5 espaços e frascos mais eficientes."),
        FacilityLevel(4, 2200, (("nucleo_instavel", 5), ("fibra_temporal", 8)), "6 espaços e recuperação melhor ao retornar."),
        FacilityLevel(5, 5200, (("coracao_fraturado", 1), ("eco_predador", 5)), "7 espaços e uma proteção de emergência por expedição."),
    ),
))

register_facility(FacilityDefinition(
    FacilityId.ARQUIVO,
    "Arquivo do Véu",
    "Registra criaturas, memórias, Rupturas e conhecimento recuperado.",
    (
        FacilityLevel(1, 0, (), "Mostra informações básicas do bestiário."),
        FacilityLevel(2, 500, (("po_do_veu", 20), ("fibra_temporal", 3)), "Revela fraquezas de inimigos já estudados."),
        FacilityLevel(3, 1250, (("eco_predador", 2), ("cinza_arcana", 8)), "Exibe nível de Memória do Véu antes de reencontros."),
        FacilityLevel(4, 3000, (("eco_predador", 5), ("vidro_do_vazio", 3)), "Revela possíveis estratégias adaptativas."),
        FacilityLevel(5, 7000, (("coracao_fraturado", 2), ("eco_predador", 8)), "Permite pesquisar ecos raros e pistas de classes secretas."),
    ),
))

register_facility(FacilityDefinition(
    FacilityId.CARTOGRAFIA,
    "Mesa de Cartografia",
    "Mapas, contratos, rotas e leitura de instabilidade regional.",
    (
        FacilityLevel(1, 0, (), "Mostra contratos e regiões desbloqueadas."),
        FacilityLevel(2, 420, (("po_do_veu", 15), ("fibra_temporal", 4)), "+4% qualidade de loot em expedições."),
        FacilityLevel(3, 1000, (("fibra_temporal", 9), ("nucleo_instavel", 2)), "Mostra uma previsão de evento possível."),
        FacilityLevel(4, 2400, (("nucleo_instavel", 6), ("vidro_do_vazio", 2)), "+10% qualidade de loot e contratos extras."),
        FacilityLevel(5, 5800, (("coracao_fraturado", 1), ("fibra_temporal", 18)), "Permite rotas especiais e expedições de alto risco."),
    ),
))

register_facility(FacilityDefinition(
    FacilityId.ESTABILIZADOR,
    "Estabilizador de Portais",
    "Controla quanto da instabilidade acompanha o jogador para uma região.",
    (
        FacilityLevel(1, 0, (), "Expedições normais."),
        FacilityLevel(2, 650, (("po_do_veu", 20), ("nucleo_instavel", 2)), "Permite levar 1 proteção contra Ruptura."),
        FacilityLevel(3, 1600, (("nucleo_instavel", 5), ("fibra_temporal", 6)), "Melhora recompensa ao aceitar múltiplas Rupturas."),
        FacilityLevel(4, 3600, (("vidro_do_vazio", 5), ("eco_predador", 4)), "Permite expedições com instabilidade extrema."),
        FacilityLevel(5, 8500, (("coracao_fraturado", 3), ("vidro_do_vazio", 8)), "Acesso a rotas que normalmente colapsariam."),
    ),
))


def facility_level(state: PlayerState, facility_id: str) -> int:
    ensure_hub_state(state)
    if facility_id not in FACILITIES:
        return 0
    return max(1, int(ensure_hub_state(state)["facilities"].get(facility_id, 1)))


def max_facility_level(facility_id: str) -> int:
    definition = FACILITIES[facility_id]
    return max(level.level for level in definition.levels)


def upgrade_facility(state: PlayerState, facility_id: str) -> Tuple[bool, str]:
    if facility_id not in FACILITIES:
        return False, "Instalação desconhecida."

    current = facility_level(state, facility_id)
    definition = FACILITIES[facility_id]
    target_level = current + 1

    level_def = next((x for x in definition.levels if x.level == target_level), None)
    if level_def is None:
        return False, "Instalação já está no nível máximo."

    if gold(state) < level_def.gold_cost:
        return False, f"Ouro insuficiente: {level_def.gold_cost}."

    for material_id, amount in level_def.material_costs:
        if material_count(state, material_id) < amount:
            return False, f"Falta {MATERIALS[material_id].nome}: {amount}."

    if not spend_gold(state, level_def.gold_cost, f"upgrade:{facility_id}"):
        return False, "Ouro insuficiente."

    spend_materials(state, level_def.costs_dict())
    ensure_hub_state(state)["facilities"][facility_id] = target_level
    _log_transaction(state, TransactionType.UPGRADE_REFUGIO, level_def.gold_cost, f"{facility_id}:{target_level}")
    return True, f"{definition.nome} agora está no nível {target_level}."


def facility_effects(state: PlayerState) -> Dict[str, float]:
    forge = facility_level(state, FacilityId.FORJA.value)
    infirmary = facility_level(state, FacilityId.ENFERMARIA.value)
    archive = facility_level(state, FacilityId.ARQUIVO.value)
    cartography = facility_level(state, FacilityId.CARTOGRAFIA.value)
    stabilizer = facility_level(state, FacilityId.ESTABILIZADOR.value)

    craft_discount = {1: 0.00, 2: 0.06, 3: 0.09, 4: 0.12, 5: 0.15}[forge]
    salvage_bonus = {1: 1.00, 2: 1.00, 3: 1.10, 4: 1.15, 5: 1.20}[forge]
    supply_slots = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7}[infirmary]
    loot_luck = {1: 0.00, 2: 0.04, 3: 0.06, 4: 0.10, 5: 0.14}[cartography]
    memory_intel = float(max(0, archive - 1))
    rift_control = float(max(0, stabilizer - 1))

    return {
        "craft_discount": craft_discount,
        "salvage_bonus": salvage_bonus,
        "supply_slots": float(supply_slots),
        "loot_luck": loot_luck,
        "memory_intel": memory_intel,
        "rift_control": rift_control,
    }


# ============================================================
# CRAFTING
# ============================================================

@dataclass(frozen=True)
class CraftRecipe:
    id: str
    nome: str
    output_type: CraftOutputType
    output_id: str
    output_amount: int
    gold_cost: int
    material_costs: Tuple[Tuple[str, int], ...]
    required_forge_level: int = 1
    required_flag: Optional[str] = None
    one_time: bool = False
    descricao: str = ""

    def costs_dict(self) -> Dict[str, int]:
        return dict(self.material_costs)


RECIPES: Dict[str, CraftRecipe] = {}


def register_recipe(recipe: CraftRecipe) -> CraftRecipe:
    if recipe.id in RECIPES:
        raise ValueError(f"Receita duplicada: {recipe.id}")
    if recipe.output_type == CraftOutputType.EQUIPMENT and recipe.output_id not in EQUIPMENT_REGISTRY:
        raise ValueError(f"Receita {recipe.id}: equipamento inexistente {recipe.output_id}")
    if recipe.output_type == CraftOutputType.CONSUMABLE and recipe.output_id not in CONSUMABLES:
        raise ValueError(f"Receita {recipe.id}: consumível inexistente {recipe.output_id}")
    if recipe.output_type == CraftOutputType.MATERIAL and recipe.output_id not in MATERIALS:
        raise ValueError(f"Receita {recipe.id}: material inexistente {recipe.output_id}")
    RECIPES[recipe.id] = recipe
    return recipe


# Consumíveis básicos
register_recipe(CraftRecipe(
    "craft_frasco_vital", "Preparar Frasco Vital",
    CraftOutputType.CONSUMABLE, "frasco_vital", 1, 20,
    (("po_do_veu", 3),), 1,
    descricao="Uma solução estável para emergências.",
))
register_recipe(CraftRecipe(
    "craft_tonico_fluxo", "Preparar Tônico de Fluxo",
    CraftOutputType.CONSUMABLE, "tonico_fluxo", 1, 28,
    (("po_do_veu", 2), ("cinza_arcana", 1)), 1,
))
register_recipe(CraftRecipe(
    "craft_sal_estabilizador", "Refinar Sal Estabilizador",
    CraftOutputType.CONSUMABLE, "sal_estabilizador", 1, 45,
    (("po_do_veu", 3), ("nucleo_instavel", 1)), 2,
))
register_recipe(CraftRecipe(
    "craft_agulha_temporal", "Montar Agulha Temporal",
    CraftOutputType.CONSUMABLE, "agulha_temporal", 1, 80,
    (("fibra_temporal", 3), ("cinza_arcana", 2)), 3,
))
register_recipe(CraftRecipe(
    "craft_selo_memoria", "Gravar Selo de Memória",
    CraftOutputType.CONSUMABLE, "selo_memoria", 1, 140,
    (("eco_predador", 1), ("vidro_do_vazio", 1)), 4,
))

# Equipamentos existentes escolhidos por ID conhecido do content_systems.
# As verificações só registram se o item existir, evitando quebrar futuras revisões.
_OPTIONAL_EQUIPMENT_RECIPES = (
    ("craft_espada_sentinela", "Forjar Espada da Sentinela", "espada_sentinela", 180, (("po_do_veu", 8), ("fragmento_carmesim", 2)), 1),
    ("craft_manto_cinzas", "Costurar Manto das Cinzas", "manto_cinzas", 260, (("cinza_arcana", 6), ("po_do_veu", 6)), 2),
    ("craft_arco_cacador_veu", "Montar Arco do Caçador", "arco_cacador_veu", 320, (("fibra_temporal", 5), ("po_do_veu", 10)), 2),
    ("craft_relogio_partido", "Reconstruir Relógio Partido", "relogio_partido", 650, (("fibra_temporal", 10), ("nucleo_instavel", 3)), 3),
    ("craft_coroa_sem_rei", "Recompor Coroa Sem Rei", "coroa_sem_rei", 1250, (("eco_predador", 3), ("vidro_do_vazio", 2)), 4),
    ("craft_fragmento_primeira_ruptura", "Estabilizar Fragmento da Primeira Ruptura", "fragmento_primeira_ruptura", 2600, (("coracao_fraturado", 1), ("vidro_do_vazio", 5), ("nucleo_instavel", 8)), 5),
)

for rid, rname, equipment_id, gcost, mats, lvl in _OPTIONAL_EQUIPMENT_RECIPES:
    if equipment_id in EQUIPMENT_REGISTRY:
        register_recipe(CraftRecipe(
            rid, rname, CraftOutputType.EQUIPMENT, equipment_id, 1,
            gcost, mats, lvl,
        ))


def recipe_available(state: PlayerState, recipe: CraftRecipe) -> Tuple[bool, str]:
    forge = facility_level(state, FacilityId.FORJA.value)
    if forge < recipe.required_forge_level:
        return False, f"Requer Forja nível {recipe.required_forge_level}."

    flags = set(ensure_campaign_state(state).get("flags", []))
    if recipe.required_flag and recipe.required_flag not in flags:
        return False, "Conhecimento necessário ainda não foi descoberto."

    hub = ensure_hub_state(state)
    if recipe.one_time and int(hub["craft_counts"].get(recipe.id, 0)) > 0:
        return False, "Projeto único já criado."

    return True, "OK"


def effective_craft_gold_cost(state: PlayerState, recipe: CraftRecipe) -> int:
    discount = facility_effects(state)["craft_discount"]
    return max(0, int(round(recipe.gold_cost * (1.0 - discount))))


def craft(state: PlayerState, recipe_id: str) -> Tuple[bool, str]:
    if recipe_id not in RECIPES:
        return False, "Receita desconhecida."

    recipe = RECIPES[recipe_id]
    available, reason = recipe_available(state, recipe)
    if not available:
        return False, reason

    gold_cost = effective_craft_gold_cost(state, recipe)
    if gold(state) < gold_cost:
        return False, f"Ouro insuficiente: {gold_cost}."

    for material_id, amount in recipe.material_costs:
        if material_count(state, material_id) < amount:
            return False, f"Falta {MATERIALS[material_id].nome}: {amount}."

    if not spend_gold(state, gold_cost, f"craft:{recipe.id}"):
        return False, "Ouro insuficiente."
    spend_materials(state, recipe.costs_dict())

    if recipe.output_type == CraftOutputType.CONSUMABLE:
        before = consumable_count(state, recipe.output_id)
        after = add_consumable(state, recipe.output_id, recipe.output_amount)
        if after == before:
            # Reembolsa de modo defensivo se stack estiver cheio.
            state.stats.ouro += gold_cost
            for material_id, amount in recipe.material_costs:
                add_material(state, material_id, amount)
            return False, "Limite desse consumível atingido."

    elif recipe.output_type == CraftOutputType.EQUIPMENT:
        for _ in range(recipe.output_amount):
            state.inventory.append(make_inventory_item(recipe.output_id, source="craft"))

    elif recipe.output_type == CraftOutputType.MATERIAL:
        add_material(state, recipe.output_id, recipe.output_amount)

    hub = ensure_hub_state(state)
    hub["craft_counts"][recipe.id] = int(hub["craft_counts"].get(recipe.id, 0)) + 1
    _log_transaction(state, TransactionType.CRAFT, gold_cost, recipe.id)
    return True, f"Criado: {recipe.nome}."


# ============================================================
# DESMONTAGEM
# ============================================================

RARITY_SALVAGE: Dict[Rarity, Tuple[Tuple[str, int], ...]] = {
    Rarity.COMUM: (("po_do_veu", 2),),
    Rarity.INCOMUM: (("po_do_veu", 3), ("fragmento_carmesim", 1)),
    Rarity.RARA: (("po_do_veu", 4), ("cinza_arcana", 1)),
    Rarity.EPICA: (("po_do_veu", 5), ("nucleo_instavel", 1)),
    Rarity.LENDARIA: (("eco_predador", 1), ("vidro_do_vazio", 1)),
    Rarity.MITICA: (("coracao_fraturado", 1), ("vidro_do_vazio", 2)),
    Rarity.CORROMPIDA: (("nucleo_instavel", 3), ("vidro_do_vazio", 1)),
}


def _find_inventory_instance(state: PlayerState, instance_id: str) -> Optional[Tuple[int, Dict[str, Any]]]:
    for i, entry in enumerate(state.inventory):
        if isinstance(entry, dict) and str(entry.get("instance_id")) == str(instance_id):
            return i, entry
    return None


def _equipped_count_for_id(state: PlayerState, equipment_id: str) -> int:
    equipped = (
        state.equipment.arma,
        state.equipment.armadura,
        state.equipment.acessorio_1,
        state.equipment.acessorio_2,
    )
    return sum(1 for x in equipped if x == equipment_id)


def _inventory_count_for_id(state: PlayerState, equipment_id: str) -> int:
    return sum(1 for x in inventory_equipment_ids(state) if x == equipment_id)


def can_remove_inventory_instance(state: PlayerState, instance_id: str) -> Tuple[bool, str]:
    found = _find_inventory_instance(state, instance_id)
    if not found:
        return False, "Item não encontrado."
    _, entry = found
    equipment_id = str(entry.get("equipment_id"))

    # Equipamento guarda definition id, não instance id. Por segurança,
    # não remove a última cópia de uma definição atualmente equipada.
    equipped_count = _equipped_count_for_id(state, equipment_id)
    inventory_count = _inventory_count_for_id(state, equipment_id)
    if equipped_count > 0 and inventory_count <= equipped_count:
        return False, "Não é possível remover a última cópia de um item equipado."
    return True, "OK"


def salvage_equipment(state: PlayerState, instance_id: str) -> Tuple[bool, str, Dict[str, int]]:
    allowed, reason = can_remove_inventory_instance(state, instance_id)
    if not allowed:
        return False, reason, {}

    found = _find_inventory_instance(state, instance_id)
    assert found is not None
    index, entry = found
    equipment_id = str(entry.get("equipment_id"))
    definition = EQUIPMENT_REGISTRY.get(equipment_id)
    if not definition:
        return False, "Equipamento inválido.", {}

    base = dict(RARITY_SALVAGE[definition.raridade])
    bonus = facility_effects(state)["salvage_bonus"]
    result = {key: max(1, int(round(value * bonus))) for key, value in base.items()}

    del state.inventory[index]
    for material_id, amount in result.items():
        add_material(state, material_id, amount)

    hub = ensure_hub_state(state)
    hub["lifetime_salvaged"] = int(hub.get("lifetime_salvaged", 0)) + 1
    _log_transaction(state, TransactionType.DESMONTAGEM, 0, equipment_id)
    return True, f"{definition.nome} desmontado.", result


# ============================================================
# VENDEDORES / MERCADO
# ============================================================

@dataclass(frozen=True)
class VendorDefinition:
    id: str
    nome: str
    tipo: VendorType
    descricao: str
    equipment_tags: Tuple[str, ...] = ()
    consumable_ids: Tuple[str, ...] = ()
    base_slots: int = 4


VENDORS: Dict[str, VendorDefinition] = {
    "daren": VendorDefinition(
        "daren", "Daren, Ferreiro", VendorType.FERREIRO,
        "Compra, vende, desmonta e reconstrói equipamento recuperado.",
        equipment_tags=("melee", "tank", "universal", "rift"),
        base_slots=5,
    ),
    "mira": VendorDefinition(
        "mira", "Mira, Boticária", VendorType.BOTICARIA,
        "Prepara suprimentos para quem atravessa o Véu.",
        consumable_ids=("frasco_vital", "tonico_fluxo", "sal_estabilizador", "oleo_carmesim", "agulha_temporal"),
        base_slots=5,
    ),
    "nox": VendorDefinition(
        "nox", "Nox, Cartógrafo", VendorType.CARTOGRAFO,
        "Vende mapas, sinalizadores e informações que normalmente custam uma vida.",
        consumable_ids=("sinalizador_eco", "pedra_retorno"),
        base_slots=3,
    ),
    "ira": VendorDefinition(
        "ira", "Ira, Guardiã de Relíquias", VendorType.RELIQUIARIO,
        "Negocia artefatos que o Refúgio prefere manter longe de curiosos.",
        equipment_tags=("memory", "mythic", "void", "universal"),
        consumable_ids=("selo_memoria",),
        base_slots=3,
    ),
}


RARITY_PRICE_MULT: Dict[Rarity, float] = {
    Rarity.COMUM: 1.0,
    Rarity.INCOMUM: 1.6,
    Rarity.RARA: 2.5,
    Rarity.EPICA: 4.0,
    Rarity.LENDARIA: 7.0,
    Rarity.MITICA: 12.0,
    Rarity.CORROMPIDA: 9.0,
}


def equipment_base_price(item: EquipmentDefinition) -> int:
    level_factor = 1.0 + max(0, item.min_level - 1) * 0.13
    slot_factor = {
        EquipmentSlot.ARMA: 1.15,
        EquipmentSlot.ARMADURA: 1.10,
        EquipmentSlot.ACESSORIO: 1.00,
    }[item.slot]
    return max(25, int(round(85 * RARITY_PRICE_MULT[item.raridade] * level_factor * slot_factor)))


def vendor_reputation(state: PlayerState, vendor_id: str) -> int:
    return max(0, int(ensure_hub_state(state)["vendor_reputation"].get(vendor_id, 0)))


def add_vendor_reputation(state: PlayerState, vendor_id: str, amount: int) -> int:
    if vendor_id not in VENDORS:
        raise ValueError(f"Vendedor desconhecido: {vendor_id}")
    hub = ensure_hub_state(state)
    hub["vendor_reputation"][vendor_id] = max(
        0,
        int(hub["vendor_reputation"].get(vendor_id, 0)) + int(amount),
    )
    return int(hub["vendor_reputation"][vendor_id])


def reputation_discount(rep: int) -> float:
    # Máximo 18%; evita economia explodir.
    return min(0.18, (max(0, rep) // 20) * 0.02)


def buy_price(state: PlayerState, vendor_id: str, base_price: int) -> int:
    discount = reputation_discount(vendor_reputation(state, vendor_id))
    return max(1, int(round(base_price * (1.0 - discount))))


def sell_price(state: PlayerState, vendor_id: str, item: EquipmentDefinition) -> int:
    rep_bonus = min(0.08, vendor_reputation(state, vendor_id) / 2000.0)
    return max(1, int(round(equipment_base_price(item) * (0.33 + rep_bonus))))


def _stable_seed(*parts: object) -> int:
    raw = "|".join(str(x) for x in parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:16], 16)


def _equipment_matches_vendor(item: EquipmentDefinition, vendor: VendorDefinition) -> bool:
    if not vendor.equipment_tags:
        return False
    tags = set(item.tags)
    return bool(tags.intersection(vendor.equipment_tags))


def refresh_vendor_stock(state: PlayerState, vendor_id: str, force: bool = False) -> List[Dict[str, Any]]:
    if vendor_id not in VENDORS:
        raise ValueError(f"Vendedor desconhecido: {vendor_id}")

    hub = ensure_hub_state(state)
    cycle = int(hub.get("market_cycle", 0))
    existing = hub["shop_stock"].get(vendor_id)

    if existing and not force and int(existing.get("cycle", -1)) == cycle:
        return list(existing.get("offers", []))

    vendor = VENDORS[vendor_id]
    rng = random.Random(_stable_seed(hub.get("market_seed", 0), vendor_id, cycle))
    rep = vendor_reputation(state, vendor_id)
    extra_slots = min(2, rep // 60)
    slots = vendor.base_slots + extra_slots

    offers: List[Dict[str, Any]] = []

    equipment_pool = [
        item for item in EQUIPMENT_REGISTRY.values()
        if _equipment_matches_vendor(item, vendor)
        and item.min_level <= max(1, state.stats.nivel + 2)
    ]
    rng.shuffle(equipment_pool)

    for item in equipment_pool[:slots]:
        offers.append({
            "offer_id": f"eq:{item.id}",
            "type": "equipment",
            "item_id": item.id,
            "price": buy_price(state, vendor_id, equipment_base_price(item)),
            "quantity": 1,
        })

    for consumable_id in vendor.consumable_ids:
        definition = CONSUMABLES[consumable_id]
        offers.append({
            "offer_id": f"con:{consumable_id}",
            "type": "consumable",
            "item_id": consumable_id,
            "price": buy_price(state, vendor_id, definition.preco_base),
            "quantity": 1,
        })

    # Limita equipamento pelo número de slots, consumíveis fixos entram junto.
    hub["shop_stock"][vendor_id] = {
        "cycle": cycle,
        "offers": offers,
    }
    return list(offers)


def advance_market_cycle(state: PlayerState) -> int:
    hub = ensure_hub_state(state)
    hub["market_cycle"] = int(hub.get("market_cycle", 0)) + 1
    hub["shop_stock"] = {}
    return int(hub["market_cycle"])


def purchase_offer(state: PlayerState, vendor_id: str, offer_id: str) -> Tuple[bool, str]:
    offers = refresh_vendor_stock(state, vendor_id)
    offer = next((x for x in offers if x.get("offer_id") == offer_id), None)
    if offer is None:
        return False, "Oferta indisponível."

    price = int(offer["price"])
    if gold(state) < price:
        return False, f"Ouro insuficiente: {price}."

    item_type = offer["type"]
    item_id = str(offer["item_id"])

    if item_type == "consumable":
        before = consumable_count(state, item_id)
        if before >= CONSUMABLES[item_id].max_stack:
            return False, "Você já está no limite desse consumível."

    if not spend_gold(state, price, f"shop:{vendor_id}:{offer_id}"):
        return False, "Ouro insuficiente."

    if item_type == "equipment":
        state.inventory.append(make_inventory_item(item_id, source=f"shop:{vendor_id}"))
        label = EQUIPMENT_REGISTRY[item_id].nome
    else:
        add_consumable(state, item_id, 1)
        label = CONSUMABLES[item_id].nome

    add_vendor_reputation(state, vendor_id, 2)
    _log_transaction(state, TransactionType.COMPRA, price, f"{vendor_id}:{item_id}")
    return True, f"Comprado: {label}."


def sell_equipment_instance(state: PlayerState, vendor_id: str, instance_id: str) -> Tuple[bool, str, int]:
    if vendor_id not in VENDORS:
        return False, "Vendedor desconhecido.", 0

    allowed, reason = can_remove_inventory_instance(state, instance_id)
    if not allowed:
        return False, reason, 0

    found = _find_inventory_instance(state, instance_id)
    assert found is not None
    index, entry = found
    equipment_id = str(entry.get("equipment_id"))
    item = EQUIPMENT_REGISTRY[equipment_id]
    value = sell_price(state, vendor_id, item)

    del state.inventory[index]
    state.stats.ouro += value
    hub = ensure_hub_state(state)
    hub["lifetime_gold_earned"] = int(hub.get("lifetime_gold_earned", 0)) + value
    add_vendor_reputation(state, vendor_id, 1)
    _log_transaction(state, TransactionType.VENDA, value, f"{vendor_id}:{equipment_id}")
    return True, f"Vendido: {item.nome} por {value} ouro.", value


# ============================================================
# EXPEDIÇÕES / PREPARAÇÃO
# ============================================================

@dataclass
class ExpeditionPlan:
    region_id: str
    contract_id: Optional[str] = None
    consumables: Dict[str, int] = field(default_factory=dict)
    protected_reward: bool = False
    notes: str = ""

    def total_supply_slots(self) -> int:
        return sum(max(0, int(v)) for v in self.consumables.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "contract_id": self.contract_id,
            "consumables": dict(self.consumables),
            "protected_reward": bool(self.protected_reward),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpeditionPlan":
        return cls(
            region_id=str(data.get("region_id", "campos_primeira_fenda")),
            contract_id=data.get("contract_id"),
            consumables={str(k): int(v) for k, v in dict(data.get("consumables", {})).items()},
            protected_reward=bool(data.get("protected_reward", False)),
            notes=str(data.get("notes", "")),
        )


def expedition_supply_limit(state: PlayerState) -> int:
    return int(facility_effects(state)["supply_slots"])


def validate_expedition_plan(state: PlayerState, plan: ExpeditionPlan) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    campaign = ensure_campaign_state(state)

    if plan.region_id not in REGIONS:
        errors.append("Região inexistente.")
    elif plan.region_id not in set(campaign.get("unlocked_regions", [])):
        errors.append("Região ainda não desbloqueada.")
    elif plan.region_id == "refugio_ultima_luz":
        errors.append("O Refúgio não é uma expedição.")

    director = CampaignDirector(state)
    if plan.contract_id:
        available = {x.id for x in director.available_contracts()}
        if plan.contract_id not in available:
            errors.append("Contrato indisponível para este personagem.")

    if plan.total_supply_slots() > expedition_supply_limit(state):
        errors.append("Suprimentos excedem a capacidade da Enfermaria.")

    for consumable_id, amount in plan.consumables.items():
        if consumable_id not in CONSUMABLES:
            errors.append(f"Consumível desconhecido: {consumable_id}.")
            continue
        if amount < 0:
            errors.append(f"Quantidade inválida: {consumable_id}.")
            continue
        if consumable_count(state, consumable_id) < amount:
            errors.append(f"Falta {CONSUMABLES[consumable_id].nome}.")

    if plan.protected_reward and plan.consumables.get("selo_memoria", 0) <= 0:
        errors.append("Proteção de recompensa exige um Selo de Memória no loadout.")

    return len(errors) == 0, errors


def prepare_expedition(state: PlayerState, plan: ExpeditionPlan) -> Tuple[bool, str]:
    valid, errors = validate_expedition_plan(state, plan)
    if not valid:
        return False, "; ".join(errors)

    hub = ensure_hub_state(state)
    hub["prepared_expedition"] = plan.to_dict()
    return True, "Expedição preparada."


def prepared_expedition(state: PlayerState) -> Optional[ExpeditionPlan]:
    data = ensure_hub_state(state).get("prepared_expedition")
    if not isinstance(data, dict):
        return None
    return ExpeditionPlan.from_dict(data)


def launch_prepared_expedition(state: PlayerState) -> Tuple[bool, str, Optional[ExpeditionPlan]]:
    plan = prepared_expedition(state)
    if plan is None:
        return False, "Nenhuma expedição preparada.", None

    valid, errors = validate_expedition_plan(state, plan)
    if not valid:
        return False, "; ".join(errors), None

    # Consome suprimentos apenas no lançamento, não ao editar o plano.
    for consumable_id, amount in plan.consumables.items():
        if amount > 0:
            if not consume_consumable(state, consumable_id, amount):
                return False, f"Falha ao consumir {consumable_id}.", None

    director = CampaignDirector(state)
    if plan.contract_id and not director.select_contract(plan.contract_id):
        return False, "Contrato não pôde ser ativado.", None
    if not director.enter_region(plan.region_id):
        return False, "Região não pôde ser acessada.", None

    hub = ensure_hub_state(state)
    hub["prepared_expedition"] = None
    _log_transaction(state, TransactionType.EXPEDICAO, 0, f"launch:{plan.region_id}:{plan.contract_id}")
    return True, "Portal estabilizado. Expedição iniciada.", plan


def finish_expedition(
    state: PlayerState,
    *,
    survived: bool,
    rooms: int,
    bosses: int,
    active_rifts: int,
    gold_reward: int = 0,
    echo_reward: int = 0,
) -> Dict[str, Any]:
    campaign = ensure_campaign_state(state)
    director = CampaignDirector(state)
    hub = ensure_hub_state(state)

    region_id = str(campaign.get("current_region", "campos_primeira_fenda"))
    contract = director.selected_contract()

    reward_mult = 1.0 + max(0, active_rifts) * 0.08
    if contract is not None:
        reward_mult *= max(1.0, float(contract.reward_multiplier))

    final_gold = max(0, int(round(gold_reward * reward_mult)))
    final_echo = max(0, int(round(echo_reward * reward_mult)))

    if not survived:
        final_gold = int(final_gold * 0.45)
        final_echo = int(final_echo * 0.60)

    if final_gold:
        add_gold(state, final_gold, source="expedition")
    if final_echo:
        add_echoes(state, final_echo)

    record = {
        "region_id": region_id,
        "contract_id": contract.id if contract else None,
        "survived": bool(survived),
        "rooms": max(0, int(rooms)),
        "bosses": max(0, int(bosses)),
        "active_rifts": max(0, int(active_rifts)),
        "gold_reward": final_gold,
        "echo_reward": final_echo,
        "cycle": int(hub.get("market_cycle", 0)),
    }

    hub["expedition_history"].append(record)
    if len(hub["expedition_history"]) > 40:
        del hub["expedition_history"][:-40]

    # Mercado muda quando uma expedição acaba; evita reroll grátis no menu.
    advance_market_cycle(state)
    director.enter_region("refugio_ultima_luz")
    director.select_contract(None)
    return record


# ============================================================
# RECOMPENSAS DE MATERIAL / RUPTURAS
# ============================================================

RIFT_MATERIALS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "carmesim": (("fragmento_carmesim", 2), ("po_do_veu", 2)),
    "temporal": (("fibra_temporal", 2), ("po_do_veu", 1)),
    "vazio": (("vidro_do_vazio", 1), ("po_do_veu", 2)),
    "vital": (("po_do_veu", 4),),
    "instavel": (("nucleo_instavel", 1), ("po_do_veu", 2)),
}


def reward_rift_materials(state: PlayerState, rift_id: str, elite: bool = False) -> Dict[str, int]:
    base = dict(RIFT_MATERIALS.get(rift_id, (("po_do_veu", 2),)))
    if elite:
        base = {k: v + 1 for k, v in base.items()}
    for material_id, amount in base.items():
        add_material(state, material_id, amount)
    return base


def reward_boss_materials(state: PlayerState, boss_id: str) -> Dict[str, int]:
    reward = {
        "eco_predador": 1,
        "nucleo_instavel": 2,
    }
    if boss_id == "guardiao_primeira_ruptura":
        reward["coracao_fraturado"] = 1
    for material_id, amount in reward.items():
        add_material(state, material_id, amount)
    return reward


# ============================================================
# RESUMO / VALIDAÇÃO
# ============================================================

def validate_hub_content() -> List[str]:
    errors: List[str] = []

    for recipe in RECIPES.values():
        for material_id, amount in recipe.material_costs:
            if material_id not in MATERIALS:
                errors.append(f"Receita {recipe.id}: material inexistente {material_id}")
            if amount <= 0:
                errors.append(f"Receita {recipe.id}: custo inválido {material_id}={amount}")

    for facility in FACILITIES.values():
        expected = 1
        for level in facility.levels:
            if level.level != expected:
                errors.append(f"Instalação {facility.id.value}: níveis não sequenciais")
                break
            expected += 1
            for material_id, amount in level.material_costs:
                if material_id not in MATERIALS or amount <= 0:
                    errors.append(f"Instalação {facility.id.value}: custo inválido {material_id}")

    for vendor in VENDORS.values():
        for consumable_id in vendor.consumable_ids:
            if consumable_id not in CONSUMABLES:
                errors.append(f"Vendedor {vendor.id}: consumível inexistente {consumable_id}")

    return errors


def hub_summary() -> Dict[str, int]:
    return {
        "materials": len(MATERIALS),
        "consumables": len(CONSUMABLES),
        "facilities": len(FACILITIES),
        "recipes": len(RECIPES),
        "vendors": len(VENDORS),
    }

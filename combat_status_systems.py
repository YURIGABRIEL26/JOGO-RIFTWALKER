"""RIFTWALKER — COMBAT STATUS / ELEMENTAL REACTIONS 0.7

Camada independente do Pygame para efeitos de estado, acúmulos, resistências
simples e reações elementais. A renderização apenas consome os resultados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


class Element(str, Enum):
    FISICO = "fisico"
    FOGO = "fogo"
    GELO = "gelo"
    RAIO = "raio"
    SOMBRA = "sombra"
    VAZIO = "vazio"
    TEMPORAL = "temporal"
    ARCANO = "arcano"


class StatusId(str, Enum):
    QUEIMANDO = "queimando"
    RESFRIADO = "resfriado"
    CONGELADO = "congelado"
    ELETRIZADO = "eletrizado"
    SANGRANDO = "sangrando"
    AMALDICOADO = "amaldicoado"
    CORROMPIDO = "corrompido"
    MARCADO = "marcado"
    LENTO = "lento"
    ACELERADO = "acelerado"
    VULNERAVEL = "vulneravel"
    QUEBRA_GUARDA = "quebra_guarda"


@dataclass(frozen=True)
class StatusDefinition:
    id: StatusId
    nome: str
    duration: float
    max_stacks: int = 1
    tick_interval: float = 0.0
    tick_damage: float = 0.0
    move_mult_per_stack: float = 1.0
    damage_taken_mult_per_stack: float = 1.0
    outgoing_damage_mult_per_stack: float = 1.0
    tags: Tuple[str, ...] = ()


STATUS_DEFINITIONS: Dict[StatusId, StatusDefinition] = {
    StatusId.QUEIMANDO: StatusDefinition(StatusId.QUEIMANDO, "Queimando", 4.0, 5, 0.5, 4.0, tags=("dot", "fire")),
    StatusId.RESFRIADO: StatusDefinition(StatusId.RESFRIADO, "Resfriado", 5.0, 4, move_mult_per_stack=0.94, tags=("ice", "control")),
    StatusId.CONGELADO: StatusDefinition(StatusId.CONGELADO, "Congelado", 1.6, 1, move_mult_per_stack=0.15, damage_taken_mult_per_stack=1.12, tags=("ice", "hard_control")),
    StatusId.ELETRIZADO: StatusDefinition(StatusId.ELETRIZADO, "Eletrizado", 4.5, 4, tags=("lightning", "conductive")),
    StatusId.SANGRANDO: StatusDefinition(StatusId.SANGRANDO, "Sangrando", 5.0, 5, 1.0, 5.0, tags=("dot", "physical")),
    StatusId.AMALDICOADO: StatusDefinition(StatusId.AMALDICOADO, "Amaldiçoado", 7.0, 3, damage_taken_mult_per_stack=1.04, tags=("shadow", "curse")),
    StatusId.CORROMPIDO: StatusDefinition(StatusId.CORROMPIDO, "Corrompido", 8.0, 5, outgoing_damage_mult_per_stack=1.025, damage_taken_mult_per_stack=1.025, tags=("void", "risk")),
    StatusId.MARCADO: StatusDefinition(StatusId.MARCADO, "Marcado", 6.0, 3, damage_taken_mult_per_stack=1.03, tags=("mark",)),
    StatusId.LENTO: StatusDefinition(StatusId.LENTO, "Lento", 3.0, 3, move_mult_per_stack=0.90, tags=("control",)),
    StatusId.ACELERADO: StatusDefinition(StatusId.ACELERADO, "Acelerado", 4.0, 3, move_mult_per_stack=1.08, tags=("buff", "temporal")),
    StatusId.VULNERAVEL: StatusDefinition(StatusId.VULNERAVEL, "Vulnerável", 4.0, 3, damage_taken_mult_per_stack=1.08, tags=("debuff",)),
    StatusId.QUEBRA_GUARDA: StatusDefinition(StatusId.QUEBRA_GUARDA, "Guarda Quebrada", 2.2, 1, damage_taken_mult_per_stack=1.18, tags=("defense_break",)),
}


@dataclass
class ActiveStatus:
    status_id: StatusId
    stacks: int
    remaining: float
    tick_accumulator: float = 0.0
    source: str = "unknown"


@dataclass(frozen=True)
class ReactionDefinition:
    id: str
    nome: str
    incoming_element: Element
    requires: Tuple[StatusId, ...]
    consumes: Tuple[StatusId, ...] = ()
    bonus_damage_multiplier: float = 0.0
    apply: Tuple[Tuple[StatusId, int], ...] = ()
    description: str = ""


REACTIONS: Tuple[ReactionDefinition, ...] = (
    ReactionDefinition("choque_termico", "Choque Térmico", Element.FOGO, (StatusId.CONGELADO,), (StatusId.CONGELADO,), 0.75, ((StatusId.VULNERAVEL, 1),), "Fogo rompe congelamento e causa explosão térmica."),
    ReactionDefinition("estilhacar", "Estilhaçar", Element.FISICO, (StatusId.CONGELADO,), (StatusId.CONGELADO,), 0.55, ((StatusId.QUEBRA_GUARDA, 1),), "Impacto físico quebra alvo congelado."),
    ReactionDefinition("sobrecarga", "Sobrecarga", Element.FOGO, (StatusId.ELETRIZADO,), (), 0.45, ((StatusId.VULNERAVEL, 1),), "Fogo em alvo eletrizado causa sobrecarga."),
    ReactionDefinition("supercondutor", "Supercondutor", Element.RAIO, (StatusId.RESFRIADO,), (), 0.35, ((StatusId.LENTO, 1),), "Raio conduz melhor em alvo resfriado."),
    ReactionDefinition("chama_maldita", "Chama Maldita", Element.SOMBRA, (StatusId.QUEIMANDO,), (), 0.40, ((StatusId.AMALDICOADO, 1),), "Sombra contamina fogo ativo."),
    ReactionDefinition("ignicao_vazio", "Ignição do Vazio", Element.VAZIO, (StatusId.QUEIMANDO,), (), 0.50, ((StatusId.CORROMPIDO, 1),), "O Vazio transforma chama em corrupção."),
    ReactionDefinition("fratura_temporal", "Fratura Temporal", Element.TEMPORAL, (StatusId.LENTO,), (StatusId.LENTO,), 0.30, ((StatusId.VULNERAVEL, 1),), "Tempo desacelerado se rompe violentamente."),
    ReactionDefinition("cacada_sangrenta", "Caçada Sangrenta", Element.FISICO, (StatusId.SANGRANDO, StatusId.MARCADO), (), 0.50, ((StatusId.SANGRANDO, 1),), "Alvo marcado e sangrando recebe golpe predatório."),
    ReactionDefinition("colapso_arcano", "Colapso Arcano", Element.ARCANO, (StatusId.CORROMPIDO,), (), 0.42, ((StatusId.QUEBRA_GUARDA, 1),), "Energia arcana desestabiliza corrupção."),
    ReactionDefinition("ruptura_condutiva", "Ruptura Condutiva", Element.VAZIO, (StatusId.ELETRIZADO,), (), 0.38, ((StatusId.CORROMPIDO, 1),), "Carga elétrica abre microfendas no alvo."),
)


@dataclass
class EffectUpdate:
    periodic_damage: float = 0.0
    expired: List[StatusId] = field(default_factory=list)


@dataclass
class HitResolution:
    base_damage: float
    final_damage: float
    reaction_ids: List[str] = field(default_factory=list)
    applied_statuses: List[StatusId] = field(default_factory=list)


class StatusController:
    def __init__(self):
        self.active: Dict[StatusId, ActiveStatus] = {}

    def has(self, status_id: StatusId) -> bool:
        return status_id in self.active and self.active[status_id].remaining > 0

    def stacks(self, status_id: StatusId) -> int:
        return self.active.get(status_id, ActiveStatus(status_id, 0, 0)).stacks

    def apply(self, status_id: StatusId, stacks: int = 1, duration: Optional[float] = None, source: str = "unknown") -> ActiveStatus:
        definition = STATUS_DEFINITIONS[status_id]
        stacks = max(1, stacks)
        if status_id in self.active:
            current = self.active[status_id]
            current.stacks = min(definition.max_stacks, current.stacks + stacks)
            current.remaining = max(current.remaining, duration or definition.duration)
            current.source = source
            return current
        active = ActiveStatus(status_id, min(definition.max_stacks, stacks), duration or definition.duration, source=source)
        self.active[status_id] = active
        return active

    def remove(self, status_id: StatusId) -> bool:
        return self.active.pop(status_id, None) is not None

    def update(self, dt: float) -> EffectUpdate:
        result = EffectUpdate()
        for status_id, active in list(self.active.items()):
            definition = STATUS_DEFINITIONS[status_id]
            active.remaining -= dt
            if definition.tick_interval > 0 and definition.tick_damage > 0:
                active.tick_accumulator += dt
                while active.tick_accumulator >= definition.tick_interval:
                    active.tick_accumulator -= definition.tick_interval
                    result.periodic_damage += definition.tick_damage * active.stacks
            if active.remaining <= 0:
                result.expired.append(status_id)
                self.active.pop(status_id, None)
        return result

    def movement_multiplier(self) -> float:
        result = 1.0
        for status_id, active in self.active.items():
            d = STATUS_DEFINITIONS[status_id]
            result *= d.move_mult_per_stack ** active.stacks
        return max(0.10, min(2.5, result))

    def incoming_damage_multiplier(self) -> float:
        result = 1.0
        for status_id, active in self.active.items():
            d = STATUS_DEFINITIONS[status_id]
            result *= d.damage_taken_mult_per_stack ** active.stacks
        return max(0.25, min(4.0, result))

    def outgoing_damage_multiplier(self) -> float:
        result = 1.0
        for status_id, active in self.active.items():
            d = STATUS_DEFINITIONS[status_id]
            result *= d.outgoing_damage_mult_per_stack ** active.stacks
        return max(0.25, min(4.0, result))

    def resolve_hit(self, damage: float, element: Element, applied: Iterable[Tuple[StatusId, int]] = ()) -> HitResolution:
        final = max(0.0, damage) * self.incoming_damage_multiplier()
        reaction_ids: List[str] = []
        applied_ids: List[StatusId] = []
        for reaction in REACTIONS:
            if reaction.incoming_element != element:
                continue
            if not all(self.has(req) for req in reaction.requires):
                continue
            final += damage * reaction.bonus_damage_multiplier
            reaction_ids.append(reaction.id)
            for consumed in reaction.consumes:
                self.remove(consumed)
            for status_id, stacks in reaction.apply:
                self.apply(status_id, stacks, source=f"reaction:{reaction.id}")
                applied_ids.append(status_id)
        for status_id, stacks in applied:
            self.apply(status_id, stacks, source=f"element:{element.value}")
            applied_ids.append(status_id)
        return HitResolution(damage, final, reaction_ids, applied_ids)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        return {
            status_id.value: {
                "stacks": active.stacks,
                "remaining": round(active.remaining, 3),
            }
            for status_id, active in self.active.items()
        }


def validate_status_content() -> List[str]:
    problems: List[str] = []
    ids = {x.id for x in REACTIONS}
    if len(ids) != len(REACTIONS):
        problems.append("reaction ids duplicados")
    for reaction in REACTIONS:
        for status_id in (*reaction.requires, *reaction.consumes):
            if status_id not in STATUS_DEFINITIONS:
                problems.append(f"{reaction.id}: status inexistente {status_id}")
    return problems


def status_summary() -> Dict[str, int]:
    return {"statuses": len(STATUS_DEFINITIONS), "reactions": len(REACTIONS)}

"""
RIFTWALKER — NARRATIVE / WORLD SYSTEMS 0.4
==========================================

Camada de campanha independente do Pygame.

Responsabilidades:
- estado persistente do mundo
- regiões e progressão narrativa
- NPCs e falas contextuais
- missões com objetivos verificáveis
- contratos de expedição
- eventos dinâmicos com proteção contra repetição
- histórico de runs
- integração com Memória do Véu

A camada visual apenas pergunta o que está disponível e registra eventos.
Isso permite testar campanha sem abrir uma janela Pygame.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core_systems import (
    CLASS_REGISTRY,
    RIFT_REGISTRY,
    SKILL_REGISTRY,
    MemoryRank,
    PlayerState,
)


# ============================================================
# ENUMS
# ============================================================

class CampaignEvent(str, Enum):
    REGION_ENTERED = "region_entered"
    ROOM_CLEARED = "room_cleared"
    RIFT_DISCOVERED = "rift_discovered"
    BOSS_DEFEATED = "boss_defeated"
    PLAYER_DIED = "player_died"
    SKILL_LEARNED = "skill_learned"
    SKILL_MASTERY = "skill_mastery"
    EQUIPMENT_COLLECTED = "equipment_collected"
    CLASS_UNLOCKED = "class_unlocked"
    DIALOGUE_SEEN = "dialogue_seen"
    CONTRACT_COMPLETED = "contract_completed"
    DYNAMIC_EVENT_COMPLETED = "dynamic_event_completed"


class ObjectiveType(str, Enum):
    CLEAR_ROOMS = "clear_rooms"
    DISCOVER_RIFT = "discover_rift"
    DEFEAT_BOSS = "defeat_boss"
    LEARN_SKILL = "learn_skill"
    REACH_MASTERY = "reach_mastery"
    COLLECT_EQUIPMENT = "collect_equipment"
    UNLOCK_CLASS = "unlock_class"
    VISIT_REGION = "visit_region"
    SURVIVE_WITH_RIFTS = "survive_with_rifts"
    COMPLETE_EVENT = "complete_event"


class QuestStatus(str, Enum):
    LOCKED = "locked"
    ACTIVE = "active"
    COMPLETE = "complete"
    CLAIMED = "claimed"


class DialogueTone(str, Enum):
    NEUTRAL = "neutral"
    WARM = "warm"
    WARNING = "warning"
    HOSTILE = "hostile"
    MYSTERIOUS = "mysterious"
    RESPECT = "respect"
    FEAR = "fear"


# ============================================================
# REGIÕES
# ============================================================

@dataclass(frozen=True)
class RegionDefinition:
    id: str
    nome: str
    descricao: str
    danger: int
    chapter: int
    unlock_flag: Optional[str] = None
    dominant_rifts: Tuple[str, ...] = ()
    tags: Tuple[str, ...] = ()


REGIONS: Dict[str, RegionDefinition] = {}


def register_region(region: RegionDefinition) -> RegionDefinition:
    if region.id in REGIONS:
        raise ValueError(f"Região duplicada: {region.id}")
    REGIONS[region.id] = region
    return region


register_region(
    RegionDefinition(
        id="refugio_ultima_luz",
        nome="Refúgio da Última Luz",
        descricao="O último ponto estável conhecido próximo à Primeira Ruptura.",
        danger=0,
        chapter=1,
        tags=("hub", "safe"),
    )
)

register_region(
    RegionDefinition(
        id="campos_primeira_fenda",
        nome="Campos da Primeira Fenda",
        descricao="Ruínas abertas onde o Véu ainda pulsa sob o solo.",
        danger=1,
        chapter=1,
        tags=("starter", "ruins"),
    )
)

register_region(
    RegionDefinition(
        id="bosque_sussurrante",
        nome="Bosque Sussurrante",
        descricao="Uma floresta onde árvores repetem vozes de viajantes mortos.",
        danger=2,
        chapter=2,
        unlock_flag="chapter_2",
        dominant_rifts=("vital", "vazio"),
        tags=("forest", "memory"),
    )
)

register_region(
    RegionDefinition(
        id="bastilha_carmesim",
        nome="Bastilha Carmesim",
        descricao="Fortaleza consumida por uma Ruptura que recompensa violência com poder.",
        danger=3,
        chapter=2,
        unlock_flag="bastilha_unlocked",
        dominant_rifts=("carmesim",),
        tags=("fortress", "blood"),
    )
)

register_region(
    RegionDefinition(
        id="observatorio_fraturado",
        nome="Observatório Fraturado",
        descricao="Cada corredor existe em mais de um instante ao mesmo tempo.",
        danger=4,
        chapter=3,
        unlock_flag="observatorio_unlocked",
        dominant_rifts=("temporal", "instavel"),
        tags=("temporal", "arcane"),
    )
)

register_region(
    RegionDefinition(
        id="abismo_sem_nome",
        nome="Abismo Sem Nome",
        descricao="Uma região que os mapas se recusam a lembrar.",
        danger=5,
        chapter=4,
        unlock_flag="abismo_unlocked",
        dominant_rifts=("vazio", "instavel"),
        tags=("void", "endgame"),
    )
)


# ============================================================
# NPCs / DIÁLOGO
# ============================================================

@dataclass(frozen=True)
class DialogueCondition:
    flag_required: Optional[str] = None
    flag_forbidden: Optional[str] = None
    boss_required: Optional[str] = None
    rift_required: Optional[str] = None
    class_required: Optional[str] = None
    min_level: int = 1
    min_deaths: int = 0
    min_memory_rank: Optional[MemoryRank] = None


@dataclass(frozen=True)
class DialogueEntry:
    id: str
    text: str
    tone: DialogueTone = DialogueTone.NEUTRAL
    priority: int = 0
    once: bool = False
    condition: DialogueCondition = DialogueCondition()
    set_flags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class NPCDefinition:
    id: str
    nome: str
    papel: str
    descricao: str
    region_id: str
    dialogues: Tuple[DialogueEntry, ...]


NPCS: Dict[str, NPCDefinition] = {}


def register_npc(npc: NPCDefinition) -> NPCDefinition:
    if npc.id in NPCS:
        raise ValueError(f"NPC duplicado: {npc.id}")
    if npc.region_id not in REGIONS:
        raise ValueError(f"NPC {npc.id} usa região inexistente")
    NPCS[npc.id] = npc
    return npc


register_npc(
    NPCDefinition(
        id="aris",
        nome="Aris",
        papel="Guardião do Portal",
        descricao="Sobreviveu à Primeira Ruptura e desconfia de tudo que retorna dela.",
        region_id="refugio_ultima_luz",
        dialogues=(
            DialogueEntry(
                id="aris_intro",
                text="O Portal não escolhe heróis. Só escolhe quem consegue voltar.",
                tone=DialogueTone.WARNING,
                priority=100,
                once=True,
                set_flags=("met_aris",),
            ),
            DialogueEntry(
                id="aris_first_boss",
                text="Você derrubou o Guardião... e mesmo assim o Véu continua olhando para cá.",
                tone=DialogueTone.RESPECT,
                priority=90,
                once=True,
                condition=DialogueCondition(boss_required="guardiao_primeira_ruptura"),
                set_flags=("aris_acknowledged_guardian",),
            ),
            DialogueEntry(
                id="aris_deaths",
                text="Cada vez que você morre lá dentro, alguma coisa volta sabendo um pouco mais sobre você.",
                tone=DialogueTone.WARNING,
                priority=80,
                once=True,
                condition=DialogueCondition(min_deaths=2),
            ),
            DialogueEntry(
                id="aris_default",
                text="Se entrar de novo, não confie num inimigo só porque já o venceu antes.",
                tone=DialogueTone.NEUTRAL,
                priority=1,
            ),
        ),
    )
)

register_npc(
    NPCDefinition(
        id="maelis",
        nome="Maelis",
        papel="Pesquisadora do Véu",
        descricao="Cataloga Rupturas e tenta descobrir por que elas guardam memórias.",
        region_id="refugio_ultima_luz",
        dialogues=(
            DialogueEntry(
                id="maelis_intro",
                text="Se o Véu lembrar de você, eu quero saber exatamente o que ele decidiu guardar.",
                tone=DialogueTone.MYSTERIOUS,
                priority=100,
                once=True,
                set_flags=("met_maelis",),
            ),
            DialogueEntry(
                id="maelis_temporal",
                text="A Ruptura Temporal não acelera o tempo. Ela discorda de qual tempo deveria existir.",
                tone=DialogueTone.MYSTERIOUS,
                priority=70,
                once=True,
                condition=DialogueCondition(rift_required="temporal"),
            ),
            DialogueEntry(
                id="maelis_predator",
                text="Predador. Esse é o nível em que eu pararia de chamar aquilo de memória e começaria a chamar de intenção.",
                tone=DialogueTone.FEAR,
                priority=95,
                once=True,
                condition=DialogueCondition(min_memory_rank=MemoryRank.PREDADOR),
            ),
            DialogueEntry(
                id="maelis_default",
                text="Traga dados. Sangue também serve, mas dados fazem menos sujeira.",
                tone=DialogueTone.NEUTRAL,
                priority=1,
            ),
        ),
    )
)

register_npc(
    NPCDefinition(
        id="nox",
        nome="Nox",
        papel="Ferreiro de Fendas",
        descricao="Transforma restos de criaturas e metal corrompido em equipamentos.",
        region_id="refugio_ultima_luz",
        dialogues=(
            DialogueEntry(
                id="nox_intro",
                text="Arma perfeita não existe. Existe arma que combina com o jeito que você pretende sobreviver.",
                tone=DialogueTone.WARM,
                priority=100,
                once=True,
                set_flags=("met_nox",),
            ),
            DialogueEntry(
                id="nox_rasgado",
                text="Se vai deixar a Ruptura entrar no corpo, pelo menos use uma armadura que aguente o resto.",
                tone=DialogueTone.WARNING,
                priority=70,
                condition=DialogueCondition(class_required="rasgado"),
            ),
            DialogueEntry(
                id="nox_default",
                text="Volte com alguma coisa impossível de forjar. É quando meu trabalho fica interessante.",
                priority=1,
            ),
        ),
    )
)

register_npc(
    NPCDefinition(
        id="ilyra",
        nome="Ilyra",
        papel="Cronista Exilada",
        descricao="Afirma ter conversado com versões futuras de pessoas que ainda não conheceu.",
        region_id="observatorio_fraturado",
        dialogues=(
            DialogueEntry(
                id="ilyra_intro",
                text="Você chegou cedo. Ou tarde. Ainda não decidi qual dos dois aconteceu.",
                tone=DialogueTone.MYSTERIOUS,
                priority=100,
                once=True,
                set_flags=("met_ilyra",),
            ),
            DialogueEntry(
                id="ilyra_cronista",
                text="Então você aprendeu a puxar o fio. Agora descubra o que acontece quando ele puxa de volta.",
                tone=DialogueTone.RESPECT,
                priority=80,
                condition=DialogueCondition(class_required="cronista"),
            ),
            DialogueEntry(
                id="ilyra_default",
                text="Não confie em uma porta que já estava aberta antes de você chegar.",
                priority=1,
            ),
        ),
    )
)


# ============================================================
# MISSÕES
# ============================================================

@dataclass(frozen=True)
class QuestObjective:
    id: str
    type: ObjectiveType
    description: str
    target_id: Optional[str] = None
    target_amount: int = 1
    minimum_value: int = 0


@dataclass(frozen=True)
class QuestReward:
    ouro: int = 0
    xp: int = 0
    unlock_flags: Tuple[str, ...] = ()
    unlock_region: Optional[str] = None
    unlock_class: Optional[str] = None
    important_item: Optional[str] = None


@dataclass(frozen=True)
class QuestDefinition:
    id: str
    nome: str
    descricao: str
    chapter: int
    objectives: Tuple[QuestObjective, ...]
    reward: QuestReward
    required_flags: Tuple[str, ...] = ()
    forbidden_flags: Tuple[str, ...] = ()
    auto_start: bool = True


QUESTS: Dict[str, QuestDefinition] = {}


def register_quest(quest: QuestDefinition) -> QuestDefinition:
    if quest.id in QUESTS:
        raise ValueError(f"Missão duplicada: {quest.id}")
    QUESTS[quest.id] = quest
    return quest


register_quest(
    QuestDefinition(
        id="primeiro_passo",
        nome="Primeiro Passo Além do Véu",
        descricao="Atravesse os Campos da Primeira Fenda e sobreviva ao primeiro contato.",
        chapter=1,
        objectives=(
            QuestObjective(
                id="clear_3_rooms",
                type=ObjectiveType.CLEAR_ROOMS,
                description="Limpe 3 áreas nos Campos da Primeira Fenda.",
                target_amount=3,
            ),
        ),
        reward=QuestReward(
            ouro=80,
            xp=80,
            unlock_flags=("first_expedition_complete",),
        ),
    )
)

register_quest(
    QuestDefinition(
        id="guardiao_da_fenda",
        nome="O Que Guarda a Primeira Fenda",
        descricao="Encontre e derrote o Guardião que bloqueia o avanço.",
        chapter=1,
        objectives=(
            QuestObjective(
                id="kill_guardian",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Derrote o Guardião da Primeira Ruptura.",
                target_id="guardiao_primeira_ruptura",
            ),
        ),
        reward=QuestReward(
            ouro=180,
            xp=180,
            unlock_flags=("chapter_2",),
            unlock_region="bosque_sussurrante",
        ),
        required_flags=("first_expedition_complete",),
    )
)

register_quest(
    QuestDefinition(
        id="ecos_que_aprendem",
        nome="Ecos Que Aprendem",
        descricao="Prove que a Memória do Véu muda depois de uma derrota.",
        chapter=2,
        objectives=(
            QuestObjective(
                id="die_once",
                type=ObjectiveType.COMPLETE_EVENT,
                description="Morra em uma expedição marcada pelo Guardião.",
                target_id="memory_death",
            ),
            QuestObjective(
                id="return_guardian",
                type=ObjectiveType.COMPLETE_EVENT,
                description="Retorne e enfrente um inimigo que se lembra de você.",
                target_id="memory_reencounter",
            ),
        ),
        reward=QuestReward(
            ouro=220,
            xp=240,
            unlock_flags=("memory_research_unlocked",),
        ),
        required_flags=("chapter_2",),
    )
)

register_quest(
    QuestDefinition(
        id="tempo_emprestado",
        nome="Tempo Emprestado",
        descricao="Investigue uma Ruptura Temporal e prove que consegue sobreviver ao ritmo alterado.",
        chapter=2,
        objectives=(
            QuestObjective(
                id="discover_temporal",
                type=ObjectiveType.DISCOVER_RIFT,
                description="Descubra a Ruptura Temporal.",
                target_id="temporal",
            ),
            QuestObjective(
                id="clear_temporal_rooms",
                type=ObjectiveType.SURVIVE_WITH_RIFTS,
                description="Limpe 4 áreas com uma Ruptura Temporal ativa.",
                target_id="temporal",
                target_amount=4,
            ),
        ),
        reward=QuestReward(
            ouro=260,
            xp=300,
            unlock_flags=("observatorio_unlocked",),
            unlock_region="observatorio_fraturado",
        ),
        required_flags=("chapter_2",),
    )
)

register_quest(
    QuestDefinition(
        id="arma_impossivel",
        nome="Uma Arma Que Não Deveria Existir",
        descricao="Leve a Nox material suficiente para uma peça criada a partir das Rupturas.",
        chapter=2,
        objectives=(
            QuestObjective(
                id="collect_6_equipment",
                type=ObjectiveType.COLLECT_EQUIPMENT,
                description="Colete 6 equipamentos diferentes.",
                target_amount=6,
            ),
            QuestObjective(
                id="discover_carmesim",
                type=ObjectiveType.DISCOVER_RIFT,
                description="Descubra a Ruptura Carmesim.",
                target_id="carmesim",
            ),
        ),
        reward=QuestReward(
            ouro=320,
            xp=260,
            unlock_flags=("bastilha_unlocked",),
            unlock_region="bastilha_carmesim",
            important_item="nucleo_de_fenda_estavel",
        ),
        required_flags=("met_nox",),
    )
)

register_quest(
    QuestDefinition(
        id="dominio",
        nome="Não É Mais Um Truque",
        descricao="Leve uma habilidade além da execução básica.",
        chapter=2,
        objectives=(
            QuestObjective(
                id="master_any_skill",
                type=ObjectiveType.REACH_MASTERY,
                description="Alcance maestria 4 com qualquer habilidade.",
                target_amount=1,
                minimum_value=4,
            ),
        ),
        reward=QuestReward(
            ouro=250,
            xp=320,
            unlock_flags=("advanced_training_unlocked",),
        ),
        required_flags=("chapter_2",),
    )
)


# ============================================================
# MISSÕES — RETA FINAL DA CAMPANHA (0.8)
# ============================================================

register_quest(
    QuestDefinition(
        id="coro_sussurrante",
        nome="A Floresta Sabe Seu Nome",
        descricao="Atravesse o Bosque Sussurrante e silencie a voz que coleciona ecos.",
        chapter=2,
        objectives=(
            QuestObjective(
                id="visit_whispering_woods",
                type=ObjectiveType.VISIT_REGION,
                description="Entre no Bosque Sussurrante.",
                target_id="bosque_sussurrante",
            ),
            QuestObjective(
                id="kill_matriarch",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Derrote a Matriarca Sussurrante.",
                target_id="matriarca_sussurrante",
            ),
        ),
        reward=QuestReward(
            ouro=420,
            xp=520,
            unlock_flags=("matriarca_derrotada", "bosque_estabilizado"),
        ),
        required_flags=("chapter_2",),
    )
)

register_quest(
    QuestDefinition(
        id="sangue_que_abre_portas",
        nome="Sangue Que Abre Portas",
        descricao="A Bastilha Carmesim guarda alguém que sobreviveu ao que deveria tê-lo apagado.",
        chapter=2,
        objectives=(
            QuestObjective(
                id="visit_crimson_bastion",
                type=ObjectiveType.VISIT_REGION,
                description="Entre na Bastilha Carmesim.",
                target_id="bastilha_carmesim",
            ),
            QuestObjective(
                id="kill_first_torn",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Derrote O Primeiro Rasgado.",
                target_id="primeiro_rasgado",
            ),
        ),
        reward=QuestReward(
            ouro=520,
            xp=650,
            unlock_flags=("primeiro_rasgado_derrotado",),
            important_item="fragmento_do_primeiro_rasgado",
        ),
        required_flags=("bastilha_unlocked",),
    )
)

register_quest(
    QuestDefinition(
        id="relogio_sem_ponteiros",
        nome="Relógio Sem Ponteiros",
        descricao="No Observatório Fraturado, encontre o homem que vive em mais de um segundo.",
        chapter=3,
        objectives=(
            QuestObjective(
                id="visit_observatory",
                type=ObjectiveType.VISIT_REGION,
                description="Entre no Observatório Fraturado.",
                target_id="observatorio_fraturado",
            ),
            QuestObjective(
                id="kill_chronarch",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Derrote o Cronarca Fraturado.",
                target_id="cronarca_fraturado",
            ),
        ),
        reward=QuestReward(
            ouro=680,
            xp=820,
            unlock_flags=("cronarca_derrotado", "abismo_unlocked"),
            unlock_region="abismo_sem_nome",
            important_item="ponteiro_impossivel",
        ),
        required_flags=("observatorio_unlocked",),
    )
)

register_quest(
    QuestDefinition(
        id="quatro_cicatrizes",
        nome="Quatro Cicatrizes",
        descricao="Antes de entrar no Abismo, prove que as quatro grandes ameaças ficaram para trás.",
        chapter=4,
        objectives=(
            QuestObjective(
                id="guardian_again",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Tenha derrotado o Guardião da Primeira Ruptura.",
                target_id="guardiao_primeira_ruptura",
            ),
            QuestObjective(
                id="matriarch_again",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Tenha derrotado a Matriarca Sussurrante.",
                target_id="matriarca_sussurrante",
            ),
            QuestObjective(
                id="torn_again",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Tenha derrotado O Primeiro Rasgado.",
                target_id="primeiro_rasgado",
            ),
            QuestObjective(
                id="chronarch_again",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Tenha derrotado o Cronarca Fraturado.",
                target_id="cronarca_fraturado",
            ),
        ),
        reward=QuestReward(
            ouro=750,
            xp=900,
            unlock_flags=("final_path_open",),
        ),
        required_flags=("abismo_unlocked",),
    )
)

register_quest(
    QuestDefinition(
        id="o_que_o_veu_esqueceu",
        nome="O Que o Véu Esqueceu",
        descricao="Desça ao Abismo Sem Nome e encare a presença que apaga tudo o que toca.",
        chapter=4,
        objectives=(
            QuestObjective(
                id="visit_nameless_abyss",
                type=ObjectiveType.VISIT_REGION,
                description="Entre no Abismo Sem Nome.",
                target_id="abismo_sem_nome",
            ),
            QuestObjective(
                id="kill_nameless",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Derrote O Nome Apagado.",
                target_id="o_nome_apagado",
            ),
        ),
        reward=QuestReward(
            ouro=1200,
            xp=1500,
            unlock_flags=("final_boss_defeated", "ending_choice_available"),
            important_item="nucleo_sem_nome",
        ),
        required_flags=("final_path_open",),
    )
)

register_quest(
    QuestDefinition(
        id="o_eco_que_ficou",
        nome="O Eco Que Ficou",
        descricao="Depois do fim, o Véu ainda guarda uma versão sua que nunca voltou.",
        chapter=4,
        objectives=(
            QuestObjective(
                id="kill_own_echo",
                type=ObjectiveType.DEFEAT_BOSS,
                description="Derrote o Eco do Riftwalker no pós-jogo.",
                target_id="eco_do_riftwalker",
            ),
        ),
        reward=QuestReward(
            ouro=2000,
            xp=2200,
            unlock_flags=("echo_conquered",),
            important_item="espelho_do_riftwalker",
        ),
        required_flags=("postgame_unlocked",),
    )
)


# ============================================================
# CONTRATOS DE EXPEDIÇÃO
# ============================================================

@dataclass(frozen=True)
class ContractDefinition:
    id: str
    nome: str
    descricao: str
    danger_bonus: int
    reward_multiplier: float
    required_level: int = 1
    required_flag: Optional[str] = None
    rules: Tuple[str, ...] = ()


CONTRACTS: Dict[str, ContractDefinition] = {
    "sem_retorno": ContractDefinition(
        id="sem_retorno",
        nome="Sem Retorno Fácil",
        descricao="Cura de campo reduzida. Elites têm maior chance de aparecer.",
        danger_bonus=2,
        reward_multiplier=1.35,
        required_level=3,
        rules=("field_heal_reduced", "elite_frequency_up"),
    ),
    "predador_do_veu": ContractDefinition(
        id="predador_do_veu",
        nome="Predador do Véu",
        descricao="Inimigos superiores entram com memória elevada.",
        danger_bonus=3,
        reward_multiplier=1.55,
        required_level=5,
        required_flag="memory_research_unlocked",
        rules=("memory_floor_observer", "boss_strategy_extra"),
    ),
    "carmesim_total": ContractDefinition(
        id="carmesim_total",
        nome="Carmesim Total",
        descricao="A expedição começa sob influência Carmesim permanente.",
        danger_bonus=3,
        reward_multiplier=1.50,
        required_level=5,
        rules=("forced_rift_carmesim",),
    ),
    "tempo_quebrado": ContractDefinition(
        id="tempo_quebrado",
        nome="Tempo Quebrado",
        descricao="Velocidade das ameaças oscila entre salas.",
        danger_bonus=4,
        reward_multiplier=1.70,
        required_level=7,
        required_flag="observatorio_unlocked",
        rules=("temporal_variance", "event_frequency_up"),
    ),
}


# ============================================================
# EVENTOS DINÂMICOS
# ============================================================

@dataclass(frozen=True)
class DynamicEventDefinition:
    id: str
    nome: str
    descricao: str
    minimum_level: int = 1
    required_flags: Tuple[str, ...] = ()
    forbidden_flags: Tuple[str, ...] = ()
    region_tags: Tuple[str, ...] = ()
    weight: float = 1.0
    reward_hint: str = ""


DYNAMIC_EVENTS: Dict[str, DynamicEventDefinition] = {
    "eco_perdido": DynamicEventDefinition(
        id="eco_perdido",
        nome="Eco Perdido",
        descricao="Uma silhueta repete os últimos movimentos de alguém que morreu ali.",
        minimum_level=1,
        weight=1.25,
        reward_hint="Pode revelar memória ou rota secreta.",
    ),
    "cacador_memoria": DynamicEventDefinition(
        id="cacador_memoria",
        nome="Caçador de Memória",
        descricao="Um inimigo superior aparece procurando especificamente pelo seu padrão de combate.",
        minimum_level=4,
        required_flags=("memory_research_unlocked",),
        weight=0.75,
        reward_hint="Recompensa maior por derrotar uma contramedida adaptativa.",
    ),
    "altar_fraturado": DynamicEventDefinition(
        id="altar_fraturado",
        nome="Altar Fraturado",
        descricao="Aceite uma bênção instável ou destrua o altar antes que ele acorde algo.",
        minimum_level=2,
        weight=1.0,
        reward_hint="Escolha de risco/recompensa.",
    ),
    "tempestade_de_ruptura": DynamicEventDefinition(
        id="tempestade_de_ruptura",
        nome="Tempestade de Ruptura",
        descricao="Duas influências de Ruptura disputam a mesma área.",
        minimum_level=5,
        weight=0.6,
        reward_hint="Alta chance de habilidade rara.",
    ),
    "expedicao_falha": DynamicEventDefinition(
        id="expedicao_falha",
        nome="Expedição Falha",
        descricao="Restos de outro grupo ainda estão sendo caçados por criaturas da região.",
        minimum_level=3,
        weight=0.9,
        reward_hint="Equipamento, informação ou sobrevivente.",
    ),
}


# ============================================================
# ESTADO PERSISTENTE
# ============================================================

DEFAULT_CAMPAIGN_STATE: Dict[str, Any] = {
    "chapter": 1,
    "flags": [],
    "visited_regions": ["refugio_ultima_luz"],
    "unlocked_regions": ["refugio_ultima_luz", "campos_primeira_fenda"],
    "current_region": "refugio_ultima_luz",
    "npc_reputation": {},
    "dialogue_seen": [],
    "quests": {},
    "completed_quests": [],
    "claimed_quests": [],
    "dynamic_event_history": [],
    "completed_dynamic_events": [],
    "contracts_completed": [],
    "selected_contract": None,
    "run_history": [],
    "total_deaths": 0,
    "total_rooms_cleared": 0,
}


def ensure_campaign_state(state: PlayerState) -> Dict[str, Any]:
    if not isinstance(getattr(state, "campaign", None), dict):
        state.campaign = {}

    campaign = state.campaign

    for key, value in DEFAULT_CAMPAIGN_STATE.items():
        if key not in campaign:
            if isinstance(value, list):
                campaign[key] = list(value)
            elif isinstance(value, dict):
                campaign[key] = dict(value)
            else:
                campaign[key] = value

    # Normalização defensiva para saves antigos/editados manualmente.
    for list_key in (
        "flags",
        "visited_regions",
        "unlocked_regions",
        "dialogue_seen",
        "completed_quests",
        "claimed_quests",
        "dynamic_event_history",
        "completed_dynamic_events",
        "contracts_completed",
        "run_history",
    ):
        if not isinstance(campaign.get(list_key), list):
            campaign[list_key] = []

    if not isinstance(campaign.get("quests"), dict):
        campaign["quests"] = {}

    if not isinstance(campaign.get("npc_reputation"), dict):
        campaign["npc_reputation"] = {}

    return campaign


# ============================================================
# QUEST PROGRESS
# ============================================================


def _quest_state(campaign: Dict[str, Any], quest_id: str) -> Dict[str, Any]:
    quests = campaign["quests"]
    if quest_id not in quests:
        definition = QUESTS[quest_id]
        quests[quest_id] = {
            "status": QuestStatus.LOCKED.value,
            "objectives": {obj.id: 0 for obj in definition.objectives},
        }
    return quests[quest_id]


def _flags(campaign: Dict[str, Any]) -> Set[str]:
    return set(campaign.get("flags", []))


def _set_flag(campaign: Dict[str, Any], flag_name: str) -> None:
    flags = set(campaign.get("flags", []))
    flags.add(flag_name)
    campaign["flags"] = sorted(flags)


def _conditions_met(campaign: Dict[str, Any], quest: QuestDefinition) -> bool:
    flags = _flags(campaign)
    if any(req not in flags for req in quest.required_flags):
        return False
    if any(blocked in flags for blocked in quest.forbidden_flags):
        return False
    return True


def refresh_quest_availability(state: PlayerState) -> List[str]:
    campaign = ensure_campaign_state(state)
    started: List[str] = []

    for quest in QUESTS.values():
        qstate = _quest_state(campaign, quest.id)
        if qstate["status"] != QuestStatus.LOCKED.value:
            continue
        if quest.auto_start and _conditions_met(campaign, quest):
            qstate["status"] = QuestStatus.ACTIVE.value
            started.append(quest.id)

    return started


def objective_complete(obj: QuestObjective, value: int) -> bool:
    return value >= max(1, obj.target_amount)


def quest_is_complete(campaign: Dict[str, Any], quest: QuestDefinition) -> bool:
    qstate = _quest_state(campaign, quest.id)
    if qstate["status"] not in (QuestStatus.ACTIVE.value, QuestStatus.COMPLETE.value):
        return False
    return all(
        objective_complete(obj, int(qstate["objectives"].get(obj.id, 0)))
        for obj in quest.objectives
    )


def claim_quest_reward(state: PlayerState, quest_id: str) -> bool:
    campaign = ensure_campaign_state(state)
    if quest_id not in QUESTS:
        return False

    quest = QUESTS[quest_id]
    qstate = _quest_state(campaign, quest_id)

    if qstate["status"] != QuestStatus.COMPLETE.value:
        return False

    if quest_id in campaign["claimed_quests"]:
        return False

    reward = quest.reward
    state.stats.ouro += reward.ouro
    state.stats.xp += reward.xp

    for flag_name in reward.unlock_flags:
        _set_flag(campaign, flag_name)

    if reward.unlock_region and reward.unlock_region in REGIONS:
        unlocked = set(campaign["unlocked_regions"])
        unlocked.add(reward.unlock_region)
        campaign["unlocked_regions"] = sorted(unlocked)

    if reward.unlock_class and reward.unlock_class in CLASS_REGISTRY:
        state.unlock_class(reward.unlock_class)

    if reward.important_item:
        state.progression.itens_importantes.add(reward.important_item)

    qstate["status"] = QuestStatus.CLAIMED.value
    campaign["claimed_quests"].append(quest_id)

    refresh_chapter(state)
    refresh_quest_availability(state)
    return True


def refresh_chapter(state: PlayerState) -> int:
    campaign = ensure_campaign_state(state)
    flags = _flags(campaign)

    chapter = 1
    if "chapter_2" in flags:
        chapter = 2
    if "observatorio_unlocked" in flags:
        chapter = 3
    if "abismo_unlocked" in flags:
        chapter = 4

    campaign["chapter"] = chapter
    return chapter


# ============================================================
# DIRETOR DE CAMPANHA
# ============================================================

class CampaignDirector:
    def __init__(self, state: PlayerState):
        self.state = state
        self.campaign = ensure_campaign_state(state)
        refresh_chapter(state)
        refresh_quest_availability(state)

    @property
    def chapter(self) -> int:
        return int(self.campaign.get("chapter", 1))

    def flags(self) -> Set[str]:
        return _flags(self.campaign)

    def set_flag(self, flag_name: str) -> None:
        _set_flag(self.campaign, flag_name)
        refresh_chapter(self.state)
        refresh_quest_availability(self.state)

    def current_region(self) -> RegionDefinition:
        region_id = self.campaign.get("current_region", "refugio_ultima_luz")
        return REGIONS.get(region_id, REGIONS["refugio_ultima_luz"])

    def enter_region(self, region_id: str) -> bool:
        if region_id not in REGIONS:
            return False
        if region_id not in set(self.campaign["unlocked_regions"]):
            return False

        self.campaign["current_region"] = region_id
        visited = set(self.campaign["visited_regions"])
        visited.add(region_id)
        self.campaign["visited_regions"] = sorted(visited)
        self.record(CampaignEvent.REGION_ENTERED, target_id=region_id)
        return True

    def record(
        self,
        event: CampaignEvent,
        *,
        target_id: Optional[str] = None,
        amount: int = 1,
        value: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        metadata = metadata or {}

        if event == CampaignEvent.PLAYER_DIED:
            self.campaign["total_deaths"] = int(self.campaign.get("total_deaths", 0)) + 1
            self.campaign["recent_deaths"] = min(3, int(self.campaign.get("recent_deaths", 0)) + 1)

        if event == CampaignEvent.ROOM_CLEARED:
            self.campaign["total_rooms_cleared"] = int(self.campaign.get("total_rooms_cleared", 0)) + amount
            # O Diretor de Encontros reage a mortes recentes, não ao total histórico.
            self.campaign["recent_deaths"] = max(0, int(self.campaign.get("recent_deaths", 0)) - max(1, amount))

        if event == CampaignEvent.DYNAMIC_EVENT_COMPLETED and target_id:
            done = set(self.campaign["completed_dynamic_events"])
            done.add(target_id)
            self.campaign["completed_dynamic_events"] = sorted(done)

        if event == CampaignEvent.CONTRACT_COMPLETED and target_id:
            done = set(self.campaign["contracts_completed"])
            done.add(target_id)
            self.campaign["contracts_completed"] = sorted(done)

        if event == CampaignEvent.PLAYER_DIED:
            self._progress_event_objective("memory_death", 1)

        # Reencontro com Guardião após ao menos uma morte registrada.
        if event == CampaignEvent.BOSS_DEFEATED and target_id == "guardiao_primeira_ruptura":
            memory = self.state.veil_memory.get("guardiao_primeira_ruptura")
            if memory.mortes_do_jogador > 0:
                self._progress_event_objective("memory_reencounter", 1)

        changed_quests: List[str] = []

        for quest in QUESTS.values():
            qstate = _quest_state(self.campaign, quest.id)
            if qstate["status"] != QuestStatus.ACTIVE.value:
                continue

            changed = False

            for obj in quest.objectives:
                current = int(qstate["objectives"].get(obj.id, 0))
                new_value = current

                if obj.type == ObjectiveType.CLEAR_ROOMS and event == CampaignEvent.ROOM_CLEARED:
                    new_value += amount

                elif obj.type == ObjectiveType.DISCOVER_RIFT and event == CampaignEvent.RIFT_DISCOVERED:
                    if obj.target_id is None or obj.target_id == target_id:
                        new_value = max(new_value, 1)

                elif obj.type == ObjectiveType.DEFEAT_BOSS and event == CampaignEvent.BOSS_DEFEATED:
                    if obj.target_id is None or obj.target_id == target_id:
                        new_value += amount

                elif obj.type == ObjectiveType.LEARN_SKILL and event == CampaignEvent.SKILL_LEARNED:
                    if obj.target_id is None or obj.target_id == target_id:
                        new_value += amount

                elif obj.type == ObjectiveType.REACH_MASTERY and event == CampaignEvent.SKILL_MASTERY:
                    if value >= obj.minimum_value:
                        if obj.target_id is None or obj.target_id == target_id:
                            new_value = max(new_value, 1)

                elif obj.type == ObjectiveType.COLLECT_EQUIPMENT and event == CampaignEvent.EQUIPMENT_COLLECTED:
                    unique_equipment = {
                        str(item.get("equipment_id"))
                        for item in self.state.inventory
                        if isinstance(item, dict) and item.get("equipment_id")
                    }
                    new_value = max(new_value, len(unique_equipment))

                elif obj.type == ObjectiveType.UNLOCK_CLASS and event == CampaignEvent.CLASS_UNLOCKED:
                    if obj.target_id is None or obj.target_id == target_id:
                        new_value += amount

                elif obj.type == ObjectiveType.VISIT_REGION and event == CampaignEvent.REGION_ENTERED:
                    if obj.target_id is None or obj.target_id == target_id:
                        new_value = max(new_value, 1)

                elif obj.type == ObjectiveType.SURVIVE_WITH_RIFTS and event == CampaignEvent.ROOM_CLEARED:
                    if obj.target_id in self.state.active_rifts.active_ids:
                        new_value += amount

                elif obj.type == ObjectiveType.COMPLETE_EVENT and event == CampaignEvent.DYNAMIC_EVENT_COMPLETED:
                    if obj.target_id is None or obj.target_id == target_id:
                        new_value += amount

                if new_value != current:
                    qstate["objectives"][obj.id] = new_value
                    changed = True

            if changed:
                changed_quests.append(quest.id)

            if quest_is_complete(self.campaign, quest):
                qstate["status"] = QuestStatus.COMPLETE.value
                completed = set(self.campaign["completed_quests"])
                completed.add(quest.id)
                self.campaign["completed_quests"] = sorted(completed)

        refresh_quest_availability(self.state)
        return changed_quests

    def _progress_event_objective(self, event_id: str, amount: int) -> None:
        for quest in QUESTS.values():
            qstate = _quest_state(self.campaign, quest.id)
            if qstate["status"] != QuestStatus.ACTIVE.value:
                continue
            for obj in quest.objectives:
                if obj.type == ObjectiveType.COMPLETE_EVENT and obj.target_id == event_id:
                    qstate["objectives"][obj.id] = int(qstate["objectives"].get(obj.id, 0)) + amount

    def claim_ready_quests(self) -> List[str]:
        claimed: List[str] = []
        for quest_id in list(self.campaign["completed_quests"]):
            if quest_id in self.campaign["claimed_quests"]:
                continue
            if claim_quest_reward(self.state, quest_id):
                claimed.append(quest_id)
        return claimed

    def active_quests(self) -> List[QuestDefinition]:
        result = []
        for quest_id, qstate in self.campaign["quests"].items():
            if qstate.get("status") == QuestStatus.ACTIVE.value and quest_id in QUESTS:
                result.append(QUESTS[quest_id])
        return sorted(result, key=lambda q: (q.chapter, q.nome))

    def completed_unclaimed_quests(self) -> List[QuestDefinition]:
        result = []
        for quest_id in self.campaign["completed_quests"]:
            if quest_id not in self.campaign["claimed_quests"] and quest_id in QUESTS:
                result.append(QUESTS[quest_id])
        return result

    def quest_progress_text(self, quest_id: str) -> List[str]:
        if quest_id not in QUESTS:
            return []
        quest = QUESTS[quest_id]
        qstate = _quest_state(self.campaign, quest_id)
        lines = []
        for obj in quest.objectives:
            current = int(qstate["objectives"].get(obj.id, 0))
            target = max(1, obj.target_amount)
            marker = "✓" if current >= target else "•"
            lines.append(f"{marker} {obj.description} ({min(current, target)}/{target})")
        return lines

    def available_contracts(self) -> List[ContractDefinition]:
        flags = self.flags()
        result = []
        for contract in CONTRACTS.values():
            if self.state.stats.nivel < contract.required_level:
                continue
            if contract.required_flag and contract.required_flag not in flags:
                continue
            result.append(contract)
        return sorted(result, key=lambda c: (c.required_level, c.danger_bonus, c.nome))

    def select_contract(self, contract_id: Optional[str]) -> bool:
        if contract_id is None:
            self.campaign["selected_contract"] = None
            return True
        available = {c.id for c in self.available_contracts()}
        if contract_id not in available:
            return False
        self.campaign["selected_contract"] = contract_id
        return True

    def selected_contract(self) -> Optional[ContractDefinition]:
        cid = self.campaign.get("selected_contract")
        return CONTRACTS.get(cid) if cid else None

    def choose_dynamic_event(self) -> Optional[DynamicEventDefinition]:
        flags = self.flags()
        region = self.current_region()
        history = list(self.campaign.get("dynamic_event_history", []))
        recent = set(history[-2:])

        eligible: List[DynamicEventDefinition] = []
        weights: List[float] = []

        for event in DYNAMIC_EVENTS.values():
            if self.state.stats.nivel < event.minimum_level:
                continue
            if any(flag not in flags for flag in event.required_flags):
                continue
            if any(flag in flags for flag in event.forbidden_flags):
                continue
            if event.region_tags and not set(event.region_tags).intersection(region.tags):
                continue

            weight = event.weight
            if event.id in recent:
                weight *= 0.08
            eligible.append(event)
            weights.append(max(0.01, weight))

        if not eligible:
            return None

        chosen = random.choices(eligible, weights=weights, k=1)[0]
        history.append(chosen.id)
        self.campaign["dynamic_event_history"] = history[-12:]
        return chosen

    def append_run_history(
        self,
        *,
        result: str,
        rooms: int,
        region_id: str,
        boss_defeated: bool,
        style: str,
        active_rifts: Sequence[str],
    ) -> None:
        history = list(self.campaign.get("run_history", []))
        history.append(
            {
                "result": result,
                "rooms": int(rooms),
                "region_id": region_id,
                "boss_defeated": bool(boss_defeated),
                "style": style,
                "active_rifts": list(active_rifts),
                "class_id": self.state.identity.class_id,
                "level": self.state.stats.nivel,
            }
        )
        self.campaign["run_history"] = history[-20:]


# ============================================================
# DIÁLOGO CONTEXTUAL
# ============================================================


def _memory_rank_value(rank: MemoryRank) -> int:
    order = {
        MemoryRank.DESCONHECIDO: 0,
        MemoryRank.OBSERVADOR: 1,
        MemoryRank.ADAPTADO: 2,
        MemoryRank.PREDADOR: 3,
    }
    return order[rank]


def dialogue_condition_met(
    state: PlayerState,
    campaign: Dict[str, Any],
    condition: DialogueCondition,
) -> bool:
    flags = _flags(campaign)

    if condition.flag_required and condition.flag_required not in flags:
        return False
    if condition.flag_forbidden and condition.flag_forbidden in flags:
        return False
    if condition.boss_required and condition.boss_required not in state.progression.bosses_derrotados:
        return False
    if condition.rift_required and condition.rift_required not in state.progression.rupturas_descobertas:
        return False
    if condition.class_required and condition.class_required != state.identity.class_id:
        return False
    if state.stats.nivel < condition.min_level:
        return False
    if int(campaign.get("total_deaths", 0)) < condition.min_deaths:
        return False

    if condition.min_memory_rank is not None:
        memory = state.veil_memory.get("guardiao_primeira_ruptura")
        if _memory_rank_value(memory.rank()) < _memory_rank_value(condition.min_memory_rank):
            return False

    return True


def select_npc_dialogue(state: PlayerState, npc_id: str) -> Optional[DialogueEntry]:
    if npc_id not in NPCS:
        return None

    campaign = ensure_campaign_state(state)
    seen = set(campaign["dialogue_seen"])
    npc = NPCS[npc_id]

    candidates = []
    for entry in npc.dialogues:
        if entry.once and entry.id in seen:
            continue
        if dialogue_condition_met(state, campaign, entry.condition):
            candidates.append(entry)

    if not candidates:
        return None

    candidates.sort(key=lambda e: e.priority, reverse=True)
    top_priority = candidates[0].priority
    top = [entry for entry in candidates if entry.priority == top_priority]
    chosen = random.choice(top)

    if chosen.once:
        seen.add(chosen.id)
        campaign["dialogue_seen"] = sorted(seen)

    for flag_name in chosen.set_flags:
        _set_flag(campaign, flag_name)

    refresh_quest_availability(state)
    return chosen


# ============================================================
# RESUMOS / VALIDAÇÃO
# ============================================================


def chapter_title(chapter: int) -> str:
    titles = {
        1: "CAPÍTULO I — A PRIMEIRA FENDA",
        2: "CAPÍTULO II — O VÉU SE LEMBRA",
        3: "CAPÍTULO III — TEMPO FRATURADO",
        4: "CAPÍTULO IV — O NOME QUE O VAZIO APAGOU",
    }
    return titles.get(chapter, f"CAPÍTULO {chapter}")


def narrative_summary() -> Dict[str, int]:
    return {
        "regions": len(REGIONS),
        "npcs": len(NPCS),
        "quests": len(QUESTS),
        "contracts": len(CONTRACTS),
        "dynamic_events": len(DYNAMIC_EVENTS),
    }


def validate_narrative_content() -> List[str]:
    errors: List[str] = []

    for quest in QUESTS.values():
        for obj in quest.objectives:
            if obj.type == ObjectiveType.DISCOVER_RIFT and obj.target_id:
                if obj.target_id not in RIFT_REGISTRY:
                    errors.append(f"{quest.id}: Ruptura inválida {obj.target_id}")
            if obj.type == ObjectiveType.LEARN_SKILL and obj.target_id:
                if obj.target_id not in SKILL_REGISTRY:
                    errors.append(f"{quest.id}: habilidade inválida {obj.target_id}")
            if obj.type == ObjectiveType.UNLOCK_CLASS and obj.target_id:
                if obj.target_id not in CLASS_REGISTRY:
                    errors.append(f"{quest.id}: classe inválida {obj.target_id}")

        if quest.reward.unlock_region and quest.reward.unlock_region not in REGIONS:
            errors.append(f"{quest.id}: região de recompensa inválida")

        if quest.reward.unlock_class and quest.reward.unlock_class not in CLASS_REGISTRY:
            errors.append(f"{quest.id}: classe de recompensa inválida")

    for npc in NPCS.values():
        if npc.region_id not in REGIONS:
            errors.append(f"{npc.id}: região inválida")

    return errors

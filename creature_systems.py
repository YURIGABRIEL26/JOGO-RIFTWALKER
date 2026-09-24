"""RIFTWALKER — Creature / Bestiary Systems 0.6

Sistema independente de renderização para criaturas, mutações, inimigos
superiores e conhecimento do Arquivo do Véu.

Objetivos:
- impedir que inimigos sejam apenas sacos de HP;
- variar encontros sem trapacear;
- dar identidade regional às criaturas;
- transformar observação e repetição em conhecimento útil;
- conectar elites/superiores à Memória do Véu;
- manter tudo serializável nos saves atuais.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from core_systems import PlayerState, Rarity


# ============================================================
# ENUMS
# ============================================================

class CreatureTier(str, Enum):
    COMUM = "Comum"
    ELITE = "Elite"
    SUPERIOR = "Superior"
    BOSS = "Boss"


class KnowledgeRank(str, Enum):
    DESCONHECIDO = "Desconhecido"
    AVISTADO = "Avistado"
    ESTUDADO = "Estudado"
    CONHECIDO = "Conhecido"
    DOMINADO = "Dominado"


class MutationCategory(str, Enum):
    OFENSIVA = "Ofensiva"
    DEFENSIVA = "Defensiva"
    MOBILIDADE = "Mobilidade"
    CONTROLE = "Controle"
    RUPTURA = "Ruptura"
    TATICA = "Tática"


# ============================================================
# DEFINIÇÕES
# ============================================================

@dataclass(frozen=True)
class CreatureDefinition:
    id: str
    nome: str
    archetype: str
    descricao: str
    regions: Tuple[str, ...]
    base_tags: Tuple[str, ...]
    behavior_notes: str
    weakness_hint: str
    resistance_hint: str
    superior_title_pool: Tuple[str, ...] = ()
    archive_lore: Tuple[str, ...] = ()


@dataclass(frozen=True)
class MutationDefinition:
    id: str
    nome: str
    categoria: MutationCategory
    raridade: Rarity
    descricao: str
    tags: Tuple[str, ...]
    incompatible_tags: Tuple[str, ...] = ()
    hp_mult: float = 1.0
    damage_mult: float = 1.0
    speed_mult: float = 1.0
    xp_mult: float = 1.0
    radius_mult: float = 1.0
    behavior_hints: Tuple[str, ...] = ()
    reaction_lines: Tuple[str, ...] = ()


@dataclass
class SpawnTraits:
    creature_id: str
    tier: CreatureTier
    mutation_ids: List[str] = field(default_factory=list)
    superior_name: Optional[str] = None
    hp_mult: float = 1.0
    damage_mult: float = 1.0
    speed_mult: float = 1.0
    xp_mult: float = 1.0
    radius_mult: float = 1.0
    behavior_hints: List[str] = field(default_factory=list)


CREATURES: Dict[str, CreatureDefinition] = {}
MUTATIONS: Dict[str, MutationDefinition] = {}


def register_creature(definition: CreatureDefinition) -> CreatureDefinition:
    if definition.id in CREATURES:
        raise ValueError(f"Criatura duplicada: {definition.id}")
    CREATURES[definition.id] = definition
    return definition


def register_mutation(definition: MutationDefinition) -> MutationDefinition:
    if definition.id in MUTATIONS:
        raise ValueError(f"Mutação duplicada: {definition.id}")
    MUTATIONS[definition.id] = definition
    return definition


# ============================================================
# CRIATURAS ATUAIS + FUTURAS
# ============================================================

register_creature(CreatureDefinition(
    id="rastejante_fenda",
    nome="Rastejante da Fenda",
    archetype="crawler",
    descricao="Predador pequeno deformado por energia de Ruptura. Pressiona por proximidade.",
    regions=("campos_primeira_fenda", "bosque_sussurrante"),
    base_tags=("melee", "swarm", "rift"),
    behavior_notes="Tenta encurtar distância; em grupo ganha valor ao cercar.",
    weakness_hint="Controle de área e knockback quebram a pressão do enxame.",
    resistance_hint="Pouca utilidade em tentar vencer apenas por corrida em linha reta.",
    superior_title_pool=("Mandíbula Rubra", "Rastreador do Eco", "Quebra-Passos"),
    archive_lore=(
        "Os primeiros registros descrevem criaturas que atravessaram antes mesmo de o Véu estabilizar.",
        "A coordenação do enxame parece vir de impulsos compartilhados, não de linguagem.",
        "Rastejantes veteranos aprendem a esperar pelo dash antes de comprometer o avanço.",
    ),
))

register_creature(CreatureDefinition(
    id="atirador_veu",
    nome="Atirador do Véu",
    archetype="shooter",
    descricao="Entidade que cristaliza energia instável em projéteis de longo alcance.",
    regions=("campos_primeira_fenda", "ruinas_meridiano"),
    base_tags=("ranged", "rift", "support"),
    behavior_notes="Mantém distância, orbita e usa aliados como barreira.",
    weakness_hint="Flanco e aproximações imprevisíveis reduzem seu espaço de tiro.",
    resistance_hint="Trocas lentas a longa distância favorecem o Atirador.",
    superior_title_pool=("Olho do Horizonte", "Vigia Partido", "Mira Sem Rosto"),
    archive_lore=(
        "Seu disparo não é uma arma: é uma extensão temporária do próprio corpo.",
        "Alguns Atiradores reconhecem padrões de esquiva após poucas trocas.",
        "Quando protegidos por Tanks, priorizam o alvo mais exposto do grupo.",
    ),
))

register_creature(CreatureDefinition(
    id="baluarte_fraturado",
    nome="Baluarte Fraturado",
    archetype="tank",
    descricao="Massa blindada que transforma o próprio corpo em parede móvel.",
    regions=("campos_primeira_fenda", "ruinas_meridiano", "fortaleza_afogada"),
    base_tags=("tank", "melee", "guard"),
    behavior_notes="Controla espaço e protege unidades frágeis.",
    weakness_hint="Ataques pelas laterais e efeitos persistentes punem sua lentidão.",
    resistance_hint="Golpes frontais repetidos alimentam sua função de muralha.",
    superior_title_pool=("Muralha que Anda", "Escudo Sem Mestre", "Último Bastião"),
    archive_lore=(
        "As placas do Baluarte crescem em resposta a impactos repetidos.",
        "Eles não precisam ser rápidos quando conseguem decidir onde a luta acontece.",
        "Baluartes superiores já foram vistos coordenando recuos para cobrir aliados.",
    ),
))

register_creature(CreatureDefinition(
    id="cacador_ecos",
    nome="Caçador de Ecos",
    archetype="hunter",
    descricao="Predador veloz especializado em perseguir alvos que acabaram de gastar mobilidade.",
    regions=("bosque_sussurrante", "cidade_invertida", "fortaleza_afogada"),
    base_tags=("hunter", "mobility", "melee"),
    behavior_notes="Espera janelas de vulnerabilidade e pune dashes mal usados.",
    weakness_hint="Guardar mobilidade para a resposta quebra seu ciclo de perseguição.",
    resistance_hint="Dash automático para trás pode ser previsto por versões adaptadas.",
    superior_title_pool=("Passo Atrás", "Farejador de Medo", "Sem-Distância"),
    archive_lore=(
        "O Caçador percebe resíduos deixados por deslocamentos rápidos.",
        "Sua fama de 'ler dashes' vem de rastrear ecos, não de prever o futuro.",
        "Indivíduos antigos alteram o momento da investida para quebrar hábitos do Riftwalker.",
    ),
))

register_creature(CreatureDefinition(
    id="guardiao_primeira_ruptura",
    nome="Guardião da Primeira Ruptura",
    archetype="guardian",
    descricao="Entidade superior ligada diretamente à memória da primeira fenda conhecida.",
    regions=("campos_primeira_fenda",),
    base_tags=("boss", "memory", "rift"),
    behavior_notes="Troca padrões conforme Memória do Véu e fase da luta.",
    weakness_hint="Variar o próprio estilo reduz o valor das contramedidas memorizadas.",
    resistance_hint="Repetir a mesma resposta entre encontros alimenta sua adaptação.",
    superior_title_pool=("A Memória que Vigia",),
    archive_lore=(
        "O Guardião não protege apenas um lugar; protege uma lembrança.",
        "Cada derrota deixa informação suficiente para que sua próxima manifestação mude.",
        "O Arquivo suspeita que destruir o corpo não destrói a entidade que o recompõe.",
    ),
))

# Criaturas já desenhadas no conteúdo futuro, mas ainda não conectadas ao render.
register_creature(CreatureDefinition(
    id="lamento_micelio",
    nome="Lamento Micélio",
    archetype="support_future",
    descricao="Organismo do Bosque Sussurrante que espalha esporos de controle.",
    regions=("bosque_sussurrante",),
    base_tags=("support", "spore", "control"),
    behavior_notes="Fortalece aliados e cria zonas ruins para permanecer parado.",
    weakness_hint="Interromper o suporte cedo evita que o grupo escale.",
    resistance_hint="Ignorá-lo transforma lutas simples em guerras de atrito.",
    superior_title_pool=("Raiz que Chora", "Voz sob a Casca"),
    archive_lore=("O som que emite é produzido por cavidades cheias de esporos.",),
))

register_creature(CreatureDefinition(
    id="sentinela_meridiano",
    nome="Sentinela do Meridiano",
    archetype="construct_future",
    descricao="Construto antigo reativado pela passagem de Rupturas temporais.",
    regions=("ruinas_meridiano",),
    base_tags=("construct", "ranged", "temporal"),
    behavior_notes="Alterna rotinas previsíveis com saltos temporais curtos.",
    weakness_hint="Observar o padrão antes do salto revela sua posição provável.",
    resistance_hint="Spam de ataque durante a fase de deslocamento desperdiça recursos.",
    superior_title_pool=("Relógio Sem Hora", "Vigia do Segundo Morto"),
    archive_lore=("Há inscrições que registram horas que nunca existiram.",),
))

register_creature(CreatureDefinition(
    id="afogado_sem_rosto",
    nome="Afogado Sem Rosto",
    archetype="ambusher_future",
    descricao="Habitante da Fortaleza Afogada que usa água e sombra para ocultar aproximações.",
    regions=("fortaleza_afogada",),
    base_tags=("ambush", "water", "shadow"),
    behavior_notes="Desaparece brevemente e tenta atacar por ângulo cego.",
    weakness_hint="Movimento constante e leitura de áudio reduzem o valor da emboscada.",
    resistance_hint="Ficar parado facilita o ataque de reaparecimento.",
    superior_title_pool=("Pulmão Vazio", "Aquele Sob a Água"),
    archive_lore=("Não há rosto sob a máscara de água condensada.",),
))

register_creature(CreatureDefinition(
    id="peregrino_invertido",
    nome="Peregrino Invertido",
    archetype="mage_future",
    descricao="Figura da Cidade Invertida que conjura usando geometria impossível.",
    regions=("cidade_invertida",),
    base_tags=("magic", "teleport", "void"),
    behavior_notes="Reposiciona após conjurações e cria falsos pontos de ameaça.",
    weakness_hint="Atacar após o reposicionamento, não antes, reduz desperdício.",
    resistance_hint="Perseguição linear é punida por teleporte curto.",
    superior_title_pool=("Passageiro do Teto", "Geômetra Partido"),
    archive_lore=("Mapas da cidade não concordam sobre qual direção é o chão.",),
))

register_creature(CreatureDefinition(
    id="eco_do_riftwalker",
    nome="Eco do Riftwalker",
    archetype="mirror_future",
    descricao="Manifestação rara formada a partir de resíduos de escolhas do próprio jogador.",
    regions=("cidade_invertida", "nucleo_do_veu"),
    base_tags=("mirror", "memory", "rift"),
    behavior_notes="Replica tendências gerais do jogador sem copiar inputs em tempo real.",
    weakness_hint="Mudar de ritmo força o Eco a trabalhar com informação velha.",
    resistance_hint="Repetir a build e o comportamento torna o espelho mais eficiente.",
    superior_title_pool=("Você que Ficou", "Nome Esquecido"),
    archive_lore=("O Arquivo proíbe chamar essas entidades de clones.",),
))


# ============================================================
# MUTAÇÕES / AFIXOS
# ============================================================

def _m(*args, **kwargs):
    return register_mutation(MutationDefinition(*args, **kwargs))

_m("feroz", "Feroz", MutationCategory.OFENSIVA, Rarity.INCOMUM,
   "Ataques mais fortes, porém postura mais agressiva.", ("aggressive",),
   damage_mult=1.25, xp_mult=1.12,
   behavior_hints=("pressao_continua",), reaction_lines=("O monstro entra em frenesi.",))

_m("colossal", "Colossal", MutationCategory.DEFENSIVA, Rarity.RARA,
   "Corpo ampliado e muito mais resistente.", ("large", "durable"),
   incompatible_tags=("swift",), hp_mult=1.65, speed_mult=0.86, radius_mult=1.18, xp_mult=1.28,
   behavior_hints=("segurar_posicao",))

_m("veloz", "Veloz", MutationCategory.MOBILIDADE, Rarity.RARA,
   "Movimentos curtos e explosivos tornam a aproximação menos previsível.", ("swift",),
   incompatible_tags=("large",), speed_mult=1.34, hp_mult=0.92, xp_mult=1.22,
   behavior_hints=("troca_de_ritmo", "flanco"))

_m("espinhos_veu", "Espinhos do Véu", MutationCategory.DEFENSIVA, Rarity.EPICA,
   "Parte do dano corpo a corpo gera retaliação telegráfica.", ("thorn", "rift"),
   hp_mult=1.15, xp_mult=1.30,
   behavior_hints=("punir_combo_longo",), reaction_lines=("Espinhos de energia surgem pela carapaça.",))

_m("faseante", "Faseante", MutationCategory.MOBILIDADE, Rarity.EPICA,
   "Periodicamente atravessa o Véu por um instante e reposiciona.", ("phase", "rift"),
   speed_mult=1.12, xp_mult=1.38,
   behavior_hints=("reposicionar", "finta"))

_m("sanguessuga", "Sanguessuga", MutationCategory.OFENSIVA, Rarity.EPICA,
   "Recupera parte da vitalidade ao acertar ataques importantes.", ("lifesteal",),
   damage_mult=1.08, hp_mult=1.12, xp_mult=1.32,
   behavior_hints=("pressao_continua",))

_m("tempestuoso", "Tempestuoso", MutationCategory.CONTROLE, Rarity.EPICA,
   "Descargas periódicas criam zonas temporárias de perigo.", ("storm", "area"),
   xp_mult=1.35, behavior_hints=("zona_de_negacao",))

_m("caçador_dash", "Caçador de Passos", MutationCategory.TATICA, Rarity.LENDARIA,
   "Especializado em punir mobilidade usada sempre da mesma forma.", ("memory", "hunter"),
   speed_mult=1.15, damage_mult=1.12, xp_mult=1.55,
   behavior_hints=("punir_dash", "cortar_rota_fuga"), reaction_lines=("Ele esperou exatamente o seu passo.",))

_m("silenciador", "Silenciador", MutationCategory.CONTROLE, Rarity.LENDARIA,
   "Ataques especiais podem criar uma curta zona que atrapalha conjurações.", ("silence", "control"),
   hp_mult=1.12, xp_mult=1.52,
   behavior_hints=("interromper_conjuracao",))

_m("eco_memoria", "Eco de Memória", MutationCategory.RUPTURA, Rarity.LENDARIA,
   "Carrega resíduos de encontros anteriores e recebe um padrão tático extra.", ("memory", "rift"),
   hp_mult=1.18, damage_mult=1.15, xp_mult=1.62,
   behavior_hints=("variacao_tatica", "troca_de_ritmo"))

_m("instavel", "Instável", MutationCategory.RUPTURA, Rarity.RARA,
   "Oscila entre explosões de velocidade e pequenas hesitações.", ("chaos", "rift"),
   speed_mult=1.16, damage_mult=1.08, xp_mult=1.25,
   behavior_hints=("troca_de_ritmo",))

_m("guardiao_enxame", "Guardião do Enxame", MutationCategory.TATICA, Rarity.EPICA,
   "Fortalece coordenação de aliados próximos e protege alvos frágeis.", ("support", "squad"),
   hp_mult=1.20, xp_mult=1.36,
   behavior_hints=("proteger_ranged", "formacao_mista"))

_m("quebra_barreira", "Quebra-Barreira", MutationCategory.OFENSIVA, Rarity.LENDARIA,
   "Golpes pesados ganham valor contra defesa repetida.", ("anti_guard",),
   damage_mult=1.20, xp_mult=1.48,
   behavior_hints=("punir_defesa_repetida", "agarrar"))

_m("vidente", "Vidente", MutationCategory.TATICA, Rarity.MITICA,
   "Lê tendências antigas do Riftwalker e alterna entre múltiplas respostas válidas.", ("memory", "seer"),
   hp_mult=1.20, damage_mult=1.18, speed_mult=1.12, xp_mult=1.90,
   behavior_hints=("variacao_tatica", "finta", "troca_de_ritmo"),
   reaction_lines=("A criatura hesita... como se lembrasse de algo que ainda não aconteceu.",))

_m("corrompido", "Corrompido", MutationCategory.RUPTURA, Rarity.CORROMPIDA,
   "Energia de Ruptura transborda: poder extremo com comportamento menos estável.", ("corruption", "rift"),
   hp_mult=1.35, damage_mult=1.38, speed_mult=1.12, xp_mult=2.25,
   behavior_hints=("desespero", "zona_de_negacao", "pressao_continua"))


RARITY_MUTATION_WEIGHT: Dict[Rarity, float] = {
    Rarity.COMUM: 0.0,
    Rarity.INCOMUM: 45.0,
    Rarity.RARA: 28.0,
    Rarity.EPICA: 15.0,
    Rarity.LENDARIA: 8.0,
    Rarity.MITICA: 2.5,
    Rarity.CORROMPIDA: 1.5,
}


# ============================================================
# MAPEAMENTO DO GAMEPLAY ATUAL
# ============================================================

ARCHETYPE_TO_CREATURE = {
    "crawler": "rastejante_fenda",
    "shooter": "atirador_veu",
    "tank": "baluarte_fraturado",
    "hunter": "cacador_ecos",
    "guardian": "guardiao_primeira_ruptura",
}


def creature_id_for_archetype(archetype: str) -> str:
    return ARCHETYPE_TO_CREATURE.get(archetype, archetype)


# ============================================================
# BESTIÁRIO / ARQUIVO
# ============================================================

BESTIARY_THRESHOLDS = {
    KnowledgeRank.DESCONHECIDO: 0,
    KnowledgeRank.AVISTADO: 1,
    KnowledgeRank.ESTUDADO: 4,
    KnowledgeRank.CONHECIDO: 12,
    KnowledgeRank.DOMINADO: 30,
}


def _entry(state: PlayerState, creature_id: str) -> Dict[str, Any]:
    if creature_id not in CREATURES:
        raise ValueError(f"Criatura desconhecida: {creature_id}")

    entry = state.progression.bestiario.get(creature_id)
    if not isinstance(entry, dict):
        entry = {}
        state.progression.bestiario[creature_id] = entry

    defaults = {
        "encounters": 0,
        "kills": 0,
        "deaths_to": 0,
        "superior_kills": 0,
        "knowledge_points": 0,
        "seen_mutations": [],
        "mastered_mutations": [],
        "last_superior_name": None,
    }
    for key, value in defaults.items():
        if key not in entry:
            entry[key] = list(value) if isinstance(value, list) else value

    return entry


def knowledge_rank(state: PlayerState, creature_id: str) -> KnowledgeRank:
    points = int(_entry(state, creature_id).get("knowledge_points", 0))
    rank = KnowledgeRank.DESCONHECIDO
    for candidate, threshold in BESTIARY_THRESHOLDS.items():
        if points >= threshold:
            rank = candidate
    return rank


def add_knowledge(state: PlayerState, creature_id: str, amount: int) -> Tuple[KnowledgeRank, KnowledgeRank]:
    entry = _entry(state, creature_id)
    before = knowledge_rank(state, creature_id)
    entry["knowledge_points"] = max(0, int(entry.get("knowledge_points", 0)) + max(0, int(amount)))
    after = knowledge_rank(state, creature_id)
    return before, after


def record_encounter(state: PlayerState, creature_id: str, mutation_ids: Iterable[str] = ()) -> Tuple[KnowledgeRank, KnowledgeRank]:
    entry = _entry(state, creature_id)
    entry["encounters"] += 1
    seen = set(entry.get("seen_mutations", []))
    seen.update(mid for mid in mutation_ids if mid in MUTATIONS)
    entry["seen_mutations"] = sorted(seen)
    return add_knowledge(state, creature_id, 1)


def record_kill(
    state: PlayerState,
    creature_id: str,
    mutation_ids: Iterable[str] = (),
    superior: bool = False,
    superior_name: Optional[str] = None,
) -> Tuple[KnowledgeRank, KnowledgeRank]:
    entry = _entry(state, creature_id)
    entry["kills"] += 1
    if superior:
        entry["superior_kills"] += 1
        entry["last_superior_name"] = superior_name
    seen = set(entry.get("seen_mutations", []))
    seen.update(mid for mid in mutation_ids if mid in MUTATIONS)
    entry["seen_mutations"] = sorted(seen)
    points = 3 + len(tuple(mutation_ids)) * 2 + (5 if superior else 0)
    return add_knowledge(state, creature_id, points)


def record_death_to(state: PlayerState, creature_id: str, mutation_ids: Iterable[str] = ()) -> Tuple[KnowledgeRank, KnowledgeRank]:
    entry = _entry(state, creature_id)
    entry["deaths_to"] += 1
    # Morrer ensina alguma coisa, mas menos que vencer.
    seen = set(entry.get("seen_mutations", []))
    seen.update(mid for mid in mutation_ids if mid in MUTATIONS)
    entry["seen_mutations"] = sorted(seen)
    return add_knowledge(state, creature_id, 2)


def bestiary_entry_view(state: PlayerState, creature_id: str) -> Dict[str, Any]:
    definition = CREATURES[creature_id]
    entry = _entry(state, creature_id)
    rank = knowledge_rank(state, creature_id)

    order = list(KnowledgeRank)
    rank_index = order.index(rank)

    data: Dict[str, Any] = {
        "id": creature_id,
        "nome": definition.nome if rank != KnowledgeRank.DESCONHECIDO else "???",
        "rank": rank.value,
        "encounters": entry["encounters"],
        "kills": entry["kills"],
        "deaths_to": entry["deaths_to"],
        "superior_kills": entry["superior_kills"],
        "seen_mutations": list(entry["seen_mutations"]),
    }

    if rank_index >= 1:
        data["descricao"] = definition.descricao
        data["regions"] = list(definition.regions)

    if rank_index >= 2:
        data["behavior"] = definition.behavior_notes
        data["weakness_hint"] = definition.weakness_hint

    if rank_index >= 3:
        data["resistance_hint"] = definition.resistance_hint
        data["lore"] = list(definition.archive_lore[:2])

    if rank_index >= 4:
        data["lore"] = list(definition.archive_lore)
        data["mastery_bonus"] = "+5% de recompensa de conhecimento ao derrotar variantes superiores desta criatura."

    return data


def bestiary_completion(state: PlayerState) -> Dict[str, Any]:
    ranks = {rank.value: 0 for rank in KnowledgeRank}
    discovered = 0
    total_points = 0

    for creature_id in CREATURES:
        rank = knowledge_rank(state, creature_id)
        ranks[rank.value] += 1
        entry = _entry(state, creature_id)
        total_points += int(entry["knowledge_points"])
        if rank != KnowledgeRank.DESCONHECIDO:
            discovered += 1

    return {
        "discovered": discovered,
        "total": len(CREATURES),
        "percent": round(discovered / max(1, len(CREATURES)) * 100, 1),
        "knowledge_points": total_points,
        "ranks": ranks,
    }


# ============================================================
# ARQUIVO DO VÉU / PESQUISA
# ============================================================


def ensure_archive_state(state: PlayerState) -> Dict[str, Any]:
    campaign = state.campaign if isinstance(state.campaign, dict) else {}
    state.campaign = campaign
    archive = campaign.get("veil_archive")
    if not isinstance(archive, dict):
        archive = {}
        campaign["veil_archive"] = archive

    defaults = {
        "research_points": 0,
        "completed_research": [],
        "specimens": {},
        "superior_history": [],
        "lifetime_superiors": 0,
    }
    for key, value in defaults.items():
        if key not in archive:
            archive[key] = list(value) if isinstance(value, list) else dict(value) if isinstance(value, dict) else value
    return archive


RESEARCH_PROJECTS: Dict[str, Dict[str, Any]] = {
    "taxonomia_fendas": {
        "name": "Taxonomia das Fendas",
        "cost": 12,
        "description": "Melhora ganho de conhecimento por primeiro encontro.",
        "requires": (),
    },
    "autopsia_superiores": {
        "name": "Autópsia de Superiores",
        "cost": 24,
        "description": "Revela mais cedo os afixos presentes em inimigos superiores.",
        "requires": ("taxonomia_fendas",),
    },
    "padroes_memoria": {
        "name": "Padrões da Memória",
        "cost": 36,
        "description": "Expõe o nível de Memória do Véu antes de reencontros importantes.",
        "requires": ("autopsia_superiores",),
    },
    "contramedidas_documentadas": {
        "name": "Contramedidas Documentadas",
        "cost": 55,
        "description": "Bestiário conhecido passa a mostrar dicas táticas completas.",
        "requires": ("padroes_memoria",),
    },
}


def add_research_points(state: PlayerState, amount: int) -> int:
    archive = ensure_archive_state(state)
    archive["research_points"] = max(0, int(archive["research_points"]) + max(0, int(amount)))
    return archive["research_points"]


def can_research(state: PlayerState, project_id: str) -> Tuple[bool, str]:
    if project_id not in RESEARCH_PROJECTS:
        return False, "Projeto desconhecido."
    archive = ensure_archive_state(state)
    project = RESEARCH_PROJECTS[project_id]
    completed = set(archive["completed_research"])
    if project_id in completed:
        return False, "Pesquisa já concluída."
    missing = [req for req in project["requires"] if req not in completed]
    if missing:
        return False, "Pesquisa anterior necessária."
    if archive["research_points"] < project["cost"]:
        return False, "Pontos de pesquisa insuficientes."
    return True, "Disponível."


def complete_research(state: PlayerState, project_id: str) -> Tuple[bool, str]:
    ok, reason = can_research(state, project_id)
    if not ok:
        return False, reason
    archive = ensure_archive_state(state)
    project = RESEARCH_PROJECTS[project_id]
    archive["research_points"] -= project["cost"]
    archive["completed_research"].append(project_id)
    return True, f"Pesquisa concluída: {project['name']}"


# ============================================================
# GERAÇÃO DE MUTAÇÕES / SUPERIORES
# ============================================================


def _weighted_mutation(pool: Sequence[MutationDefinition]) -> MutationDefinition:
    weights = [RARITY_MUTATION_WEIGHT[m.raridade] for m in pool]
    return random.choices(list(pool), weights=weights, k=1)[0]


def mutation_pool_for(creature_id: str, active_rift_ids: Iterable[str] = ()) -> List[MutationDefinition]:
    creature = CREATURES[creature_id]
    creature_tags = set(creature.base_tags)
    rift_tags = set(active_rift_ids)
    pool: List[MutationDefinition] = []

    for mutation in MUTATIONS.values():
        # Algumas mutações fazem mais sentido em arquétipos específicos.
        if "hunter" in mutation.tags and "hunter" not in creature_tags and "memory" not in creature_tags:
            continue
        if "support" in mutation.tags and not ({"support", "tank"} & creature_tags):
            continue
        if "anti_guard" in mutation.tags and creature.archetype not in ("tank", "guardian", "hunter"):
            continue
        if mutation.id == "corrompido" and not rift_tags:
            continue
        pool.append(mutation)

    return pool


def roll_spawn_traits(
    creature_id: str,
    wave: int,
    active_rift_ids: Iterable[str] = (),
    elite: bool = False,
    boss: bool = False,
    force_superior: bool = False,
    rng: Optional[random.Random] = None,
) -> SpawnTraits:
    if creature_id not in CREATURES:
        raise ValueError(f"Criatura desconhecida: {creature_id}")

    rng = rng or random
    active_rifts = list(active_rift_ids)

    if boss:
        tier = CreatureTier.BOSS
    elif force_superior:
        tier = CreatureTier.SUPERIOR
    elif elite:
        tier = CreatureTier.ELITE
    else:
        # Chance cresce devagar com wave e Rupturas.
        superior_chance = min(0.28, 0.015 + wave * 0.006 + len(active_rifts) * 0.025)
        tier = CreatureTier.SUPERIOR if rng.random() < superior_chance else CreatureTier.COMUM

    mutation_count = 0
    if tier == CreatureTier.ELITE:
        mutation_count = 1 if wave >= 4 and rng.random() < 0.45 else 0
    elif tier == CreatureTier.SUPERIOR:
        mutation_count = 1 + (1 if wave >= 8 or len(active_rifts) >= 2 else 0)
        if wave >= 15 and rng.random() < 0.35:
            mutation_count += 1
    elif tier == CreatureTier.BOSS:
        mutation_count = min(2, len(active_rifts))

    pool = mutation_pool_for(creature_id, active_rifts)
    chosen: List[MutationDefinition] = []
    chosen_tags: Set[str] = set()

    # Usa o RNG fornecido também no peso para teste determinístico.
    for _ in range(mutation_count):
        valid = [
            mutation for mutation in pool
            if mutation.id not in {x.id for x in chosen}
            and not (set(mutation.incompatible_tags) & chosen_tags)
            and not any(set(x.incompatible_tags) & set(mutation.tags) for x in chosen)
        ]
        if not valid:
            break
        weights = [RARITY_MUTATION_WEIGHT[m.raridade] for m in valid]
        mutation = rng.choices(valid, weights=weights, k=1)[0]
        chosen.append(mutation)
        chosen_tags.update(mutation.tags)

    traits = SpawnTraits(
        creature_id=creature_id,
        tier=tier,
        mutation_ids=[m.id for m in chosen],
    )

    for mutation in chosen:
        traits.hp_mult *= mutation.hp_mult
        traits.damage_mult *= mutation.damage_mult
        traits.speed_mult *= mutation.speed_mult
        traits.xp_mult *= mutation.xp_mult
        traits.radius_mult *= mutation.radius_mult
        traits.behavior_hints.extend(mutation.behavior_hints)

    if tier == CreatureTier.SUPERIOR:
        creature = CREATURES[creature_id]
        title = rng.choice(creature.superior_title_pool or ("Marcado pelo Véu",))
        if chosen:
            traits.superior_name = f"{creature.nome}, {title} [{chosen[0].nome}]"
        else:
            traits.superior_name = f"{creature.nome}, {title}"
        # Superior é perigoso mesmo antes do primeiro afixo.
        traits.hp_mult *= 1.35
        traits.damage_mult *= 1.12
        traits.xp_mult *= 1.50

    if tier == CreatureTier.BOSS:
        traits.hp_mult *= 1.0
        traits.xp_mult *= 1.0

    return traits


def apply_traits_to_enemy(enemy: Any, traits: SpawnTraits) -> None:
    """Aplica traits por duck typing para não acoplar este módulo ao Pygame."""
    enemy.creature_id = traits.creature_id
    enemy.creature_tier = traits.tier.value
    enemy.mutation_ids = list(traits.mutation_ids)
    enemy.superior_name = traits.superior_name
    enemy.mutation_behavior_hints = list(traits.behavior_hints)

    enemy.max_hp = max(1, int(enemy.max_hp * traits.hp_mult))
    enemy.hp = enemy.max_hp
    enemy.damage = max(1, enemy.damage * traits.damage_mult)
    enemy.speed = max(1.0, enemy.speed * traits.speed_mult)
    enemy.xp = max(1, int(enemy.xp * traits.xp_mult))
    enemy.radius = max(5, int(enemy.radius * traits.radius_mult))


def mutation_display(mutation_ids: Iterable[str]) -> str:
    names = [MUTATIONS[mid].nome for mid in mutation_ids if mid in MUTATIONS]
    return " • ".join(names)


def superior_memory_id(traits: SpawnTraits) -> str:
    if traits.tier != CreatureTier.SUPERIOR:
        return traits.creature_id
    suffix = "+".join(sorted(traits.mutation_ids)) or "base"
    return f"superior:{traits.creature_id}:{suffix}"


# ============================================================
# RECOMPENSA / CONHECIMENTO DE SUPERIOR
# ============================================================


def record_superior_history(state: PlayerState, traits: SpawnTraits, defeated: bool) -> None:
    if traits.tier != CreatureTier.SUPERIOR:
        return
    archive = ensure_archive_state(state)
    archive["superior_history"].append({
        "creature_id": traits.creature_id,
        "name": traits.superior_name,
        "mutations": list(traits.mutation_ids),
        "defeated": bool(defeated),
    })
    archive["superior_history"] = archive["superior_history"][-30:]
    if defeated:
        archive["lifetime_superiors"] += 1
        add_research_points(state, 3 + len(traits.mutation_ids) * 2)


def knowledge_reward_multiplier(state: PlayerState, creature_id: str) -> float:
    return 1.05 if knowledge_rank(state, creature_id) == KnowledgeRank.DOMINADO else 1.0


# ============================================================
# VALIDAÇÃO / RESUMO
# ============================================================


def validate_creature_content() -> List[str]:
    problems: List[str] = []

    archetypes = set()
    for creature in CREATURES.values():
        if not creature.regions:
            problems.append(f"{creature.id}: sem região")
        if not creature.base_tags:
            problems.append(f"{creature.id}: sem tags")
        archetypes.add(creature.archetype)

    for mutation in MUTATIONS.values():
        if mutation.hp_mult <= 0 or mutation.damage_mult <= 0 or mutation.speed_mult <= 0:
            problems.append(f"{mutation.id}: multiplicador inválido")
        if mutation.xp_mult < 1.0:
            problems.append(f"{mutation.id}: mutação reduz XP")

    for archetype, creature_id in ARCHETYPE_TO_CREATURE.items():
        if creature_id not in CREATURES:
            problems.append(f"mapa {archetype}: criatura ausente")

    return problems


def creature_summary() -> Dict[str, Any]:
    return {
        "creatures": len(CREATURES),
        "mutations": len(MUTATIONS),
        "research_projects": len(RESEARCH_PROJECTS),
        "current_archetypes": len(ARCHETYPE_TO_CREATURE),
    }

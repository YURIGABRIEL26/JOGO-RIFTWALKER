"""RIFTWALKER — CLASS KITS / EXPANDED SKILLS 0.9 RC

Fecha a identidade mecânica das 10 classes sem depender do Pygame.
As definições entram no SKILL_REGISTRY no import e os comportamentos
são descritos por metadados que a camada visual/gameplay pode executar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from core_systems import (
    DamageType,
    Rarity,
    SkillCategory,
    SkillDefinition,
    SKILL_REGISTRY,
    register_skill,
)


@dataclass(frozen=True)
class SkillBehavior:
    mode: str
    radius: float = 0.0
    range: float = 0.0
    projectile_speed: float = 0.0
    projectile_count: int = 1
    spread: float = 0.0
    pierce: int = 0
    duration: float = 0.0
    power_scale: float = 1.0
    knockback: float = 0.0
    dash_distance: float = 0.0
    status: Optional[str] = None
    note: str = ""


@dataclass(frozen=True)
class ClassKit:
    class_id: str
    nome: str
    assinatura: str
    role: str
    recommended_skills: Tuple[str, ...]
    mastery_goal: str


SKILL_BEHAVIORS: Dict[str, SkillBehavior] = {}
CLASS_KITS: Dict[str, ClassKit] = {}


def _skill(skill: SkillDefinition, behavior: SkillBehavior) -> None:
    if skill.id not in SKILL_REGISTRY:
        register_skill(skill)
    SKILL_BEHAVIORS[skill.id] = behavior


def _def(
    skill_id: str,
    nome: str,
    descricao: str,
    rarity: Rarity,
    category: SkillCategory,
    dtype: DamageType,
    damage: float,
    cooldown: float,
    cost: float,
    class_id: str,
    tags: Tuple[str, ...],
    behavior: SkillBehavior,
    voice: Tuple[str, ...] = (),
    unique: bool = False,
    corrupted: bool = False,
) -> None:
    _skill(
        SkillDefinition(
            id=skill_id,
            nome=nome,
            descricao=descricao,
            raridade=rarity,
            categoria=category,
            damage_type=dtype,
            base_damage=damage,
            cooldown=cooldown,
            resource_cost=cost,
            allowed_classes=(class_id,),
            tags=tags,
            unique=unique,
            corrupted=corrupted,
            voice_lines_male=voice,
            voice_lines_female=voice,
            gameplay_notes=behavior.note,
        ),
        behavior,
    )


# ---------------------------------------------------------------------------
# GUERREIRO
# ---------------------------------------------------------------------------
_def(
    "investida_de_ferro", "Investida de Ferro",
    "Avança com o escudo e atravessa a linha inimiga.",
    Rarity.INCOMUM, SkillCategory.MOBILIDADE, DamageType.FISICO,
    46, 4.2, 15, "guerreiro", ("melee", "dash", "shield"),
    SkillBehavior("dash_strike", radius=72, dash_distance=150, power_scale=1.0, knockback=48,
                  note="Avanço ofensivo com controle de espaço."),
    ("SAIAM DA FRENTE!", "ABRAM!"),
)
_def(
    "golpe_sismico", "Golpe Sísmico",
    "Golpeia o chão e envia uma onda curta ao redor.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.FISICO,
    74, 7.5, 23, "guerreiro", ("melee", "area", "stagger"),
    SkillBehavior("aoe_self", radius=175, power_scale=1.0, knockback=62,
                  note="Área curta com grande stagger."),
    ("AO CHÃO!", "QUEBREM!"),
)
_def(
    "juramento_de_guerra", "Juramento de Guerra",
    "Por alguns segundos, dano recebido alimenta o próximo golpe.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.FISICO,
    0, 24.0, 38, "guerreiro", ("buff", "tank", "retaliation"),
    SkillBehavior("self_buff", duration=6.0, status="war_oath",
                  note="Converte pressão sofrida em retaliação."),
    ("EU NÃO CAIO!", "VENHAM TODOS!"), unique=True,
)

# ---------------------------------------------------------------------------
# MAGO
# ---------------------------------------------------------------------------
_def(
    "corrente_arcana", "Corrente Arcana",
    "Raio arcano salta entre inimigos próximos.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.RAIO,
    40, 3.2, 18, "mago", ("magic", "lightning", "chain"),
    SkillBehavior("multi_projectile", projectile_speed=620, projectile_count=3, spread=10, range=720,
                  power_scale=0.82, note="Rajada curta; executor pode encadear em alvos."),
    ("CORRENTE ARCANA!", "SALTE!"),
)
_def(
    "meteoro_do_veu", "Meteoro do Véu",
    "Marca o solo; após o aviso, um meteoro rompe o Véu e explode.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.FOGO,
    220, 25.0, 78, "mago", ("magic", "fire", "area", "ultimate"),
    SkillBehavior("delayed_aoe", radius=190, duration=1.15, power_scale=1.0,
                  note="Grande telegraph antes do impacto."),
    ("CAIA SOBRE ELES!", "METEORO DO VÉU!"), unique=True,
)

# ---------------------------------------------------------------------------
# ARQUEIRO
# ---------------------------------------------------------------------------
_def(
    "passo_do_cacador", "Passo do Caçador",
    "Reposiciona rapidamente e fortalece o próximo disparo.",
    Rarity.INCOMUM, SkillCategory.MOBILIDADE, DamageType.FISICO,
    0, 4.4, 16, "arqueiro", ("mobility", "precision", "dash"),
    SkillBehavior("dash_buff", dash_distance=135, duration=3.5, status="hunter_step",
                  note="Dash + buff do próximo projétil."),
    ("MUITO LENTO.", "TENTE ACOMPANHAR."),
)
_def(
    "flecha_fantasma", "Flecha Fantasma",
    "Disparo do Véu que atravessa inimigos e retorna uma vez.",
    Rarity.LENDARIA, SkillCategory.ATIVA, DamageType.VAZIO,
    105, 8.0, 32, "arqueiro", ("ranged", "pierce", "void"),
    SkillBehavior("projectile", projectile_speed=900, pierce=8, range=1100, power_scale=1.0,
                  note="Projétil perfurante; retorno será polido visualmente depois."),
    ("ATRAVESSE.", "FLECHA FANTASMA!"), unique=True,
)

# ---------------------------------------------------------------------------
# CEIFADOR
# ---------------------------------------------------------------------------
_def(
    "manto_funerario", "Manto Funerário",
    "Envolve-se em sombra, reduzindo dano e aumentando roubo de vida.",
    Rarity.RARA, SkillCategory.DEFENSIVA, DamageType.SOMBRA,
    0, 9.0, 24, "ceifador", ("shadow", "defense", "lifesteal"),
    SkillBehavior("self_buff", duration=5.5, status="funeral_mantle"),
    ("AINDA NÃO.", "A MORTE ESPERA."),
)
_def(
    "foice_espectral", "Foice Espectral",
    "Projeta uma lâmina de sombra em linha reta.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.SOMBRA,
    58, 2.8, 15, "ceifador", ("shadow", "ranged", "scythe"),
    SkillBehavior("projectile", projectile_speed=650, pierce=2, range=800, power_scale=1.0),
    ("CORTE.",),
)
_def(
    "banquete_de_almas", "Banquete de Almas",
    "Consome marcas de inimigos mortos recentemente para recuperar vida e Essência.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.SOMBRA,
    0, 12.0, 0, "ceifador", ("heal", "soul", "sustain"),
    SkillBehavior("self_buff", duration=0.1, status="soul_feast",
                  note="Executor converte recursos de combate em cura."),
    ("VENHAM A MIM.",),
)
_def(
    "procissao_dos_mortos", "Procissão dos Mortos",
    "Ecos de inimigos executados atravessam a arena em direção ao alvo.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.SOMBRA,
    165, 23.0, 60, "ceifador", ("shadow", "summon", "ultimate"),
    SkillBehavior("multi_projectile", projectile_speed=500, projectile_count=7, spread=42, pierce=1,
                  power_scale=0.42),
    ("CAMINHEM COMIGO!", "PROCISSÃO DOS MORTOS!"), unique=True,
)

# ---------------------------------------------------------------------------
# RASGADO
# ---------------------------------------------------------------------------
_def(
    "estilhaco_corrupto", "Estilhaço Corrupto",
    "Dispara fragmento instável; dano cresce com Corrupção atual.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.VAZIO,
    54, 2.4, 10, "rasgado", ("corruption", "void", "projectile"),
    SkillBehavior("projectile", projectile_speed=680, pierce=1, range=820, power_scale=1.0),
    ("PARTA.",),
)
_def(
    "salto_da_fenda", "Salto da Fenda",
    "Desaparece por um instante e emerge violentamente no destino.",
    Rarity.RARA, SkillCategory.MOBILIDADE, DamageType.VAZIO,
    66, 6.5, 20, "rasgado", ("void", "dash", "area"),
    SkillBehavior("dash_strike", radius=105, dash_distance=190, power_scale=1.0, knockback=28),
    ("RASGUE O ESPAÇO!",),
)
_def(
    "carne_do_vazio", "Carne do Vazio",
    "Corrupção endurece o corpo; vida baixa aumenta resistência e dano.",
    Rarity.EPICA, SkillCategory.PASSIVA, DamageType.VAZIO,
    0, 0, 0, "rasgado", ("corruption", "survival", "passive"),
    SkillBehavior("passive", status="void_flesh"),
)
_def(
    "apoteose_rasgada", "Apoteose Rasgada",
    "Abre totalmente a fenda interior por poucos segundos.",
    Rarity.CORROMPIDA, SkillCategory.SUPREMA, DamageType.VAZIO,
    90, 26.0, 52, "rasgado", ("corruption", "ultimate", "risk"),
    SkillBehavior("self_buff", duration=7.0, status="torn_apotheosis",
                  note="Poder extremo; deverá consumir vida enquanto ativo."),
    ("ABRA-SE POR COMPLETO!",), unique=True, corrupted=True,
)

# ---------------------------------------------------------------------------
# CRONISTA
# ---------------------------------------------------------------------------
_def(
    "corte_de_segundo", "Corte de Segundo",
    "Um corte temporal causa dano agora e repete parte do impacto depois.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.TEMPORAL,
    44, 2.6, 16, "cronista", ("temporal", "delayed", "projectile"),
    SkillBehavior("projectile", projectile_speed=700, pierce=1, range=820, power_scale=1.0),
    ("AGORA... E DE NOVO.",),
)
_def(
    "atraso_forcado", "Atraso Forçado",
    "Zona temporal reduz drasticamente ataques e deslocamento inimigos.",
    Rarity.RARA, SkillCategory.ATIVA, DamageType.TEMPORAL,
    22, 8.0, 30, "cronista", ("temporal", "area", "slow"),
    SkillBehavior("area", radius=150, duration=3.2, status="temporal_slow", power_scale=0.15),
    ("ATRASADO.",),
)
_def(
    "eco_do_futuro", "Eco do Futuro",
    "Cria um eco que replica parte do próximo ataque usado.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.TEMPORAL,
    0, 11.0, 38, "cronista", ("temporal", "echo", "buff"),
    SkillBehavior("self_buff", duration=6.0, status="future_echo"),
    ("EU JÁ FIZ ISSO.",),
)
_def(
    "paradoxo", "Paradoxo",
    "Colapsa dois instantes incompatíveis no mesmo ponto.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.TEMPORAL,
    190, 25.0, 72, "cronista", ("temporal", "area", "ultimate"),
    SkillBehavior("delayed_aoe", radius=175, duration=0.85, power_scale=1.0),
    ("DOIS FINS. UM INSTANTE.",), unique=True,
)

# ---------------------------------------------------------------------------
# ARTÍFICE
# ---------------------------------------------------------------------------
_def(
    "drone_vigia", "Drone Vigia",
    "Lança drone que dispara uma sequência contra ameaças próximas.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.ARCANO,
    28, 6.0, 22, "artifice", ("deployable", "drone", "technology"),
    SkillBehavior("multi_projectile", projectile_speed=620, projectile_count=5, spread=30, power_scale=0.5),
    ("DRONE, ATIVO!",),
)
_def(
    "campo_de_reparo", "Campo de Reparo",
    "Cria zona que restaura lentamente o usuário e dispositivos.",
    Rarity.RARA, SkillCategory.DEFENSIVA, DamageType.ARCANO,
    0, 12.0, 36, "artifice", ("technology", "healing", "area"),
    SkillBehavior("area", radius=135, duration=5.0, status="repair_field"),
    ("REPARO DE EMERGÊNCIA!",),
)
_def(
    "canhao_ressonante", "Canhão Ressonante",
    "Disparo concentrado que explode ao atingir massa inimiga.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.RAIO,
    110, 8.5, 38, "artifice", ("technology", "projectile", "explosion"),
    SkillBehavior("projectile", projectile_speed=780, pierce=1, range=900, radius=95, power_scale=1.0),
    ("RESSONÂNCIA MÁXIMA!",),
)
_def(
    "protocolo_zero", "Protocolo Zero",
    "Todos os dispositivos descarregam energia ao mesmo tempo.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.RAIO,
    170, 24.0, 68, "artifice", ("technology", "area", "ultimate"),
    SkillBehavior("aoe_self", radius=260, power_scale=1.0, knockback=35),
    ("PROTOCOLO ZERO!",), unique=True,
)

# ---------------------------------------------------------------------------
# DUELISTA
# ---------------------------------------------------------------------------
_def(
    "estocada_relampago", "Estocada Relâmpago",
    "Estocada veloz que atravessa o alvo e reposiciona o Duelista.",
    Rarity.INCOMUM, SkillCategory.MOBILIDADE, DamageType.FISICO,
    52, 3.4, 12, "duelista", ("melee", "dash", "precision"),
    SkillBehavior("dash_strike", radius=68, dash_distance=145, power_scale=1.0, knockback=12),
    ("TARDE DEMAIS.",),
)
_def(
    "passo_sem_sombra", "Passo Sem Sombra",
    "Esquiva curta com invulnerabilidade estendida se feita perto de um ataque.",
    Rarity.RARA, SkillCategory.MOBILIDADE, DamageType.FISICO,
    0, 5.5, 20, "duelista", ("mobility", "evade", "precision"),
    SkillBehavior("dash_buff", dash_distance=120, duration=1.2, status="shadowless_step"),
    ("ERROU.",),
)
_def(
    "marca_do_duelo", "Marca do Duelo",
    "Escolhe um alvo; dano contra ele cresce enquanto nenhum outro inimigo é atingido.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.FISICO,
    18, 8.0, 25, "duelista", ("mark", "duel", "precision"),
    SkillBehavior("projectile", projectile_speed=900, pierce=0, range=700, status="duel_mark"),
    ("VOCÊ. COMIGO.",),
)
_def(
    "cem_cortes", "Cem Cortes",
    "Uma sequência tão rápida que os impactos parecem simultâneos.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.FISICO,
    185, 22.0, 62, "duelista", ("melee", "combo", "ultimate"),
    SkillBehavior("aoe_self", radius=180, power_scale=1.0),
    ("CONTE SE CONSEGUIR!",), unique=True,
)

# ---------------------------------------------------------------------------
# ORÁCULO
# ---------------------------------------------------------------------------
_def(
    "selo_fragil", "Selo Frágil",
    "Marca uma área; inimigos dentro recebem vulnerabilidade crescente.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.ARCANO,
    20, 5.0, 18, "oraculo", ("mark", "area", "curse"),
    SkillBehavior("area", radius=130, duration=4.0, status="fragile_seal", power_scale=0.12),
    ("SEU ERRO COMEÇA AQUI.",),
)
_def(
    "visao_iminente", "Visão Iminente",
    "Prevê perigo e concede breve janela ampliada de esquiva/parry.",
    Rarity.RARA, SkillCategory.DEFENSIVA, DamageType.ARCANO,
    0, 8.0, 28, "oraculo", ("prediction", "defense", "utility"),
    SkillBehavior("self_buff", duration=4.0, status="imminent_vision"),
    ("EU VI ISSO.",),
)
_def(
    "maldicao_espelho", "Maldição do Espelho",
    "Parte do dano causado pelo alvo marcado ecoa de volta nele.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.SOMBRA,
    32, 10.0, 35, "oraculo", ("curse", "mark", "reflect"),
    SkillBehavior("projectile", projectile_speed=620, range=700, status="mirror_curse"),
    ("OLHE PARA SI.",),
)
_def(
    "eclipse_oracular", "Eclipse Oracular",
    "Todas as marcas ativas entram em colapso e a arena escurece brevemente.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.VAZIO,
    175, 25.0, 70, "oraculo", ("curse", "area", "ultimate"),
    SkillBehavior("aoe_self", radius=340, power_scale=1.0, status="oracle_eclipse"),
    ("EU VI O FIM DE TODOS VOCÊS.",), unique=True,
)

# ---------------------------------------------------------------------------
# GUARDIÃO DO VÉU
# ---------------------------------------------------------------------------
_def(
    "impacto_baluarte", "Impacto Baluarte",
    "Avança com a barreira e derruba inimigos da linha frontal.",
    Rarity.INCOMUM, SkillCategory.ATIVA, DamageType.FISICO,
    48, 4.0, 14, "guardiao_veu", ("tank", "shield", "dash"),
    SkillBehavior("dash_strike", radius=82, dash_distance=120, power_scale=1.0, knockback=62),
    ("RECUEM!",),
)
_def(
    "corrente_protetora", "Corrente Protetora",
    "Ancora energia do Véu, fortalecendo a defesa por alguns segundos.",
    Rarity.RARA, SkillCategory.DEFENSIVA, DamageType.ARCANO,
    0, 8.0, 24, "guardiao_veu", ("barrier", "tank", "buff"),
    SkillBehavior("self_buff", duration=5.0, status="protective_chain"),
    ("EU SEGURO A LINHA!",),
)
_def(
    "provocacao_do_veu", "Provocação do Véu",
    "Emite pulso que puxa atenção e reduz dano de inimigos próximos.",
    Rarity.EPICA, SkillCategory.ATIVA, DamageType.ARCANO,
    18, 9.0, 30, "guardiao_veu", ("tank", "control", "area"),
    SkillBehavior("area", radius=220, duration=4.0, status="veil_taunt", power_scale=0.18),
    ("OLHEM PARA MIM!",),
)
_def(
    "quebra_cerco", "Quebra-Cerco",
    "Explosão frontal que rompe guarda e abre espaço.",
    Rarity.LENDARIA, SkillCategory.ATIVA, DamageType.FISICO,
    105, 10.5, 34, "guardiao_veu", ("tank", "stagger", "area"),
    SkillBehavior("cone", radius=175, power_scale=1.0, knockback=80),
    ("ABRAM A LINHA!",),
)
_def(
    "cidadela_final", "Cidadela Final",
    "Transforma o Guardião em uma fortaleza temporária.",
    Rarity.MITICA, SkillCategory.SUPREMA, DamageType.ARCANO,
    0, 26.0, 58, "guardiao_veu", ("tank", "barrier", "ultimate"),
    SkillBehavior("self_buff", duration=8.0, status="final_citadel"),
    ("AQUI É O FIM DA SUA PASSAGEM!",), unique=True,
)


CLASS_KITS.update({
    "guerreiro": ClassKit("guerreiro", "Guerreiro", "Ritmo + parry + décimo impacto", "Bruiser/Tank",
                           ("corte_crescente", "investida_de_ferro", "muralha_de_aco", "golpe_sismico", "ruptura_da_lamina", "juramento_de_guerra"),
                           "Transformar defesa perfeita em pressão ofensiva."),
    "mago": ClassKit("mago", "Mago", "Elementos + conjuração + controle", "Caster",
                     ("bola_de_fogo", "corrente_arcana", "prisao_glacial", "singularidade_arcana", "fim_da_linha_temporal", "meteoro_do_veu"),
                     "Dominar elementos e reduzir conjurações com maestria."),
    "arqueiro": ClassKit("arqueiro", "Arqueiro", "Precisão + mobilidade + perfuração", "Ranged DPS",
                         ("flecha_serrilhada", "passo_do_cacador", "tiro_ricochete", "chuva_de_flechas", "flecha_fantasma", "horizonte_partido"),
                         "Manter cadeia de acertos e controlar distância."),
    "ceifador": ClassKit("ceifador", "Ceifador", "Execução + roubo de vida + almas", "Sustain Assassin",
                         ("foice_espectral", "colheita_sombria", "manto_funerario", "banquete_de_almas", "sentenca_final", "procissao_dos_mortos"),
                         "Converter mortes em sobrevivência e execuções."),
    "rasgado": ClassKit("rasgado", "Rasgado", "Corrupção + risco + poder crescente", "Risk Hybrid",
                        ("estilhaco_corrupto", "fenda_interior", "salto_da_fenda", "carne_do_vazio", "coracao_da_ruptura", "apoteose_rasgada"),
                        "Jogar perto do limite sem perder o controle."),
    "cronista": ClassKit("cronista", "Cronista", "Tempo + rewind + ecos", "Control",
                         ("corte_de_segundo", "passo_rebobinado", "atraso_forcado", "instante_imovel", "eco_do_futuro", "paradoxo"),
                         "Planejar o combate alguns segundos à frente."),
    "artifice": ClassKit("artifice", "Artífice", "Dispositivos + zonas + tecnologia", "Engineer",
                         ("drone_vigia", "torreta_do_veu", "mina_de_fenda", "campo_de_reparo", "canhao_ressonante", "protocolo_zero"),
                         "Construir uma rede de vantagem no terreno."),
    "duelista": ClassKit("duelista", "Duelista", "Parry + mobilidade + sequência limpa", "Precision Melee",
                         ("estocada_relampago", "contra_golpe", "passo_sem_sombra", "marca_do_duelo", "danca_de_laminas", "cem_cortes"),
                         "Não ser atingido e transformar timing em dano."),
    "oraculo": ClassKit("oraculo", "Oráculo", "Marcas + previsão + maldições", "Debuff Control",
                        ("selo_fragil", "marca_do_pressagio", "visao_iminente", "maldicao_espelho", "destino_condenado", "eclipse_oracular"),
                        "Preparar consequências antes de detoná-las."),
    "guardiao_veu": ClassKit("guardiao_veu", "Guardião do Véu", "Barreiras + controle + proteção", "Tank",
                             ("impacto_baluarte", "barreira_do_veu", "corrente_protetora", "provocacao_do_veu", "quebra_cerco", "cidadela_final"),
                             "Controlar espaço e sobreviver onde outros recuariam."),
})


def behavior_for(skill_id: str) -> Optional[SkillBehavior]:
    return SKILL_BEHAVIORS.get(skill_id)


def class_kit_summary() -> Dict[str, int]:
    return {
        "kits": len(CLASS_KITS),
        "skills_total": len(SKILL_REGISTRY),
        "new_behaviors": len(SKILL_BEHAVIORS),
        "recommended_slots": sum(len(k.recommended_skills) for k in CLASS_KITS.values()),
    }

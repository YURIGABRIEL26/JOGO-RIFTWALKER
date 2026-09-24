"""RIFTWALKER — PRODUCTION / RELEASE AUDIT 0.9 RC

Valida referências cruzadas e separa bloqueadores de release de avisos
que dependem de assets/teste visual.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Dict, Iterable, List, Tuple

from core_systems import CLASS_REGISTRY, RIFT_REGISTRY, SKILL_REGISTRY
from content_systems import EQUIPMENT_REGISTRY
from narrative_systems import QUESTS, REGIONS
from boss_systems import BOSSES, PATTERNS
import endgame_systems  # registra boss final e boss de pós-jogo
from creature_systems import CREATURES
from class_kit_systems import CLASS_KITS, SKILL_BEHAVIORS
from audio_systems import expected_audio_assets


@dataclass(frozen=True)
class AuditIssue:
    severity: str  # blocker / warning / info
    code: str
    message: str


@dataclass
class ReleaseAudit:
    issues: List[AuditIssue] = field(default_factory=list)

    def add(self, severity: str, code: str, message: str) -> None:
        self.issues.append(AuditIssue(severity, code, message))

    @property
    def blockers(self) -> List[AuditIssue]:
        return [x for x in self.issues if x.severity == "blocker"]

    @property
    def warnings(self) -> List[AuditIssue]:
        return [x for x in self.issues if x.severity == "warning"]

    def releasable_codewise(self) -> bool:
        return not self.blockers


@dataclass(frozen=True)
class CreditEntry:
    asset_id: str
    category: str
    title: str
    author: str
    source: str
    license: str
    required_attribution: str = ""


class CreditRegistry:
    def __init__(self):
        self.entries: Dict[str, CreditEntry] = {}

    def add(self, entry: CreditEntry) -> None:
        if entry.asset_id in self.entries:
            raise ValueError(f"Asset duplicado nos créditos: {entry.asset_id}")
        self.entries[entry.asset_id] = entry

    def validate(self) -> List[AuditIssue]:
        issues: List[AuditIssue] = []
        for entry in self.entries.values():
            if not entry.license.strip():
                issues.append(AuditIssue("blocker", "asset_without_license", f"{entry.asset_id} sem licença registrada."))
            if not entry.source.strip():
                issues.append(AuditIssue("warning", "asset_without_source", f"{entry.asset_id} sem fonte registrada."))
        return issues

    def render_text(self) -> str:
        lines = ["RIFTWALKER — ASSET CREDITS", "=" * 28, ""]
        for entry in sorted(self.entries.values(), key=lambda x: (x.category, x.title)):
            lines.append(f"[{entry.category}] {entry.title}")
            lines.append(f"Autor: {entry.author}")
            lines.append(f"Fonte: {entry.source}")
            lines.append(f"Licença: {entry.license}")
            if entry.required_attribution:
                lines.append(f"Atribuição: {entry.required_attribution}")
            lines.append("")
        if not self.entries:
            lines.append("Nenhum asset externo registrado ainda.")
        return "\n".join(lines)


def run_content_audit(asset_root: str = ".", require_audio_assets: bool = False) -> ReleaseAudit:
    audit = ReleaseAudit()

    # Classes / kits
    if set(CLASS_KITS) != set(CLASS_REGISTRY):
        missing = sorted(set(CLASS_REGISTRY) - set(CLASS_KITS))
        extra = sorted(set(CLASS_KITS) - set(CLASS_REGISTRY))
        if missing: audit.add("blocker", "missing_class_kit", f"Classes sem kit: {missing}")
        if extra: audit.add("blocker", "orphan_class_kit", f"Kits sem classe: {extra}")

    for class_id, kit in CLASS_KITS.items():
        if len(kit.recommended_skills) < 6:
            audit.add("warning", "small_class_kit", f"{class_id} tem menos de 6 skills recomendadas.")
        for sid in kit.recommended_skills:
            if sid not in SKILL_REGISTRY:
                audit.add("blocker", "missing_skill", f"Kit {class_id} referencia skill inexistente: {sid}")
            elif SKILL_REGISTRY[sid].allowed_classes and class_id not in SKILL_REGISTRY[sid].allowed_classes:
                audit.add("blocker", "skill_class_mismatch", f"{sid} não permite {class_id}.")

    # Skills novas precisam de comportamento; antigas podem ter executor dedicado no main.
    for sid in SKILL_BEHAVIORS:
        if sid not in SKILL_REGISTRY:
            audit.add("blocker", "orphan_behavior", f"Comportamento sem skill: {sid}")

    # Bosses / padrões / regiões
    for boss in BOSSES.values():
        if boss.region_id not in REGIONS:
            audit.add("blocker", "boss_region_missing", f"Boss {boss.id} usa região inexistente {boss.region_id}.")
        for phase in boss.phases:
            if not phase.pattern_ids:
                audit.add("blocker", "boss_phase_empty", f"Boss {boss.id} tem fase vazia {phase.nome}.")
            for pid in phase.pattern_ids:
                if pid not in PATTERNS:
                    audit.add("blocker", "boss_pattern_missing", f"Boss {boss.id} referencia padrão inexistente {pid}.")

    # Quests
    for quest in QUESTS.values():
        if not quest.objectives:
            audit.add("blocker", "quest_no_objectives", f"Missão {quest.id} sem objetivos.")
        for obj in quest.objectives:
            if obj.type.value == "defeat_boss" and obj.target_id not in BOSSES:
                audit.add("blocker", "quest_boss_missing", f"Missão {quest.id} referencia boss inexistente {obj.target_id}.")
            if obj.type.value == "visit_region" and obj.target_id not in REGIONS:
                audit.add("blocker", "quest_region_missing", f"Missão {quest.id} referencia região inexistente {obj.target_id}.")
            if obj.type.value == "discover_rift" and obj.target_id not in RIFT_REGISTRY:
                audit.add("blocker", "quest_rift_missing", f"Missão {quest.id} referencia Ruptura inexistente {obj.target_id}.")

    # Conteúdo mínimo de mundo
    if len(REGIONS) < 6: audit.add("warning", "few_regions", "Menos de 6 regiões registradas.")
    if len(CREATURES) < 10: audit.add("warning", "few_creatures", "Menos de 10 criaturas registradas.")
    if len(EQUIPMENT_REGISTRY) < 20: audit.add("warning", "few_equipment", "Pool de equipamento ainda pequena.")
    if len(SKILL_REGISTRY) < 50: audit.add("warning", "few_skills", "Menos de 50 habilidades registradas.")

    # Áudio: antes de assets definitivos, ausência é warning; para release vira blocker.
    root = Path(asset_root)
    missing_audio = [p for p in expected_audio_assets() if not (root / p).exists()]
    if missing_audio:
        severity = "blocker" if require_audio_assets else "warning"
        audit.add(severity, "audio_assets_missing", f"{len(missing_audio)} arquivos de áudio esperados ainda ausentes.")

    # Voz provisória: manifest + arquivos precisam existir na RC.
    voice_manifest_path = root / "assets/audio/voice_manifest.json"
    if not voice_manifest_path.exists():
        severity = "blocker" if require_audio_assets else "warning"
        audit.add(severity, "voice_manifest_missing", "Manifest de vozes provisórias ausente.")
    else:
        try:
            voice_manifest = json.loads(voice_manifest_path.read_text(encoding="utf-8"))
            missing_voice = []
            for text, variants in voice_manifest.items():
                for gender in ("male", "female"):
                    rel = variants.get(gender)
                    if not rel or not (root / rel).exists():
                        missing_voice.append((text, gender, rel))
            if missing_voice:
                severity = "blocker" if require_audio_assets else "warning"
                audit.add(severity, "voice_assets_missing", f"{len(missing_voice)} arquivos de voz registrados estão ausentes.")
            elif len(voice_manifest) < 20:
                audit.add("warning", "voice_pool_small", f"Apenas {len(voice_manifest)} falas registradas.")
        except Exception as exc:
            severity = "blocker" if require_audio_assets else "warning"
            audit.add(severity, "voice_manifest_invalid", f"Manifest de voz inválido: {exc}")

    enemy_manifest_path = root / "assets/audio/enemy_voice_manifest.json"
    if not enemy_manifest_path.exists():
        severity = "blocker" if require_audio_assets else "warning"
        audit.add(severity, "enemy_voice_manifest_missing", "Manifest de vozes de boss/inimigo ausente.")
    else:
        try:
            enemy_manifest = json.loads(enemy_manifest_path.read_text(encoding="utf-8"))
            missing_enemy_voice = [
                (text, rel) for text, rel in enemy_manifest.items()
                if not rel or not (root / rel).exists()
            ]
            if missing_enemy_voice:
                severity = "blocker" if require_audio_assets else "warning"
                audit.add(severity, "enemy_voice_assets_missing", f"{len(missing_enemy_voice)} vozes inimigas registradas estão ausentes.")
        except Exception as exc:
            severity = "blocker" if require_audio_assets else "warning"
            audit.add(severity, "enemy_voice_manifest_invalid", f"Manifest de voz inimiga inválido: {exc}")

    return audit


def content_metrics() -> Dict[str, int]:
    return {
        "classes": len(CLASS_REGISTRY),
        "skills": len(SKILL_REGISTRY),
        "equipment": len(EQUIPMENT_REGISTRY),
        "regions": len(REGIONS),
        "quests": len(QUESTS),
        "bosses": len(BOSSES),
        "boss_patterns": len(PATTERNS),
        "creatures": len(CREATURES),
    }


def production_summary() -> Dict[str, int]:
    return {"audit_categories": 7, "credit_fields": 7, **content_metrics()}

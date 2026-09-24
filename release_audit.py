"""Auditoria rápida de referências e conteúdo antes de empacotar RIFTWALKER."""
from __future__ import annotations

import class_kit_systems  # registra conteúdo 0.9 RC
import endgame_systems     # registra bosses finais

from production_systems import content_metrics, run_content_audit


def main() -> int:
    audit = run_content_audit(asset_root=".", require_audio_assets=True)
    print("RIFTWALKER — RELEASE AUDIT 0.9 RC")
    print("CONTENT:", content_metrics())
    print()
    if not audit.issues:
        print("Nenhum problema encontrado.")
    else:
        for issue in audit.issues:
            print(f"[{issue.severity.upper()}] {issue.code}: {issue.message}")
    print()
    print(f"BLOCKERS: {len(audit.blockers)}")
    print(f"WARNINGS: {len(audit.warnings)}")
    return 1 if audit.blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())

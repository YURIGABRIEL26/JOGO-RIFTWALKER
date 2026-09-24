"""RIFTWALKER — MULTI SLOT SAVE / PROFILE METADATA 0.9 RC"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from core_systems import PlayerState, SaveManager, player_state_from_dict


@dataclass
class SaveSlotMeta:
    slot: int
    exists: bool
    character_name: str = ""
    class_id: str = ""
    level: int = 0
    chapter: int = 0
    playtime_seconds: int = 0
    last_saved_unix: float = 0.0
    ending: Optional[str] = None
    ng_plus_cycle: int = 0
    checksum: str = ""


class ProfileManager:
    def __init__(self, root: str = "saves", slots: int = 3):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.slots = max(1, min(9, int(slots)))

    def _validate_slot(self, slot: int) -> int:
        slot = int(slot)
        if slot < 1 or slot > self.slots:
            raise ValueError(f"Slot deve estar entre 1 e {self.slots}.")
        return slot

    def save_path(self, slot: int) -> Path:
        slot = self._validate_slot(slot)
        return self.root / f"slot_{slot}.json"

    def meta_path(self, slot: int) -> Path:
        slot = self._validate_slot(slot)
        return self.root / f"slot_{slot}.meta.json"

    def trash_path(self, slot: int) -> Path:
        slot = self._validate_slot(slot)
        return self.root / f"slot_{slot}.deleted.json"

    @staticmethod
    def _checksum(path: Path) -> str:
        if not path.exists():
            return ""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _write_meta(self, meta: SaveSlotMeta) -> None:
        path = self.meta_path(meta.slot)
        fd, tmp = tempfile.mkstemp(prefix=f"slot_{meta.slot}_meta_", suffix=".tmp", dir=str(self.root))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(meta), f, indent=4, ensure_ascii=False)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def save(self, slot: int, state: PlayerState, playtime_seconds: int = 0) -> SaveSlotMeta:
        slot = self._validate_slot(slot)
        path = self.save_path(slot)
        SaveManager(str(path)).save(state)
        endgame = state.campaign.get("endgame", {}) if isinstance(state.campaign, dict) else {}
        meta = SaveSlotMeta(
            slot=slot,
            exists=True,
            character_name=state.identity.nome,
            class_id=state.identity.class_id,
            level=int(state.stats.nivel),
            chapter=int(state.campaign.get("chapter", 1)),
            playtime_seconds=max(0, int(playtime_seconds)),
            last_saved_unix=time.time(),
            ending=endgame.get("ending"),
            ng_plus_cycle=int(endgame.get("ng_plus_cycle", 0)),
            checksum=self._checksum(path),
        )
        self._write_meta(meta)
        return meta

    def load(self, slot: int) -> PlayerState:
        slot = self._validate_slot(slot)
        return SaveManager(str(self.save_path(slot))).load()

    def slot_meta(self, slot: int) -> SaveSlotMeta:
        slot = self._validate_slot(slot)
        save_path = self.save_path(slot)
        meta_path = self.meta_path(slot)
        if not save_path.exists():
            return SaveSlotMeta(slot=slot, exists=False)
        if meta_path.exists():
            try:
                raw = json.loads(meta_path.read_text(encoding="utf-8"))
                raw["slot"] = slot
                raw["exists"] = True
                meta = SaveSlotMeta(**{k: v for k, v in raw.items() if k in SaveSlotMeta.__dataclass_fields__})
                actual = self._checksum(save_path)
                if meta.checksum == actual:
                    return meta
                # Autosave do runtime pode atualizar o JSON sem regravar o sidecar.
                # Nesse caso, reconstrói metadata a partir do save real.
            except Exception:
                pass
        state = self.load(slot)
        endgame = state.campaign.get("endgame", {}) if isinstance(state.campaign, dict) else {}
        return SaveSlotMeta(
            slot=slot,
            exists=True,
            character_name=state.identity.nome,
            class_id=state.identity.class_id,
            level=int(state.stats.nivel),
            chapter=int(state.campaign.get("chapter", 1)),
            last_saved_unix=save_path.stat().st_mtime,
            ending=endgame.get("ending"),
            ng_plus_cycle=int(endgame.get("ng_plus_cycle", 0)),
            checksum=self._checksum(save_path),
        )

    def all_slots(self) -> List[SaveSlotMeta]:
        return [self.slot_meta(i) for i in range(1, self.slots + 1)]

    def delete(self, slot: int, keep_recovery: bool = True) -> None:
        slot = self._validate_slot(slot)
        save = self.save_path(slot)
        if save.exists() and keep_recovery:
            shutil.copy2(save, self.trash_path(slot))
        for path in (
            save,
            Path(str(save) + ".backup"),
            self.meta_path(slot),
        ):
            path.unlink(missing_ok=True)

    def restore_deleted(self, slot: int) -> bool:
        slot = self._validate_slot(slot)
        trash = self.trash_path(slot)
        if not trash.exists():
            return False
        shutil.copy2(trash, self.save_path(slot))
        state = self.load(slot)
        self.save(slot, state)
        return True

    def verify(self, slot: int) -> Dict[str, object]:
        slot = self._validate_slot(slot)
        path = self.save_path(slot)
        if not path.exists():
            return {"exists": False, "checksum_ok": False, "load_ok": False, "recovery_available": Path(str(path) + ".backup").exists()}

        actual = self._checksum(path)
        expected = ""
        meta_path = self.meta_path(slot)
        if meta_path.exists():
            try:
                raw_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                expected = str(raw_meta.get("checksum", ""))
            except Exception:
                expected = ""

        # Valida o arquivo principal diretamente. SaveManager.load() possui fallback
        # e, portanto, não serve como teste de integridade do principal.
        load_ok = False
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            player_state_from_dict(raw)
            load_ok = True
        except Exception:
            load_ok = False

        recovery_available = False
        backup_path = Path(str(path) + ".backup")
        if backup_path.exists():
            try:
                raw_backup = json.loads(backup_path.read_text(encoding="utf-8"))
                player_state_from_dict(raw_backup)
                recovery_available = True
            except Exception:
                recovery_available = False

        return {
            "exists": True,
            "checksum_ok": bool(expected) and expected == actual,
            "load_ok": load_ok,
            "recovery_available": recovery_available,
        }


def profile_summary() -> Dict[str, int]:
    return {"default_slots": 3, "max_slots": 9, "recovery_copies": 1}

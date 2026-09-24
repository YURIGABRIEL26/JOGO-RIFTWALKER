"""Validação offline de assets da RIFTWALKER RC 0.9."""
from __future__ import annotations
import json
from pathlib import Path

import audio_systems

ROOT = Path(__file__).resolve().parent


def check_ogg(path: Path) -> str | None:
    if not path.exists():
        return "ausente"
    if path.stat().st_size < 512:
        return "arquivo pequeno demais"
    try:
        head = path.read_bytes()[:4]
    except Exception as exc:
        return f"erro de leitura: {exc}"
    if head != b"OggS":
        return "cabeçalho OGG inválido"
    return None


def main() -> int:
    failures=[]
    base=list(audio_systems.expected_audio_assets())
    for rel in base:
        err=check_ogg(ROOT/rel)
        if err: failures.append((rel,err))

    player_manifest_path=ROOT/'assets/audio/voice_manifest.json'
    enemy_manifest_path=ROOT/'assets/audio/enemy_voice_manifest.json'
    player_manifest=json.loads(player_manifest_path.read_text(encoding='utf-8'))
    enemy_manifest=json.loads(enemy_manifest_path.read_text(encoding='utf-8'))

    player_files=[]
    for text, variants in player_manifest.items():
        for gender in ('male','female'):
            rel=variants[gender]; player_files.append(rel)
            err=check_ogg(ROOT/rel)
            if err: failures.append((rel,err))
    enemy_files=[]
    for text, rel in enemy_manifest.items():
        enemy_files.append(rel)
        err=check_ogg(ROOT/rel)
        if err: failures.append((rel,err))

    branding=[ROOT/'assets/branding/riftwalker_icon.png', ROOT/'assets/branding/riftwalker.ico']
    for path in branding:
        if not path.exists() or path.stat().st_size < 1000:
            failures.append((str(path.relative_to(ROOT)),'branding ausente/inválido'))

    print('RIFTWALKER ASSET INTEGRITY 0.9 RC')
    print(f'Base audio: {len(base)}')
    print(f'Player voice lines: {len(player_manifest)} / files: {len(player_files)}')
    print(f'Enemy/boss voice lines: {len(enemy_manifest)} / files: {len(enemy_files)}')
    print(f'Total OGG validated: {len(base)+len(player_files)+len(enemy_files)}')
    if failures:
        for rel,err in failures[:40]: print('[FAIL]',rel,'-',err)
        print('FAILURES:',len(failures))
        return 1
    print('ASSETS: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

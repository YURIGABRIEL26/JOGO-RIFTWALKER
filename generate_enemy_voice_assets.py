from __future__ import annotations
import hashlib, json, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'assets'/'audio'/'enemy_voice'
OUT.mkdir(parents=True, exist_ok=True)

import endgame_systems  # registra bosses finais
from boss_systems import BOSSES, PATTERNS

lines=set()
for boss in BOSSES.values():
    lines.update(x.strip() for x in boss.intro_lines if x.strip())
    lines.update(x.strip() for x in boss.memory_lines if x.strip())
for pattern in PATTERNS.values():
    if pattern.voice_line:
        lines.add(pattern.voice_line.strip())
lines.update({
    'Você voltou.', 'Eu me lembro.', 'O mesmo ritmo... não funcionará de novo.',
    'Eu conheço seus passos.', 'Sua estratégia deixou marcas no Véu.',
    'Eu aprendi cada fuga sua.', 'O Véu me mostrou como você morre.',
    'Mude... ou repita seu fim.'
})
manifest={}
for idx,text in enumerate(sorted(lines),1):
    key=hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
    out=OUT/f'{key}.ogg'
    with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
        subprocess.run(['espeak','-v','pt-br+m1','-s','142','-p','28','-a','165','-w',tmp.name,text],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['ffmpeg','-y','-loglevel','error','-i',tmp.name,
                        '-af','highpass=f=70,lowpass=f=5200,aecho=0.8:0.45:55:0.18,volume=0.92',
                        '-c:a','libvorbis','-q:a','4',str(out)],check=True)
    manifest[text]=str(out.relative_to(ROOT)).replace('\\','/')
(ROOT/'assets'/'audio'/'enemy_voice_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('enemy voice lines:',len(lines))

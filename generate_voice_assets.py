from __future__ import annotations
import ast, hashlib, json, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'assets'/'audio'/'voice'
OUT.mkdir(parents=True, exist_ok=True)

# Import registries after all class content is registered.
import class_kit_systems  # noqa
from core_systems import SKILL_REGISTRY

lines=set()
for skill in SKILL_REGISTRY.values():
    lines.update(x.strip() for x in skill.voice_lines_male if x.strip())
    lines.update(x.strip() for x in skill.voice_lines_female if x.strip())
    lines.update(x.strip() for x in skill.incantations_male if x.strip())
    lines.update(x.strip() for x in skill.incantations_female if x.strip())

# Also collect literal runtime reactions in main.py.
tree=ast.parse((ROOT/'main.py').read_text(encoding='utf-8'))
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr=='speak_player' and node.args:
        arg=node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value,str) and arg.value.strip():
            lines.add(arg.value.strip())

manifest={}
for idx,text in enumerate(sorted(lines),1):
    key=hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
    record={}
    for gender,voice,speed,pitch,hp in (
        ('male','pt-br+m3',164,46,95),
        ('female','pt-br+f3',168,61,125),
    ):
        out=OUT/f'{key}_{gender}.ogg'
        with tempfile.NamedTemporaryFile(suffix='.wav') as tmp:
            subprocess.run([
                'espeak','-v',voice,'-s',str(speed),'-p',str(pitch),'-a','155','-w',tmp.name,text
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([
                'ffmpeg','-y','-loglevel','error','-i',tmp.name,
                '-af',f'highpass=f={hp},lowpass=f=6500,aecho=0.8:0.32:36:0.10,volume=0.90',
                '-c:a','libvorbis','-q:a','4',str(out)
            ], check=True)
        record[gender]=str(out.relative_to(ROOT)).replace('\\','/')
    manifest[text]=record
    if idx%25==0: print(f'voices {idx}/{len(lines)}')

(ROOT/'assets'/'audio'/'voice_manifest.json').write_text(
    json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8'
)
print('voice lines:',len(lines),'files:',len(lines)*2)

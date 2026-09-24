from __future__ import annotations

import math
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
ROOT = Path(__file__).resolve().parent
AUDIO = ROOT / 'assets' / 'audio'
RNG = np.random.default_rng(424242)


def tvec(duration: float):
    return np.arange(int(SR * duration), dtype=np.float64) / SR


def env(duration: float, attack=0.01, release=0.08):
    n = max(1, int(SR * duration))
    e = np.ones(n, dtype=np.float64)
    a = min(n, max(1, int(SR * attack)))
    r = min(n, max(1, int(SR * release)))
    e[:a] *= np.linspace(0, 1, a, endpoint=False)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def sine(freq, duration, phase=0.0):
    t = tvec(duration)
    return np.sin(2*np.pi*freq*t + phase)


def osc(freq, duration, kind='sine'):
    t = tvec(duration)
    ph = (freq * t) % 1.0
    if kind == 'saw':
        return 2.0*ph - 1.0
    if kind == 'tri':
        return 2.0*np.abs(2.0*ph - 1.0) - 1.0
    if kind == 'square':
        return np.where(ph < 0.5, 1.0, -1.0)
    return np.sin(2*np.pi*freq*t)


def sweep(f0, f1, duration, kind='sine'):
    n = max(1, int(SR*duration))
    freqs = np.geomspace(max(1, f0), max(1, f1), n)
    phase = 2*np.pi*np.cumsum(freqs)/SR
    if kind == 'saw':
        cyc = (phase/(2*np.pi)) % 1
        return 2*cyc - 1
    return np.sin(phase)


def noise(duration, color='white'):
    x = RNG.normal(0, 1, int(SR*duration))
    if color == 'brown':
        x = np.cumsum(x)
        x -= np.mean(x)
        x /= np.max(np.abs(x)) + 1e-9
    elif color == 'pinkish':
        x = lowpass(x, 5000)
    return x


def lowpass(x, hz):
    sos = butter(4, min(0.99, hz/(SR/2)), btype='low', output='sos')
    return sosfilt(sos, x)


def highpass(x, hz):
    sos = butter(4, min(0.99, hz/(SR/2)), btype='high', output='sos')
    return sosfilt(sos, x)


def bandpass(x, low, high):
    lo = max(1e-4, low/(SR/2)); hi = min(0.999, high/(SR/2))
    sos = butter(3, [lo, hi], btype='band', output='sos')
    return sosfilt(sos, x)


def pad_to(x, n):
    if len(x) >= n: return x[:n]
    return np.pad(x, (0, n-len(x)))


def mix(parts, duration=None):
    if not parts:
        return np.zeros(1)
    n = max(len(p) for p, _ in parts) if duration is None else int(SR*duration)
    y = np.zeros(n, dtype=np.float64)
    for p, gain in parts:
        y[:min(n, len(p))] += p[:n] * gain
    return y


def delay(x, seconds, gain=0.35):
    d = int(seconds*SR)
    y = np.zeros(len(x)+d)
    y[:len(x)] += x
    y[d:d+len(x)] += x*gain
    return y


def normalize(x, peak=0.90):
    if x.ndim == 1:
        mx = np.max(np.abs(x)) + 1e-12
    else:
        mx = np.max(np.abs(x)) + 1e-12
    return x / mx * peak


def stereo(x, pan=0.0):
    if x.ndim == 2:
        return x
    pan = max(-1.0, min(1.0, pan))
    left = math.cos((pan+1)*math.pi/4)
    right = math.sin((pan+1)*math.pi/4)
    return np.column_stack([x*left, x*right])


def stereo_widen(x, amount=0.18):
    x = np.asarray(x)
    d = max(1, int(SR*0.012))
    right = np.pad(x, (d, 0))[:len(x)]
    return np.column_stack([x, x*(1-amount)+right*amount])


def save_ogg(relpath: str, audio, quality=5):
    path = ROOT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = normalize(np.asarray(audio, dtype=np.float64))
    pcm = np.int16(np.clip(audio, -1, 1)*32767)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        wavname = tmp.name
    try:
        wavfile.write(wavname, SR, pcm)
        subprocess.run([
            'ffmpeg','-y','-loglevel','error','-i',wavname,
            '-c:a','libvorbis','-q:a',str(quality),str(path)
        ], check=True)
    finally:
        try: os.unlink(wavname)
        except FileNotFoundError: pass


# ------------------------------------------------------------
# SFX
# ------------------------------------------------------------

def ui_confirm(variant=0):
    d=.16
    f=720+variant*90
    x = sine(f,d)*env(d,.004,.12) + sine(f*1.5,d)*env(d,.004,.10)*.35
    return stereo(delay(x,.055,.22)[:int(SR*.24)], pan=.08 if variant else -.08)


def ui_back():
    d=.18
    return stereo(sweep(620,330,d)*env(d,.004,.12)*.8, -.15)


def ui_hover():
    d=.07
    x=sine(1100,d)*env(d,.002,.05)+sine(1650,d)*env(d,.002,.05)*.25
    return stereo(x,.12)


def drop_sound(legendary=False):
    dur=1.15 if legendary else .75
    y=np.zeros(int(SR*dur))
    notes=[523.25,659.25,783.99,1046.5] if legendary else [440,554.37,659.25]
    step=.12
    for i,f in enumerate(notes):
        s=sine(f,.45)*env(.45,.008,.38)
        start=int(i*step*SR); y[start:start+len(s)] += s[:max(0,len(y)-start)]*(.48+.08*i)
    shimmer=highpass(noise(dur),7000)*np.exp(-tvec(dur)*2.8)*(.10 if legendary else .06)
    y+=shimmer
    return stereo_widen(y,.35)


def sword_swing(v):
    dur=.28 + .015*v
    who=bandpass(noise(dur),500,7000)
    who*=env(dur,.015,.12)
    pitch=sweep(1300+70*v,350+20*v,dur)*env(dur,.01,.14)*.18
    return stereo(who*.38+pitch, pan=(-.25+.16*v))


def sword_hit(v):
    dur=.34
    n=lowpass(noise(dur),2600)*np.exp(-tvec(dur)*16)
    metal=(sine(780+55*v,dur)+.45*sine(1380+80*v,dur))*np.exp(-tvec(dur)*8)
    thump=sine(75+8*v,dur)*np.exp(-tvec(dur)*15)
    x=n*.45+metal*.35+thump*.75
    return stereo_widen(x,.18)


def arrow(v):
    dur=.25
    snap=sweep(2100+150*v,650,dur)*env(dur,.002,.16)*.22
    who=bandpass(noise(dur),1200,9000)*env(dur,.004,.13)*.20
    twang=sine(180+15*v,dur)*np.exp(-tvec(dur)*13)*.25
    return stereo(snap+who+twang, .18-0.18*v)


def dash(v):
    dur=.34
    who=bandpass(noise(dur),250,5000)*env(dur,.015,.18)*.33
    sw=sweep(280+v*25,1400+v*60,dur)*env(dur,.01,.19)*.15
    return stereo_widen(who+sw,.45)


def enemy_death(v):
    dur=.68
    grow=sweep(180-v*12,48,dur,'saw')*env(dur,.008,.34)*.28
    breath=bandpass(noise(dur),90,900)*env(dur,.02,.40)*.35
    pop=lowpass(noise(.12),400)*env(.12,.001,.11)
    x=mix([(grow,1),(breath,1),(pop,.5)],dur)
    return stereo_widen(x,.14)


def fire_impact(v):
    dur=.55
    boom=sine(62+5*v,dur)*np.exp(-tvec(dur)*9)*.8
    roar=bandpass(noise(dur),120,2600)*env(dur,.003,.35)*.45
    crack=highpass(noise(dur),4500)*(RNG.random(len(tvec(dur)))>.94)*.18
    return stereo_widen(boom+roar+crack,.25)


def ice_break(v):
    dur=.52
    n=highpass(noise(dur),3200)*np.exp(-tvec(dur)*5.5)*.28
    glass=np.zeros(int(SR*dur))
    for i,f in enumerate([1800+v*130,2400,3100,4200]):
        start=int(i*.035*SR)
        s=sine(f,dur-start/SR)*np.exp(-tvec(dur-start/SR)*8)*.18
        glass[start:start+len(s)] += s[:len(glass)-start]
    return stereo_widen(n+glass,.35)


def magic_cast(v):
    dur=.58
    rise=sweep(180+20*v,1400+150*v,dur)*env(dur,.02,.18)*.25
    ch=sine(440*(1+v*.03),dur)*env(dur,.02,.25)*.16
    spark=highpass(noise(dur),6000)*env(dur,.03,.25)*.07
    return stereo_widen(delay(rise+ch+spark,.08,.22)[:int(SR*.72)],.3)


def parry(v):
    dur=.62
    impulse=bandpass(noise(.06),900,9000)*env(.06,.001,.05)*.5
    ring=(sine(1700+170*v,dur)+.45*sine(2700+210*v,dur))*np.exp(-tvec(dur)*5.8)
    low=sine(95,dur)*np.exp(-tvec(dur)*14)*.55
    return stereo_widen(mix([(impulse,1),(ring,.38),(low,.6)],dur),.28)


def player_hurt(v):
    dur=.32
    grunt=sweep(150+10*v,95,dur,'saw')*env(dur,.005,.18)*.22
    breath=bandpass(noise(dur),130,1200)*env(dur,.01,.16)*.32
    return stereo(grunt+breath, -.08+.16*v)


def rift_open():
    dur=2.2
    low=sweep(55,38,dur)*env(dur,.08,.7)*.55
    swirl=sweep(180,1700,dur)*env(dur,.12,.45)*.22
    air=bandpass(noise(dur),180,6000)*env(dur,.2,.6)*.16
    pulse=sine(72,dur)*(0.5+0.5*np.sin(2*np.pi*3.1*tvec(dur)))*env(dur,.1,.7)*.25
    return stereo_widen(delay(low+swirl+air+pulse,.17,.18)[:int(SR*2.6)],.55)


def rift_accept():
    dur=1.15
    hit=sine(58,dur)*np.exp(-tvec(dur)*7)*.75
    rise=sweep(240,2100,dur)*env(dur,.01,.35)*.22
    ch=sum(sine(f,dur) for f in [220,330,440])*env(dur,.01,.55)*.08
    return stereo_widen(hit+rise+ch,.42)


def superior_spawn():
    dur=1.5
    low=sweep(90,45,dur,'saw')*env(dur,.01,.55)*.28
    horn=(sine(130,dur)+.5*sine(195,dur)+.25*sine(260,dur))*env(dur,.04,.55)*.40
    air=bandpass(noise(dur),500,5000)*env(dur,.08,.6)*.12
    return stereo_widen(low+horn+air,.32)


def boss_phase():
    dur=1.85
    impact=sine(46,dur)*np.exp(-tvec(dur)*5.5)*.9
    braam=(sine(82,dur)+.4*sine(123,dur)+.2*sine(164,dur))*env(dur,.025,.7)*.42
    riser=sweep(280,2200,1.2)*env(1.2,.05,.18)*.16
    return stereo_widen(mix([(impact,1),(braam,1),(riser,1)],dur),.40)


# ------------------------------------------------------------
# MUSIC / AMBIENCE
# ------------------------------------------------------------

NOTE = {'C':0,'Cs':1,'D':2,'Ds':3,'E':4,'F':5,'Fs':6,'G':7,'Gs':8,'A':9,'As':10,'B':11}

def hz(note: str, octave: int):
    midi=(octave+1)*12+NOTE[note]
    return 440.0*2**((midi-69)/12)


def synth_note(freq, duration, brightness=.25, soft=False):
    x=osc(freq,duration,'tri')*.65 + osc(freq*2,duration,'sine')*brightness + osc(freq*.5,duration,'sine')*.12
    if not soft: x += osc(freq*3,duration,'sine')*.06
    return x*env(duration,.02 if soft else .006,.15 if not soft else .45)


def add_note(track, start, duration, freq, gain=.2, pan=0.0, brightness=.25, soft=False):
    s=synth_note(freq,duration,brightness,soft)*gain
    i=int(start*SR); j=min(len(track),i+len(s))
    if j<=i: return
    st=stereo(s,pan)
    track[i:j]+=st[:j-i]


def add_kick(track, start, gain=.32):
    if start < 0 or start >= len(track)/SR: return
    dur=.22; s=sweep(110,44,dur)*np.exp(-tvec(dur)*16)*gain
    i=int(start*SR); j=min(len(track),i+len(s))
    if j<=i: return
    track[i:j]+=stereo(s)[:j-i]


def add_hat(track,start,gain=.07):
    if start < 0 or start >= len(track)/SR: return
    dur=.08; s=highpass(noise(dur),6000)*env(dur,.001,.06)*gain
    i=int(start*SR); j=min(len(track),i+len(s))
    if j<=i: return
    track[i:j]+=stereo(s, .25 if int(start*4)%2 else -.25)[:j-i]


def add_snare(track,start,gain=.12):
    if start < 0 or start >= len(track)/SR: return
    dur=.16; s=bandpass(noise(dur),500,8000)*env(dur,.001,.12)*gain + sine(170,dur)*np.exp(-tvec(dur)*20)*gain*.3
    i=int(start*SR); j=min(len(track),i+len(s))
    if j<=i: return
    track[i:j]+=stereo(s)[:j-i]


def make_music(name, tempo, root_notes, intensity=1, duration=24.0, major=False):
    n=int(SR*duration); tr=np.zeros((n,2),dtype=np.float64)
    beat=60/tempo
    # Drone / chord bed
    for bar in range(int(duration/(beat*4))+1):
        root=root_notes[bar%len(root_notes)]
        start=bar*beat*4
        r=hz(root,2)
        third=r*(2**((4 if major else 3)/12))
        fifth=r*(2**(7/12))
        for f,pan,g in [(r,-.2,.10),(third,.18,.06),(fifth,.28,.07)]:
            add_note(tr,start,min(beat*4.2,duration-start),f,g,pan,.10,True)
    # Bass
    for b in np.arange(0,duration,beat):
        bar=int(b//(beat*4)); root=root_notes[bar%len(root_notes)]
        add_note(tr,b,min(beat*.8,duration-b),hz(root,2),.13+intensity*.015,-.08,.15,False)
    # Arp
    intervals=[0,7,12,7,3 if not major else 4,7,12,15 if not major else 16]
    step=beat/2 if intensity<=1 else beat/4
    for k,b in enumerate(np.arange(0,duration,step)):
        bar=int(b//(beat*4)); root=root_notes[bar%len(root_notes)]
        base=hz(root,3)
        f=base*2**(intervals[k%len(intervals)]/12)
        add_note(tr,b,min(step*.85,duration-b),f,.055+intensity*.012,(-.35 if k%2==0 else .35),.28,False)
    # Percussion
    if intensity>=2:
        for b in np.arange(0,duration,beat):
            add_kick(tr,b,.22+intensity*.025)
            add_hat(tr,b+beat/2,.045+intensity*.01)
        for b in np.arange(beat,duration,beat*2): add_snare(tr,b,.09+intensity*.012)
    if intensity>=4:
        for b in np.arange(0,duration,beat/2): add_hat(tr,b,.045)
    # Rift noise layer
    amb=lowpass(noise(duration),2500)*.018*(1+intensity*.18)
    tr += stereo_widen(amb,.45)
    # slow fade, keep loop-friendly modest edge
    fade=int(SR*.25)
    tr[:fade]*=np.linspace(.5,1,fade)[:,None]
    tr[-fade:]*=np.linspace(1,.5,fade)[:,None]
    return tr


def make_ambience(kind, duration=18.0):
    n=int(SR*duration)
    base=noise(duration,'pinkish')
    if kind=='hub':
        wind=bandpass(base,90,1300)*.12; hum=sine(55,duration)*.04
        bells=np.zeros(n)
        for s in [2.4,7.8,13.2]:
            tone=sine(660,.8)*env(.8,.01,.65)*.06; i=int(s*SR); bells[i:i+len(tone)] += tone[:n-i]
        x=wind+hum+bells
    elif kind=='fields':
        x=bandpass(base,180,4200)*.10 + sine(42,duration)*.025
        # rustle pulses
        x *= .8+.2*np.sin(2*np.pi*.11*tvec(duration))
    elif kind=='forest':
        x=bandpass(base,220,5200)*.12 + sine(48,duration)*.025
        for s in [1.7,5.1,9.9,14.6]:
            chirp=sweep(2200,3400,.16)*env(.16,.01,.12)*.035; i=int(s*SR); x[i:i+len(chirp)] += chirp[:n-i]
    elif kind=='bastion':
        x=bandpass(base,55,1000)*.16 + sine(38,duration)*.05
        for s in [3.0,10.8]:
            clang=sine(330,.9)*np.exp(-tvec(.9)*4)*.045; i=int(s*SR); x[i:i+len(clang)] += clang[:n-i]
    elif kind=='observatory':
        x=bandpass(base,500,7000)*.07 + sine(110,duration)*.025 + sine(165,duration)*.018
        x += sweep(420,860,duration)*.018
    else: # abyss
        x=bandpass(base,30,600)*.18 + sine(31,duration)*.06 + sweep(80,42,duration)*.03
        x *= .75+.25*np.sin(2*np.pi*.07*tvec(duration))
    return stereo_widen(x,.5)


def generate_all():
    # UI
    save_ogg('assets/audio/ui/confirm_01.ogg', ui_confirm(0))
    save_ogg('assets/audio/ui/confirm_02.ogg', ui_confirm(1))
    save_ogg('assets/audio/ui/back.ogg', ui_back())
    save_ogg('assets/audio/ui/hover.ogg', ui_hover())
    save_ogg('assets/audio/ui/rare_drop.ogg', drop_sound(False))
    save_ogg('assets/audio/ui/legendary_drop.ogg', drop_sound(True))

    for i in range(1,5):
        save_ogg(f'assets/audio/combat/sword_swing_{i:02d}.ogg', sword_swing(i-1))
        save_ogg(f'assets/audio/combat/sword_hit_{i:02d}.ogg', sword_hit(i-1))
    for i in range(1,4):
        save_ogg(f'assets/audio/combat/arrow_{i:02d}.ogg', arrow(i-1))
        save_ogg(f'assets/audio/combat/magic_cast_{i:02d}.ogg', magic_cast(i-1))
        save_ogg(f'assets/audio/combat/fire_impact_{i:02d}.ogg', fire_impact(i-1))
        save_ogg(f'assets/audio/combat/enemy_death_{i:02d}.ogg', enemy_death(i-1))
    for i in range(1,3):
        save_ogg(f'assets/audio/combat/dash_{i:02d}.ogg', dash(i-1))
        save_ogg(f'assets/audio/combat/ice_break_{i:02d}.ogg', ice_break(i-1))
        save_ogg(f'assets/audio/combat/parry_{i:02d}.ogg', parry(i-1))
        save_ogg(f'assets/audio/combat/player_hurt_{i:02d}.ogg', player_hurt(i-1))

    save_ogg('assets/audio/rift/open.ogg', rift_open())
    save_ogg('assets/audio/rift/accept.ogg', rift_accept())
    save_ogg('assets/audio/enemy/superior_spawn.ogg', superior_spawn())
    save_ogg('assets/audio/boss/phase_change.ogg', boss_phase())

    # Ambience
    for kind in ['hub','fields','forest','bastion','observatory','abyss']:
        save_ogg(f'assets/audio/ambience/{kind}.ogg', make_ambience(kind), quality=4)

    # Music
    tracks = [
        ('menu_theme', 72, ['D','As','F','C'], 1, False),
        ('last_light', 74, ['A','F','C','G'], 1, True),
        ('beyond_the_veil', 92, ['C','Gs','Ds','As'], 1, False),
        ('rupture_combat', 128, ['D','Ds','C','D'], 3, False),
        ('superior_hunt', 142, ['E','C','D','B'], 4, False),
        ('boss_veilbreaker', 150, ['Cs','A','B','Gs'], 5, False),
        ('the_nameless', 156, ['D','Ds','As','C'], 5, False),
        ('after_the_rift', 68, ['F','C','D','As'], 1, True),
    ]
    for fname, tempo, roots, intensity, major in tracks:
        save_ogg(f'assets/audio/music/{fname}.ogg', make_music(fname,tempo,roots,intensity,24.0,major), quality=5)

    print('Generated OGG assets:', len(list(AUDIO.rglob('*.ogg'))))


if __name__ == '__main__':
    generate_all()

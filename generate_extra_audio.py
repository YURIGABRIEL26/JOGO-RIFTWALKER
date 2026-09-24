from generate_audio_assets import *


def arrow_hit(v):
    d=.30
    wood=bandpass(noise(d),500,4500)*np.exp(-tvec(d)*13)*.32
    ping=sine(980+v*130,d)*np.exp(-tvec(d)*10)*.18
    thunk=sine(82,d)*np.exp(-tvec(d)*15)*.5
    return stereo_widen(wood+ping+thunk,.15)


def arcane_impact(v):
    d=.48
    pulse=sweep(900+v*100,180,d)*env(d,.002,.26)*.24
    shimmer=(sine(1320+v*80,d)+.5*sine(1760,d))*np.exp(-tvec(d)*7)*.18
    air=bandpass(noise(d),800,7000)*env(d,.005,.25)*.12
    return stereo_widen(pulse+shimmer+air,.35)


def lightning_impact():
    d=.42
    crack=highpass(noise(d),2500)*np.exp(-tvec(d)*10)*.34
    snap=sweep(3200,280,d)*env(d,.001,.20)*.20
    low=sine(70,d)*np.exp(-tvec(d)*13)*.55
    return stereo_widen(crack+snap+low,.32)


def void_impact():
    d=.75
    low=sweep(88,34,d,'saw')*env(d,.004,.42)*.28
    reverse=sweep(320,1300,d)*env(d,.02,.38)*.18
    air=bandpass(noise(d),100,2500)*env(d,.01,.42)*.16
    return stereo_widen(low+reverse+air,.5)


def heal_sound():
    d=.65
    x=np.zeros(int(SR*d))
    for i,f in enumerate([523.25,659.25,783.99]):
        start=int(i*.08*SR)
        s=sine(f,.48)*env(.48,.005,.40)*.18
        x[start:start+len(s)] += s[:len(x)-start]
    return stereo_widen(x,.28)


def boss_death():
    d=2.3
    hit=sine(41,d)*np.exp(-tvec(d)*3.8)*.75
    fall=sweep(320,32,d,'saw')*env(d,.01,.85)*.23
    shatter=highpass(noise(d),1800)*np.exp(-tvec(d)*2.8)*.12
    return stereo_widen(hit+fall+shatter,.55)

save_ogg('assets/audio/combat/arrow_hit_01.ogg', arrow_hit(0))
save_ogg('assets/audio/combat/arrow_hit_02.ogg', arrow_hit(1))
save_ogg('assets/audio/combat/arcane_impact_01.ogg', arcane_impact(0))
save_ogg('assets/audio/combat/arcane_impact_02.ogg', arcane_impact(1))
save_ogg('assets/audio/combat/lightning_impact.ogg', lightning_impact())
save_ogg('assets/audio/combat/void_impact.ogg', void_impact())
save_ogg('assets/audio/combat/heal.ogg', heal_sound())
save_ogg('assets/audio/boss/death.ogg', boss_death())
print('extras generated')

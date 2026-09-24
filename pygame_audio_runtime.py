"""RIFTWALKER — Pygame audio runtime.

Liga o roteador lógico de áudio aos arquivos reais e ao pygame.mixer.
Falha de áudio nunca derruba o jogo: se não houver dispositivo, entra em modo silencioso.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
from array import array
import json

import pygame

from audio_systems import AudioBus, AudioRouter, MUSIC, MusicDirector


REGION_AMBIENCE = {
    "refugio_ultima_luz": "amb_hub",
    "campos_primeira_fenda": "amb_fields",
    "bosque_sussurrante": "amb_forest",
    "bastilha_carmesim": "amb_bastion",
    "observatorio_fraturado": "amb_observatory",
    "abismo_sem_nome": "amb_abyss",
}


class PygameAudioRuntime:
    def __init__(self, settings, asset_root: str = "."):
        self.settings = settings
        self.asset_root = Path(asset_root)
        self.router = AudioRouter(seed=81092)
        self.music_director = MusicDirector()
        self.sound_cache: Dict[str, pygame.mixer.Sound] = {}
        self.voice_variant_cache: Dict[str, pygame.mixer.Sound] = {}
        self.available = False
        self.last_ambience_cue: Optional[str] = None
        self.ambience_channel = None
        self.voice_channel = None
        self._last_focus = True
        self.voice_manifest = {}
        self.enemy_voice_manifest = {}
        manifest_path = self.asset_root / "assets/audio/voice_manifest.json"
        if manifest_path.exists():
            try:
                self.voice_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                self.voice_manifest = {}
        enemy_manifest_path = self.asset_root / "assets/audio/enemy_voice_manifest.json"
        if enemy_manifest_path.exists():
            try:
                self.enemy_voice_manifest = json.loads(enemy_manifest_path.read_text(encoding="utf-8"))
            except Exception:
                self.enemy_voice_manifest = {}

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(max(32, pygame.mixer.get_num_channels()))
            # pygame.mixer.set_reserved(N) reserva os PRIMEIROS N canais.
            # Voz e ambiente precisam usar exatamente esses canais para não serem
            # roubados pelo find_channel() dos SFX.
            pygame.mixer.set_reserved(2)
            self.voice_channel = pygame.mixer.Channel(0)
            self.ambience_channel = pygame.mixer.Channel(1)
            self.available = True
        except Exception:
            self.available = False

    def bus_volume(self, bus: AudioBus) -> float:
        master = self.settings.audio.master / 100.0
        if bus == AudioBus.MUSIC:
            child = self.settings.audio.music / 100.0
        elif bus == AudioBus.VOICE:
            child = self.settings.audio.voices / 100.0
        elif bus == AudioBus.AMBIENCE:
            child = self.settings.audio.ambience / 100.0
        else:
            child = self.settings.audio.sfx / 100.0
        return max(0.0, min(1.0, master * child))

    def _sound(self, relpath: str) -> Optional[pygame.mixer.Sound]:
        if not self.available:
            return None
        path = self.asset_root / relpath
        key = str(path)
        if key in self.sound_cache:
            return self.sound_cache[key]
        try:
            sound = pygame.mixer.Sound(str(path))
            self.sound_cache[key] = sound
            return sound
        except Exception:
            return None

    def play(self, cue_id: str) -> bool:
        if not self.available:
            return False
        plan = self.router.resolve(cue_id, str(self.asset_root))
        if plan is None or not plan.path:
            return False
        sound = self._sound(plan.path)
        if sound is None:
            return False
        sound.set_volume(max(0.0, min(1.0, plan.volume * self.bus_volume(plan.bus))))
        try:
            channel = pygame.mixer.find_channel(True)
            channel.play(sound)
            return True
        except Exception:
            return False


    def play_voice(self, text: str, gender) -> bool:
        if not self.available or not text:
            return False
        record = self.voice_manifest.get(text)
        if not record:
            return False
        raw = str(getattr(gender, "value", gender)).lower()
        key = "female" if ("fem" in raw or raw.startswith("f")) else "male"
        relpath = record.get(key) or record.get("male")
        if not relpath:
            return False
        source = self._sound(relpath)
        sound = self._voice_variant(source, relpath, gender)
        if sound is None:
            return False
        sound.set_volume(min(1.0, self.bus_volume(AudioBus.VOICE) * 1.24))
        try:
            channel = self.voice_channel or pygame.mixer.find_channel(True)
            channel.play(sound)
            return True
        except Exception:
            return False


    def play_enemy_voice(self, text: str) -> bool:
        if not self.available or not text:
            return False
        relpath = self.enemy_voice_manifest.get(text)
        if not relpath:
            return False
        source = self._sound(relpath)
        sound = self._voice_variant(source, relpath, "monster")
        if sound is None:
            return False
        sound.set_volume(min(1.0, self.bus_volume(AudioBus.VOICE) * 1.18))
        try:
            channel = self.voice_channel or pygame.mixer.find_channel(True)
            channel.play(sound)
            return True
        except Exception:
            return False

    def _voice_variant(self, source, relpath: str, gender) -> Optional[pygame.mixer.Sound]:
        if source is None or pygame.mixer.get_init() is None:
            return source
        raw_gender = str(getattr(gender, "value", gender)).lower()
        is_monster = raw_gender == "monster"
        is_female = "fem" in raw_gender or raw_gender.startswith("f")
        # Pequena diferença de tom: as vozes continuam naturais, mas não soam
        # como o mesmo narrador com dois arquivos diferentes.
        pitch_factor = 0.82 if is_monster else (1.055 if is_female else 0.945)
        key = f"{relpath}|{pitch_factor:.3f}"
        cached = self.voice_variant_cache.get(key)
        if cached is not None:
            return cached
        try:
            init = pygame.mixer.get_init()
            channels = abs(init[2])
            samples = array("h")
            samples.frombytes(source.get_raw())
            frame_count = len(samples) // channels
            if frame_count < 2:
                return source
            output = array("h")
            output.extend(
                samples[min(frame_count - 1, int(index * pitch_factor)) * channels + channel]
                for index in range(max(1, int(frame_count / pitch_factor)))
                for channel in range(channels)
            )
            variant = pygame.mixer.Sound(buffer=output.tobytes())
            self.voice_variant_cache[key] = variant
            return variant
        except Exception:
            return source

    def set_ambience(self, region_id: Optional[str]) -> None:
        if not self.available or self.ambience_channel is None:
            return
        cue_id = REGION_AMBIENCE.get(region_id or "", "amb_fields")
        if cue_id == self.last_ambience_cue and self.ambience_channel.get_busy():
            return
        cue = self.router.resolve(cue_id, str(self.asset_root))
        if cue is None or not cue.path:
            return
        sound = self._sound(cue.path)
        if sound is None:
            return
        sound.set_volume(max(0.0, min(1.0, cue.volume * self.bus_volume(AudioBus.AMBIENCE))))
        try:
            self.ambience_channel.fadeout(450)
            self.ambience_channel.play(sound, loops=-1, fade_ms=600)
            self.last_ambience_cue = cue_id
        except Exception:
            pass

    def set_music(self, music_id: str, force: bool = False) -> None:
        if not self.available or music_id not in MUSIC:
            return
        state = MUSIC[music_id]
        if not force and self.music_director.current == music_id and pygame.mixer.music.get_busy():
            return
        path = self.asset_root / state.path
        if not path.exists():
            return
        try:
            old = self.music_director.current
            self.music_director.current = music_id
            pygame.mixer.music.fadeout(int(state.fade_seconds * 500))
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(self.bus_volume(AudioBus.MUSIC))
            pygame.mixer.music.play(-1 if state.loop else 0, fade_ms=int(state.fade_seconds * 1000))
        except Exception:
            self.music_director.current = old if 'old' in locals() else None

    def update_game(self, dt: float, *, region_id: Optional[str], enemies, ending: bool = False) -> None:
        self.router.update(dt)
        if not self.available:
            return

        # Respeita a opção de silenciar quando a janela perde foco.
        focused = bool(pygame.key.get_focused())
        if self.settings.audio.mute_when_unfocused and not focused:
            if self._last_focus:
                try: pygame.mixer.pause(); pygame.mixer.music.pause()
                except Exception: pass
            self._last_focus = False
            return
        elif not self._last_focus:
            try: pygame.mixer.unpause(); pygame.mixer.music.unpause()
            except Exception: pass
        self._last_focus = True

        # Os manifests de voz são carregados uma única vez em __init__.
        # Relê-los do disco a 60 Hz causava I/O desnecessário durante a partida.
        live = [e for e in enemies if not getattr(e, 'dead', False)]
        bosses = [e for e in live if getattr(e, 'kind', '') == 'guardian']
        final_boss = any(getattr(e, 'boss_id', '') == 'o_nome_apagado' for e in bosses)
        superior = any(getattr(e, 'creature_tier', '') == 'Superior' for e in live)

        desired = self.music_director.desired_state(
            in_hub=(region_id == 'refugio_ultima_luz'),
            in_combat=bool(live),
            elite_present=superior,
            boss_present=bool(bosses),
            final_boss=final_boss,
            ending=ending,
        )
        if desired.id != self.music_director.current:
            self.set_music(desired.id)
        self.set_ambience(region_id)

    def refresh_volumes(self) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.music.set_volume(self.bus_volume(AudioBus.MUSIC))
        except Exception:
            pass
        if self.ambience_channel and self.last_ambience_cue:
            cue = self.router.resolve(self.last_ambience_cue, str(self.asset_root))
            if cue is not None:
                self.ambience_channel.set_volume(max(0.0, min(1.0, cue.volume * self.bus_volume(AudioBus.AMBIENCE))))
        if self.voice_channel:
            self.voice_channel.set_volume(self.bus_volume(AudioBus.VOICE))

    def stop_all(self) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
        except Exception:
            pass

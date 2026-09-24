from __future__ import annotations
import math, random
from dataclasses import dataclass
from typing import Dict, Tuple
import pygame

Color = Tuple[int,int,int]

@dataclass(frozen=True)
class RegionTheme:
    floor: Color
    floor2: Color
    accent: Color
    accent2: Color
    edge: Color
    fog: Color
    prop: str

THEMES: Dict[str, RegionTheme] = {
    'refugio_ultima_luz': RegionTheme((43,39,45),(58,51,48),(238,184,96),(87,170,232),(23,20,25),(46,38,35),'refuge'),
    'campos_primeira_fenda': RegionTheme((42,38,43),(54,47,50),(186,66,79),(113,90,118),(24,22,28),(41,33,44),'ruin'),
    'bosque_sussurrante': RegionTheme((29,43,37),(39,57,45),(90,181,121),(83,143,115),(18,27,24),(28,48,40),'forest'),
    'bastilha_carmesim': RegionTheme((52,28,31),(67,34,35),(224,73,63),(243,135,68),(27,16,19),(61,23,27),'fortress'),
    'observatorio_fraturado': RegionTheme((27,34,52),(34,45,65),(84,188,222),(176,108,238),(15,20,34),(24,31,53),'observatory'),
    'abismo_sem_nome': RegionTheme((20,17,29),(28,22,39),(161,73,214),(70,206,224),(8,7,14),(20,10,31),'abyss'),
}

class EnvironmentRenderer:
    def __init__(self):
        self.cache: Dict[Tuple[str,int,int,bool], pygame.Surface] = {}

    def _theme(self, region_id:str) -> RegionTheme:
        return THEMES.get(region_id, THEMES['campos_primeira_fenda'])

    def _seed(self, region_id:str, boss:bool) -> int:
        s = sum((i+1)*ord(c) for i,c in enumerate(region_id))
        return s + (99173 if boss else 0)

    def _floor(self, region_id:str, size:Tuple[int,int], boss:bool) -> pygame.Surface:
        key=(region_id,size[0],size[1],boss)
        if key in self.cache:
            return self.cache[key]
        t=self._theme(region_id); w,h=size; rng=random.Random(self._seed(region_id,boss))
        surf=pygame.Surface(size).convert()
        surf.fill(t.floor)
        # Base de placas top-down: a variação de escala e as linhas quebradas
        # dão profundidade ao piso sem competir com gameplay ou sprites.
        tile_w, tile_h = 72, 48
        for row, y in enumerate(range(0, h, tile_h)):
            for col, x in enumerate(range(0, w, tile_w)):
                shade = 5 if (row + col) % 2 == 0 else -4
                tile = tuple(max(0, min(255, c + shade)) for c in t.floor)
                rect = pygame.Rect(x + 1, y + 1, tile_w - 2, tile_h - 2)
                pygame.draw.rect(surf, tile, rect)
                if (row * 3 + col) % 4 == 0:
                    pygame.draw.line(surf, tuple(max(0, c - 8) for c in tile),
                                     (x + 12, y + tile_h - 8),
                                     (x + tile_w - 18, y + 10), 1)
        # irregular floor patches
        for _ in range(140):
            x=rng.randrange(0,w); y=rng.randrange(0,h)
            rw=rng.randrange(14,80); rh=rng.randrange(8,45)
            col=t.floor2 if rng.random()<0.62 else tuple(max(0,c-rng.randrange(2,12)) for c in t.floor)
            pygame.draw.ellipse(surf,col,(x-rw//2,y-rh//2,rw,rh))
        # biome-specific props
        if t.prop=='forest':
            for _ in range(34):
                x=rng.randrange(18,w-18); y=rng.randrange(18,h-18); r=rng.randrange(5,13)
                pygame.draw.ellipse(surf,(12,22,17),(x-r-5,y+r//2,r*2+10,max(4,r//2)))
                pygame.draw.circle(surf,(21,35,28),(x,y),r+4)
                pygame.draw.circle(surf,(45,79,51),(x,y),r)
                if rng.random()<.45:
                    pygame.draw.line(surf,(31,67,44),(x-r,y+r),(x+r,y-r),2)
        elif t.prop=='ruin':
            for _ in range(28):
                x=rng.randrange(12,w-40); y=rng.randrange(12,h-30)
                ww=rng.randrange(12,46); hh=rng.randrange(5,16)
                pygame.draw.ellipse(surf,(25,21,25),(x-3,y+hh-1,ww+7,max(4,hh//2)))
                pygame.draw.rect(surf,(68,61,65),(x,y,ww,hh),border_radius=2)
                pygame.draw.line(surf,(92,76,78),(x,y),(x+ww,y),1)
        elif t.prop=='fortress':
            for x in range(0,w,64):
                pygame.draw.line(surf,(78,42,42),(x,0),(x,h),1)
            for y in range(0,h,48):
                pygame.draw.line(surf,(75,38,40),(0,y),(w,y),1)
            for _ in range(18):
                x=rng.randrange(w); y=rng.randrange(h)
                pygame.draw.line(surf,t.accent2,(x,y),(x+rng.randrange(-25,26),y+rng.randrange(-25,26)),2)
            for _ in range(14):
                x=rng.randrange(24,w-24); y=rng.randrange(24,h-24)
                pygame.draw.ellipse(surf,(30,16,19),(x-12,y+5,x+12,y+12))
                pygame.draw.rect(surf,(103,48,45),(x-8,y-7,16,13),border_radius=2)
        elif t.prop=='observatory':
            cx,cy=w//2,h//2
            for r in (85,145,215): pygame.draw.circle(surf,(53,72,100),(cx,cy),r,2)
            for a in range(0,360,30):
                rad=math.radians(a); p=(cx+int(math.cos(rad)*230),cy+int(math.sin(rad)*230))
                pygame.draw.circle(surf,t.accent,p,3)
            for _ in range(50):
                pygame.draw.circle(surf,(123,166,199),(rng.randrange(w),rng.randrange(h)),rng.choice((1,1,2)))
            for _ in range(12):
                x=rng.randrange(30,w-30); y=rng.randrange(30,h-30)
                pygame.draw.ellipse(surf,(15,22,37),(x-13,y+5,x+13,y+11))
                pygame.draw.circle(surf,(63,92,126),(x,y),rng.randrange(5,10),2)
        elif t.prop=='abyss':
            for _ in range(36):
                x=rng.randrange(w); y=rng.randrange(h)
                length=rng.randrange(20,90); a=rng.uniform(0,math.tau)
                x2=x+math.cos(a)*length; y2=y+math.sin(a)*length
                pygame.draw.line(surf,t.accent,(x,y),(x2,y2),rng.choice((1,2,3)))
            for _ in range(18):
                pygame.draw.circle(surf,(8,5,14),(rng.randrange(w),rng.randrange(h)),rng.randrange(8,30))
            for _ in range(10):
                x=rng.randrange(30,w-30); y=rng.randrange(30,h-30)
                pygame.draw.ellipse(surf,(7,5,13),(x-16,y+7,x+16,y+14))
                pygame.draw.circle(surf,t.accent2,(x,y),rng.randrange(4,9),2)
        elif t.prop=='refuge':
            for y in range(18,h,42):
                off=20 if (y//42)%2 else 0
                for x in range(-off,w,56): pygame.draw.rect(surf,(69,61,60),(x,y,48,28),1,border_radius=4)
            for _ in range(12):
                pygame.draw.circle(surf,t.accent,(rng.randrange(w),rng.randrange(h)),3)
        # boss arena sigil
        if boss:
            cx,cy=w//2,h//2
            glow=pygame.Surface(size,pygame.SRCALPHA)
            for r,a in ((210,34),(170,46),(125,58)):
                pygame.draw.circle(glow,(*t.accent,a),(cx,cy),r,3)
            for a in range(0,360,45):
                rad=math.radians(a)
                p1=(cx+math.cos(rad)*110,cy+math.sin(rad)*110)
                p2=(cx+math.cos(rad)*208,cy+math.sin(rad)*208)
                pygame.draw.line(glow,(*t.accent,38),p1,p2,2)
            surf.blit(glow,(0,0))
        # dark irregular boundary inside floor image
        edge=pygame.Surface(size,pygame.SRCALPHA)
        for i in range(14):
            alpha=max(5,72-i*4)
            pygame.draw.rect(edge,(*t.edge,alpha),(i,i,w-i*2,h-i*2),2,border_radius=18+i//2)
        surf.blit(edge,(0,0))
        self.cache[key]=surf
        return surf

    def draw_base(self, surface:pygame.Surface, room:pygame.Rect, region_id:str, wave:int, rift_count:int, boss:bool, time_s:float, offset:pygame.Vector2):
        t=self._theme(region_id)
        # outer world / vignette background
        surface.fill(tuple(max(0,c-12) for c in t.edge))
        rr=room.move(int(offset.x),int(offset.y))
        floor=self._floor(region_id,(room.width,room.height),boss)
        surface.blit(floor,rr.topleft)
        # region boundary: rocks/roots/runes, deliberately irregular
        rng=random.Random(self._seed(region_id,boss)+17)
        for side in range(4):
            count=22 if side<2 else 16
            for i in range(count):
                if side==0: x=rr.left+int((i+.5)*rr.width/count); y=rr.top+rng.randint(-6,8)
                elif side==1: x=rr.left+int((i+.5)*rr.width/count); y=rr.bottom+rng.randint(-8,6)
                elif side==2: x=rr.left+rng.randint(-6,8); y=rr.top+int((i+.5)*rr.height/count)
                else: x=rr.right+rng.randint(-8,6); y=rr.top+int((i+.5)*rr.height/count)
                rad=rng.randint(5,13)
                pygame.draw.circle(surface,t.edge,(x,y),rad)
                if rng.random()<.32: pygame.draw.circle(surface,t.floor2,(x-2,y-2),max(2,rad//2))
        # animated ambient motes
        motes=24 if region_id!='abismo_sem_nome' else 38
        for i in range(motes):
            phase=time_s*(0.35+(i%5)*0.05)+i*2.11
            x=rr.left+((i*79 + int(time_s*10*(1+(i%3)))) % max(1,rr.width))
            y=rr.top+((i*131 + int(math.sin(phase)*45)+i*17) % max(1,rr.height))
            a=65+int(35*(.5+.5*math.sin(phase)))
            rad=1+(i%3==0)
            mote=pygame.Surface((rad*4,rad*4),pygame.SRCALPHA)
            pygame.draw.circle(mote,(*t.accent,a),(rad*2,rad*2),rad)
            surface.blit(mote,(x-rad*2,y-rad*2))
        # active rifts visually scar the floor
        if rift_count:
            overlay=pygame.Surface((room.width,room.height),pygame.SRCALPHA)
            rng2=random.Random(8899+wave*101+rift_count*17)
            for i in range(min(18,5+rift_count*4)):
                x=rng2.randrange(20,room.width-20); y=rng2.randrange(20,room.height-20)
                pts=[(x,y)]
                for _ in range(rng2.randrange(2,5)):
                    x+=rng2.randrange(-35,36); y+=rng2.randrange(-35,36); pts.append((x,y))
                pygame.draw.lines(overlay,(*t.accent,75),False,pts,2)
            surface.blit(overlay,rr.topleft)

    def draw_foreground(self, surface:pygame.Surface, room:pygame.Rect, region_id:str, time_s:float, offset:pygame.Vector2, player_pos:pygame.Vector2):
        t=self._theme(region_id)
        # subtle top/bottom fog strips and vignette
        fog=pygame.Surface((surface.get_width(),surface.get_height()),pygame.SRCALPHA)
        for i in range(7):
            a=max(0,26-i*3)
            pygame.draw.rect(fog,(*t.fog,a),(0,i*12,surface.get_width(),22))
            pygame.draw.rect(fog,(*t.fog,a),(0,surface.get_height()-22-i*12,surface.get_width(),22))
        surface.blit(fog,(0,0))

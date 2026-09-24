from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math

ROOT=Path(__file__).resolve().parent
out=ROOT/'assets'/'branding'
out.mkdir(parents=True, exist_ok=True)
size=512
im=Image.new('RGBA',(size,size),(10,12,22,255))
# subtle radial background
pix=im.load(); cx=cy=size/2
for y in range(size):
    for x in range(size):
        d=((x-cx)**2+(y-cy)**2)**0.5/(size*.72)
        glow=max(0,1-d)
        pix[x,y]=(int(10+18*glow),int(12+8*glow),int(22+32*glow),255)
# glow rings on separate layer
glow=Image.new('RGBA',im.size,(0,0,0,0)); g=ImageDraw.Draw(glow)
for r,a,w in [(165,65,24),(135,100,14),(105,120,8)]:
    g.ellipse((cx-r,cy-r,cx+r,cy+r),outline=(170,70,255,a),width=w)
glow=glow.filter(ImageFilter.GaussianBlur(12))
im=Image.alpha_composite(im,glow)
d=ImageDraw.Draw(im)
# broken rift ring
for start,end,col,w in [(210,320,(178,80,245,255),20),(338,92,(75,225,235,255),16),(105,190,(238,238,248,255),10)]:
    d.arc((96,96,416,416),start=start,end=end,fill=col,width=w)
# central slash / veil tear
pts=[(256,100),(228,214),(268,196),(238,310),(286,284),(252,414),(314,268),(274,286),(298,176),(260,198)]
d.polygon(pts,fill=(240,242,250,255))
# inner purple edge
pts2=[(257,122),(241,211),(262,205),(248,291),(269,279),(255,383),(290,278),(271,287),(286,192),(263,203)]
d.polygon(pts2,fill=(112,48,174,255))
# small sparks
for ang in range(0,360,45):
    rad=205
    x=cx+math.cos(math.radians(ang))*rad; y=cy+math.sin(math.radians(ang))*rad
    rr=4 if ang%90 else 6
    d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(75,225,235,220))
png=out/'riftwalker_icon.png'; ico=out/'riftwalker.ico'
im.save(png)
im.save(ico,format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(png, ico)

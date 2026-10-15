"""Align generated complete frames, audit cross-frame consistency and package a playable pixel sequence.

ImageGen owns artwork. This step measures feet, audits the generated set against
the export grid, aligns, samples the export pixel grid, snaps opaque pixels to
the scheme B palette (nearest colour, no dither) and packs frames; all
full-resolution originals are kept unchanged.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import json
import shutil
import sys

BASE=Path(__file__).resolve().parent
NAMES=['战斗待机','回收蓄力','蓄力峰值','挥出','命中','跟随','收势','归位']
TIMES=[70,90,100,40,70,60,110,80]
CANVAS=(384,256)
ROOT=(176,246)
HEIGHT_WARN=0.025
# Closed board: any opaque colour on the sampled export grid that is not an
# exact palette entry is foreign. One is already too many for pixel art,
# because the snap below will repaint it. Continuous-tone sources warn.
PALETTE_OFF_COLOUR_MAX=0
PALETTE_PATH=BASE/'config'/'palette.candidate.json'
PREVIEW=BASE/'preview'
ASSETS=BASE/'godot/assets'
for folder in [PREVIEW,ASSETS/'slash',ASSETS/'idle']:folder.mkdir(parents=True,exist_ok=True)

def feet(im):
    """Measure soles only in the lower body region; exclude the right-side blade."""
    alpha=im.getchannel('A');w,h=im.size;data=alpha.load()
    x0,x1=int(w*.18),int(w*.72)
    rows=[y for y in range(int(h*.74),h) if any(data[x,y]>128 for x in range(x0,x1))]
    if not rows:raise ValueError('No feet in expected lower-body region')
    bottom=max(rows)+1
    columns=[x for x in range(x0,x1) if any(data[x,y]>128 for y in range(max(0,bottom-int(h*.025)),bottom))]
    groups=[]
    for x in columns:
        if not groups or x>groups[-1][-1]+1:groups.append([x])
        else:groups[-1].append(x)
    groups=[g for g in groups if len(g)>w*.025]
    if len(groups)!=2:raise ValueError(f'Expected two separate soles, found {len(groups)}')
    centers=[(g[0]+g[-1])/2 for g in groups]
    return [(centers[0]+centers[1])/2,bottom],[[g[0],g[-1]+1] for g in groups]

def colour_run_width(im,step=3):
    """Average width of a flat colour run, from 1/(1 - identical horizontal neighbour share).
    Real pixel art scores at or above the source-to-export scale; continuous-tone art scores near 1."""
    alpha=im.getchannel('A');px=im.load();w,h=im.size
    same=tot=0
    for y in range(0,h,step):
        for x in range(0,w-1,step):
            if px[x,y][3]>=128 and px[x+1,y][3]>=128:
                tot+=1
                if px[x,y][:3]==px[x+1,y][:3]: same+=1
    if not tot:raise ValueError('No opaque horizontal neighbour pairs to measure')
    return round(1/(1-same/tot),2)

def colour_signature(im,step=4,keep=16):
    """Top 12-bit colour bins over opaque pixels only, so empty canvas does not count."""
    w,h=im.size;px=im.load();counts={}
    for y in range(0,h,step):
        for x in range(0,w,step):
            r,g,b,a=px[x,y]
            if a>=128:
                key=(r>>4)<<8|(g>>4)<<4|(b>>4)
                counts[key]=counts.get(key,0)+1
    total=sum(counts.values())
    return {k:round(v/total,4) for k,v in sorted(counts.items(),key=lambda kv:-kv[1])[:keep]}

def colour_distance(a,b):
    """Total variation between two colour distributions, 0 = identical mix. Poses that expose
    different amounts of the same palette also move this, so it is a review cue, not a gate."""
    keys=set(a)|set(b)
    return round(sum(abs(a.get(k,0)-b.get(k,0)) for k in keys)/2,4)

def load_palette(path):
    """Scheme B board. The JSON is the source of truth; export refuses any other count."""
    doc=json.loads(path.read_text())
    colours=[]
    for entry in doc['colours']:
        rgb=tuple(int(v) for v in entry['rgb'])
        if len(rgb)!=3 or any(v<0 or v>255 for v in rgb):
            raise ValueError(f'palette rgb out of range: {entry.get("role","")} {rgb}')
        hex_s=str(entry['hex']).lstrip('#').lower()
        expect=f'{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
        if hex_s!=expect:
            raise ValueError(f'palette {entry.get("role","")} hex {entry["hex"]} does not match rgb {rgb}')
        colours.append(rgb)
    if len(colours)!=22:
        raise ValueError(f'现行 22 色板需要 22 色，{path.name} 里有 {len(colours)} 色')
    if len(set(colours))!=len(colours):
        raise ValueError(f'{path.name} 有重复色')
    return colours

def rgba_pixels(im):
    """Pillow 12 renamed getdata to get_flattened_data; keep the older name working."""
    reader=getattr(im,'get_flattened_data',None)
    return reader() if reader else im.getdata()

def palette_deviation(im,palette_set):
    """Distinct opaque colours that are not exact palette entries. Transparent pixels are ignored."""
    off=set();opaque=off_px=0
    for r,g,b,a in rgba_pixels(im):
        if a<128:continue
        opaque+=1
        if (r,g,b) not in palette_set:
            off.add((r,g,b));off_px+=1
    return len(off),off_px,opaque

def map_nearest_palette(im,palette):
    """Snap opaque pixels to the nearest palette colour. No dither. Equal distances keep the earlier entry."""
    cache={}
    out=[]
    for r,g,b,a in rgba_pixels(im):
        if a<128:
            out.append((r,g,b,a));continue
        key=(r,g,b)
        mapped=cache.get(key)
        if mapped is None:
            best_d=1<<62;best=palette[0]
            for colour in palette:
                d=(r-colour[0])**2+(g-colour[1])**2+(b-colour[2])**2
                if d<best_d:
                    best_d=d;best=colour
                    if d==0:break
            mapped=best;cache[key]=mapped
        out.append((mapped[0],mapped[1],mapped[2],255))
    im.putdata(out)
    return im

def sample_export(im,index,overrides):
    """Nearest-neighbour sample onto the export scale, then hard alpha. Palette snap is separate."""
    origin,soles=feet(im)
    frame_override=overrides.get(str(index),{})
    origin=frame_override.get('origin',origin)
    scale=CANVAS[0]/im.width*frame_override.get('scale',1.0)
    sampled=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
    sampled.putalpha(sampled.getchannel('A').point(lambda value:255 if value>=128 else 0))
    offset=(ROOT[0]-round(origin[0]*scale),ROOT[1]-round(origin[1]*scale))
    return origin,soles,scale,sampled,offset

def audit(files):
    """Measure the generated set against the export assumptions. Returns (per-frame rows, warnings)."""
    rows=[];warnings=[];ref=None;heads=[]
    for i,path in enumerate(files):
        im=Image.open(path).convert('RGBA');w,h=im.size
        alpha=im.getchannel('A')
        run_width=colour_run_width(im)
        bbox=alpha.getbbox()
        band_x=(int(w*.30),int(w*.62));adata=alpha.load()
        head=next((y for y in range(h) if any(adata[x,y]>128 for x in range(*band_x))),None)
        if head is None:raise ValueError(f'Frame {i+1} has no body in the measurement band')
        height=feet(im)[0][1]-head
        heads.append(height)
        sig=colour_signature(im)
        drift=0.0 if ref is None else colour_distance(ref,sig)
        if ref is None:ref=sig
        bleed=[side for side,gap in zip(('left','top','right','bottom'),(bbox[0],bbox[1],w-bbox[2],h-bbox[3])) if gap<=1]
        rows.append({'frame':i+1,'name':NAMES[i],'source_size':[w,h],'colour_run_width_px':run_width,
                     'head_y':head,'body_height_px':height,
                     'content_bbox':list(bbox),'source_edge_bleed':bleed,
                     'colour_drift_vs_frame_01':drift,'opaque_px':sum(alpha.histogram()[128:])})
    median=sorted(heads)[len(heads)//2]
    for row in rows:
        deviation=(row['body_height_px']-median)/median
        row['body_height_deviation']=round(deviation,4)
        if abs(deviation)>HEIGHT_WARN:
            warnings.append(f"帧 {row['frame']:02d} {row['name']}：头到脚底高度比中位数偏 {deviation:+.1%}，确认是蓄力蹲伏还是比例漂移")
        if row['source_edge_bleed']:
            warnings.append(f"帧 {row['frame']:02d} {row['name']}：内容被源图边界裁掉（{','.join(row['source_edge_bleed'])}），该帧需重新生成或扩画布")
        min_run=row['source_size'][0]/CANVAS[0]
        if row['colour_run_width_px']<min_run:
            warnings.append(f"帧 {row['frame']:02d} {row['name']}：源图平均色块宽 {row['colour_run_width_px']}px，低于导出缩放所需的 {min_run:g}px，"
                            f"最近邻按点取样会得到噪点状边缘而不是像素簇；需让角色在源图里占比更小，或导出改为 BOX 平均并量化色板")
    return rows,warnings

def main():
    overrides_path=BASE/'registration.json'
    overrides=json.loads(overrides_path.read_text()) if overrides_path.exists() else {}
    if not PALETTE_PATH.exists():raise SystemExit(f'Missing palette: {PALETTE_PATH}')
    palette=load_palette(PALETTE_PATH);palette_set=set(palette)
    files=[BASE/'source'/f'2026-09-26-{i+1:02d}-{n}.png' for i,n in enumerate(NAMES)]
    if not all(p.exists() for p in files[:7]):raise SystemExit('Generate source frames 01 through 07 first.')
    shutil.copy2(files[0],files[7])
    # Frame 08 is a byte copy of frame 01, so only 01-07 are independent samples.
    audit_rows,audit_warnings=audit(files[:7])
    prepared=[]
    for i,path in enumerate(files):
        im=Image.open(path).convert('RGBA')
        origin,soles,scale,sampled,offset=sample_export(im,i+1,overrides)
        if i<7:
            off_colours,off_px,opaque=palette_deviation(sampled,palette_set)
            audit_rows[i]['palette_off_colours']=off_colours
            audit_rows[i]['palette_off_px']=off_px
            audit_rows[i]['palette_sampled_opaque_px']=opaque
            if off_colours>PALETTE_OFF_COLOUR_MAX:
                audit_warnings.append(
                    f"帧 {i+1:02d} {NAMES[i]}：导出取样后有 {off_colours} 个现行 22 色板（方案 B）以外的颜色"
                    f"（{off_px}/{opaque} 个不透明像素不在板上）。闭合色板不接受板外色；"
                    f"这些像素会按最近色、无抖动贴回色板，色阶会被压平")
        prepared.append((origin,soles,scale,sampled,offset,path,list(im.size)))
    (PREVIEW/'2026-09-26-一致性检查.json').write_text(json.dumps({
        'palette':'config/palette.candidate.json','palette_colours':len(palette),
        'palette_off_colour_max':PALETTE_OFF_COLOUR_MAX,
        'frames':audit_rows,'warnings':audit_warnings},indent=2,ensure_ascii=False))
    for text in audit_warnings:print(f'WARN {text}')
    if '--strict' in sys.argv and audit_warnings:raise SystemExit(f'{len(audit_warnings)} consistency warnings; see preview/2026-09-26-一致性检查.json')
    records=[];frames=[];manifest={'canvas':list(CANVAS),'root_px':list(ROOT),'character_id':'hero_memory','equipment_id':'one_hand_sword','source':'imagegen_complete_frames','clips':{}}
    for i,(origin,soles,scale,sampled,offset,path,source_size) in enumerate(prepared):
        map_nearest_palette(sampled,palette)
        exported=Image.new('RGBA',CANVAS);exported.paste(sampled,offset)
        bbox=exported.getchannel('A').getbbox()
        if not bbox or min(bbox[0],bbox[1],CANVAS[0]-bbox[2],CANVAS[1]-bbox[3])<2:raise ValueError(f'Frame {i+1} touches export boundary: {bbox}')
        left=palette_deviation(exported,palette_set)[0]
        if left:raise ValueError(f'Frame {i+1} still has {left} off-palette colours after mapping')
        exported.save(ASSETS/'slash'/f'{i+1:02d}.png');frames.append(exported)
        records.append({'frame':i+1,'name':NAMES[i],'source':path.name,'source_size':source_size,'source_root':origin,'source_sole_ranges':soles,'scale':scale,'offset':offset,'export_bbox':bbox})
    assert frames[0].tobytes()==frames[-1].tobytes(),'Loop seam mismatch'
    frames[0].save(ASSETS/'idle/01.png')
    manifest['clips']['slash']={'loop':False,'next':'idle','frames':[{'id':i+1,'path':f'slash/{i+1:02d}.png','duration_ms':ms,'event':'hit' if i==4 else ''} for i,ms in enumerate(TIMES)]}
    manifest['clips']['idle']={'loop':True,'next':'idle','frames':[{'id':1,'path':'idle/01.png','duration_ms':500,'event':''}]}
    (ASSETS/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (PREVIEW/'2026-09-26-帧对齐检查.json').write_text(json.dumps(records,indent=2,ensure_ascii=False))
    atlas=Image.new('RGBA',(CANVAS[0]*4,CANVAS[1]*2))
    sheet=Image.new('RGB',(CANVAS[0]*4,(CANVAS[1]+28)*2),'#18212f');draw=ImageDraw.Draw(sheet)
    for i,im in enumerate(frames):
        x=(i%4)*CANVAS[0];y=(i//4)*CANVAS[1];atlas.paste(im,(x,y))
        sy=(i//4)*(CANVAS[1]+28);sheet.paste(im,(x,sy),im)
        draw.line((x+4,sy+ROOT[1],x+CANVAS[0]-4,sy+ROOT[1]),fill='#465266')
        draw.text((x+8,sy+CANVAS[1]+8),f'{i+1:02d} / {TIMES[i]} ms',fill='#f5d7a5')
    atlas.save(PREVIEW/'2026-09-26-八帧透明总图.png');sheet.save(PREVIEW/'2026-09-26-八帧检查图.png')
    animation=[]
    for im in [frames[0],*frames,frames[0]]:
        matte=Image.new('RGBA',CANVAS,'#18212f');matte.alpha_composite(im)
        animation.append(matte.convert('RGB').resize((CANVAS[0]*3,CANVAS[1]*3),Image.Resampling.NEAREST))
    animation[0].save(PREVIEW/'2026-09-26-逐张绘制完整横斩.gif',save_all=True,append_images=animation[1:],duration=[350,*TIMES,400],loop=0,disposal=2)
    (PREVIEW/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'frames':len(frames),'duration_ms':sum(TIMES),'root':ROOT,'palette_colours':len(palette),'palette_off_colours':[row['palette_off_colours'] for row in audit_rows],'source_sizes':[r['source_size'] for r in records],'sole_widths':[[b-a for a,b in r['source_sole_ranges']] for r in records]},indent=2))

if __name__=='__main__':main()

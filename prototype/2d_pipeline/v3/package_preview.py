"""Package Blender exports without repainting: atlas, nearest-pixel previews, checks."""
from pathlib import Path
import base64
import json
import math
import shutil
from PIL import Image, ImageDraw

BASE=Path(__file__).resolve().parent
ASSETS=BASE/'godot/assets'
PREVIEW=BASE/'preview'
manifest=json.loads((ASSETS/'manifest.json').read_text())
w,h=manifest['canvas']
errors=[];records=[]

for clip,data in manifest['clips'].items():
    for frame in data['frames']:
        paths=frame['paths']
        composite=Image.open(ASSETS/paths['composite']).convert('RGBA')
        assert composite.size==(w,h)
        combined=Image.new('RGBA',(w,h))
        for layer in manifest['layers']:
            layer_image=Image.open(ASSETS/paths[layer]).convert('RGBA')
            assert layer_image.size==(w,h)
            combined=Image.alpha_composite(combined,layer_image)
        # RGB under alpha=0 is unspecified in Blender PNGs; compare visible pixels.
        unequal=sum(a[3]!=b[3] or ((a[3]>0 or b[3]>0) and a[:3]!=b[:3])
                    for a,b in zip(composite.get_flattened_data(),combined.get_flattened_data()))
        bbox=composite.getchannel('A').getbbox()
        if not set(composite.getchannel('A').get_flattened_data()).issubset({0,255}):errors.append(f'{clip}/{frame["id"]}: non-binary alpha')
        if not bbox or min(bbox[0],bbox[1],w-bbox[2],h-bbox[3])<2:errors.append(f'{clip}/{frame["id"]}: clipped')
        if unequal:errors.append(f'{clip}/{frame["id"]}: {unequal} layer pixels differ')
        records.append({'clip':clip,'frame':frame['id'],'bbox':bbox,'layer_difference_pixels':unequal})

slash=manifest['clips']['slash']['frames']
images=[Image.open(ASSETS/f['paths']['composite']).convert('RGBA') for f in slash]
if images[0].tobytes()!=images[-1].tobytes():errors.append('First and last slash frames differ')
idle=Image.open(ASSETS/manifest['clips']['idle']['frames'][0]['paths']['composite']).convert('RGBA')
if images[0].tobytes()!=idle.tobytes():errors.append('Idle and slash rest poses differ')

atlas=Image.new('RGBA',(w*4,h*3))
sheet=Image.new('RGB',(w*2*4,(h*2+30)*3),'#18212f')
draw=ImageDraw.Draw(sheet)
names=['READY','START','COIL','WINDUP','RELEASE','SWING','CONTACT','FOLLOW','ABSORB','RECOVER','SETTLE','READY']
for i,im in enumerate(images):
    x=(i%4)*w;y=(i//4)*h
    atlas.paste(im,(x,y))
    px=x*2;py=(i//4)*(h*2+30)
    large=im.resize((w*2,h*2),Image.Resampling.NEAREST)
    sheet.paste(large,(px,py),large)
    ground=py+manifest['root_px'][1]*2
    draw.line((px+8,ground,px+w*2-8,ground),fill='#34435a')
    draw.text((px+12,py+h*2+7),f'{i+1:02d}  {names[i]}  /  {slash[i]["duration_ms"]} ms',fill='#e8d9b7')
atlas.save(PREVIEW/'2026-09-26-横斩序列总图.png')
sheet.save(PREVIEW/'2026-09-26-横斩逐帧检查图.png')

# GIF is a viewing aid on a fixed matte; original PNGs retain transparency.
view_frames=[]
for im in [idle,*images,idle]:
    bg=Image.new('RGBA',(w,h),'#18212f');bg.alpha_composite(im)
    view_frames.append(bg.convert('RGB').resize((w*3,h*3),Image.Resampling.NEAREST))
source_durations=[300,*[f['duration_ms'] for f in slash],400]
cumulative=0;previous=0;gif_durations=[]
for ms in source_durations:
    cumulative+=ms;rounded=math.floor((cumulative+5)/10)*10
    gif_durations.append(rounded-previous);previous=rounded
view_frames[0].save(PREVIEW/'2026-09-26-主角完整横斩.gif',save_all=True,append_images=view_frames[1:],duration=gif_durations,loop=0,disposal=2)

key_dir=PREVIEW/'2026-09-26-关键姿势';key_dir.mkdir(exist_ok=True)
for i,name in [(0,'战斗待机'),(3,'蓄力'),(5,'挥出'),(6,'命中'),(8,'跟随'),(11,'归位')]:
    shutil.copy2(ASSETS/slash[i]['paths']['composite'],key_dir/f'2026-09-26-{i+1:02d}-{name}.png')

# Embed assets so the HTML works on double-click without a server or file-fetch permissions.
embedded={}
for data in manifest['clips'].values():
    for frame in data['frames']:
        for path in frame['paths'].values():
            embedded[path]='data:image/png;base64,'+base64.b64encode((ASSETS/path).read_bytes()).decode()
template=(BASE/'preview_template.html').read_text()
page=template.replace('__MANIFEST__',json.dumps(manifest)).replace('__IMAGES__',json.dumps(embedded))
(PREVIEW/'2026-09-26-动作预览.html').write_text(page)

rig=json.loads((PREVIEW/'rig_checks.json').read_text())
for entry in rig:
    if entry.get('evaluated_pose_error_units',1)>.0001:errors.append('Unevaluated or inaccurate rig pose')
    if entry['hand_clamped_units']>.001:errors.append('Unreachable hand target')
report={'errors':errors,'canvas':[w,h],'root_px':manifest['root_px'],'slash_duration_ms':sum(f['duration_ms'] for f in slash),
        'slash_frames':len(slash),'idle_frames':len(manifest['clips']['idle']['frames']),'records':records,
        'first_equals_last':images[0].tobytes()==images[-1].tobytes(),'max_rig_error':max(f.get('evaluated_pose_error_units',1) for f in rig)}
(PREVIEW/'asset_checks.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))
if errors:raise SystemExit(1)

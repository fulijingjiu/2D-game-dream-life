"""Build an editable, textured 2.5D armature and export pixel animation layers.

blender --background --python build_rig.py [-- --preview]
Appearance, weapon and clip data live in ../config; no generated image is repainted.
"""
import bpy
import json
import math
import sys
from pathlib import Path
from mathutils import Vector, Matrix

BASE = Path(__file__).resolve().parents[1]
CHAR = json.loads((BASE / 'config/character.json').read_text())
GEAR = json.loads((BASE / 'config/weapon.json').read_text())
CLIP = json.loads((BASE / 'config/slash.json').read_text())
OUT = BASE / 'godot/assets'
OUT.mkdir(parents=True, exist_ok=True)
W, H = CHAR['canvas']
PPU = CHAR['pixels_per_unit']
ROOT_X, ROOT_Y = CHAR['root_px']
CHECKS = []

def v(p):
    return Vector((p[0], 0, p[1]))

def ik(a, target, l1, l2, bend=1):
    delta = target-a
    raw = delta.length
    distance = min(max(raw, abs(l1-l2)+.001), l1+l2-.001)
    direction = delta.normalized()
    end = a + direction*distance
    along = (l1*l1-l2*l2+distance*distance)/(2*distance)
    side = math.sqrt(max(0, l1*l1-along*along))
    normal = Vector((-direction.z, 0, direction.x))
    return a + direction*along + normal*side*bend, end, max(0, raw-distance)

def solve(p):
    x, z = p['pelvis']
    t = math.radians(p['lean_deg'])
    def point(a,b):
        return v((x+math.cos(t)*a+math.sin(t)*(b-2.12),
                  z-math.sin(t)*a+math.cos(t)*(b-2.12)))
    bones = {'root': (v((0,0)),v((0,.3))),
             'pelvis': (v((x,z)),v((x,z+.54))),
             'spine': (point(0,2.35),point(0,3.50)),
             'head': (point(.08,3.54),point(.08,4.30))}
    sword_angle=math.radians(p['sword_deg'])
    sword_direction=v((math.cos(sword_angle),math.sin(sword_angle)))
    for side, sx in [('r',.23),('l',-.23)]:
        shoulder=point(sx,3.28)
        target=v(p['hand_r'])-sword_direction*CHAR['rig']['hand_length'] if side=='r' else point(-.30,2.08)
        length=CHAR['rig'].get('forearm_r',CHAR['rig']['forearm']) if side=='r' else CHAR['rig']['forearm']
        bend=p.get('elbow_bend',-1) if side=='r' else -1
        elbow,hand,clamp=ik(shoulder,target,CHAR['rig']['upper_arm'],length,bend)
        bones['upper_'+side]=(shoulder,elbow)
        bones['fore_'+side]=(elbow,hand)
        bones['hand_'+side]=(hand,hand+(sword_direction*CHAR['rig']['hand_length'] if side=='r' else v((.15,0))))
        if side=='r': hand_clamp=clamp
    for side,hx,fx in [('l',-.16,CHAR['rig']['feet_x'][0]),('r',.16,CHAR['rig']['feet_x'][1])]:
        hip=v((x+hx,z))
        ankle=v((fx,CHAR['rig']['ankle_z']))
        knee,end,clamp=ik(hip,ankle,CHAR['rig']['thigh'],CHAR['rig']['shin'],1)
        assert clamp < 1e-6, 'Leg target outside reach'
        bones['thigh_'+side]=(hip,knee)
        bones['shin_'+side]=(knee,end)
        bones['foot_'+side]=(end,end+v((.35,0)))
    angle=math.radians(p['sword_deg'])
    grip=bones[GEAR['socket']][GEAR.get('socket_end',0)]
    bones['weapon']=(grip,grip+v((math.cos(angle),math.sin(angle)))*GEAR['length'])
    a=math.radians(p['scarf_deg'])
    start=point(-.28,3.45)
    mid=start+v((math.sin(a),-math.cos(a)))*.95
    end=mid+v((math.sin(a*1.4),-math.cos(a*1.4)))*.95
    bones['scarf_a']=(start,mid);bones['scarf_b']=(mid,end)
    a=math.radians(p['coat_deg'])
    for side,offset in [('l',-.24),('r',.21)]:
        start=point(offset,2.47)
        bones['coat_'+side]=(start,start+v((-math.sin(a),-math.cos(a)))*(1.25 if side=='l' else 1.1))
    bones['memory']=(v((x+.24,z+.26)),v((x+.24,z+.50)))
    bones['collar']=(point(-.02,3.35),point(-.02,3.70))
    return bones,hand_clamp

PARENTS={'root':None,'pelvis':'root','spine':'pelvis','head':'spine',
         'upper_r':'spine','fore_r':'upper_r','hand_r':'fore_r',
         'upper_l':'spine','fore_l':'upper_l','hand_l':'fore_l',
         'thigh_l':'pelvis','shin_l':'thigh_l','foot_l':'shin_l',
         'thigh_r':'pelvis','shin_r':'thigh_r','foot_r':'shin_r',
         'weapon':GEAR['socket'],'scarf_a':'spine','scarf_b':'scarf_a',
         'coat_l':'pelvis','coat_r':'pelvis','memory':'pelvis','collar':'spine'}

def bone_matrix(a,b):
    d=(b-a).normalized()
    right=Vector((d.z,0,-d.x))
    m=Matrix((right,d,Vector((0,-1,0)))).transposed().to_4x4()
    m.translation=a
    return m

def material(image):
    mat=bpy.data.materials.new('Hero_Pixel_Atlas_AlphaCut')
    mat.use_nodes=True
    mat.surface_render_method='DITHERED'
    n=mat.node_tree.nodes;n.clear();links=mat.node_tree.links
    tex=n.new('ShaderNodeTexImage');tex.image=image;tex.interpolation='Closest';tex.extension='CLIP'
    emission=n.new('ShaderNodeEmission');links.new(tex.outputs['Color'],emission.inputs['Color'])
    clip=n.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.5
    links.new(tex.outputs['Alpha'],clip.inputs[0])
    trans=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader')
    links.new(clip.outputs[0],mix.inputs[0]);links.new(trans.outputs[0],mix.inputs[1]);links.new(emission.outputs[0],mix.inputs[2])
    out=n.new('ShaderNodeOutputMaterial');links.new(mix.outputs[0],out.inputs[0])
    return mat

def part(name, key, bone, depth, rig, rest, mat, image, layer='body', deform=None):
    cfg=CHAR['parts'][key];x0,y0,x1,y1=cfg['rect'];rw=x1-x0;rh=y1-y0
    a=Vector((cfg['a'][0]*rw,cfg['a'][1]*rh));b=Vector((cfg['b'][0]*rw,cfg['b'][1]*rh))
    art_direction=(b-a).normalized();art_right=Vector((art_direction.y,-art_direction.x))
    if art_direction.y<0:art_right=-art_right
    start,end=rest[bone]
    if deform=='scarf':end=rest['scarf_b'][1]
    world_direction=(end-start).normalized();world_right=Vector((-world_direction.z,0,world_direction.x))
    if art_direction.y<0:world_right=-world_right
    scale=(end-start).length/(b-a).length
    rows=16 if deform else 1;cols=4 if deform else 1
    vertices=[];uvs=[];weights=[]
    for row in range(rows+1):
        for col in range(cols+1):
            pixel=Vector((rw*col/cols,rh*row/rows));delta=pixel-a
            along=delta.dot(art_direction);side=delta.dot(art_right)
            pos=start+world_direction*along*scale+world_right*side*scale*cfg['width_scale'];pos.y=depth
            vertices.append(pos);uvs.append(((x0+pixel.x)/image.size[0],1-(y0+pixel.y)/image.size[1]))
            if deform=='scarf':
                t=max(0,min(1,(row/rows-.35)/.30));weights.append({bone:1-t,'scarf_b':t})
            elif deform=='foot':
                t=max(0,min(1,(row/rows-.63)/.18))
                # The boot sole is horizontal in bind pose as well as in animation.
                foot_pos=end+Vector(((pixel.x-b.x)*scale*cfg['width_scale'],depth,-(pixel.y-b.y)*scale+CHAR['rig'].get('sole_offset_units',0)))
                vertices[-1]=pos.lerp(foot_pos,t)
                knee_weight=max(0,(.19-row/rows)/.19)*.65
                weights.append({bone:1-t-knee_weight,'foot_'+bone[-1]:t,'thigh_'+bone[-1]:knee_weight})
            elif deform in ('elbow','shoulder'):
                parent_weight=max(0,(.24-row/rows)/.24)*.7
                weights.append({bone:1-parent_weight,PARENTS[bone]:parent_weight})
            else:weights.append({bone:1})
    faces=[]
    for row in range(rows):
        for col in range(cols):
            k=row*(cols+1)+col;faces.append((k,k+1,k+cols+2,k+cols+1))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.materials.append(mat)
    uv=mesh.uv_layers.new(name='AtlasUV')
    for face in mesh.polygons:
        for li in face.loop_indices:uv.data[li].uv=uvs[mesh.loops[li].vertex_index]
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
    for i,mapping in enumerate(weights):
        for group,weight in mapping.items():
            vg=obj.vertex_groups.get(group) or obj.vertex_groups.new(name=group)
            if weight:vg.add([i],weight,'REPLACE')
    mod=obj.modifiers.new('Skeleton','ARMATURE');mod.object=rig
    obj['export_layer']=layer;obj['art_part']=key
    return obj

def make_effect(p):
    # Independent procedural mesh effect. No character artwork is repainted.
    active=p['id'] in CLIP['effects']['frames']
    grip=solve(p)[0]['weapon'][0];x,z=grip.x,grip.z;rad=CLIP['effects']['radius']
    angle=p['sword_deg'];span=CLIP['effects'].get('span_deg',48)
    points=[]
    for i in range(17):
        a=math.radians(angle+span-i*(span+4)/16)
        width=CLIP['effects']['width']*math.sin(math.pi*i/16)**.7
        for r in (rad-width,rad):points.append((x+math.cos(a)*r,-.25,z+math.sin(a)*r))
    faces=[(i*2,i*2+1,i*2+3,i*2+2) for i in range(16)]
    mesh=bpy.data.meshes.new('SlashArc');mesh.from_pydata(points,[],faces)
    obj=bpy.data.objects.new('FX_SlashArc',mesh);bpy.context.collection.objects.link(obj)
    mat=bpy.data.materials.get('FX_Amber')
    if mat is None:
        mat=bpy.data.materials.new('FX_Amber');mat.use_nodes=True
        nt=mat.node_tree;nt.nodes.clear();e=nt.nodes.new('ShaderNodeEmission')
        color=CLIP['effects']['color'];srgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        rgb=[c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in srgb]
        e.inputs[0].default_value=(*rgb,1);out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(e.outputs[0],out.inputs[0])
    mesh.materials.append(mat);obj['export_layer']='fx';obj.hide_render=not active
    return obj,active

def main():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.eevee.taa_render_samples=1
    scene.render.resolution_x=W;scene.render.resolution_y=H;scene.render.resolution_percentage=100
    scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.render.fps=200
    image=bpy.data.images.load(str((BASE/'config'/CHAR['atlas']).resolve()));image.pack();mat=material(image)
    sources={CHAR['atlas']:(mat,image)}
    def source(key):
        path=CHAR['parts'][key].get('atlas',CHAR['atlas'])
        if path not in sources:
            im=bpy.data.images.load(str((BASE/'config'/path).resolve()));im.pack();sources[path]=(material(im),im)
        return sources[path]
    arm=bpy.data.armatures.new('HeroSkeleton');rig=bpy.data.objects.new('HeroRig',arm);scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);rig.show_in_front=True
    rest,_=solve(CLIP['frames'][0]);bpy.ops.object.mode_set(mode='EDIT')
    for name,parent in PARENTS.items():
        eb=arm.edit_bones.new(name);eb.head=rest[name][0];eb.tail=rest[name][1];eb.align_roll(Vector((0,-1,0)))
        if parent:eb.parent=arm.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    bindings=[('coat_l','coat_tail','coat_l',.19,None),('coat_r','coat_tail','coat_r',.06,None),
              ('scarf','scarf','scarf_a',.24,'scarf'),('upper_l','upper_l','upper_l',.13,'shoulder'),
              ('fore_l','fore_l','fore_l',.12,None),('thigh_l','thigh_l','thigh_l',.16,None),
              ('shin_l','shin_l','shin_l',.15,'foot'),('thigh_r','thigh_r','thigh_r',.08,None),
              ('shin_r','shin_r','shin_r',.07,'foot'),('pelvis','pelvis','pelvis',.04,None),
              ('torso','torso','spine',0,None),('head','head','head',-.03,None),
              ('collar','collar','collar',-.04,None),('memory','memory','memory',-.06,None),
              ('upper_r','upper_r','upper_r',-.08,'shoulder'),('fore_r','fore_r','fore_r',-.12,'elbow'),
              ('hand_r','hand_r','hand_r',-.13,None)]
    for name,key,bone,depth,deform in bindings:
        source_mat,source_image=source(key)
        part('Body_'+name,key,bone,depth,rig,rest,source_mat,source_image,layer='hands' if name in ('fore_r','hand_r') else 'body',deform=deform)
    source_mat,source_image=source(GEAR['part'])
    part('Equipment_Sword',GEAR['part'],'weapon',-.10,rig,rest,source_mat,source_image,'weapon')
    cam_data=bpy.data.cameras.new('PixelCamera');cam=bpy.data.objects.new('PixelCamera',cam_data);scene.collection.objects.link(cam)
    cam.location=((W/2-ROOT_X)/PPU,-15,(ROOT_Y-H/2)/PPU);cam.rotation_euler=(math.pi/2,0,0)
    cam_data.type='ORTHO';cam_data.ortho_scale=W/PPU;scene.camera=cam
    # Editable reference sheet in the viewport; it does not render into animation frames.
    ref=bpy.data.objects.new('Reference_Atlas',None);scene.collection.objects.link(ref);ref.empty_display_type='IMAGE';ref.data=image
    ref.location=(-5,1,2);ref.rotation_euler=(math.pi/2,0,0);ref.empty_display_size=4;ref.hide_render=True
    idle=[]
    for i,bob in enumerate([0,.018,0,-.010],1):
        p=dict(CLIP['frames'][0]);p.update(id=i,duration_ms=180,event='');p['pelvis']=[0,2.12+bob]
        p['hand_r']=[.51,2.76+bob];p['scarf_deg']=-8+[0,1,0,-1][i-1];idle.append(p)
    rig.animation_data_create();manifest={'canvas':[W,H],'root_px':[ROOT_X,ROOT_Y],'layers':['body','weapon','hands','fx'],'clips':{}}
    actions={};timeline={}
    for clip_name,poses in [('slash',CLIP['frames']),('idle',idle)]:
        action=bpy.data.actions.new('Hero_'+clip_name);action.use_fake_user=True;rig.animation_data.action=action;actions[clip_name]=action
        tick=1;times=[]
        for p in poses:
            bones,clamp=solve(p);times.append(tick)
            scene.frame_set(tick)
            for name in PARENTS:
                pb=rig.pose.bones[name];pb.rotation_mode='QUATERNION';pb.matrix=bone_matrix(*bones[name]);bpy.context.view_layer.update()
                pb.keyframe_insert('location',frame=tick,group=name);pb.keyframe_insert('rotation_quaternion',frame=tick,group=name);pb.keyframe_insert('scale',frame=tick,group=name)
            CHECKS.append({'clip':clip_name,'frame':p['id'],'hand_clamped_units':round(clamp,6),'grip_error_units':round((bones['weapon'][0]-bones[GEAR['socket']][GEAR.get('socket_end',0)]).length,8),
                           'ankles':[[round(c,6) for c in bones['foot_'+s][0]] for s in ('l','r')]})
            tick+=p['duration_ms']//5
        # Blender 5 stores curves in action slots; keep the pose holds used by the PNG sequence.
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='CONSTANT'
        timeline[clip_name]=(times,tick-1)
        manifest['clips'][clip_name]={'loop':clip_name=='idle','next':'idle','frames':[]}
        selected=range(len(poses)) if '--preview' not in sys.argv else ([0,3,6,8] if clip_name=='slash' else [])
        for idx in selected:
            p=poses[idx];scene.frame_set(times[idx]);bpy.context.view_layer.update()
            wanted,_=solve(p)
            entry=next(c for c in CHECKS if c['clip']==clip_name and c['frame']==p['id'])
            entry['evaluated_pose_error_units']=round(max((rig.pose.bones[n].head-wanted[n][0]).length for n in PARENTS),8)
            socket=rig.pose.bones[GEAR['socket']]
            socket_position=socket.tail if GEAR.get('socket_end',0)==1 else socket.head
            entry['evaluated_grip_error_units']=round((rig.pose.bones['weapon'].head-socket_position).length,8)
            assert entry['evaluated_pose_error_units'] < .0001, entry
            assert entry['evaluated_grip_error_units'] < .0001, entry
            fx,active=make_effect(p) if clip_name=='slash' else (None,False)
            objects=[o for o in scene.objects if o.type=='MESH'];paths={}
            for export in ['composite','body','weapon','hands','fx']:
                if '--preview' in sys.argv and export!='composite':continue
                for obj in objects:
                    obj.hide_render=(export!='composite' and obj['export_layer']!=export) or (obj==fx and not active)
                dest=OUT/clip_name/export;dest.mkdir(parents=True,exist_ok=True)
                scene.render.filepath=str(dest/f'{idx+1:02d}.png');bpy.ops.render.render(write_still=True)
                paths[export]=str(Path(clip_name)/export/f'{idx+1:02d}.png')
            manifest['clips'][clip_name]['frames'].append({'id':idx+1,'duration_ms':p['duration_ms'],'paths':paths,'event':p['event']})
            if fx:bpy.data.objects.remove(fx,do_unlink=True)
    for obj in scene.objects:
        if obj.type=='MESH':obj.hide_render=False
    rig.animation_data.action=actions['slash'];scene.frame_start=1;scene.frame_end=timeline['slash'][1];scene.frame_set(1)
    for i,tick in enumerate(timeline['slash'][0],1):scene.timeline_markers.new(f'Slash_{i:02d}',frame=tick)
    rig['pipeline']='2.5D textured mesh + armature; PNG holds at 5 ms ticks'
    rig['appearance_config']='../config/character.json';rig['motion_config']='../config/slash.json'
    # Save all effects as individually keyed objects so the .blend timeline includes them too.
    for i,p in enumerate(CLIP['frames']):
        if p['id'] not in CLIP['effects']['frames']:continue
        fx,_=make_effect(p);fx.name=f'FX_Slash_{p["id"]:02d}'
        start=timeline['slash'][0][i];end=start+p['duration_ms']//5
        for tick,hidden in [(0,True),(start,False),(end,True)]:
            fx.hide_render=hidden;fx.hide_viewport=hidden;fx.keyframe_insert('hide_render',frame=tick);fx.keyframe_insert('hide_viewport',frame=tick)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(BASE/'blender/2026-09-26-主角横斩骨架.blend'))
    (BASE/'preview/rig_checks.json').write_text(json.dumps(CHECKS,indent=2))
    if '--preview' not in sys.argv:(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('EXPORT COMPLETE',BASE)

if __name__=='__main__':main()

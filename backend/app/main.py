from __future__ import annotations
import os, shutil, subprocess, uuid, zipfile
from pathlib import Path
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import APP_NAME, ROOT_DIR, DATA_DIR, CHARACTERS_DIR, MODELS_DIR
from .models import ProjectCreate, Project, Character, Scene, ScenePatch, ReorderRequest, VoiceSettings
from .storage import init_db,create_project,save_project,load_project,list_projects,save_character,list_characters,load_character,ensure_default_characters
from .services.story_parser import read_story_file,split_bilingual,parse_script_blocks,assign_blocks_to_scenes
from .services.acting import build_acting_plan
from .services.hardware import system_status,mode_recommendations
from .services.media import render_scene,render_story,build_scene_audio
from .services.queue import render_queue
from .engines.tts import generate_voice,chatterbox_available
from .engines.comfyui import ComfyUIAdapter

app=FastAPI(title=APP_NAME,version='0.1.0');app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
init_db();ensure_default_characters();app.mount('/media',StaticFiles(directory=str(DATA_DIR)),name='media')
MOTIONITY_DIR=DATA_DIR/'tools'/'motionity'/'src'
if MOTIONITY_DIR.exists():
    app.mount('/motionity',StaticFiles(directory=str(MOTIONITY_DIR),html=True),name='motionity')

def _url(path):
    if not path:return None
    try:return '/media/'+Path(path).resolve().relative_to(DATA_DIR.resolve()).as_posix()
    except:return None

def public(p:Project):
    d=p.model_dump();d['thumbnail_url']=_url(p.thumbnail);lang=p.settings.language if p.settings.language in {'en','pt-br'} else 'en'
    for s in d['scenes']:
        s['source_image_url']=_url(s['source_image']);s['preview_url']=_url((s.get('preview_paths')or{}).get(lang)or s.get('preview_path'));s['render_url']=_url((s.get('render_paths')or{}).get(lang)or s.get('render_path'))
    return d

@app.get('/api/health')
def health():return {'ok':True,'app':APP_NAME}
@app.get('/api/system')
def system():
    s=system_status();s.update({'backend':'Ready','comfyui':'Ready' if ComfyUIAdapter().availability().get('available') else 'Not Installed / Not Running','chatterbox':'Ready' if chatterbox_available() else 'Not Installed','motionity':'Ready' if MOTIONITY_DIR.exists() else 'Not Installed','models_folder':str(MODELS_DIR),'modes':mode_recommendations(s)});return s
@app.get('/api/tools/motionity')
def motionity_status():
    return {'installed':MOTIONITY_DIR.exists(),'path':str(MOTIONITY_DIR)}

@app.post('/api/projects/{pid}/scenes/{sid}/motionity-context')
def motionity_context(pid:str,sid:str,language:str='en'):
    if not MOTIONITY_DIR.exists():
        raise HTTPException(409,'Motionity is not installed. Run INSTALL-MOTIONITY.bat, then restart Clay Studio.')
    p=load_project(pid)
    s=next((x for x in p.scenes if x.id==sid),None)
    if not s: raise HTTPException(404,'Scene not found')
    if language not in {'en','pt-br'}: language='en'
    s.blocks=s.blocks_by_language.get(language,s.blocks)
    audio,cues,duration=build_scene_audio(p,s,language)
    return {
        'motionity_url':'/motionity/index.html',
        'image_url':_url(s.source_image),
        'audio_url':_url(str(audio)),
        'width':p.settings.width,
        'height':p.settings.height,
        'fps':p.settings.fps,
        'duration':duration,
        'scene_number':s.number,
        'scene_name':s.name,
        'acting_plan':[b.model_dump() for b in s.acting_plan],
    }

@app.get('/api/projects')
def projects():return [public(p) for p in list_projects()]
@app.post('/api/projects')
def new_project(data:ProjectCreate):return public(create_project(data))
@app.get('/api/projects/{pid}')
def get_project(pid:str):return public(load_project(pid))
@app.put('/api/projects/{pid}')
def put_project(pid:str,payload:dict=Body(...)):
    old=load_project(pid);payload['id']=old.id;payload['folder']=old.folder;payload['created_at']=old.created_at;p=Project.model_validate(payload);save_project(p);return public(p)

@app.post('/api/projects/{pid}/import-story')
async def import_story(pid:str,file:UploadFile|None=File(None),text:str|None=Form(None)):
    p=load_project(pid);raw=text or ''
    if file:
        target=Path(p.folder)/'story'/(file.filename or 'story.txt');target.write_bytes(await file.read());raw=read_story_file(target)
    if not raw.strip():raise HTTPException(400,'No story text was provided')
    p.story=split_bilingual(raw);names=[c.name for c in list_characters() if c.id!='narrator'];p.script_blocks_en=parse_script_blocks(p.story.english,names);p.script_blocks_pt=parse_script_blocks(p.story.portuguese,names);_assign(p);save_project(p);return public(p)

def _assign(p:Project):
    if not p.scenes:return
    en=assign_blocks_to_scenes(p.script_blocks_en,len(p.scenes));pt=assign_blocks_to_scenes(p.script_blocks_pt,len(p.scenes));lang=p.settings.language if p.settings.language in {'en','pt-br'} else 'en'
    names=[c.name for c in list_characters() if c.id!='narrator']
    for i,s in enumerate(sorted(p.scenes,key=lambda x:x.number)):
        s.blocks_by_language['en']=en[i] if i<len(en) else []
        s.blocks_by_language['pt-br']=pt[i] if i<len(pt) else []
        s.blocks=s.blocks_by_language.get(lang,[])
        s.acting_plan=build_acting_plan(s.blocks,names)
        if s.acting_plan:
            s.characters_visible=sorted({b.character for b in s.acting_plan if b.character})

@app.post('/api/projects/{pid}/scenes')
async def add_scenes(pid:str,files:list[UploadFile]=File(...)):
    p=load_project(pid);folder=Path(p.folder)/'images';folder.mkdir(parents=True,exist_ok=True)
    for f in files:
        ext=Path(f.filename or '.png').suffix.lower()
        if ext not in {'.png','.jpg','.jpeg','.webp','.bmp'}:continue
        sid=uuid.uuid4().hex[:12];target=folder/f'{len(p.scenes)+1:03}-{sid}{ext}';target.write_bytes(await f.read());p.scenes.append(Scene(id=sid,number=len(p.scenes)+1,name=f'Scene {len(p.scenes)+1:02}',source_image=str(target)))
    if p.scenes and not p.thumbnail:p.thumbnail=p.scenes[0].source_image
    _assign(p);save_project(p);return public(p)
@app.post('/api/projects/{pid}/scenes/{sid}/replace-image')
async def replace_scene_image(pid:str,sid:str,file:UploadFile=File(...)):
    p=load_project(pid);s=next((x for x in p.scenes if x.id==sid),None)
    if not s:raise HTTPException(404,'Scene not found')
    ext=Path(file.filename or '').suffix.lower()
    if ext not in {'.png','.jpg','.jpeg','.webp','.bmp'}:raise HTTPException(400,'Please choose a PNG, JPG, JPEG, WEBP, or BMP image.')
    folder=Path(p.folder)/'images';folder.mkdir(parents=True,exist_ok=True)
    old_source=Path(s.source_image)
    target=folder/f'{s.number:03}-{s.id}-replacement-{uuid.uuid4().hex[:8]}{ext}'
    target.write_bytes(await file.read())
    # Remove only generated media for this scene. Story text, speakers, acting plan,
    # scene order and all other scene metadata remain intact.
    generated=set()
    if s.preview_path:generated.add(s.preview_path)
    if s.render_path:generated.add(s.render_path)
    generated.update((s.preview_paths or {}).values())
    generated.update((s.render_paths or {}).values())
    for value in generated:
        try:
            path=Path(value)
            if path.exists():path.unlink()
        except Exception:
            pass
    s.source_image=str(target)
    s.preview_path=None;s.preview_signature=None;s.preview_paths={};s.preview_signatures={}
    s.render_path=None;s.render_signature=None;s.render_paths={};s.render_signatures={}
    s.render_status='pending';s.error=None
    if p.thumbnail and Path(p.thumbnail)==old_source:p.thumbnail=str(target)
    save_project(p)
    # Delete the old scene source only after the new project state has been saved.
    try:
        if old_source.exists() and old_source.parent.resolve()==folder.resolve():old_source.unlink()
    except Exception:
        pass
    return public(p)

@app.patch('/api/projects/{pid}/scenes/{sid}')
def patch_scene(pid:str,sid:str,patch:ScenePatch):
    p=load_project(pid);s=next((x for x in p.scenes if x.id==sid),None)
    if not s:raise HTTPException(404,'Scene not found')
    for k,v in patch.model_dump(exclude_none=True).items():setattr(s,k,v)
    lang=p.settings.language if p.settings.language in {'en','pt-br'} else 'en';s.blocks_by_language[lang]=s.blocks;save_project(p);return public(p)
@app.post('/api/projects/{pid}/scenes/{sid}/character-reference')
def scene_character_reference(pid:str,sid:str,payload:dict=Body(...)):
    p=load_project(pid)
    s=next((x for x in p.scenes if x.id==sid),None)
    if not s: raise HTTPException(404,'Scene not found')
    cid=str(payload.get('character_id') or '').strip()
    if not cid: raise HTTPException(400,'character_id is required')
    try: character=load_character(cid)
    except Exception: raise HTTPException(404,'Character not found')
    try:
        x=float(payload.get('x')); y=float(payload.get('y')); size=float(payload.get('size',0.22))
    except Exception:
        raise HTTPException(400,'x, y and size must be numbers')
    x=max(0.0,min(1.0,x)); y=max(0.0,min(1.0,y)); size=max(0.08,min(0.65,size))
    source=Path(s.source_image)
    if not source.exists(): raise HTTPException(404,'Scene image file is missing')
    with Image.open(source) as im:
        im=im.convert('RGB'); w,h=im.size
        side=max(64,int(min(w,h)*size))
        cx=int(x*w); cy=int(y*h)
        left=max(0,min(w-side,cx-side//2)); top=max(0,min(h-side,cy-side//2))
        crop=im.crop((left,top,min(w,left+side),min(h,top+side)))
        folder=CHARACTERS_DIR/cid/'references'; folder.mkdir(parents=True,exist_ok=True)
        target=folder/f'scene-{sid}-{uuid.uuid4().hex[:6]}.png'
        crop.save(target,'PNG')
    character.reference_images.append(str(target))
    character.main_portrait=character.main_portrait or str(target)
    save_character(character)
    return {'ok':True,'character':character.model_dump(),'reference_url':_url(str(target))}

@app.post('/api/projects/{pid}/scenes/reorder')
def reorder(pid:str,data:ReorderRequest):
    p=load_project(pid);m={s.id:s for s in p.scenes}
    if set(data.scene_ids)!=set(m):raise HTTPException(400,'scene_ids must contain every scene exactly once')
    p.scenes=[m[x] for x in data.scene_ids]
    for i,s in enumerate(p.scenes,1):s.number=i
    save_project(p);return public(p)
@app.post('/api/projects/{pid}/language/{lang}')
def language(pid:str,lang:str):
    if lang not in {'en','pt-br'}:raise HTTPException(400,'Language must be en or pt-br')
    p=load_project(pid);old=p.settings.language if p.settings.language in {'en','pt-br'} else 'en'
    names=[c.name for c in list_characters() if c.id!='narrator']
    for s in p.scenes:
        s.blocks_by_language[old]=s.blocks
        s.blocks=s.blocks_by_language.get(lang,[])
        s.acting_plan=build_acting_plan(s.blocks,names)
    p.settings.language=lang;save_project(p);return public(p)

@app.get('/api/characters')
def characters():return [c.model_dump() for c in list_characters()]
@app.post('/api/characters')
def create_character(c:Character):return save_character(c)
@app.put('/api/characters/{cid}')
def update_character(cid:str,c:Character):c.id=cid;return save_character(c)
@app.post('/api/characters/{cid}/references')
async def refs(cid:str,files:list[UploadFile]=File(...)):
    c=load_character(cid);folder=CHARACTERS_DIR/cid/'references';folder.mkdir(parents=True,exist_ok=True)
    for f in files:
        t=folder/(f.filename or f'{uuid.uuid4().hex[:6]}.png');t.write_bytes(await f.read());c.reference_images.append(str(t));c.main_portrait=c.main_portrait or str(t)
    save_character(c);return c
@app.post('/api/characters/{cid}/voice-reference')
async def voice_ref(cid:str,language:str=Form(...),file:UploadFile=File(...)):
    c=load_character(cid);folder=CHARACTERS_DIR/cid/'voices';folder.mkdir(parents=True,exist_ok=True);t=folder/f'{language}-{Path(file.filename or "reference.wav").name}';t.write_bytes(await file.read());(setattr(c.voice_pt_br,'reference_audio',str(t)) if language=='pt-br' else setattr(c.voice_en,'reference_audio',str(t)));save_character(c);return c
@app.post('/api/characters/{cid}/voice-preview')
def voice_preview(cid:str,payload:dict=Body(...)):
    c=load_character(cid);lang=payload.get('language','en');settings=c.voice_pt_br if lang=='pt-br' else c.voice_en;settings=VoiceSettings.model_validate({**settings.model_dump(),**payload.get('settings',{})});target=CHARACTERS_DIR/cid/'voices'/f'preview-{lang}.wav';generate_voice(payload.get('text','Hello'),target,lang,settings);return {'url':_url(str(target))}

@app.post('/api/projects/{pid}/confirm-speakers')
def confirm_speakers(pid:str, language:str='en'):
    p=load_project(pid)
    missing=[]
    for s in p.scenes:
        blocks=s.blocks_by_language.get(language,s.blocks)
        changed=False
        for b in blocks:
            if b.type!='dialogue':
                continue
            if b.speaker and str(b.speaker).strip():
                b.needs_review=False
                b.speaker_confidence=1.0
                changed=True
            else:
                missing.append({'scene':s.number,'block_id':b.id,'text':b.text})
        if changed:
            s.blocks_by_language[language]=blocks
            if p.settings.language==language:
                s.blocks=blocks
    save_project(p)
    return {'ok':len(missing)==0,'missing':missing,'project':public(p)}

@app.get('/api/queue')
def queue():return [j.model_dump() for j in render_queue.list()]
@app.post('/api/queue/pause')
def pause():render_queue.pause();return {'ok':True}
@app.post('/api/queue/resume')
def resume():render_queue.resume();return {'ok':True}
@app.post('/api/queue/{jid}/cancel')
def cancel(jid:str):render_queue.cancel(jid);return {'ok':True}

def _review(blocks):return [b for b in blocks if b.type=='dialogue' and (b.needs_review or not b.speaker)]
@app.post('/api/projects/{pid}/scenes/{sid}/preview')
def preview(pid:str,sid:str,language:str='en'):
    def run(progress):
        p=load_project(pid);s=next(x for x in p.scenes if x.id==sid);path=render_scene(p,s,language,True,progress);save_project(p);return path
    return render_queue.add(pid,'preview_scene',run,sid,metadata={'language':language}).model_dump()
@app.post('/api/projects/{pid}/scenes/{sid}/render')
def render_one(pid:str,sid:str,language:str='en'):
    p=load_project(pid);s=next(x for x in p.scenes if x.id==sid)
    if _review(s.blocks_by_language.get(language,s.blocks)):raise HTTPException(409,'This scene has speakers that still need review.')
    def run(progress):
        p=load_project(pid);s=next(x for x in p.scenes if x.id==sid);path=render_scene(p,s,language,False,progress);save_project(p);return path
    return render_queue.add(pid,'render_scene',run,sid,metadata={'language':language}).model_dump()
@app.post('/api/projects/{pid}/render-story')
def render_full(pid:str,language:str='en'):
    p=load_project(pid)
    blocks=[b for s in p.scenes for b in s.blocks_by_language.get(language,s.blocks)]
    spoken=[b for b in blocks if b.type in {'dialogue','narrator'} and b.text.strip()]
    if not spoken:
        raise HTTPException(409,'No narration/dialogue is assigned to the scenes. Import the story text first so audio can be generated.')
    if any(_review(s.blocks_by_language.get(language,s.blocks)) for s in p.scenes):raise HTTPException(409,'Speaker review is required before final rendering.')
    def run(progress):
        p=load_project(pid);path=render_story(p,language,progress);save_project(p);return path
    return render_queue.add(pid,'render_story',run,metadata={'language':language}).model_dump()
@app.get('/api/workflows')
def workflows():return ComfyUIAdapter().list_workflows()
@app.get('/api/models')
def models():return [{'id':'chatterbox','name':'Chatterbox','installed':chatterbox_available()},{'id':'rhubarb','name':'Rhubarb','installed':bool(shutil.which('rhubarb'))},{'id':'comfyui','name':'ComfyUI','installed':(MODELS_DIR/'comfyui/main.py').exists()}]
@app.post('/api/projects/{pid}/open-folder')
def open_folder(pid:str):
    p=load_project(pid)
    if os.name=='nt':os.startfile(p.folder)
    return {'ok':True,'path':p.folder}

_dist=ROOT_DIR/'frontend'/'dist'
if _dist.exists():app.mount('/',StaticFiles(directory=str(_dist),html=True),name='frontend')

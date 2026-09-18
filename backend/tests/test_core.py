from __future__ import annotations
import time,uuid,wave
from pathlib import Path
from PIL import Image
from app.models import ProjectCreate, Character, VoiceSettings, Scene, ScriptBlock
from app.storage import init_db,create_project,load_project,save_project
from app.services.story_parser import split_bilingual,parse_script_blocks,assign_blocks_to_scenes
from app.services.subtitles import write_srt,write_vtt
from app.services.aspect import preset_dimensions,crop_box
from app.services.queue import RenderQueue
from app.services.media import render_clay_motion,render_scene,_silent_wav

def test_project_creation_and_autosave():
    init_db();p=create_project(ProjectCreate(title='Unit Test Story',story_number='99'));assert Path(p.folder,'project.json').exists();p.title='Changed';save_project(p);assert load_project(p.id).title=='Changed'

def test_bilingual_and_speaker_mapping():
    text='Story 1\nEnglish\nPip smiled. “Hello, Grace!”\nHeart Lesson\nBe kind.\nHistória 1\nPortuguês Brasileiro\nPip sorriu. “Olá, Grace!”\nLição para o Coração\nSeja gentil.'
    v=split_bilingual(text);assert 'Hello' in v.english and 'Olá' in v.portuguese
    blocks=parse_script_blocks(v.english,['Pip','Grace']);d=[b for b in blocks if b.type=='dialogue'][0];assert d.speaker=='Pip' and not d.needs_review

def test_uncertain_speaker_needs_review():
    b=parse_script_blocks('“Who is there?”',['Pip','Grace'])[0];assert b.type=='dialogue' and b.needs_review and b.speaker is None

def test_scene_distribution_order():
    blocks=parse_script_blocks('One.\nTwo.\nThree.\nFour.',['Pip']);parts=assign_blocks_to_scenes(blocks,2);assert sum(len(x) for x in parts)==len(blocks);assert parts[0][0].text=='One.'

def test_voice_configuration_bounds():
    v=VoiceSettings(speed=1.35,exaggeration=.7);assert v.speed==1.35

def test_subtitles_utf8(tmp_path:Path):
    cues=[(0,1.2,'Olá, Grace! Coração, ação, você.')];s=write_srt(cues,tmp_path/'x.srt');v=write_vtt(cues,tmp_path/'x.vtt');assert 'coração' in s.read_text(encoding='utf-8').lower();assert v.read_text(encoding='utf-8').startswith('WEBVTT')

def test_aspect_ratio_calculation():
    assert preset_dimensions('9:16')==(1080,1920);b=crop_box(1920,1080,1080,1920,(.5,.5));assert b[2]-b[0]==1080 and b[3]-b[1]==1920

def test_render_queue_failure_recovery():
    q=RenderQueue();j=q.add('p','render_story',lambda progress:(_ for _ in ()).throw(RuntimeError('boom')))
    for _ in range(50):
        if q.jobs[j.id].state=='failed':break
        time.sleep(.02)
    assert q.jobs[j.id].state=='failed' and 'boom' in (q.jobs[j.id].error or '')

def test_clay_motion_ffmpeg_smoke(tmp_path:Path):
    img=tmp_path/'img.png';Image.new('RGB',(320,180),(120,170,120)).save(img);audio=_silent_wav(tmp_path/'a.wav',.35)
    p=create_project(ProjectCreate(title='Render Smoke',width=320,height=180));p.settings.width=320;p.settings.height=180;p.settings.fps=8;p.settings.background_fill='crop'
    s=Scene(id='s1',number=1,name='Scene 1',source_image=str(img),duration=.35);target=tmp_path/'out.mp4';render_clay_motion(p,s,audio,[],target,preview=False);assert target.exists() and target.stat().st_size>500


def test_scene_render_cache_is_separate_by_language(tmp_path:Path):
    img=tmp_path/'bilingual.png';Image.new('RGB',(160,90),(80,110,150)).save(img)
    p=create_project(ProjectCreate(title='Bilingual Render Cache',width=160,height=90));p.settings.width=160;p.settings.height=90;p.settings.fps=5;p.settings.subtitle.enabled=False
    en=ScriptBlock(id='pen',type='pause',duration=.2,metadata={'seconds':.2},pause_after=0)
    pt=ScriptBlock(id='ppt',type='pause',duration=.3,metadata={'seconds':.3},pause_after=0)
    s=Scene(id='bi1',number=1,name='Bilingual',source_image=str(img),duration=.3,animation_mode='no-motion',blocks=[en],blocks_by_language={'en':[en],'pt-br':[pt]})
    p.scenes=[s]
    en_path=render_scene(p,s,'en',False);pt_path=render_scene(p,s,'pt-br',False)
    assert en_path.exists() and pt_path.exists() and en_path != pt_path
    assert s.render_paths['en']==str(en_path) and s.render_paths['pt-br']==str(pt_path)

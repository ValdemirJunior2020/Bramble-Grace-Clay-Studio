from __future__ import annotations
import sys
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.storage import init_db,ensure_default_characters,create_project,save_project,load_character,save_character,list_projects
from app.models import ProjectCreate,Scene,ScriptBlock,CharacterPlacement

def make_scene(path:Path,bg,bramble_x:int,grace_x:int):
    im=Image.new('RGB',(960,540),bg);d=ImageDraw.Draw(im)
    d.rectangle((0,390,960,540),fill=(105,139,83));d.ellipse((bramble_x-90,170,bramble_x+90,400),fill=(145,92,58),outline=(90,55,36),width=7);d.ellipse((bramble_x-58,205,bramble_x+58,310),fill=(183,125,79));d.ellipse((bramble_x-27,263,bramble_x+27,278),fill=(70,35,30))
    d.ellipse((grace_x-70,165,grace_x+70,350),fill=(230,184,139),outline=(119,86,67),width=6);d.ellipse((grace_x-50,185,grace_x+50,280),fill=(241,202,167));d.arc((grace_x-28,242,grace_x+28,268),0,180,fill=(90,45,45),width=5)
    d.text((28,28),'Bramble & Grace Clay Studio Demo',fill='white');im.save(path)

def main():
    init_db();ensure_default_characters()
    if any(p.title=='Clay Studio Demo' for p in list_projects()):print('Demo project already exists.');return
    p=create_project(ProjectCreate(title='Clay Studio Demo',story_number='00',english_title='A Tiny Hello',portuguese_title='Um Pequeno Olá',language='en',mode='bramble',width=960,height=540))
    imgdir=Path(p.folder)/'images';a=imgdir/'001-demo.png';b=imgdir/'002-demo.png';make_scene(a,(85,120,88),300,690);make_scene(b,(96,103,142),340,650)
    p.story.english='Bramble smiled. “Hello, Grace!”\nGrace smiled. “Hello, Bramble. What a beautiful day.”'
    p.story.portuguese='Bramble sorriu. “Olá, Grace!”\nGrace sorriu. “Olá, Bramble. Que dia bonito.”'
    p.script_blocks_en=[ScriptBlock(id='demo-en-1',type='dialogue',speaker='bramble',speaker_confidence=1,needs_review=False,text='Hello, Grace!'),ScriptBlock(id='demo-en-2',type='dialogue',speaker='grace',speaker_confidence=1,needs_review=False,text='Hello, Bramble. What a beautiful day.')]
    p.script_blocks_pt=[ScriptBlock(id='demo-pt-1',type='dialogue',speaker='bramble',speaker_confidence=1,needs_review=False,text='Olá, Grace!'),ScriptBlock(id='demo-pt-2',type='dialogue',speaker='grace',speaker_confidence=1,needs_review=False,text='Olá, Bramble. Que dia bonito.')]
    p.scenes=[Scene(id='demo-scene-1',number=1,name='Hello',source_image=str(a),duration=3.5,blocks=[p.script_blocks_en[0]],blocks_by_language={'en':[p.script_blocks_en[0]],'pt-br':[p.script_blocks_pt[0]]},characters_visible=['bramble','grace'],character_placements=[CharacterPlacement(character_id='bramble',visible=True,mouth_x=.31,mouth_y=.51,confirmed=True),CharacterPlacement(character_id='grace',visible=True,mouth_x=.72,mouth_y=.48,confirmed=True)]),Scene(id='demo-scene-2',number=2,name='Beautiful Day',source_image=str(b),duration=4.5,blocks=[p.script_blocks_en[1]],blocks_by_language={'en':[p.script_blocks_en[1]],'pt-br':[p.script_blocks_pt[1]]},characters_visible=['bramble','grace'],character_placements=[CharacterPlacement(character_id='bramble',visible=True,mouth_x=.35,mouth_y=.51,confirmed=True),CharacterPlacement(character_id='grace',visible=True,mouth_x=.68,mouth_y=.48,confirmed=True)])]
    p.thumbnail=str(a);p.settings.width=960;p.settings.height=540;p.settings.output_format='16:9';p.settings.subtitle.font_size=38
    for cid in ['bramble','grace']:
        c=load_character(cid);c.mouth.procedural_fallback=True;save_character(c)
    save_project(p);print('Demo project created:',p.folder)
if __name__=='__main__':main()

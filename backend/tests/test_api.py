from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health():assert client.get('/api/health').json()['ok'] is True
def test_project_api_create_and_reorder(tmp_path):
    p=client.post('/api/projects',json={'title':'API Story','language':'en','output_format':'16:9','width':1920,'height':1080,'mode':'bramble'}).json();assert p['title']=='API Story'

from pathlib import Path
from PIL import Image
from app.storage import load_project, save_project
from app.models import Scene, ScriptBlock


def test_language_switch_preserves_scene_speakers(tmp_path: Path):
    created=client.post('/api/projects',json={'title':'Bilingual API','language':'en','output_format':'16:9','width':640,'height':360,'mode':'bramble'}).json()
    p=load_project(created['id'])
    img=Path(p.folder)/'images'/'one.png';Image.new('RGB',(64,36),(50,90,120)).save(img)
    en=ScriptBlock(id='en1',type='dialogue',text='Hello!',speaker='bramble',speaker_confidence=1,needs_review=False)
    pt=ScriptBlock(id='pt1',type='dialogue',text='Olá!',speaker='bramble',speaker_confidence=1,needs_review=False)
    p.scenes=[Scene(id='s1',number=1,name='One',source_image=str(img),blocks=[en],blocks_by_language={'en':[en],'pt-br':[pt]})]
    save_project(p)
    switched=client.post(f"/api/projects/{p.id}/language/pt-br").json()
    assert switched['settings']['language']=='pt-br'
    assert switched['scenes'][0]['blocks'][0]['text']=='Olá!'
    back=client.post(f"/api/projects/{p.id}/language/en").json()
    assert back['scenes'][0]['blocks'][0]['text']=='Hello!'


def test_scene_reorder_endpoint():
    created=client.post('/api/projects',json={'title':'Reorder API','language':'en','output_format':'16:9','width':640,'height':360,'mode':'bramble'}).json()
    p=load_project(created['id']); folder=Path(p.folder)/'images'
    a=folder/'a.png';b=folder/'b.png';Image.new('RGB',(32,18)).save(a);Image.new('RGB',(32,18)).save(b)
    p.scenes=[Scene(id='a',number=1,name='A',source_image=str(a)),Scene(id='b',number=2,name='B',source_image=str(b))];save_project(p)
    out=client.post(f"/api/projects/{p.id}/scenes/reorder",json={'scene_ids':['b','a']}).json()
    assert [x['id'] for x in out['scenes']]==['b','a']
    assert [x['number'] for x in out['scenes']]==[1,2]

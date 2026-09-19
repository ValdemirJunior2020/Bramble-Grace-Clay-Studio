import {useEffect,useState} from 'react';import {api,media} from './lib/api';import type{Project,Character,Scene}from'./types';

type Page='projects'|'editor'|'characters'|'system';
const empty={title:'',story_number:'',english_title:'',portuguese_title:'',language:'en',output_format:'16:9',width:1920,height:1080,mode:'bramble'};
export default function App(){
 const[page,setPage]=useState<Page>('projects'),[projects,setProjects]=useState<Project[]>([]),[project,setProject]=useState<Project|null>(null),[chars,setChars]=useState<Character[]>([]),[system,setSystem]=useState<any>(null),[queue,setQueue]=useState<any[]>([]),[form,setForm]=useState<any>(empty),[showNew,setShowNew]=useState(false),[msg,setMsg]=useState('');
 const load=async()=>{setProjects(await api('/api/projects'));setChars(await api('/api/characters'));};
 useEffect(()=>{load();const t=setInterval(async()=>{try{setQueue(await api('/api/queue'))}catch{}},1200);return()=>clearInterval(t)},[]);
 const open=async(id:string)=>{setProject(await api(`/api/projects/${id}`));setPage('editor')};
 const save=async(p=project)=>{if(!p)return;setProject(await api(`/api/projects/${p.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}));};
 const create=async()=>{const p=await api<Project>('/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(form)});setShowNew(false);setProject(p);setPage('editor');load()};
 const switchLang=async(lang:string)=>{if(!project)return;setProject(await api(`/api/projects/${project.id}/language/${lang}`,{method:'POST'}));};
 const importStory=async(file?:File,text?:string)=>{if(!project)return null;const fd=new FormData();if(file)fd.append('file',file);if(text)fd.append('text',text);const updated=await api<Project>(`/api/projects/${project.id}/import-story`,{method:'POST',body:fd});setProject(updated);return updated;};
 const addImages=async(fs:FileList|null)=>{if(!project||!fs)return;const fd=new FormData();Array.from(fs).forEach(f=>fd.append('files',f));setProject(await api(`/api/projects/${project.id}/scenes`,{method:'POST',body:fd}));};
 const patchScene=async(s:Scene,patch:any)=>{if(!project)return;setProject(await api(`/api/projects/${project.id}/scenes/${s.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)}));};
 const move=async(s:Scene,dir:number)=>{if(!project)return;const a=[...project.scenes],i=a.findIndex(x=>x.id===s.id),j=Math.max(0,Math.min(a.length-1,i+dir));[a[i],a[j]]=[a[j],a[i]];setProject(await api(`/api/projects/${project.id}/scenes/reorder`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scene_ids:a.map(x=>x.id)})}));};
 const render=async(kind:'preview'|'render-story',s?:Scene)=>{if(!project)return;try{setMsg('Queued');const lang=project.settings.language==='pt-br'?'pt-br':'en';await api(kind==='preview'?`/api/projects/${project.id}/scenes/${s!.id}/preview?language=${lang}`:`/api/projects/${project.id}/render-story?language=${lang}`,{method:'POST'})}catch(e:any){setMsg(e.message)}};
 return <div className="app"><aside className="sidebar"><div className="brand">Bramble & Grace<small>Clay Studio • Local</small></div><div className="nav">{(['projects','characters','system'] as Page[]).map(x=><button key={x} className={page===x?'active':''} onClick={async()=>{setPage(x);if(x==='system')setSystem(await api('/api/system'))}}>{x==='projects'?'Projects':x==='characters'?'Characters & Voices':'System Status'}</button>)}{project&&<button className={page==='editor'?'active':''} onClick={()=>setPage('editor')}>Current Story</button>}</div></aside><main className="content">
 {page==='projects'&&<><div className="hero"><h1>Local clay story videos</h1><p>One story at a time. Upload as many scene images as you need.</p><button className="btn primary" onClick={()=>setShowNew(true)}>New Story Project</button></div><div className="grid">{projects.map(p=><div key={p.id} className="card" onClick={()=>open(p.id)}><h3>{p.title}</h3><div className="muted">Story {p.story_number||'—'} • {p.settings.language} • {p.scenes.length} scenes</div></div>)}</div></>}
 {page==='editor'&&project&&<Editor p={project} chars={chars} setP={setProject} save={save} importStory={importStory} addImages={addImages} patchScene={patchScene} move={move} switchLang={switchLang} render={render} setMsg={setMsg}/>} 
 {page==='characters'&&<Characters chars={chars} refresh={load}/>} 
 {page==='system'&&<System data={system}/>} 
 {msg&&<div className="pill warn">{msg}</div>}{queue.length>0&&<div className="queue"><b>Generation Queue</b>{queue.slice(0,4).map((j:any)=><div key={j.id} style={{marginTop:10}}><div><b>{j.kind}</b>: {j.stage}</div><div className="progress"><div style={{width:`${j.progress*100}%`}}/></div>{j.error&&<div style={{marginTop:8,padding:8,borderRadius:8,background:'#7f1d1d',fontSize:12,whiteSpace:'pre-wrap'}}><b>Details:</b> {j.error}<div style={{marginTop:4,opacity:.85}}>Full traceback: logs/render.log</div></div>}</div>)}</div>}
 {showNew&&<div className="modal"><div className="modalbox"><h2>New Story Project</h2><div className="modecards"><div className={'modecard '+(form.mode==='bramble'?'selected':'')} onClick={()=>setForm({...form,mode:'bramble'})}><b>Bramble & Grace</b><p>Saved characters, clay defaults, bilingual workflow.</p></div><div className={'modecard '+(form.mode==='general'?'selected':'')} onClick={()=>setForm({...form,mode:'general'})}><b>General Video</b><p>Any characters, images and story style.</p></div></div>{['title','story_number','english_title','portuguese_title'].map(k=><div className="field" key={k}><label>{k.replaceAll('_',' ')}</label><input value={form[k]} onChange={e=>setForm({...form,[k]:e.target.value})}/></div>)}<div className="toolbar"><button className="btn primary" onClick={create}>Create</button><button className="btn" onClick={()=>setShowNew(false)}>Cancel</button></div></div></div>}
 </main></div>
}
function Editor({p,chars,setP,save,importStory,addImages,patchScene,move,switchLang,render,setMsg}:any){
 const[text,setText]=useState('');
 const[busy,setBusy]=useState(false);
 const[showSpeakerReview,setShowSpeakerReview]=useState(false);
 const[workflows,setWorkflows]=useState<any[]>([]);
 useEffect(()=>{api('/api/workflows').then(setWorkflows).catch(()=>setWorkflows([]))},[]);
 const noScript=p.scenes.length>0&&p.scenes.every((s:Scene)=>s.blocks.length===0);
 const unresolved=p.scenes.flatMap((s:Scene)=>s.blocks.filter((b:any)=>b.type==='dialogue'&&(b.needs_review||!b.speaker)).map((b:any)=>({scene:s,block:b})));
 const missingSpeakerCount=unresolved.filter(({block}:any)=>!block.speaker).length;
 const confirmSelectedSpeakers=async()=>{
   const scenes=new Map<string,Scene>();
   unresolved.forEach(({scene}:any)=>scenes.set(scene.id,scene));
   for(const scene of scenes.values()){
     const blocks=scene.blocks.map((b:any)=>b.type==='dialogue'&&b.speaker?{...b,needs_review:false,speaker_confidence:1}:b);
     await patchScene(scene,{blocks});
   }
 };
 const renderFull=async()=>{
   if(busy)return;
   setBusy(true);
   try{
     let active=p;
     if(noScript){
       if(!text.trim()){
         setMsg('Paste/import the story text first. No narration or dialogue is assigned to the scenes yet.');
         return;
       }
       setMsg('Importing story and assigning script to scenes...');
       const updated=await importStory(undefined,text);
       if(updated)active=updated;
     }
     const lang=active.settings.language==='pt-br'?'pt-br':'en';
     const spoken=active.scenes.reduce((n:number,s:Scene)=>n+s.blocks.filter((b:any)=>['dialogue','narrator'].includes(b.type)&&b.text?.trim()).length,0);
     if(spoken===0){
       setMsg('No narration/dialogue was assigned after import. Check the story text before generating.');
       return;
     }
     const pending=active.scenes.flatMap((s:Scene)=>s.blocks.filter((b:any)=>b.type==='dialogue'&&(b.needs_review||!b.speaker)));
     const missing=pending.filter((b:any)=>!b.speaker);
     if(missing.length>0){
       setShowSpeakerReview(true);
       setMsg(`${missing.length} dialogue line(s) still need a speaker before the full movie can be generated.`);
       return;
     }
     if(pending.length>0){
       await confirmSelectedSpeakers();
       active=await api<Project>(`/api/projects/${active.id}`);
     }
     setMsg('Queuing full movie...');
     await api(`/api/projects/${active.id}/render-story?language=${lang}`,{method:'POST'});
     setMsg('Full movie queued.');
   }catch(e:any){
     setMsg(e?.message||'Could not queue the full movie.');
   }finally{
     setBusy(false);
   }
 };
 return <>{showSpeakerReview&&<div className="modal"><div className="modalbox">
   <h2>Speaker Review Required</h2>
   <p>Choose who is speaking for each dialogue line below. Any line that already shows a selected speaker is ready; only blank dropdowns will block the movie.</p>
   {unresolved.length===0?<div className="pill ok">All dialogue speakers are confirmed.</div>:unresolved.map(({scene,block}:any)=><div className="card" key={block.id} style={{marginBottom:10}}>
     <div className="muted">Scene {scene.number}</div>
     <p style={{margin:'8px 0 10px'}}><b>“{block.text}”</b></p>
     <div className="field"><label>Who is speaking?</label><select value={block.speaker||''} onChange={async e=>{
       const blocks=scene.blocks.map((x:any)=>x.id===block.id?{...x,speaker:e.target.value,needs_review:false,speaker_confidence:1}:x);
       await patchScene(scene,{blocks});
     }}>
       <option value="">Select speaker</option>
       <option value="Narrator">Narrator</option>
       {chars.filter((c:Character)=>c.id!=='narrator').map((c:Character)=><option key={c.id} value={c.name}>{c.name}</option>)}
     </select></div>
   </div>)}
   <div className="toolbar" style={{marginTop:16}}>
     <button className="btn" onClick={()=>setShowSpeakerReview(false)}>Close</button>
     <button className="btn primary" disabled={missingSpeakerCount>0} onClick={async()=>{await confirmSelectedSpeakers();setShowSpeakerReview(false);await renderFull()}}>Generate Full Movie</button>
   </div>
 </div></div>}<div className="toolbar"><button className="btn" onClick={()=>switchLang('en')}>English</button><button className="btn" onClick={()=>switchLang('pt-br')}>Português Brasileiro</button><button className="btn primary" disabled={busy} onClick={renderFull}>{busy?'Working...':'Generate Full Movie'}</button><button className="btn" onClick={()=>api(`/api/projects/${p.id}/open-folder`,{method:'POST'})}>Open Project Folder</button></div><h1>{p.title}</h1><div className="two"><div className="card"><h3>Story text</h3><textarea style={{width:'100%',minHeight:160}} value={text} onChange={e=>setText(e.target.value)} placeholder="Paste one story here..."/><div className="toolbar"><button className="btn primary" onClick={()=>importStory(undefined,text)}>Import pasted text</button><label className="btn">Import DOCX/TXT/MD<input hidden type="file" accept=".docx,.txt,.md" onChange={e=>e.target.files&&importStory(e.target.files[0])}/></label></div></div><div className="card"><h3>Output</h3>
<div className="card" style={{marginBottom:14,background:'#f7f8f5'}}>
  <h3 style={{marginTop:0}}>Video Settings</h3>
  <div className="field"><label>Video mode</label><select value={p.settings.video_mode||'clay'} onChange={e=>setP({...p,settings:{...p.settings,video_mode:e.target.value}})}>
    <option value="clay">Clay Animation — Balanced</option>
    <option value="cinematic">Cinematic — ComfyUI Image-to-Video</option>
  </select></div>
  <div className="field"><label>Render profile</label><select value={p.settings.render_profile||'balanced'} onChange={e=>setP({...p,settings:{...p.settings,render_profile:e.target.value}})}>
    <option value="balanced">Balanced — current AMD GPU</option>
    <option value="high">High Quality — future 5090 / stronger GPU</option>
  </select></div>
  {(p.settings.video_mode||'clay')==='cinematic'&&<>
    <div className="field"><label>Cinematic workflow</label><select value={p.settings.cinematic_workflow||''} onChange={e=>setP({...p,settings:{...p.settings,cinematic_workflow:e.target.value||null}})}>
      <option value="">Select installed ComfyUI video workflow</option>
      {workflows.map((w:any)=><option key={w.name||w.id||w.config_file} value={w.name||w.id}>{w.label||w.name||w.id}</option>)}
    </select></div>
    <div className="field"><label>Motion strength</label><input type="range" min={0} max={1} step={.05} value={p.settings.cinematic_motion_strength??.65} onChange={e=>setP({...p,settings:{...p.settings,cinematic_motion_strength:+e.target.value}})}/><b>{Math.round((p.settings.cinematic_motion_strength??.65)*100)}%</b></div>
    <div className="pill warn">{workflows.length? 'Cinematic will use the selected real ComfyUI workflow and your uploaded scene image as the source.' : 'No compatible ComfyUI video workflow is configured yet. Cinematic mode will not fake motion; install/select a real workflow first.'}</div>
  </>}
</div>
<div className="field"><label>Voice speed</label><input type="range" min={.5} max={2} step={.05} value={p.settings.voice_speed_global} onChange={e=>setP({...p,settings:{...p.settings,voice_speed_global:+e.target.value}})}/><b>{p.settings.voice_speed_global}x</b></div><div className="field"><label>Subtitle size</label><input type="number" value={p.settings.subtitle.font_size} onChange={e=>setP({...p,settings:{...p.settings,subtitle:{...p.settings.subtitle,font_size:+e.target.value}}})}/></div><div className="colorrow"><div className="field"><label>Subtitle color</label><input value={p.settings.subtitle.text_color} onChange={e=>setP({...p,settings:{...p.settings,subtitle:{...p.settings.subtitle,text_color:e.target.value}}})}/></div><input type="color" value={p.settings.subtitle.text_color} onChange={e=>setP({...p,settings:{...p.settings,subtitle:{...p.settings.subtitle,text_color:e.target.value}}})}/></div><button className="btn primary" onClick={()=>save(p)}>Save Settings</button></div></div>{noScript&&p.scenes.length>0&&<div className="pill warn" style={{marginBottom:12}}>No script/audio is assigned to these scenes yet. Paste/import the story before generating the movie.</div>}<div className="toolbar"><label className="btn primary">+ Add Scene Images<input hidden multiple type="file" accept="image/*" onChange={e=>addImages(e.target.files)}/></label></div>{p.scenes.map((s:Scene)=><div className="scene-row" key={s.id}><input className="bigcheck" type="checkbox"/><img src={media(s.source_image_url)}/><div><b>Scene {s.number}: {s.name}</b><div className="muted">{s.blocks.length} script blocks • {s.animation_mode}</div>{s.blocks.map((b:any)=><div className="speaker" key={b.id}><select value={b.speaker||''} onChange={e=>{const blocks=s.blocks.map((x:any)=>x.id===b.id?{...x,speaker:e.target.value,needs_review:false}:x);patchScene(s,{blocks})}}><option value="">Speaker needs review</option><option value="Narrator">Narrator</option>{chars.filter((c:Character)=>c.id!=='narrator').map((c:Character)=><option key={c.id} value={c.name}>{c.name}</option>)}</select><textarea value={b.text} readOnly/></div>)}</div><div><button className="btn" onClick={()=>move(s,-1)}>↑</button><button className="btn" onClick={()=>move(s,1)}>↓</button><button className="btn primary" onClick={()=>render('preview',s)}>Preview</button>{s.preview_url&&<video controls width="210" src={media(s.preview_url)}/>}</div></div>)}</>}
function Characters({chars,refresh}:any){
 const uploadFor=async(c:Character,files:FileList|null)=>{
   if(!files||files.length===0)return;
   const fd=new FormData();Array.from(files).forEach(f=>fd.append('files',f));
   await api(`/api/characters/${c.id}/references`,{method:'POST',body:fd});
   await refresh();
 };
 const bulkUpload=async(files:FileList|null)=>{
   if(!files)return;
   const unmatched:string[]=[];
   for(const file of Array.from(files)){
     const base=file.name.toLowerCase().replace(/\.[^.]+$/,'').replace(/[_-]+/g,' ');
     const match=chars.find((c:Character)=>{
       const name=c.name.toLowerCase();
       const id=c.id.toLowerCase().replace(/[_-]+/g,' ');
       return base===name||base===id||base.includes(name)||name.includes(base);
     });
     if(!match){unmatched.push(file.name);continue}
     const fd=new FormData();fd.append('files',file);
     await api(`/api/characters/${match.id}/references`,{method:'POST',body:fd});
   }
   await refresh();
   if(unmatched.length)alert('Could not match: '+unmatched.join(', ')+'\nRename them Grace, Bramble, Pip, Oliver, Barnaby, etc. and try again.');
 };
 return <><h1>Characters & Voices</h1>
   <div className="card" style={{marginBottom:16}}>
     <h3>Character Faces</h3>
     <p className="muted">Upload face/reference images named Grace, Bramble, Pip, Oliver, Barnaby, etc. The app will match them automatically by filename.</p>
     <label className="btn primary">Upload Character Faces
       <input hidden multiple type="file" accept="image/*" onChange={e=>bulkUpload(e.target.files)}/>
     </label>
   </div>
   <div className="grid">{chars.map((c:Character)=><div className="card" key={c.id}>
     <h3>{c.name}</h3><div className="muted">{c.species}</div>
     <div className="muted" style={{margin:'8px 0'}}>{c.reference_images?.length||0} face/reference image(s) saved</div>
     <label className="btn">Add {c.name} Face
       <input hidden multiple type="file" accept="image/*" onChange={e=>uploadFor(c,e.target.files)}/>
     </label>
     <div className="field" style={{marginTop:12}}><label>English speed</label><input type="number" step={.05} min={.5} max={2} value={c.voice_en.speed} onChange={async e=>{c.voice_en.speed=+e.target.value;await api(`/api/characters/${c.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)});refresh()}}/></div>
     <div className="field"><label>PT-BR speed</label><input type="number" step={.05} min={.5} max={2} value={c.voice_pt_br.speed} onChange={async e=>{c.voice_pt_br.speed=+e.target.value;await api(`/api/characters/${c.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)});refresh()}}/></div>
   </div>)}</div></>
}
function System({data}:any){if(!data)return <p>Open System Status again to refresh.</p>;return <><h1>System Status</h1><div className="card">{Object.entries(data).filter(([k])=>!['modes'].includes(k)).map(([k,v])=><div className="status" key={k}><span>{k}</span><strong>{typeof v==='object'?JSON.stringify(v):String(v??'Not Installed')}</strong></div>)}</div></>}

from __future__ import annotations
import hashlib, json, shutil, subprocess, tempfile, wave
from pathlib import Path
from typing import Callable
from PIL import Image, ImageDraw, ImageFont
from ..models import Project, Scene
from ..storage import load_character
from ..engines.tts import generate_voice
from .subtitles import write_srt, write_vtt

def require_ffmpeg()->str:
    exe=shutil.which('ffmpeg')
    if not exe: raise RuntimeError('FFmpeg is not installed.')
    return exe

def _silent_wav(path:Path,duration:float)->Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    rate=48000; frames=max(1,int(rate*max(.05,duration)))
    with wave.open(str(path),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes(b'\0\0\0\0'*frames)
    return path

def _duration(path:Path)->float:
    with wave.open(str(path),'rb') as w:return w.getnframes()/w.getframerate()

def _sig(project:Project,scene:Scene,lang:str,preview:bool)->str:
    payload={'img':scene.source_image,'blocks':[b.model_dump() for b in scene.blocks_by_language.get(lang,scene.blocks)],'lang':lang,'preview':preview,'w':project.settings.preview_width if preview else project.settings.width,'h':project.settings.preview_height if preview else project.settings.height,'fps':project.settings.preview_fps if preview else project.settings.fps,'subtitle':(scene.subtitle_override or project.settings.subtitle).model_dump(),'focus':scene.focus_points,'fill':project.settings.background_fill}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()

def build_scene_audio(project:Project,scene:Scene,lang:str,progress:Callable|None=None):
    ff=require_ffmpeg(); folder=Path(project.folder); blocks=scene.blocks_by_language.get(lang,scene.blocks); parts=[]; cues=[]; t=0.0
    for i,b in enumerate(blocks):
        if progress: progress(i/max(1,len(blocks)),'Generating Voice')
        out=folder/'audio'/lang/f'{scene.id}-{i:03}.wav'
        if b.type in {'dialogue','narrator'} and b.text.strip():
            speaker=b.speaker or 'Narrator'; cid=speaker.lower().replace(' ','-')
            try:c=load_character(cid)
            except Exception:c=load_character('narrator')
            settings=c.voice_pt_br if lang=='pt-br' else c.voice_en
            if not out.exists(): generate_voice(b.text,out,lang,settings,project.settings.voice_speed_global)
            dur=_duration(out); cues.append((t,t+dur,b.text)); t+=dur
        elif b.type=='pause':
            dur=float(b.duration or b.metadata.get('seconds',.5)); _silent_wav(out,dur); t+=dur
        else: continue
        parts.append(out); pause=float(b.pause_after or 0)
        if pause>0:
            p=folder/'audio'/lang/f'{scene.id}-{i:03}-pause.wav'; _silent_wav(p,pause); parts.append(p); t+=pause
    if not parts:
        out=folder/'audio'/lang/f'{scene.id}-silence.wav'; _silent_wav(out,max(.25,scene.duration)); parts=[out]; t=scene.duration
    joined=folder/'audio'/lang/f'{scene.id}.wav'; joined.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False,encoding='utf-8') as f:
        for p in parts:f.write("file '"+str(p).replace("'","'\\''")+"'\n")
        lst=f.name
    try: subprocess.run([ff,'-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',lst,'-c:a','pcm_s16le',str(joined)],check=True)
    finally: Path(lst).unlink(missing_ok=True)
    return joined,cues,max(t,.25)

def _fit_frame(image:Image.Image,w:int,h:int,mode:str,focus:tuple[float,float]):
    im=image.convert('RGB'); iw,ih=im.size
    if mode=='fit':
        scale=min(w/iw,h/ih); nw,nh=max(1,int(iw*scale)),max(1,int(ih*scale)); r=im.resize((nw,nh),Image.Resampling.LANCZOS); bg=Image.new('RGB',(w,h),(20,20,20));bg.paste(r,((w-nw)//2,(h-nh)//2));return bg
    scale=max(w/iw,h/ih); nw,nh=max(w,int(iw*scale)),max(h,int(ih*scale)); r=im.resize((nw,nh),Image.Resampling.LANCZOS); fx,fy=focus; x=max(0,min(nw-w,int(fx*nw-w/2)));y=max(0,min(nh-h,int(fy*nh-h/2)));return r.crop((x,y,x+w,y+h))

def render_clay_motion(project:Project,scene:Scene,audio:Path,timings:list,target:Path,preview:bool=False,progress:Callable|None=None,mouth_cues:list|None=None,subtitle_cues:list|None=None,subtitle_style=None)->Path:
    ff=require_ffmpeg(); w=project.settings.preview_width if preview else project.settings.width; h=project.settings.preview_height if preview else project.settings.height; fps=project.settings.preview_fps if preview else project.settings.fps; dur=_duration(audio); frames=max(1,int(dur*fps)); src=Image.open(scene.source_image);focus=scene.focus_points[0] if scene.focus_points else (.5,.5); target.parent.mkdir(parents=True,exist_ok=True)
    proc=subprocess.Popen([ff,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(fps),'-i','-','-i',str(audio),'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest',str(target)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(frames):
            phase=i/max(1,frames-1); zoom=1+0.035*phase if scene.camera_movement=='slow_push' else 1
            base=_fit_frame(src,max(2,int(w/zoom)),max(2,int(h/zoom)),project.settings.background_fill,focus).resize((w,h),Image.Resampling.LANCZOS)
            sec=i/fps
            if scene.blocks:
                active=None; cursor=0.0
                for b in scene.blocks:
                    d=float(b.duration or .9)
                    if cursor<=sec<cursor+d and b.type=='dialogue': active=b.speaker; break
                    cursor+=d+float(b.pause_after or 0)
                if active:
                    try:c=load_character(active.lower().replace(' ','-')); x=int(c.mouth.x*w);y=int(c.mouth.y*h);s=max(4,int(12*c.mouth.scale));d=ImageDraw.Draw(base);open_amt=3+int(4*((i//2)%2));d.ellipse((x-s,y-open_amt,x+s,y+open_amt),fill=(55,25,25))
                    except Exception: pass
            if subtitle_cues and subtitle_style and subtitle_style.enabled and subtitle_style.burn_in:
                current=next((text for start,end,text in subtitle_cues if start<=sec<end),None)
                if current:
                    draw=ImageDraw.Draw(base)
                    font_px=max(14,int(subtitle_style.font_size*(h/360)))
                    try: font=ImageFont.truetype("arial.ttf",font_px)
                    except Exception: font=ImageFont.load_default()
                    max_width=int(w*.84)
                    words=current.split()
                    lines=[]; line=""
                    for word in words:
                        test=(line+" "+word).strip()
                        box=draw.textbbox((0,0),test,font=font,stroke_width=max(1,int(subtitle_style.outline)))
                        if box[2]-box[0] > max_width and line:
                            lines.append(line); line=word
                        else:
                            line=test
                    if line: lines.append(line)
                    line_h=max(font_px+8,int(font_px*1.25))
                    total_h=line_h*len(lines)
                    y=max(10,h-int(subtitle_style.bottom_margin*(h/360))-total_h)
                    stroke=max(1,int(subtitle_style.outline))
                    for line in lines:
                        box=draw.textbbox((0,0),line,font=font,stroke_width=stroke)
                        tw=box[2]-box[0]
                        draw.text(((w-tw)//2,y),line,font=font,fill=subtitle_style.text_color,stroke_width=stroke,stroke_fill="black")
                        y+=line_h
            proc.stdin.write(base.tobytes())
            if progress and i%max(1,fps)==0:progress(i/frames,'Rendering')
        proc.stdin.close();rc=proc.wait(timeout=120)
        if rc: raise RuntimeError((proc.stderr.read() or b'').decode(errors='replace')[-1000:])
    except Exception:
        proc.kill();raise
    if progress:progress(1.0,'Rendering')
    return target

def render_static(project:Project,scene:Scene,audio:Path,target:Path,preview=False,progress=None):
    return render_clay_motion(project,scene,audio,[],target,preview,progress)

def _burn(video:Path,srt:Path,target:Path,style)->Path:
    ff=require_ffmpeg()
    size=style.font_size
    # Windows FFmpeg/libass can be fragile when a subtitles filter contains an
    # absolute drive-letter path (C:\\...). Run from the subtitle directory
    # and pass only the filename so the filter never has to parse a drive colon.
    subtitle_name=srt.name.replace("'","\\'")
    font=str(style.font).replace("'","")
    vf=f"subtitles=filename='{subtitle_name}':force_style='FontName={font},FontSize={size},Outline={style.outline},Shadow={style.shadow},MarginV={style.bottom_margin}'"
    cmd=[ff,'-y','-hide_banner','-loglevel','error','-i',str(video.resolve()),'-vf',vf,'-c:v','libx264','-crf','20','-c:a','copy',str(target.resolve())]
    result=subprocess.run(cmd,cwd=str(srt.parent),capture_output=True,text=True)
    if result.returncode!=0:
        details=(result.stderr or result.stdout or f'FFmpeg exited with code {result.returncode}').strip()
        raise RuntimeError(f'Subtitle burn-in failed: {details[-3000:]}')
    return target

def render_scene(project:Project,scene:Scene,language:str,preview:bool=False,progress:Callable|None=None)->Path:
    scene.blocks=scene.blocks_by_language.get(language,scene.blocks); sig=_sig(project,scene,language,preview); paths=scene.preview_paths if preview else scene.render_paths; sigs=scene.preview_signatures if preview else scene.render_signatures
    if paths.get(language) and sigs.get(language)==sig and Path(paths[language]).exists():return Path(paths[language])
    audio,cues,_=build_scene_audio(project,scene,language,progress); sub=Path(project.folder)/'subtitles'/language; srt=write_srt(cues,sub/f'{scene.id}.srt');write_vtt(cues,sub/f'{scene.id}.vtt')
    outdir=Path(project.folder)/('cache/previews' if preview else f'scenes/{language}');outdir.mkdir(parents=True,exist_ok=True);base=outdir/f'{scene.number:03}-{scene.id}-base.mp4'
    style=scene.subtitle_override or project.settings.subtitle
    render_clay_motion(project,scene,audio,[],base,preview,progress,subtitle_cues=cues,subtitle_style=style);final=outdir/f'{scene.number:03}-{scene.id}.mp4'
    base.replace(final)
    paths[language]=str(final);sigs[language]=sig;scene.render_status='complete';scene.blocks_by_language[language]=scene.blocks
    if preview:scene.preview_path=str(final);scene.preview_signature=sig
    else:scene.render_path=str(final);scene.render_signature=sig
    return final

def render_story(project:Project,language:str,progress:Callable|None=None)->Path:
    scenes=sorted(project.scenes,key=lambda s:s.number); rendered=[]
    for i,s in enumerate(scenes):rendered.append(render_scene(project,s,language,False,lambda v,st,i=i:progress((i+v)/max(1,len(scenes))*.85,st) if progress else None))
    if not rendered:raise RuntimeError('This project has no scenes.')
    out=Path(project.folder)/'renders'/language;out.mkdir(parents=True,exist_ok=True);name=f"Bramble-and-Grace_Story-{project.story_number or '00'}_{language}_{project.settings.output_format.replace(':','x')}.mp4";target=out/name
    with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False,encoding='utf-8') as f:
        for p in rendered:f.write("file '"+str(p).replace("'","'\\''")+"'\n");lst=f.name
    try:subprocess.run([require_ffmpeg(),'-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',lst,'-c','copy',str(target)],check=True)
    finally:Path(lst).unlink(missing_ok=True)
    project.render_status='complete'
    if progress:progress(1.0,'Complete')
    return target

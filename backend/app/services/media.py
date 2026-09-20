from __future__ import annotations
import hashlib, json, shutil, subprocess, tempfile, wave
from pathlib import Path
from typing import Callable
from PIL import Image, ImageDraw, ImageFont
from ..models import Project, Scene
from ..storage import load_character
from ..engines.tts import generate_voice, validate_voice_file
from ..engines.comfyui import ComfyUIAdapter
from .subtitles import write_srt, write_vtt
from .acting import acting_prompt

# Bump whenever rendering behavior changes so old scene videos are not reused.
RENDER_ENGINE_VERSION = "2026-09-19-ai-clay-v10"
TTS_CACHE_VERSION = "2026-09-19-voice-v3"

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
    payload={'renderer_version':RENDER_ENGINE_VERSION,'img':scene.source_image,'blocks':[b.model_dump() for b in scene.blocks_by_language.get(lang,scene.blocks)],'lang':lang,'preview':preview,'w':project.settings.preview_width if preview else project.settings.width,'h':project.settings.preview_height if preview else project.settings.height,'fps':project.settings.preview_fps if preview else project.settings.fps,'subtitle':(scene.subtitle_override or project.settings.subtitle).model_dump(),'focus':scene.focus_points,'fill':project.settings.background_fill,'acting_plan':[b.model_dump() for b in scene.acting_plan],'performance_enabled':scene.performance_enabled,'video_mode':project.settings.video_mode,'render_profile':project.settings.render_profile,'clay_workflow':project.settings.clay_performance_workflow,'clay_strength':project.settings.clay_performance_strength,'cinematic_workflow':project.settings.cinematic_workflow,'cinematic_strength':project.settings.cinematic_motion_strength}
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
            voice_sig=hashlib.sha256(json.dumps({
                'version':TTS_CACHE_VERSION,
                'text':b.text,
                'speaker':speaker,
                'language':lang,
                'settings':settings.model_dump(),
                'global_speed':project.settings.voice_speed_global
            },sort_keys=True,default=str).encode()).hexdigest()
            sig_path=out.with_suffix(out.suffix+'.sig')
            cached_sig=sig_path.read_text(encoding='utf-8').strip() if sig_path.exists() else ''
            if out.exists() and (cached_sig!=voice_sig or not validate_voice_file(out)):
                out.unlink(missing_ok=True)
                sig_path.unlink(missing_ok=True)
            if not out.exists():
                generate_voice(b.text,out,lang,settings,project.settings.voice_speed_global)
                sig_path.write_text(voice_sig,encoding='utf-8')
            if not validate_voice_file(out):
                out.unlink(missing_ok=True)
                sig_path.unlink(missing_ok=True)
                raise RuntimeError(f'Voice generation failed validation for {speaker}.')
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

def render_ai_clay_performance(project:Project,scene:Scene,audio:Path,cues:list,target:Path,preview:bool=False,progress:Callable|None=None)->Path:
    workflow=project.settings.clay_performance_workflow
    if not workflow:
        raise RuntimeError('AI Clay Performance is selected, but no clay performance workflow is installed/configured yet.')
    adapter=ComfyUIAdapter()
    if not adapter.availability().get('available'):
        raise RuntimeError('AI Clay Performance requires ComfyUI to be running.')

    out_w=project.settings.preview_width if preview else project.settings.width
    out_h=project.settings.preview_height if preview else project.settings.height
    out_fps=project.settings.preview_fps if preview else project.settings.fps
    performance=acting_prompt(scene.acting_plan)
    story_text=' '.join(b.text.strip() for b in scene.blocks if b.text.strip())
    prompt=(
        project.settings.clay_style_prompt+' '
        'Animate the characters as physical handcrafted clay puppets performing the story. '
        'Use full-body acting, articulated arms and legs, walking or running when requested, '
        'clear head turns, readable facial expressions, eye-line changes, and believable reactions between characters. '
        'Keep non-speaking characters alive with subtle reactions; only the active speaker should lip-sync. '
        +performance+' Story context: '+story_text
    ).strip()

    duration=_duration(audio)
    ff=require_ffmpeg()

    # Wan TI2V can exceed 16 GB VRAM very quickly at 1280x704 and long frame counts.
    # Balanced mode therefore renders short low-resolution chunks and stitches them.
    # High mode keeps the larger settings for future higher-VRAM GPUs.
    balanced = project.settings.render_profile == 'balanced'
    gen_w = min(out_w, 640) if balanced else out_w
    gen_h = min(out_h, 352) if balanced else out_h
    gen_w = max(256, (gen_w // 32) * 32)
    gen_h = max(256, (gen_h // 32) * 32)
    gen_fps = min(out_fps, 12) if balanced else out_fps
    max_chunk_frames = 33 if balanced else 81  # 4n+1 frame counts
    max_chunk_seconds = (max_chunk_frames - 1) / max(1, gen_fps)

    target.parent.mkdir(parents=True,exist_ok=True)
    chunk_dir=target.parent/f'{target.stem}-wan-chunks'
    if chunk_dir.exists():
        shutil.rmtree(chunk_dir,ignore_errors=True)
    chunk_dir.mkdir(parents=True,exist_ok=True)

    chunk_paths=[]
    remaining=duration
    chunk_index=0
    source_image=Path(scene.source_image)
    try:
        while remaining > 0.05:
            chunk_index += 1
            chunk_seconds=min(remaining,max_chunk_seconds)
            requested_frames=max(17,int(round(chunk_seconds*gen_fps/4))*4+1)
            length=min(max_chunk_frames,requested_frames)
            raw=chunk_dir/f'chunk-{chunk_index:03}.mp4'
            values={
                'input_image':str(source_image),
                'audio':str(audio),
                'prompt':prompt,
                'negative_prompt':'frozen pose, slideshow, still frame, camera-only movement, deformed limbs, extra limbs, identity change, warped face, duplicate character, melted clay, random mouth movement',
                'width':gen_w,'height':gen_h,'fps':gen_fps,'duration':chunk_seconds,'length':length,
                'seed':(abs(hash((project.id,scene.id)))+chunk_index)%(2**63-1),
                'motion_strength':project.settings.clay_performance_strength,
                'output_path':str(raw),
            }
            if progress:
                base=.05 + .72*((duration-remaining)/max(duration,.01))
                progress(base,f'Generating Motion Chunk {chunk_index}')

            adapter.generate(workflow,values,progress_cb=(
                (lambda v,st,base=base: progress(min(.82,base+v*.18),f'Chunk {chunk_index}: {st}'))
                if progress else None
            ))
            if not raw.exists():
                raise RuntimeError(f'Wan chunk {chunk_index} completed without producing a video file.')
            chunk_paths.append(raw)

            # Continue the next chunk from the last generated frame for smoother motion continuity.
            last_frame=chunk_dir/f'chunk-{chunk_index:03}-last.png'
            grab=subprocess.run([
                ff,'-y','-hide_banner','-loglevel','error',
                '-sseof','-0.05','-i',str(raw),'-frames:v','1',str(last_frame)
            ],capture_output=True,text=True)
            if grab.returncode==0 and last_frame.exists():
                source_image=last_frame

            actual_chunk=(length-1)/max(1,gen_fps)
            remaining-=max(.1,actual_chunk)

        if progress: progress(.84,'Joining Motion Chunks')

        concat_file=chunk_dir/'concat.txt'
        concat_file.write_text(''.join(
            "file '"+str(p.resolve()).replace("'","'\\''")+"'"+"\n" for p in chunk_paths
        ),encoding='utf-8')
        joined=chunk_dir/'joined.mp4'
        join=subprocess.run([
            ff,'-y','-hide_banner','-loglevel','error',
            '-f','concat','-safe','0','-i',str(concat_file),
            '-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p',
            str(joined)
        ],capture_output=True,text=True)
        if join.returncode!=0:
            details=(join.stderr or join.stdout or 'FFmpeg concat failed').strip()
            raise RuntimeError(f'Could not join Wan motion chunks: {details[-3000:]}')

        if progress: progress(.92,'Adding Audio and Finalizing')
        filters=[]
        if gen_w!=out_w or gen_h!=out_h:
            filters.append(f'scale={out_w}:{out_h}:flags=lanczos')
        # Never create the final FPS by simply duplicating low-FPS Wan frames.
        # Motion interpolation generates intermediate frames and removes the
        # frame-by-frame judder that looks like a tiny pause on every image.
        if gen_fps < out_fps:
            filters.append(
                f'minterpolate=fps={out_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1'
            )
        vf=['-vf',','.join(filters)] if filters else []
        result=subprocess.run([
            ff,'-y','-hide_banner','-loglevel','error',
            '-i',str(joined),'-i',str(audio),
            '-map','0:v:0','-map','1:a:0',
            *vf,
            '-c:v','libx264','-preset','veryfast','-crf','21',
            '-c:a','aac','-b:a','192k',
            '-t',f'{duration:.3f}',
            str(target)
        ],capture_output=True,text=True)
        if result.returncode!=0:
            details=(result.stderr or result.stdout or f'FFmpeg exited with code {result.returncode}').strip()
            raise RuntimeError(f'AI clay performance finalization failed: {details[-3000:]}')
    finally:
        shutil.rmtree(chunk_dir,ignore_errors=True)

    if progress: progress(1.0,'Complete')
    return target

def render_cinematic_motion(project:Project,scene:Scene,audio:Path,cues:list,target:Path,preview:bool=False,progress:Callable|None=None)->Path:
    workflow=project.settings.cinematic_workflow
    if not workflow:
        raise RuntimeError('Cinematic mode is selected, but no ComfyUI video workflow is configured. Open Video Settings and select an installed image-to-video workflow.')
    adapter=ComfyUIAdapter()
    available=adapter.availability()
    if not available.get('available'):
        raise RuntimeError('Cinematic mode requires ComfyUI to be running.')
    w=project.settings.preview_width if preview else project.settings.width
    h=project.settings.preview_height if preview else project.settings.height
    fps=project.settings.preview_fps if preview else project.settings.fps
    story_text=' '.join(b.text.strip() for b in scene.blocks if b.text.strip())
    performance=acting_prompt(scene.acting_plan) if scene.performance_enabled else ''
    prompt=(project.settings.clay_style_prompt+' '+performance+' '+scene.motion_description.strip()+' Story context: '+story_text).strip()
    raw=target.with_name(target.stem+'-cinematic-raw.mp4')
    values={
        'input_image': scene.source_image,
        'audio': str(audio),
        'prompt': prompt,
        'negative_prompt': 'deformed face, extra limbs, identity change, warped hands, duplicate character, random mouth movement',
        'width': w,
        'height': h,
        'fps': fps,
        'duration': _duration(audio),
        'motion_strength': project.settings.cinematic_motion_strength,
        'output_path': str(raw),
    }
    if progress: progress(.05,'Starting Cinematic Generation')
    adapter.generate(workflow,values,progress_cb=progress)
    if not raw.exists():
        raise RuntimeError('The selected cinematic workflow completed without producing a video file.')
    ff=require_ffmpeg()
    target.parent.mkdir(parents=True,exist_ok=True)
    result=subprocess.run([
        ff,'-y','-hide_banner','-loglevel','error',
        '-i',str(raw),'-i',str(audio),
        '-map','0:v:0','-map','1:a:0',
        '-c:v','libx264','-preset','veryfast','-crf','21',
        '-c:a','aac','-b:a','192k','-shortest',str(target)
    ],capture_output=True,text=True)
    raw.unlink(missing_ok=True)
    if result.returncode!=0:
        details=(result.stderr or result.stdout or f'FFmpeg exited with code {result.returncode}').strip()
        raise RuntimeError(f'Cinematic audio mux failed: {details[-3000:]}')
    return target

def render_scene(project:Project,scene:Scene,language:str,preview:bool=False,progress:Callable|None=None)->Path:
    scene.blocks=scene.blocks_by_language.get(language,scene.blocks); sig=_sig(project,scene,language,preview); paths=scene.preview_paths if preview else scene.render_paths; sigs=scene.preview_signatures if preview else scene.render_signatures
    if paths.get(language) and sigs.get(language)==sig and Path(paths[language]).exists():
        if progress: progress(1.0,'Using cached scene')
        return Path(paths[language])
    audio,cues,_=build_scene_audio(project,scene,language,progress); sub=Path(project.folder)/'subtitles'/language; srt=write_srt(cues,sub/f'{scene.id}.srt');write_vtt(cues,sub/f'{scene.id}.vtt')
    outdir=Path(project.folder)/('cache/previews' if preview else f'scenes/{language}');outdir.mkdir(parents=True,exist_ok=True);base=outdir/f'{scene.number:03}-{scene.id}-base.mp4'
    style=scene.subtitle_override or project.settings.subtitle
    final=outdir/f'{scene.number:03}-{scene.id}.mp4'
    if project.settings.video_mode=='clay-ai':
        render_ai_clay_performance(project,scene,audio,cues,final,preview,progress)
        if style.enabled and style.burn_in and cues:
            if progress: progress(.98,'Burning Subtitles')
            subtitled=outdir/f'{scene.number:03}-{scene.id}-subtitled.mp4'
            _burn(final,srt,subtitled,style)
            subtitled.replace(final)
    elif project.settings.video_mode=='cinematic':
        render_cinematic_motion(project,scene,audio,cues,final,preview,progress)
        if style.enabled and style.burn_in and cues:
            if progress: progress(.98,'Burning Subtitles')
            subtitled=outdir/f'{scene.number:03}-{scene.id}-subtitled.mp4'
            _burn(final,srt,subtitled,style)
            subtitled.replace(final)
    else:
        if project.settings.mode=='bramble':
            raise RuntimeError('Legacy Clay Motion is disabled for Bramble & Grace because it does not provide real character acting. Select AI Clay Performance in Video Settings.')
        render_clay_motion(project,scene,audio,[],base,preview,progress,subtitle_cues=cues,subtitle_style=style)
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

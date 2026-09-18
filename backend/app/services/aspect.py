from __future__ import annotations
PRESETS={"16:9":(1920,1080),"9:16":(1080,1920),"1:1":(1080,1080),"4:5":(1080,1350)}
def preset_dimensions(name:str,custom:tuple[int,int]|None=None)->tuple[int,int]:
    if name in PRESETS:return PRESETS[name]
    if name.lower()=="custom" and custom and custom[0]>0 and custom[1]>0:return custom
    raise ValueError("Unknown or invalid aspect ratio")
def crop_box(in_w:int,in_h:int,out_w:int,out_h:int,focus:tuple[float,float]=(0.5,0.5))->tuple[int,int,int,int]:
    scale=max(out_w/in_w,out_h/in_h);rw,rh=in_w*scale,in_h*scale;fx=max(0,min(1,focus[0]))*rw;fy=max(0,min(1,focus[1]))*rh
    left=min(max(0,fx-out_w/2),max(0,rw-out_w));top=min(max(0,fy-out_h/2),max(0,rh-out_h));return round(left),round(top),round(left+out_w),round(top+out_h)

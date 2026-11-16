#!/usr/bin/env python3
"""Render the Sciescape research film locally, without model/API calls.

Requires Python, Pillow, NumPy, OpenCV and FFmpeg. Streams frames, keeps no
frame sequence, uses at most two OpenCV/encoder threads. The camera rotates
inside original panoramas; it never invents translation or new geometry.
"""
from pathlib import Path
import argparse, hashlib, json, math, subprocess, tempfile, wave
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FPS, DURATION = 24, 84
NIGHT, CREAM, GOLD, MINT = (10, 25, 24), (246, 241, 229), (231, 195, 148), (196, 216, 203)
cv2.setNumThreads(2)

# Each shot has a declared evidence status. The film contains no live API UI,
# simulated conversation, borrowed actor performance, or fabricated avatar.
SHOTS = [
    dict(start=0, end=8, asset='bamboo', yaw=(4, 25), title='Somewhere starts\nwith a sentence.', label='SCIESCAPE / A RESEARCH FILM', note='Original generated panorama · camera rotation from one position'),
    dict(start=8, end=15, asset='hut', yaw=(-24, 8), title='Five places.\nGenerated from words.', label='01 / WHAT EXISTS', note='Selected prototype outputs · not a live generation recording'),
    dict(start=15, end=22, asset='canal', yaw=(20, 53), title='Stay for the blue hour.', label='CANAL AT DUSK', note='Original generated panorama · fixed viewpoint'),
    dict(start=22, end=28, asset='oasis', yaw=(-20, 12), title='Follow your curiosity.', label='DESERT OASIS', note='Original generated panorama · fixed viewpoint'),
    dict(start=28, end=40, asset='flashworld', yaw=(0, 0), title='A scene with depth.', label='RECORDED 3D EXPERIMENT', note='FlashWorld baseline · recorded camera path · not live app navigation'),
    dict(start=40, end=49, asset='reading-room', yaw=(-19, 17), title='A beautiful view\nis only the beginning.', label='02 / THE UNSOLVED PART', note='Archived geometry evaluation: 2 of 21 development cases completed'),
    dict(start=49, end=58, asset='bamboo', yaw=(28, -5), title='What if the world remembered\nwhat you changed?', label='RESEARCH GOAL', note='Coherent movement and persistent edits remain under development'),
    dict(start=58, end=66, asset='canal', yaw=(50, 22), title='A lifelike guide.\nAn understanding of your view.', label='RESEARCH GOAL', note='Natural voice and a grounded 3D avatar · the full journey is not yet solved'),
    dict(start=66, end=74, asset='hut', yaw=(9, -19), title='One shared world.\nSight. Action. Conversation.', label='THE ENGINEERING QUESTION', note='Can shared persistent scene state make the complete journey reliable?'),
    dict(start=74, end=84, asset='bamboo', yaw=(0, 18), title='Help turn a scene\ninto somewhere.', label='SCIESCAPE / NAVISH KUMAR', note='Independent research · inspect the evidence · support the next experiment'),
]

def smooth(x):
    x = min(1., max(0., x)); return x*x*(3-2*x)

def font_path(serif=False):
    paths = (['/System/Library/Fonts/Supplemental/Didot.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'] if serif else
             ['/System/Library/Fonts/Avenir Next.ttc', '/System/Library/Fonts/Helvetica.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    return next(p for p in paths if Path(p).exists())

class Film:
    def __init__(self, width=1920, height=1080):
        self.w, self.h = width, height
        self.scale = width / 1920
        self.bar = round(88*self.scale)
        self.inner_h = height-2*self.bar
        self.fonts = {}
        self.images = {p.stem: cv2.cvtColor(cv2.imread(str(p)), cv2.COLOR_BGR2RGB) for p in (ROOT/'assets').glob('*.png')}
        # Perspective camera rays intersect a unit sphere. Only their yaw changes.
        fov = math.radians(106)
        xx = np.linspace(-math.tan(fov/2), math.tan(fov/2), width, dtype=np.float32)
        yy = np.linspace(math.tan(fov/2)*self.inner_h/width, -math.tan(fov/2)*self.inner_h/width, self.inner_h, dtype=np.float32)
        x, y = np.meshgrid(xx, yy)
        self.base_u = (np.arctan2(x, 1)/(2*np.pi)+.5).astype(np.float32)
        self.base_v = (.5-np.arctan2(y, np.sqrt(x*x+1))/np.pi).astype(np.float32)
        self.clip = cv2.VideoCapture(str(ROOT/'assets/film-source/flashworld-research.mp4'))
        self.clip_rate = self.clip.get(cv2.CAP_PROP_FPS)
        self.last_frame_no, self.last_clip = -1, None
        # Titles fade over a lower shadow, not a colour grade of source footage.
        yy = np.linspace(0, 1, height, dtype=np.float32)[:, None]
        shade = np.clip((yy-.38)/.62, 0, 1)**1.6*.77
        self.shade = np.broadcast_to(shade, (height,width))[...,None]

    def font(self, size, serif=False):
        key=(size,serif)
        if key not in self.fonts:
            path=font_path(serif)
            self.fonts[key]=ImageFont.truetype(path,max(10,round(size*self.scale)),index=5 if 'Avenir Next' in path else 0)
        return self.fonts[key]

    def background(self, shot, t):
        base=np.full((self.h,self.w,3),NIGHT,dtype=np.uint8)
        if shot['asset']=='flashworld':
            # A contiguous 12-second excerpt at original speed; no invented frames.
            n=int((3+max(0,t-shot['start']))*self.clip_rate)
            if n!=self.last_frame_no:
                if n!=self.last_frame_no+1: self.clip.set(cv2.CAP_PROP_POS_FRAMES,n)
                ok, frame=self.clip.read()
                if not ok: raise RuntimeError('Could not decode the source 3D clip')
                self.last_clip=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB);self.last_frame_no=n
            im=self.last_clip
            h=self.inner_h;w=round(h*im.shape[1]/im.shape[0]);x=(self.w-w)//2
            base[self.bar:self.bar+h,x:x+w]=cv2.resize(im,(w,h),interpolation=cv2.INTER_CUBIC)
        else:
            img=self.images[shot['asset']]
            f=smooth((t-shot['start'])/(shot['end']-shot['start']))
            yaw=shot['yaw'][0]+f*(shot['yaw'][1]-shot['yaw'][0])
            u=((self.base_u+yaw/360)%1*img.shape[1]).astype(np.float32)
            v=(self.base_v*img.shape[0]).astype(np.float32)
            base[self.bar:self.h-self.bar]=cv2.remap(img,u,v,cv2.INTER_CUBIC,borderMode=cv2.BORDER_WRAP)
        return base

    def text(self, draw, xy, text, size, color=CREAM, serif=False, alpha=255, anchor=None):
        draw.text(tuple(round(c*self.scale) for c in xy),text,font=self.font(size,serif),fill=(*color,int(alpha)),anchor=anchor,spacing=round(6*self.scale))

    def shot_frame(self, shot, t):
        base=self.background(shot,t)
        local=t-shot['start'];length=shot['end']-shot['start']
        show=smooth((local-.55)/.9)*smooth((length-local)/.5)
        # Opening/closing typesetting grows gently; the source image is not warped.
        shade=self.shade*show
        if shot['asset']=='flashworld': shade=shade*.48
        base=(base.astype(np.float32)*(1-shade)+np.array(NIGHT)*shade).astype(np.uint8)
        im=Image.fromarray(base,'RGB').convert('RGBA')
        words=Image.new('RGBA',im.size);d=ImageDraw.Draw(words)
        self.text(d,(76,24),'sciescape.',34,GOLD,alpha=235)
        tag='RECORDED PROTOTYPE' if shot['start']<40 else ('RESEARCH QUESTION' if shot['start']<74 else 'INDEPENDENT RESEARCH')
        self.text(d,(1844,42),tag,21,MINT,alpha=220,anchor='rm')
        # Oversized type, restrained copy, large photographic areas.
        if shot['asset']=='flashworld':
            self.text(d,(96,838),shot['title'],62,serif=True,alpha=255*show)
            self.text(d,(96,800),shot['label'],21,GOLD,alpha=255*show)
        else:
            lines=shot['title'].count('\n')+1
            size=88 if max(map(len,shot['title'].split('\n')))<30 else 74
            title_y=805-(lines-1)*(size+12)
            self.text(d,(96,title_y-52),shot['label'],22,GOLD,alpha=255*show)
            self.text(d,(96,title_y),shot['title'],size,serif=True,alpha=255*show)
        self.text(d,(96,1028),shot['note'],22,MINT,alpha=255)
        if shot['start']==74 and local>4:
            fade=smooth((local-4)/.7)
            self.text(d,(96,934),'kumarnavish.github.io/sciescape-research',28,GOLD,alpha=255*fade)
            self.text(d,(96,976),'Qwen-Image / QwenImage360 / Lightning · FlashWorld (Li et al.) · Film: CC BY-NC-SA 4.0',18,MINT,alpha=255*fade)
        # A thin continuous time mark makes the 84-second scope visible.
        d.line([(round(96*self.scale),round(994*self.scale)),(round((96+1728*t/DURATION)*self.scale),round(994*self.scale))],fill=(*GOLD,150),width=max(1,round(2*self.scale)))
        return Image.alpha_composite(im,words).convert('RGB')

    def frame(self,t):
        i=next(i for i,s in enumerate(SHOTS) if t<s['end'])
        im=self.shot_frame(SHOTS[i],t)
        if i and t-SHOTS[i]['start']<.65:
            prev=self.shot_frame(SHOTS[i-1],SHOTS[i-1]['end']-.04)
            im=Image.blend(prev,im,smooth((t-SHOTS[i]['start'])/.65))
        fade=smooth(t/1.2)*smooth((DURATION-t)/1.8)
        if fade<1: im=Image.blend(Image.new('RGB',im.size,NIGHT),im,fade)
        return im

def soundtrack(path):
    """Original restrained ambient score, composed here, no third-party samples."""
    rate=48000;n=rate*DURATION
    out=np.zeros((n,2),dtype=np.float32)
    chords=[(50,57,61,64,69),(47,54,57,62,66),(43,50,54,57,62),(45,52,57,59,64)]
    def note(start,duration,midi,gain,pan,kind='pad'):
        a=round(start*rate);count=min(round(duration*rate),n-a)
        if count<=0:return
        t=np.arange(count,dtype=np.float32)/rate
        freq=440*2**((midi-69)/12)
        if kind=='pad':
            env=np.minimum(t/1.8,1)*np.minimum((duration-t)/2,1)
            sound=(np.sin(2*np.pi*freq*t)+.24*np.sin(2*np.pi*(freq*1.0015)*t)+.08*np.sin(2*np.pi*2*freq*t))*env
        else:
            env=(1-np.exp(-t*55))*np.exp(-t/1.5)
            sound=(np.sin(2*np.pi*freq*t+.7*np.sin(2*np.pi*2*freq*t)*np.exp(-t*2))+.1*np.sin(2*np.pi*3*freq*t))*env
        gains=np.array([math.cos((pan+1)*math.pi/4),math.sin((pan+1)*math.pi/4)],dtype=np.float32)*gain
        out[a:a+count]+=sound[:,None]*gains
    for k,start in enumerate(np.arange(0,DURATION,8.0)):
        chord=chords[k%4]
        for j,midi in enumerate(chord):note(float(start),11.5,midi,.025,(-.65+j*.325))
        note(float(start),9,chord[0]-12,.027,0)
        for j in range(8):
            # Sparse, rising notes; a little more presence around the real 3D reveal.
            gain=.04 if 26<=start<41 else .028
            note(float(start+j*.87+.4),4.2,chord[[2,3,4,3,1,2,3,4][j]]+12,gain,math.sin(j*1.7)*.5,'bell')
    t=np.arange(n,dtype=np.float32)/rate
    envelope=np.minimum(t/4,1)*np.minimum((DURATION-t)/5,1)
    out*=envelope[:,None]
    peak=float(np.max(np.abs(out)));out*=.55/max(peak,1e-6)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate);w.writeframes((out*32767).astype('<i2').tobytes())

def stamp(t):
    return f'{int(t)//3600:02}:{int(t)//60%60:02}:{int(t)%60:02}.000'

def metadata(output):
    sources=[]
    for p in sorted((ROOT/'assets').glob('*.png')):
        sources.append({'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'use':'Original panorama, perspective camera rotation only'})
    clip=ROOT/'assets/film-source/flashworld-research.mp4'
    sources.append({'path':str(clip.relative_to(ROOT)),'sha256':hashlib.sha256(clip.read_bytes()).hexdigest(),'use':'Contiguous 3–15 second excerpt, original speed, full frame; frame duplication converts 15 to 24 fps','model':'FlashWorld','model_revision':'6a8e88c6f88678ac098e4c82675f0aee555d6e5d','model_license':'CC BY-NC-SA 4.0','source_job':'ff5af870853041119c1972c83bea0a7f'})
    data={'date':'2026-11-16','duration_seconds':DURATION,'fps':FPS,'output':str(output.relative_to(ROOT)),'output_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'sources':sources,'shots':SHOTS,'audio':'Original synthesized ambient composition; no third-party samples or voice','limits':['Selected prototype and baseline outputs, not representative performance','Panoramas rotate at one viewpoint; no new geometry','3D sequence is a FlashWorld baseline, not a Sciescape novelty claim','No live generation, free-walking app session, interactive avatar or voice acceptance is claimed'],'visual_method':{'mechanism':'Camera orientation changes which rays sample an unchanged spherical panorama. The recorded 3D baseline separately shows actual camera-path parallax.','construction':'Perspective camera inside the original image sphere; no invented camera translation. Flat image panning was rejected because it distorts viewing geometry.','references':['Plenoxels: follow one camera ray into spatial samples; oblique camera and sparse labels','Gauge paths: retain object identity while orientation changes; shared object colour and matched states'],'colour':'Original source colours preserved; warm cream type, gold editorial labels, mint secondary text, deep green letterbox; no data colour mapping'}}
    (ROOT/'evidence/film.json').write_text(json.dumps(data,indent=2)+'\n')
    vtt='WEBVTT\n\nNOTE Research film, original instrumental soundtrack, no spoken dialogue.\n\n'
    for s in SHOTS:
        vtt+=f"{stamp(s['start'])} --> {stamp(s['end'])}\n{s['label']}. {s['title'].replace(chr(10),' ')}\n{s['note']}\n\n"
    (ROOT/'assets/film-captions.vtt').write_text(vtt)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',action='store_true');parser.add_argument('--width',type=int,default=1920);args=parser.parse_args()
    h=round(args.width*9/16)//2*2;film=Film(args.width,h)
    if args.preview:
        dest=ROOT/'film/review';dest.mkdir(exist_ok=True)
        for t in [4,11,18,25,33,44,53,62,70,79]:film.frame(t).save(dest/f'{t:02}.jpg',quality=90)
        print(dest,flush=True);return
    output=ROOT/'assets/sciescape-film.mp4'
    with tempfile.TemporaryDirectory(prefix='sciescape-film-') as tmp:
        tmp=Path(tmp);music=tmp/'score.wav';soundtrack(music)
        cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{args.width}x{h}','-r',str(FPS),'-i','pipe:0','-i',str(music),'-c:v','libx264','-preset','fast','-crf','21','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-af','loudnorm=I=-20:TP=-2:LRA=9','-movflags','+faststart','-metadata','title=Sciescape — Somewhere starts with a sentence','-metadata','comment=Recorded research outputs and labelled goals. Credits and limits: evidence/film.json and film/README.md','-shortest',str(output)]
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
        try:
            for n in range(DURATION*FPS):
                proc.stdin.write(film.frame(n/FPS).tobytes())
                if n% (FPS*6)==0:print(f'rendered {n/FPS:.0f}/{DURATION}s',flush=True)
            proc.stdin.close();code=proc.wait(timeout=120)
            if code:raise RuntimeError(f'FFmpeg exit {code}')
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
    film.frame(4).save(ROOT/'assets/film-poster.jpg',quality=90)
    metadata(output)
    print(f'Completed {output} ({output.stat().st_size/1e6:.1f} MB)',flush=True)

if __name__=='__main__': main()

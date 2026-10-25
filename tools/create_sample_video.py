"""Create a labelled synthetic room walkthrough for repeatable integration tests.

The reference geometry is NEVER fed to extraction or used as a fallback scene.
"""
from pathlib import Path
import math,subprocess,tempfile,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
def box(cx,cz,w,d,h,color):
    v=[(cx+x,y,cz+z) for y in (0,h) for x,z in [(-w/2,-d/2),(w/2,-d/2),(w/2,d/2),(-w/2,d/2)]]
    return [([v[i] for i in ids],color) for ids in [[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]]]
def render(index,total):
    im=Image.new('RGB',(960,600),'#e7edf0');draw=ImageDraw.Draw(im)
    t=index/(total-1);eye=np.array([-1.35+2.7*t,1.65,2.25]);target=np.array([.15,.9,-.7])
    f=target-eye;f=f/np.linalg.norm(f);right=np.cross(f,np.array([0.,1.,0.]));right=right/np.linalg.norm(right);up=np.cross(right,f)
    def project(p):
        q=np.array(p)-eye;z=float(q@f)
        if z<=.1:return None
        return (480+float(q@right)*560/z,300-float(q@up)*560/z,z)
    faces=[([(-3,0,-2.5),(3,0,-2.5),(3,0,2.5),(-3,0,2.5)],'#cbd5cd'),
           ([(-3,0,-2.5),(3,0,-2.5),(3,2.7,-2.5),(-3,2.7,-2.5)],'#f2eee4'),
           ([(-3,0,2.5),(-3,0,-2.5),(-3,2.7,-2.5),(-3,2.7,2.5)],'#deded5'),
           ([(3,0,-2.5),(3,0,2.5),(3,2.7,2.5),(3,2.7,-2.5)],'#d9e2e0')]
    faces += [([(-2.6,0,-2.49),(-1.7,0,-2.49),(-1.7,2.1,-2.49),(-2.6,2.1,-2.49)],'#556c74'),
              ([(.9,1.0,-2.48),(2.5,1.0,-2.48),(2.5,2.1,-2.48),(.9,2.1,-2.48)],'#8ac1d5')]
    faces+=box(0.,-.2,1.6,.9,.75,'#be8355')+box(2.35,-1.3,.6,1.2,1.5,'#5f8b87')+box(-1.25,.1,.5,.5,.48,'#3e647b')
    items=[]
    for vertices,color in faces:
        pts=[project(p) for p in vertices]
        if all(p is not None for p in pts):items.append((sum(p[2] for p in pts)/len(pts),[(p[0],p[1]) for p in pts],color))
    for _,pts,color in sorted(items,reverse=True):draw.polygon(pts,fill=color,outline='#485c60',width=2)
    draw.rectangle((0,0,960,48),fill='#132c35');draw.text((22,15),'ROOMLAB / SYNTHETIC ROOM WALKTHROUGH / translated camera',fill='white')
    draw.rectangle((0,566,960,600),fill='#132c35');draw.text((22,577),'Test scene only. Estimated geometry must still come from the video model.',fill='#cbdedb')
    return im
def main():
    out=ROOT/'runtime/roomlab';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        for i in range(48):render(i,48).save(Path(temp)/f'{i:03}.png')
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-framerate','8','-i',str(Path(temp)/'%03d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'sample-room.mp4')],check=True)
    (out/'sample-reference.json').write_text(json.dumps({'label':'synthetic ground truth, held out from model','room_width_m':6,'room_depth_m':5,'table_width_m':1.6,'table_depth_m':.9,'duration_s':6},indent=2))
    print(out/'sample-room.mp4')
if __name__=='__main__':main()

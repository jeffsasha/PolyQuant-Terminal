'use client';
import {useEffect,useRef} from 'react';
// Ambient, decorative background: drifting aurora (CSS), panning grid (CSS) and a pointer-reactive node network (canvas).
// Purely visual. It never reads market data and pauses when the tab is hidden or reduced motion is requested.
type Node={x:number;y:number;vx:number;vy:number;r:number};
type Packet={a:Node;b:Node;t:number;speed:number};
export default function Backdrop(){
 const canvasRef=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{
  const canvas=canvasRef.current;const ctx=canvas?.getContext('2d');if(!canvas||!ctx)return;
  const root=document.documentElement;const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  let width=0,height=0,dpr=1,frame=0,last=performance.now(),spawnIn=0,ink='130,143,255',accent='94,106,210';
  let nodes:Node[]=[],packets:Packet[]=[];
  const pointer={x:-1e4,y:-1e4,px:0,py:0,tx:0,ty:0};
  const readColors=()=>{const style=getComputedStyle(root);ink=style.getPropertyValue('--node-rgb').trim()||ink;accent=style.getPropertyValue('--accent-rgb').trim()||accent;};
  function resize(){
   if(!canvas||!ctx)return;
   width=window.innerWidth;height=window.innerHeight;dpr=Math.min(window.devicePixelRatio||1,1.5);
   canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);
   const count=Math.round(Math.min(110,Math.max(28,width*height/15000)));
   nodes=Array.from({length:count},()=>({x:Math.random()*width,y:Math.random()*height,vx:(Math.random()-.5)*.22,vy:(Math.random()-.5)*.22,r:Math.random()*1.3+.5}));packets=[];
  }
  function step(dt:number){
   for(const n of nodes){
    const dx=n.x-pointer.x,dy=n.y-pointer.y,d2=dx*dx+dy*dy;
    if(d2<180*180&&d2>1){const f=(1-Math.sqrt(d2)/180)*.018;n.vx+=dx*f/Math.sqrt(d2);n.vy+=dy*f/Math.sqrt(d2);}
    n.vx*=.985;n.vy*=.985;const speed=Math.hypot(n.vx,n.vy);if(speed<.06){n.vx+=(Math.random()-.5)*.02;n.vy+=(Math.random()-.5)*.02;}
    n.x+=n.vx*dt*.06;n.y+=n.vy*dt*.06;
    if(n.x<-20)n.x=width+20;else if(n.x>width+20)n.x=-20;if(n.y<-20)n.y=height+20;else if(n.y>height+20)n.y=-20;
   }
   spawnIn-=dt;
   if(spawnIn<=0&&packets.length<14&&nodes.length>1){
    spawnIn=260+Math.random()*420;const a=nodes[Math.floor(Math.random()*nodes.length)];let best:Node|null=null,bestD=1e9;
    for(const n of nodes){if(n===a)continue;const d=(n.x-a.x)**2+(n.y-a.y)**2;if(d<bestD&&d<140*140){bestD=d;best=n;}}
    if(best)packets.push({a,b:best,t:0,speed:.0009+Math.random()*.0012});
   }
   packets=packets.filter(p=>(p.t+=p.speed*dt)<1);
   pointer.px+=(pointer.tx-pointer.px)*.06;pointer.py+=(pointer.ty-pointer.py)*.06;
   root.style.setProperty('--px',pointer.px.toFixed(4));root.style.setProperty('--py',pointer.py.toFixed(4));
  }
  function draw(){
   if(!ctx)return;ctx.clearRect(0,0,width,height);const max=140;
   for(let i=0;i<nodes.length;i++){const a=nodes[i];for(let j=i+1;j<nodes.length;j++){const b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;if(d2>max*max)continue;const alpha=(1-Math.sqrt(d2)/max)*.22;ctx.strokeStyle=`rgba(${ink},${alpha.toFixed(3)})`;ctx.lineWidth=.6;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}}
   for(const n of nodes){const near=Math.hypot(n.x-pointer.x,n.y-pointer.y)<200;if(near){ctx.strokeStyle=`rgba(${accent},${(.5*(1-Math.hypot(n.x-pointer.x,n.y-pointer.y)/200)).toFixed(3)})`;ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(n.x,n.y);ctx.lineTo(pointer.x,pointer.y);ctx.stroke();}ctx.fillStyle=`rgba(${near?accent:ink},${near?.95:.55})`;ctx.beginPath();ctx.arc(n.x,n.y,n.r,0,Math.PI*2);ctx.fill();}
   for(const p of packets){const x=p.a.x+(p.b.x-p.a.x)*p.t,y=p.a.y+(p.b.y-p.a.y)*p.t,glow=ctx.createRadialGradient(x,y,0,x,y,7);glow.addColorStop(0,`rgba(${accent},.95)`);glow.addColorStop(1,`rgba(${accent},0)`);ctx.fillStyle=glow;ctx.beginPath();ctx.arc(x,y,7,0,Math.PI*2);ctx.fill();}
  }
  function loop(now:number){const dt=Math.min(48,now-last);last=now;step(dt);draw();frame=requestAnimationFrame(loop);}
  function start(){cancelAnimationFrame(frame);if(motion.matches||document.hidden){draw();return;}last=performance.now();frame=requestAnimationFrame(loop);}
  function move(e:PointerEvent){
   pointer.x=e.clientX;pointer.y=e.clientY;pointer.tx=e.clientX/width*2-1;pointer.ty=e.clientY/height*2-1;
   const target=(e.target as Element|null)?.closest?.('.panel,.market-card,.stats,.login-card,.login-art') as HTMLElement|null;
   if(target){const rect=target.getBoundingClientRect();target.style.setProperty('--mx',`${e.clientX-rect.left}px`);target.style.setProperty('--my',`${e.clientY-rect.top}px`);}
  }
  const leave=()=>{pointer.x=-1e4;pointer.y=-1e4;};
  const themeWatch=new MutationObserver(()=>{readColors();if(motion.matches)draw();});
  readColors();resize();start();
  themeWatch.observe(root,{attributes:true,attributeFilter:['data-theme']});
  window.addEventListener('resize',resize);window.addEventListener('pointermove',move,{passive:true});document.addEventListener('pointerleave',leave);
  document.addEventListener('visibilitychange',start);motion.addEventListener('change',start);
  return()=>{cancelAnimationFrame(frame);themeWatch.disconnect();window.removeEventListener('resize',resize);window.removeEventListener('pointermove',move);document.removeEventListener('pointerleave',leave);document.removeEventListener('visibilitychange',start);motion.removeEventListener('change',start);};
 },[]);
 return <div className="backdrop" aria-hidden="true"><div className="aurora"><span className="aurora-a"/><span className="aurora-b"/><span className="aurora-c"/></div><div className="grid-plane"/><canvas ref={canvasRef} className="network"/><div className="beam"/><div className="grain"/></div>;
}

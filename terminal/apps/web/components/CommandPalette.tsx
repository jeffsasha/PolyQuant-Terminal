'use client';
import {useEffect,useMemo,useRef,useState} from 'react';
export interface Command {id:string;label:string;group:string;hint?:string;run:()=>void}
// ⌘K / Ctrl+K navigator. Navigation and view commands only: it never places, runs or stops anything.
export default function CommandPalette({open,onClose,commands}:{open:boolean;onClose:()=>void;commands:Command[]}){
 const [query,setQuery]=useState(''),[active,setActive]=useState(0);const input=useRef<HTMLInputElement>(null),list=useRef<HTMLDivElement>(null);
 const results=useMemo(()=>{const q=query.trim().toLowerCase();return q?commands.filter(c=>(c.label+' '+c.group+' '+(c.hint??'')).toLowerCase().includes(q)):commands;},[commands,query]);
 useEffect(()=>{if(open){setQuery('');setActive(0);requestAnimationFrame(()=>input.current?.focus());}},[open]);
 useEffect(()=>{setActive(0);},[query]);
 useEffect(()=>{list.current?.querySelector('[data-active=true]')?.scrollIntoView({block:'nearest'});},[active]);
 if(!open)return null;
 function choose(c:Command|undefined){if(!c)return;onClose();c.run();}
 function key(e:React.KeyboardEvent){
  if(e.key==='ArrowDown'){e.preventDefault();setActive(a=>Math.min(results.length-1,a+1));}
  else if(e.key==='ArrowUp'){e.preventDefault();setActive(a=>Math.max(0,a-1));}
  else if(e.key==='Enter'){e.preventDefault();choose(results[active]);}
  else if(e.key==='Escape'){e.preventDefault();onClose();}
 }
 let lastGroup='';
 return <div className="palette-scrim" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div className="palette" role="dialog" aria-modal="true" aria-label="Command palette" onKeyDown={key}><div className="palette-search"><span aria-hidden="true">⌕</span><input ref={input} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Jump to a panel, account or view…" aria-label="Search commands" role="combobox" aria-expanded="true" aria-controls="palette-list" aria-activedescendant={results[active]?'cmd-'+results[active].id:undefined}/><kbd>esc</kbd></div><div className="palette-list" id="palette-list" role="listbox" ref={list}>{results.length?results.map((c,i)=>{const header=c.group!==lastGroup;lastGroup=c.group;return <div key={c.id}>{header&&<div className="palette-group">{c.group}</div>}<div id={'cmd-'+c.id} role="option" aria-selected={i===active} data-active={i===active} className="palette-item" onMouseMove={()=>setActive(i)} onClick={()=>choose(c)}><span>{c.label}</span>{c.hint&&<kbd>{c.hint}</kbd>}</div></div>;}):<p className="palette-empty">No matching command.</p>}</div><div className="palette-foot"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span>Paper only · no order commands</span></div></div></div>;
}

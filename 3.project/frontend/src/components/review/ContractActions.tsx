import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Download, Plus } from 'lucide-react';

interface Action { label:string; onClick:()=>void; danger?:boolean; hidden?:boolean }
export function ContractActions({actions,canEdit,onUpload}:{actions:Action[];canEdit:boolean;onUpload:()=>void}) {
  const [menu,setMenu]=useState<'download'|'more'|null>(null);
  const root=useRef<HTMLDivElement>(null),more=useRef<HTMLButtonElement>(null),download=useRef<HTMLButtonElement>(null);
  useEffect(()=>{
    if(!menu)return;
    const outside=(event:PointerEvent)=>{if(!root.current?.contains(event.target as Node))setMenu(null);};
    const keyboard=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();event.stopPropagation();setMenu(null);(menu==='download'?download:more).current?.focus();}
      if(event.key==='Tab')setMenu(null);
      if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
        const items=[...(root.current?.querySelectorAll<HTMLButtonElement>('[role=menuitem]')||[])];if(!items.length)return;
        event.preventDefault();const current=items.indexOf(document.activeElement as HTMLButtonElement);
        const next=event.key==='Home'?0:event.key==='End'?items.length-1:(current+(event.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next].focus();
      }
    };
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',keyboard);
    return()=>{document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',keyboard);};
  },[menu]);
  const toggle=(next:'download'|'more',event:React.MouseEvent)=>{setMenu(menu===next?null:next);if(event.detail===0)requestAnimationFrame(()=>root.current?.querySelector<HTMLButtonElement>('[role=menuitem]')?.focus());};
  const exports=actions.filter(action=>/ZIP|엑셀/.test(action.label));
  const extra=actions.filter(action=>!exports.includes(action)&&!['서류 추가로 올리기','처리 기록 보기'].includes(action.label)).sort((a,b)=>Number(!!a.danger)-Number(!!b.danger));
  return <div className="header-actions" ref={root}>
    {canEdit&&<button className="button" onClick={onUpload}><Plus size={15}/><span>서류 추가</span></button>}
    <button ref={download} className="button" aria-haspopup="menu" aria-expanded={menu==='download'} onClick={event=>toggle('download',event)}><Download size={15}/><span>내려받기</span><ChevronDown size={13}/></button>
    <button ref={more} className="button quiet" aria-label="더보기" aria-haspopup="menu" aria-expanded={menu==='more'} onClick={event=>toggle('more',event)}>더보기<ChevronDown size={13}/></button>
    {menu&&<div className="dropdown" role="menu" aria-label={menu==='download'?'자료 다운로드':'계약 작업'}>{(menu==='download'?exports:extra).map(action=><button role="menuitem" key={action.label} className={action.danger?'danger-menu':''} onClick={()=>{setMenu(null);action.onClick();}}>{action.label==='다른 담당자에게 맡기기'?'담당자 변경':action.label}</button>)}</div>}
  </div>;
}

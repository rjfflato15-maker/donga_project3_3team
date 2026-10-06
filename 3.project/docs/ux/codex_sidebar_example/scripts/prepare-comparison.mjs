import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
const root=resolve(import.meta.dirname,'..');
const source=resolve('C:/3조 색인-ui/3.project/docs/ux/flow_prototype/index.html');
const destination=resolve(root,'public/comparison');
mkdirSync(resolve(destination,'captures'),{recursive:true});
const html=readFileSync(source,'utf8').replace(/\r+/g,'').replace(/[ \t]+$/gm,'');
// Read-only source; fixture-only edits to the copy keep the former screen layout.
let aligned=html.replace(/(<section\b[^>]*\bid="(C2|E1|D7|D8|D9)"[\s\S]*?)(?=<section\b[^>]*class="pv-screen|<\/body>)/g,(block,_all,id)=>{
  if(id==='C2')return block.replaceAll('document_04.pdf','아직 없음').replaceAll('document_05.pdf','아직 없음').replaceAll('서류 6개','서류 4개');
  if(id==='E1')return block.replaceAll('필요 6종 · 받은 6종','필요 6종 · 받은 4종');
  return block.replaceAll('서버 장비 임대','업무지원 시스템 구축').replaceAll('5,500,000','3,410,000').replaceAll('1,210,000','3,410,000').replaceAll('보완 · 해당 없음','보완 · 완료');
});
// Two prepared snapshots of the same request: before/after choosing partial receipts.
const partial=aligned.match(/<section\b[^>]*\bid="S3"[\s\S]*?(?=<section\b[^>]*class="pv-screen|<\/body>)/)?.[0];
if(!partial)throw new Error('Current S3 source not found');
let wait=partial.replace('id="S3"','id="WAIT"').replaceAll('2건 받음 · 1건 기다림','0건 받음 · 3건 기다림').replaceAll('받은 6종','받은 4종').replace(/<div class="text-emerald-700">✓ (통장사본|전자세금계산서) 받음 <span[^>]*>[^<]*<\/span><\/div>/g,(_,name)=>`<div class="flex items-center gap-2"><input type="checkbox" class="h-4 w-4"><span class="font-medium">${name}</span></div>`);
const stillMissing=html.match(/<section\b[^>]*\bid="D3"[\s\S]*?(?=<section\b[^>]*class="pv-screen|<\/body>)/)?.[0]?.match(/<li\b[\s\S]*?<\/li>/)?.[0];
if(stillMissing)wait=wait.replace(/<li\b[\s\S]*?<\/li>/,stillMissing);
aligned=aligned.replace('</body>',wait+'</body>').replace('</head>','<style>body .pv-nav,body .pv-when{display:none!important}.pv-stage{min-height:100vh}</style></head>');
writeFileSync(resolve(destination,'current-aligned.html'),aligned);
writeFileSync(resolve(destination,'source-info.json'),JSON.stringify({source,sourceKind:'현재 구조 재현 HTML',date:'2026-10-06',fixtureEdits:['C2: 누락 2종, 파일 4종','E1: 받은 서류 4종','D7/D9: 같은 계약명·3,410,000원','WAIT: S3 받음 선택 전 상태'],excluded:'Claude ERP redesign'},null,2));
console.log('Comparison source prepared; Claude ERP alternative excluded.');

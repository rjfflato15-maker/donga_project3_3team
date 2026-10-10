import {ArrowLeft,FileText,Plus} from 'lucide-react';
import {DocumentType} from '../../types';
import {DOCUMENT_LABEL} from '../../utils/documentLabels';

interface Props {type:DocumentType;canEdit:boolean;canRequest:boolean;alreadyRequested:boolean;queued:boolean;
  onClose:()=>void;onUpload:()=>void;onRequest:()=>void;onRequests:()=>void;onDraft?:()=>void;}
export function MissingDocumentReview({type,canEdit,canRequest,alreadyRequested,queued,onClose,onUpload,onRequest,onRequests,onDraft}:Props){
  return <section className="flow-review review-frame"><div className="flow-workspace-head"><button className="text-button" onClick={onClose}><ArrowLeft size={14}/>서류 목록</button><strong>{DOCUMENT_LABEL[type]} · 미제출</strong></div><div className="flow-grid"><div className="flow-paper"><div className="flow-source-empty"><FileText size={28}/><strong>아직 받은 서류가 없어요</strong></div></div><div className="flow-results"><div className="flow-results-head"><strong>필수 서류 제출</strong></div><section className="flow-action-panel"><h3>{DOCUMENT_LABEL[type]}</h3>{type==='inspection_confirmation'&&<p>회사 안에서 작성한 서류를 등록하세요.</p>}<div className="flow-buttons">{canEdit&&<button className="button primary" onClick={onUpload}>서류 올리기</button>}{canEdit&&canRequest&&!alreadyRequested&&!queued&&<button className="button" onClick={onRequest}><Plus size={13}/>제출 요청에 담기</button>}{queued&&onDraft&&<button className="button" onClick={onDraft}>요청 내용 작성</button>}{alreadyRequested&&<button className="button" onClick={onRequests}>회신 내역 보기</button>}</div></section></div></div></section>;
}

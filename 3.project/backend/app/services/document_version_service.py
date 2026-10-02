"""Explicit logical documents; same-type uploads remain independent additions."""
import json
from fastapi import HTTPException
from ..db.models import Document, DocumentVersion, DocumentFileInfo
from ..schemas.document import AnalysisFields


def active_documents(contract):
    return [d for d in contract.documents if not d.version or d.version.is_current]


def require_current(doc):
    if doc.version and not doc.version.is_current:
        raise HTTPException(409, "이전 버전은 읽기 전용입니다. 현재 문서에서 수정하거나 재발행하세요.")


def metadata(doc):
    row = doc.version
    return {"logical_document_id": row.logical_document_id if row else doc.document_id,
            "version_number": row.version_number if row else 1,
            "is_current": row.is_current if row else True,
            "previous_document_id": row.previous_document_id if row else None}


def fields(doc):
    return AnalysisFields(**json.loads(doc.extract.raw_fields or '{}') if doc.extract else {}).model_dump()


def version_history(db, doc):
    group = metadata(doc)['logical_document_id']
    rows = db.query(Document).join(DocumentVersion).filter(DocumentVersion.logical_document_id == group).order_by(DocumentVersion.version_number).all() if doc.version else [doc]
    result=[]
    for item in rows:
        info=db.get(DocumentFileInfo,item.document_id)
        row=item.version
        result.append({"document_id":item.document_id, "file_name":item.file_name, "document_type":item.document_type,
                       **metadata(item), "source_sha256":info.sha256 if info else None, "fields":fields(item),
                       "extracted_status":item.extract.extracted_status if item.extract else None,
                       "uploaded_at":item.uploaded_at.isoformat(), "actor_name":row.actor_name if row else None,
                       "change_note":row.change_note if row else None})
    return result


def compare_versions(db, current, previous_id=None):
    previous_id = previous_id or metadata(current)['previous_document_id']
    if previous_id is None:
        raise HTTPException(404,"비교할 이전 버전이 없습니다.")
    previous=db.get(Document,previous_id)
    if not previous or metadata(previous)['logical_document_id'] != metadata(current)['logical_document_id']:
        raise HTTPException(404,"같은 논리 문서의 이전 버전을 찾을 수 없습니다.")
    if metadata(previous)['version_number'] >= metadata(current)['version_number']:
        raise HTTPException(400,"현재 문서보다 앞선 버전을 선택하세요.")
    before,after=fields(previous),fields(current)
    changes=[{"field":key,"previous_value":before[key],"new_value":after[key]} for key in before if before[key] != after[key]]
    return {"logical_document_id":metadata(current)['logical_document_id'],
            "previous_document_id":previous.document_id,"new_document_id":current.document_id,
            "previous_version":metadata(previous)['version_number'],"new_version":metadata(current)['version_number'],
            "comparison_basis":"CURRENT_SAVED_FIELDS", "changes":changes, "changed_field_count":len(changes),
            "previous_fields":before,"new_fields":after}

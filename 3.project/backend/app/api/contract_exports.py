from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, Response
from urllib.parse import quote
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from ..db.database import get_db
from ..security import Actor, get_current_user
from ..services.contract_export_service import create_bundle
from ..services.settlement_export_service import create_settlement

router = APIRouter(tags=['Contract exports'])


@router.get('/api/contracts/{contract_id}/settlement-export')
def export_settlement(contract_id: int, masked: bool = True,
                      revision: int | None = Query(None, ge=1),
                      db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    content = create_settlement(db, contract_id, actor, masked, revision)
    name = f"계약_{contract_id}_정산내역_{'가림' if masked else '실제값'}.xlsx"
    return Response(content, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(name),
                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/api/contracts/{contract_id}/export')
def export_contract(contract_id: int, masked: bool = True, revision: int | None = Query(None, ge=1),
                    db: Session = Depends(get_db), actor: Actor = Depends(get_current_user)):
    path, workspace = create_bundle(db, contract_id, actor, masked, revision)
    name = f"계약_{contract_id}_자료묶음_{'가림' if masked else '원본'}.zip"
    return FileResponse(path, filename=name, media_type='application/zip',
        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'},
        background=BackgroundTask(workspace.cleanup))

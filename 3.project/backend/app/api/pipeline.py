from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..db.database import get_db
from ..services.pipeline_service import PipelineService

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Simulation"])
pipeline_service = PipelineService()


@router.post("/{contract_id}/simulate")
def simulate_pipeline_endpoint(contract_id: int, db: Session = Depends(get_db)):
    """
    Simulates the 5-step data processing pipeline:
    1. 계약 및 문서 업로드 확인 (CONTRACTS, DOCUMENTS)
    2. 마스킹 및 국세청 검증 (1:0..1 비동기 결과 적재)
    3. AI OCR 분석 (최신 추출 레코드)
    4. 문서별 필드 정규화 (가변 필드 매핑)
    5. 최종 대조 검수 (extract_id 기반 교차 대조 검수)
    """
    try:
        return pipeline_service.simulate_pipeline(db, contract_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

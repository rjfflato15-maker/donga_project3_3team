from fastapi import APIRouter, Depends
from ..security import authorize_company_request
from .contracts import router as contracts_router
from .documents import router as documents_router
from .validations import router as validations_router
from .pipeline import router as pipeline_router
from .auto_contract import router as auto_contract_router
from .auth import router as auth_router
from .pilot import router as pilot_router
from .metrics import router as metrics_router
from .workflow import router as workflow_router
from .assignments import router as assignments_router

api_router = APIRouter()
api_router.include_router(contracts_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(auto_contract_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(documents_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(validations_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(pipeline_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(pilot_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(metrics_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(workflow_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(assignments_router, dependencies=[Depends(authorize_company_request)])
api_router.include_router(auth_router)

__all__ = ["api_router"]


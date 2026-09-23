from fastapi import APIRouter
from .contracts import router as contracts_router
from .documents import router as documents_router
from .validations import router as validations_router
from .pipeline import router as pipeline_router
from .auto_contract import router as auto_contract_router

api_router = APIRouter()
api_router.include_router(contracts_router)
api_router.include_router(auto_contract_router)
api_router.include_router(documents_router)
api_router.include_router(validations_router)
api_router.include_router(pipeline_router)

__all__ = ["api_router"]


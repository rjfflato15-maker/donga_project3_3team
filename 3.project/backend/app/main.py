import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .db.database import engine, Base, SessionLocal
from .db import models
from .api import api_router
from .services.contract_service import ContractService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    Base.metadata.create_all(bind=engine)

    # Seed demo contract if empty
    db = SessionLocal()
    try:
        cs = ContractService()
        contracts = cs.list_contracts(db)
        if len(contracts) == 0:
            cs.seed_demo_contract(db)
    except Exception as e:
        print(f"[Warning] Failed to seed initial demo contract: {e}")
    finally:
        db.close()

    yield


app = FastAPI(
    title="AI Contract Evidence Manager API",
    description="계약 증빙서류 누락·불일치 자동 검수 시스템 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "AI Contract Evidence Manager",
        "version": "1.0.0",
    }


# Include API Routers
app.include_router(api_router)

# Serve Frontend static build if present
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("health") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            return None
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Frontend not built yet."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)

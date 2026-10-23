from contextlib import asynccontextmanager
from app.api.credits import router as credits_router
from fastapi import Depends, FastAPI
from app.api.credits import router as credits_router
from app import models
from app.api.admin import router as admin_router
from app.auth.dependencies import get_current_principal
from app.config import settings
from app.database import Base, engine
from app.models import Principal
from app.api.chat import router as chat_router
from app.api import policy_documents
from app.api import rag



@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(credits_router)
app.include_router(policy_documents.router)
app.include_router(rag.router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
    }


@app.get("/v1/whoami", tags=["Identity"])
def who_am_i(
    principal: Principal = Depends(get_current_principal),
):
    return {
        "principal_id": principal.id,
        "name": principal.name,
        "type": principal.type,
        "email": principal.email,
        "team_id": principal.team_id,
        "is_active": principal.is_active,
    }
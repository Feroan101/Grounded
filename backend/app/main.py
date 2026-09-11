import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.errors import register_exception_handlers
from app.api.preferences import router as preferences_router
from app.auth import get_current_user
from app.config import ALLOWED_ORIGINS, API_HOST, API_PORT, IS_PRODUCTION

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Firebase init is best-effort; the health endpoint must work without it.
    from app.firebase import init_firebase

    try:
        init_firebase()
    except Exception:
        pass
    yield


app = FastAPI(title="Grounded API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

logger.info("CORS allowed origins: %s", ALLOWED_ORIGINS)

register_exception_handlers(app)

app.include_router(chat_router)
app.include_router(preferences_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": "production" if IS_PRODUCTION else "development",
    }


@app.get("/api/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "uid": user.get("uid"),
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "firebase_sign_in_provider": user.get("firebase", {})
        .get("sign_in_provider"),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT, reload=True)
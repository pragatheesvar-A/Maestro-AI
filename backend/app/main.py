import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.database import Base, engine
from app.routers import auth, employees, tasks, allocation, analytics, ws

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("smartalloc.main")

settings = get_settings()

Base.metadata.create_all(bind=engine)

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(title=settings.APP_NAME, version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(tasks.router)
app.include_router(allocation.router)
app.include_router(analytics.router)
app.include_router(ws.router)


@app.get("/health")
def health():
    from app.services.skills import embedding_backend_name
    from app.services.events import event_bus_backend
    return {
        "status": "ok", "app": settings.APP_NAME,
        "embedding_backend": embedding_backend_name(),
        "event_bus_backend": event_bus_backend(),
        "database": settings.DATABASE_URL.split("://")[0],
    }


@app.on_event("startup")
def on_startup():
    from app.services.skills import build_skill_graph
    from app.database import SessionLocal
    from app.models import Skill
    db = SessionLocal()
    try:
        names = [s.name for s in db.query(Skill).all()]
        if names:
            build_skill_graph(names)
            logger.info("Skill graph built with %d nodes", len(names))
    finally:
        db.close()
    logger.info("%s backend started.", settings.APP_NAME)

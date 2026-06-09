from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.routers import residents, affairs, announcements


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="乡镇政务服务系统", version="1.0.0", lifespan=lifespan)

app.include_router(residents.router)
app.include_router(affairs.router)
app.include_router(announcements.router)


@app.get("/")
def root():
    return {"service": "乡镇政务服务系统", "version": "1.0.0"}

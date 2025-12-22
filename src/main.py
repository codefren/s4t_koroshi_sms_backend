from fastapi import FastAPI
from src.adapters.secondary.database.config import engine, Base
from src.adapters.primary.api.router import router as item_router
from src.adapters.primary.api.websockets import ws_router

# Create tables (for demo purposes)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FastAPI Hexagonal ODBC")

app.include_router(item_router, prefix="/api/v1")
app.include_router(ws_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

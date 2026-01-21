from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.adapters.secondary.database.config import engine, Base
# from src.adapters.primary.api.router import router as item_router  # LEGACY - Removed InventoryItemModel
from src.adapters.primary.api.order_router import router as order_router
from src.adapters.primary.api.operator_router import router as operator_router
from src.adapters.primary.api.product_router import router as product_router
from src.adapters.primary.api.packing_boxes_router import router as packing_boxes_router
from src.adapters.primary.api.websockets import ws_router
from src.adapters.primary.websocket.operator_websocket import router as operator_ws_router

# Create tables (for demo purposes)
# COMMENTED: Tables already exist in s4t_sms database created via SQL script
# Base.metadata.create_all(bind=engine)

from contextlib import asynccontextmanager
from src.core.logging_config import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield

app = FastAPI(title="FastAPI Hexagonal ODBC", lifespan=lifespan)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # URLs del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(item_router, prefix="/api/v1")  # LEGACY - Removed InventoryItemModel
app.include_router(order_router, prefix="/api/v1")
app.include_router(operator_router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")
app.include_router(packing_boxes_router, prefix="/api/v1")
app.include_router(ws_router)
app.include_router(operator_ws_router, tags=["WebSocket PDA"])

@app.get("/health")
def health_check():
    return {"status": "ok"}

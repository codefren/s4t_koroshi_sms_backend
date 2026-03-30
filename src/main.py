import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sentry_sdk
from src.adapters.secondary.database.config import engine, Base

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    send_default_pii=True,
)
# from src.adapters.primary.api.router import router as item_router  # LEGACY - Removed InventoryItemModel
from src.adapters.primary.api.order_router import router as order_router
from src.adapters.primary.api.operator_router import router as operator_router
from src.adapters.primary.api.product_router import router as product_router
from src.adapters.primary.api.packing_boxes_router import router as packing_boxes_router
from src.adapters.primary.api.replenishment_router import router as replenishment_router
from src.adapters.primary.api.almacen_router import router as almacen_router
from src.adapters.primary.api.stock_movement_router import router as stock_movement_router
from src.adapters.primary.api.websockets import ws_router
from src.adapters.primary.websocket.operator_websocket import router as operator_ws_router
from src.api_service.routes import router as api_service_router

# Create tables (for demo purposes)
# COMMENTED: Tables already exist in s4t_sms database created via SQL script
# Base.metadata.create_all(bind=engine)

from src.core.logging_config import setup_logging
from src.services.stock_reservation_cron_service import start_stock_reservation_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    stock_scheduler = start_stock_reservation_scheduler()
    yield
    stock_scheduler.shutdown()

app = FastAPI(title="FastAPI Hexagonal ODBC", lifespan=lifespan)

# CORS Middleware
# In Starlette, the LAST added middleware is the OUTERMOST and runs first
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8004",
        "http://192.168.1.14:8000",
        "http://192.168.1.14:19000",  # Expo Metro bundler
        "http://192.168.1.14:19006",  # Expo web
        "http://172.20.10.9:8000",  # API Backend
        "http://172.20.10.9:8081",  # Cliente PDA
        "http://192.168.1.13:8081",  # PDA LAN
        "http://192.168.1.13:19000",  # Expo Metro bundler LAN
        "http://82.223.131.45:1717",  # Production frontend server
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=600,
)

# app.include_router(item_router, prefix="/api/v1")  # LEGACY - Removed InventoryItemModel
app.include_router(order_router, prefix="/api/v1")
app.include_router(operator_router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")
app.include_router(packing_boxes_router, prefix="/api/v1")
app.include_router(replenishment_router, prefix="/api/v1")
app.include_router(almacen_router, prefix="/api/v1")
app.include_router(stock_movement_router, prefix="/api/v1")
app.include_router(ws_router)
app.include_router(operator_ws_router, tags=["WebSocket PDA"])
app.include_router(api_service_router, prefix="/api/service", tags=["B2B Service API"])

class RootResponse(BaseModel):
    message: str
    version: str
    status: str
    endpoints: dict[str, str]

class HealthResponse(BaseModel):
    status: str

@app.get("/", response_model=RootResponse)
def root():
    """Endpoint raíz de la API."""
    return RootResponse(
        message="S4T Koroshi SMS Backend API",
        version="1.0.0",
        status="running",
        endpoints={
            "docs": "/docs",
            "health": "/health",
            "orders": "/api/v1/orders",
            "operators": "/api/v1/operators",
            "products": "/api/v1/products",
            "packing_boxes": "/api/v1/packing-boxes",
            "replenishment": "/api/v1/replenishment",
            "stock_movements": "/api/v1/stock-movements"
        }
    )

@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok")

if os.getenv("ENVIRONMENT") != "production":
    @app.get("/sentry-debug")
    async def trigger_error():
        division_by_zero = 1 / 0

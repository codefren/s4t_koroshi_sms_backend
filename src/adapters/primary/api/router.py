from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.domain.models import Item
from src.application.services import ItemService
from src.adapters.secondary.database.config import get_db
from src.adapters.secondary.database.odbc_repository import ODBCItemRepository

router = APIRouter()

# Dependency Injection Helper
def get_service(db: Session = Depends(get_db)) -> ItemService:
    repository = ODBCItemRepository(db)
    return ItemService(repository)

@router.post("/items/", response_model=Item)
async def create_item(item: Item, service: ItemService = Depends(get_service)):
    return await service.create_item(item)

@router.get("/items/{item_id}", response_model=Item)
async def read_item(item_id: int, service: ItemService = Depends(get_service)):
    item = await service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/items/", response_model=list[Item])
async def list_items(service: ItemService = Depends(get_service)):
    return await service.list_items()

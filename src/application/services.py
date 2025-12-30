from typing import List, Optional
from src.core.domain.models import InventoryItem
from src.core.ports.repository import ItemRepositoryPort

class ItemService:
    def __init__(self, repository: ItemRepositoryPort):
        self.repository = repository

    async def create_item(self, item: InventoryItem) -> InventoryItem:
        return await self.repository.create(item)

    async def get_item(self, item_id: int) -> Optional[InventoryItem]:
        return await self.repository.get_by_id(item_id)

    async def list_items(self) -> List[InventoryItem]:
        return await self.repository.list_all()

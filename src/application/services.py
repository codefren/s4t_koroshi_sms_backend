from typing import List, Optional
from src.core.domain.models import Item
from src.core.ports.repository import ItemRepositoryPort

class ItemService:
    def __init__(self, repository: ItemRepositoryPort):
        self.repository = repository

    async def create_item(self, item: Item) -> Item:
        return await self.repository.create(item)

    async def get_item(self, item_id: int) -> Optional[Item]:
        return await self.repository.get_by_id(item_id)

    async def list_items(self) -> List[Item]:
        return await self.repository.list_all()

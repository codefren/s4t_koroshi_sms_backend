from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.domain.models import InventoryItem

class ItemRepositoryPort(ABC):
    @abstractmethod
    async def create(self, item: InventoryItem) -> InventoryItem:
        pass

    @abstractmethod
    async def get_by_id(self, item_id: int) -> Optional[InventoryItem]:
        pass

    @abstractmethod
    async def list_all(self) -> List[InventoryItem]:
        pass

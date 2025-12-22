from abc import ABC, abstractmethod
from typing import List, Optional
from src.core.domain.models import Item

class ItemRepositoryPort(ABC):
    @abstractmethod
    async def create(self, item: Item) -> Item:
        pass

    @abstractmethod
    async def get_by_id(self, item_id: int) -> Optional[Item]:
        pass

    @abstractmethod
    async def list_all(self) -> List[Item]:
        pass

from typing import List, Optional
from sqlalchemy.orm import Session
from src.core.domain.models import Item
from src.core.ports.repository import ItemRepositoryPort
from src.adapters.secondary.database.orm import ItemModel

class ODBCItemRepository(ItemRepositoryPort):
    def __init__(self, db_session: Session):
        self.db = db_session

    async def create(self, item: Item) -> Item:
        db_item = ItemModel(name=item.name, description=item.description, price=item.price)
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return Item.model_validate(db_item)

    async def get_by_id(self, item_id: int) -> Optional[Item]:
        db_item = self.db.query(ItemModel).filter(ItemModel.id == item_id).first()
        if db_item:
            return Item.model_validate(db_item)
        return None

    async def list_all(self) -> List[Item]:
        items = self.db.query(ItemModel).all()
        return [Item.model_validate(item) for item in items]

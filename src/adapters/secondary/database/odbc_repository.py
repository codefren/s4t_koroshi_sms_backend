# ============================================================================
# LEGACY FILE - InventoryItemModel REMOVED
# ============================================================================
# This file is no longer used because InventoryItemModel was removed from ORM
# Kept for reference only
# ============================================================================

# from typing import List, Optional
# from sqlalchemy.orm import Session
# from src.core.domain.models import InventoryItem
# from src.core.ports.repository import ItemRepositoryPort
# from src.adapters.secondary.database.orm import InventoryItemModel

# class ODBCItemRepository(ItemRepositoryPort):
#     def __init__(self, db_session: Session):
#         self.db = db_session

#     async def create(self, item: InventoryItem) -> InventoryItem:
#         db_item = InventoryItemModel(
#             ean=item.ean,
#             ubicacion=item.ubicacion,
#             articulo=item.articulo,
#             color=item.color,
#             talla=item.talla,
#             posicion_talla=item.posicion_talla,
#             descripcion_producto=item.descripcion_producto,
#             descripcion_color=item.descripcion_color,
#             temporada=item.temporada,
#             numero_orden=item.numero_orden,
#             cliente=item.cliente,
#             nombre_cliente=item.nombre_cliente,
#             cantidad=item.cantidad,
#             servida=item.servida,
#             operario=item.operario,
#             status=item.status,
#             fecha=item.fecha,
#             hora=item.hora,
#             caja=item.caja
#         )
#         self.db.add(db_item)
#         self.db.commit()
#         self.db.refresh(db_item)
#         return InventoryItem.model_validate(db_item)

#     async def get_by_id(self, item_id: int) -> Optional[InventoryItem]:
#         db_item = self.db.query(InventoryItemModel).filter(InventoryItemModel.id == item_id).first()
#         if db_item:
#             return InventoryItem.model_validate(db_item)
#         return None

#     async def list_all(self) -> List[InventoryItem]:
#         items = self.db.query(InventoryItemModel).all()
#         return [InventoryItem.model_validate(item) for item in items]

from sqlalchemy import Column, Integer, String, Float
from src.adapters.secondary.database.config import Base

class ItemModel(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(String(1000), nullable=True)
    price = Column(Float)

class InventoryItemModel(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True) # Adding an internal ID since the CSV doesn't seem to have a unique PK, or EAN isn't unique enough?
    ean = Column(String(50), index=True)
    ubicacion = Column(String)
    articulo = Column(String)
    color = Column(String)
    talla = Column(String)
    posicion_talla = Column(String, nullable=True)
    descripcion_producto = Column(String, nullable=True)
    descripcion_color = Column(String, nullable=True)
    temporada = Column(String, nullable=True)
    numero_orden = Column(String(50), index=True)
    cliente = Column(String)
    nombre_cliente = Column(String, nullable=True)
    cantidad = Column(Integer)
    servida = Column(Integer)
    operario = Column(String, nullable=True)
    status = Column(String, nullable=True)
    fecha = Column(String, nullable=True) # Could be Date type if we parse it
    hora = Column(String, nullable=True)  # Could be Time type
    caja = Column(String, nullable=True)

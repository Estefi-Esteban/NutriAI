from pydantic import BaseModel
from typing import Dict, List


class ItemListaCompra(BaseModel):
    nombre: str
    cantidad_total: float
    unidad: str


class ListaCompraResponse(BaseModel):
    user_id: int
    plan_id: int
    categorias: Dict[str, List[ItemListaCompra]]
    total_items: int

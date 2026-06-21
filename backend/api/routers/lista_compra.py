from fastapi import APIRouter, HTTPException, Depends

from backend.api.schemas.lista_compra_schema import ListaCompraResponse
from backend.api.dependencies import get_current_user
from backend.database.connection import SessionLocal
from backend.database.repositories.plan_repository import obtener_plan_activo
from backend.database.models import User
from backend.utils.shopping_list_generator import generar_lista_compra

router = APIRouter(prefix="/lista-compra", tags=["Lista de la compra"])


@router.get("", response_model=ListaCompraResponse)
def obtener_lista_compra(current_user: User = Depends(get_current_user)):
    """
    Genera la lista de la compra a partir del plan activo del usuario autenticado.
    Se calcula on-demand cada vez (no se guarda en BD).
    """
    with SessionLocal() as db:
        plan = obtener_plan_activo(db, user_id=current_user.id)
        if plan is None:
            raise HTTPException(
                status_code=404,
                detail="No hay plan activo para este usuario. Genera uno primero con /planes/generar",
            )

        lista = generar_lista_compra(plan.plan_semanal)
        total_items = sum(len(v) for v in lista.values())

        return ListaCompraResponse(
            user_id=current_user.id,
            plan_id=plan.id,
            categorias=lista,
            total_items=total_items,
        )

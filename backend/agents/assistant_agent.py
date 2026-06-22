"""
assistant_agent.py
-------------------
Agente asistente general con memoria persistente entre sesiones.
Combina el contexto del perfil, plan activo y historial de conversación
para dar respuestas personalizadas y con continuidad real.
"""

import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from backend.config import GROQ_API_KEY
from backend.agents.prompts.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


class AssistantAgent:

    MODEL = "llama-3.3-70b-versatile"
    TEMPERATURE = 0.7
    MAX_HISTORIAL = 10  # últimos N mensajes del historial

    def __init__(self):
        self.llm = ChatGroq(
            model=self.MODEL,
            api_key=GROQ_API_KEY,
            temperature=self.TEMPERATURE,
        )
        self.prompt_template = load_prompt("assistant_prompt.md")

    def responder(
        self,
        mensaje_usuario: str,
        perfil: dict,
        plan_activo: dict | None,
        protocolo: dict | None,
        historial: list[dict],
    ) -> str:
        """
        Genera una respuesta contextualizada para el usuario.

        Args:
            mensaje_usuario: lo que acaba de escribir el usuario
            perfil: datos completos del UserProfile
            plan_activo: el NutritionPlan activo (puede ser None)
            protocolo: el ProtocoloNutricional activo (puede ser None)
            historial: lista de dicts [{rol, contenido}] — mensajes recientes

        Returns:
            La respuesta del asistente como string
        """
        system_prompt = self._construir_system_prompt(perfil, plan_activo, protocolo)
        mensajes = self._construir_mensajes(system_prompt, historial, mensaje_usuario)

        logger.info(
            "AssistantAgent: respondiendo a %s (%d mensajes en historial)",
            perfil.get("nombre", "usuario"),
            len(historial),
        )

        respuesta = self.llm.invoke(mensajes)
        return respuesta.content

    def _construir_system_prompt(
        self,
        perfil: dict,
        plan_activo: dict | None,
        protocolo: dict | None,
    ) -> str:
        """Rellena el template del prompt con los datos reales del usuario."""

        restricciones = ""
        if protocolo and protocolo.get("notas_dietista"):
            restricciones = f"Restricciones clínicas activas: {protocolo['notas_dietista']}"

        calorias = plan_activo.get("calorias_objetivo", "no generado") if plan_activo else "no generado"
        proteinas = plan_activo.get("proteinas_g", "-") if plan_activo else "-"
        carbos = plan_activo.get("carbos_g", "-") if plan_activo else "-"
        grasas = plan_activo.get("grasas_g", "-") if plan_activo else "-"

        alergias = perfil.get("alergias") or []
        alergias_str = ", ".join(alergias) if alergias else "ninguna"

        patologias = perfil.get("patologias") or []
        patologias_str = ", ".join(patologias) if patologias else "ninguna"

        return self.prompt_template.format(
            nombre=perfil.get("nombre", "usuario"),
            edad=perfil.get("edad", "-"),
            sexo=perfil.get("sexo", "-"),
            peso_kg=perfil.get("peso_kg", "-"),
            altura_cm=perfil.get("altura_cm", "-"),
            objetivo_principal=perfil.get("objetivo_principal", "-"),
            nivel_actividad=perfil.get("nivel_actividad", "-"),
            tipo_entrenamiento=perfil.get("tipo_entrenamiento", "-"),
            dias_entrenamiento=perfil.get("dias_entrenamiento", "-"),
            dieta_tipo=perfil.get("dieta_tipo", "-"),
            alergias=alergias_str,
            patologias=patologias_str,
            calorias_objetivo=calorias,
            proteinas_g=proteinas,
            carbos_g=carbos,
            grasas_g=grasas,
            restricciones_activas=restricciones,
        )

    def _construir_mensajes(
        self,
        system_prompt: str,
        historial: list[dict],
        mensaje_actual: str,
    ) -> list:
        """
        Construye la lista de mensajes para Groq:
        [System] + [historial alternado user/assistant] + [nuevo mensaje]
        """
        mensajes = [SystemMessage(content=system_prompt)]

        for msg in historial:
            if msg["rol"] == "user":
                mensajes.append(HumanMessage(content=msg["contenido"]))
            else:
                mensajes.append(AIMessage(content=msg["contenido"]))

        mensajes.append(HumanMessage(content=mensaje_actual))
        return mensajes

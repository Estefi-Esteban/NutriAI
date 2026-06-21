import re
import json
from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Optional
from backend.database.models import UserProfile
from backend.database.connection import SessionLocal
from backend.config import google_api_key
from backend.agents.prompts.prompt_loader import load_prompt
from backend.database.repositories.user_repository import guardar_perfil


"""
El agente mantiene memoria de la conversacion para no repetir preguntas y detectar incosistencias
Lo que vamos a hacer aqui es un agente que tiene que conversar con el usuario para recoger todos los datos de perfil, en un orden natural,
no como un formulario.

El flujo que seguira ser:
1. Saluda y pregunta el nombre
2. Pregunta el objetivo principal
3. Según el objetivo, ajusta las siguientes preguntas
4. Recoge datos biométricos
5. Recoge actividad física
6. Recoge preferencias y restricciones
7. Confirma todo con el usuario
8. Guarda en la tabla user_profiles
"""

SYSTEM_PROMPT = load_prompt("profile_prompt.md")

class ProfileAgent:

    def __init__(self):
        # Inicializamos el modelo Groq
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_api_key,
            temperature=0.7,
        )

        # Memoria de la conversación
        self.memory = ChatMessageHistory()

        # Estado del agente
        self.perfil_completo = False
        self.datos_perfil = None

    def _extraer_json(self, texto: str) -> dict | None:
        """
        Busca y extrae el JSON del mensaje de Gemini.
        Devuelve el dict si lo encuentra, None si no hay JSON todavía.
        """
        # Buscamos un bloque JSON en el texto
        patron = r'\{[\s\S]*"perfil_completo"[\s\S]*\}'
        match = re.search(patron, texto)

        if match:
            try:
                datos = json.loads(match.group())
                if datos.get("perfil_completo") is True:
                    return datos
            except json.JSONDecodeError:
                return None

        return None

    def _construir_mensajes(self, mensaje_usuario: str) -> list:
        """
        Construye la lista completa de mensajes para enviar a Gemini:
        [SystemMessage] + [historial] + [nuevo mensaje usuario]
        """
        mensajes = [SystemMessage(content=SYSTEM_PROMPT)]

        # Añadimos el historial de la memoria
        for msg in self.memory.messages:
            mensajes.append(msg)

        # Añadimos el nuevo mensaje del usuario
        mensajes.append(HumanMessage(content=mensaje_usuario))

        return mensajes

    def chat(self, mensaje_usuario: str) -> dict:
        """
        Método principal. Recibe el mensaje del usuario y devuelve
        la respuesta del agente.

        Devuelve un dict con:
        - respuesta: texto para mostrar al usuario
        - perfil_completo: True cuando ya tenemos todos los datos
        - datos: el perfil completo (solo cuando perfil_completo=True)
        """

        # Si ya terminamos, no seguimos
        if self.perfil_completo:
            return {
                "respuesta": "El perfil ya está completo. ¡Generando tu plan!",
                "perfil_completo": True,
                "datos": self.datos_perfil
            }

        # Construimos los mensajes con el historial
        mensajes = self._construir_mensajes(mensaje_usuario)

        # Llamamos a Gemini
        respuesta_llm = self.llm.invoke(mensajes)
        texto_respuesta = respuesta_llm.content

        # Guardamos en memoria
        self.memory.add_user_message(mensaje_usuario)
        self.memory.add_ai_message(texto_respuesta)

        # Comprobamos si Gemini ha devuelto el JSON final
        json_detectado = self._extraer_json(texto_respuesta)

        if json_detectado:
            self.perfil_completo = True
            self.datos_perfil = json_detectado.get("datos")

            # Limpiamos el JSON del texto para mostrar solo el mensaje bonito
            texto_limpio = texto_respuesta[:texto_respuesta.find("{")].strip()

            return {
                "respuesta": texto_limpio,
                "perfil_completo": True,
                "datos": self.datos_perfil
            }

        # Conversación normal, todavía recogiendo datos
        return {
            "respuesta": texto_respuesta,
            "perfil_completo": False,
            "datos": None
        }

    def reiniciar(self):
        """Reinicia el agente para empezar un perfil nuevo."""
        self.memory.clear()
        self.perfil_completo = False
        self.datos_perfil = None
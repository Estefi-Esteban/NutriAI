import re
import json
from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage
from backend.config import groq_api_key
from backend.agents.prompts.prompt_loader import load_prompt
from backend.utils.decorators import reintentar_llamada_llm

class FollowupAgent:
    def __init__(self, perfil_data: dict, plan_data: dict):
        """
        Agente de seguimiento nutricional semanal.
        Recibe el perfil del usuario y su plan activo para contextualizar el prompt del sistema.
        """
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_api_key,
            temperature=0.7,
        )
        self.memory = ChatMessageHistory()
        
        # Guardamos la info para formatear el prompt del sistema
        self.perfil_data = perfil_data
        self.plan_data = plan_data
        
        # Cargar y formatear prompt de sistema
        raw_prompt = load_prompt("followup_prompt.md")
        
        perfil_str = json.dumps(perfil_data, indent=2, ensure_ascii=False)
        plan_str = json.dumps(plan_data, indent=2, ensure_ascii=False)
        
        self.system_prompt = raw_prompt.replace("{perfil_usuario}", perfil_str).replace("{plan_nutricional}", plan_str)

    def _extraer_accion_json(self, texto: str) -> dict | None:
        """
        Busca y extrae un bloque JSON de acción al final de la respuesta.
        """
        patron = r'\{[\s\S]*"accion"[\s\S]*\}'
        match = re.search(patron, texto)
        
        if match:
            try:
                datos = json.loads(match.group())
                return datos
            except json.JSONDecodeError:
                return None
        return None

    @reintentar_llamada_llm(max_intentos=3, retardo_inicial=15.0, backoff=1.5)
    def _llamar_groq(self, mensajes: list) -> str:
        """Invoca el LLM de Groq con reintentos en caso de error."""
        respuesta = self.llm.invoke(mensajes)
        return respuesta.content

    def chat(self, mensaje_usuario: str) -> dict:
        """
        Procesa el mensaje del usuario.
        Devuelve un dict con:
        - respuesta: Texto limpio para mostrar al usuario.
        - accion: Nombre de la acción a ejecutar ("actualizar_perfil", "modificar_comida", "regenerar_plan") o None.
        - datos: Diccionario con los datos asociados a la acción o None.
        """
        mensajes = [SystemMessage(content=self.system_prompt)]
        
        # Historial de mensajes
        for msg in self.memory.messages:
            mensajes.append(msg)
            
        mensajes.append(HumanMessage(content=mensaje_usuario))
        
        # Invocar LLM con reintentos
        texto_respuesta = self._llamar_groq(mensajes)
        
        # Guardar en memoria de conversación
        self.memory.add_user_message(mensaje_usuario)
        self.memory.add_ai_message(texto_respuesta)
        
        # Buscar acciones estructuradas
        accion_json = self._extraer_accion_json(texto_respuesta)
        
        if accion_json:
            # Limpiar la respuesta cortando el JSON para que el usuario no vea código crudo
            idx_json = texto_respuesta.find("{")
            texto_limpio = texto_respuesta[:idx_json].strip()
            
            # En caso de que se haya cortado todo el mensaje por error
            if not texto_limpio:
                texto_limpio = "Perfecto, procedo a realizar el ajuste solicitado."
                
            return {
                "respuesta": texto_limpio,
                "accion": accion_json.get("accion"),
                "datos": accion_json.get("datos")
            }
            
        return {
            "respuesta": texto_respuesta,
            "accion": None,
            "datos": None
        }

    def reiniciar(self):
        """Reinicia la memoria del chat de seguimiento."""
        self.memory.clear()

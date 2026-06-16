"""
app.py — NutriAI Frontend
=========================
Streamlit app con 3 flujos:
  1. Chat conversacional con el ProfileAgent para recoger el perfil.
  2. Generación del plan semanal (Nutricionista + Dietista, 7 días).
  3. Vista del plan: menú semanal y lista de la compra.

Ejecución:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import sys
import os
import time
import json

import streamlit as st

# ─── Asegurar que el raíz del proyecto esté en el path ───────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.agents.profile_agent import ProfileAgent
from backend.agents.nutrition_agent import NutritionAgent
from backend.agents.dietist_agent import DietistAgent, DIAS_SEMANA
from backend.utils.nutrition_calculator import calcular_todo
from backend.utils.shopping_list_generator import generar_lista_compra
from backend.database.connection import SessionLocal
from backend.database.repositories.user_repository import crear_usuario, guardar_perfil
from backend.database.repositories.plan_repository import guardar_plan, obtener_plan_activo
from sqlalchemy.exc import IntegrityError
from backend.database.models import User

# ─── Configuración de página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="NutriAI — Tu nutricionista inteligente",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS personalizado ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Fondo general */
.stApp {
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
    min-height: 100vh;
}

/* Header principal */
.hero-title {
    font-size: 3rem;
    font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.25rem;
    text-align: center;
}

.hero-subtitle {
    font-size: 1.1rem;
    color: #8892b0;
    text-align: center;
    margin-bottom: 2rem;
}

/* Cards glassmorphism */
.glass-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 1.5rem;
    backdrop-filter: blur(10px);
    margin-bottom: 1rem;
}

/* Badges de macros */
.macro-badge {
    display: inline-block;
    background: rgba(102, 126, 234, 0.2);
    border: 1px solid rgba(102, 126, 234, 0.4);
    border-radius: 20px;
    padding: 0.25rem 0.75rem;
    font-size: 0.85rem;
    font-weight: 500;
    color: #a8b4ff;
    margin-right: 0.5rem;
    margin-bottom: 0.5rem;
}

.macro-badge.prot  { background: rgba(248, 113, 113, 0.15); border-color: rgba(248,113,113,0.4); color: #fca5a5; }
.macro-badge.carb  { background: rgba(251, 191, 36, 0.15);  border-color: rgba(251,191,36,0.4);  color: #fde68a; }
.macro-badge.fat   { background: rgba(52, 211, 153, 0.15);  border-color: rgba(52,211,153,0.4);  color: #6ee7b7; }
.macro-badge.kcal  { background: rgba(167, 139, 250, 0.15); border-color: rgba(167,139,250,0.4); color: #c4b5fd; }

/* Chips de categoría */
.category-header {
    font-size: 1rem;
    font-weight: 600;
    color: #ccd6f6;
    margin: 1.25rem 0 0.5rem 0;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

/* Item de lista de la compra */
.shopping-item {
    display: flex;
    justify-content: space-between;
    padding: 0.4rem 0.6rem;
    border-radius: 8px;
    font-size: 0.9rem;
    color: #a8b2d8;
    transition: background 0.15s;
}
.shopping-item:hover { background: rgba(255,255,255,0.04); }
.shopping-item .qty  { color: #667eea; font-weight: 500; }

/* Pasos de receta */
.step-item {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
    align-items: flex-start;
}
.step-num {
    min-width: 24px;
    height: 24px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    color: white;
    flex-shrink: 0;
}
.step-text { color: #a8b2d8; font-size: 0.9rem; line-height: 1.5; }

/* Indicador de progreso chat */
.progress-dots {
    display: flex;
    gap: 8px;
    justify-content: center;
    margin: 1rem 0;
}
.dot { width:10px; height:10px; border-radius:50%; }
.dot.done { background:#667eea; }
.dot.active { background:#f093fb; animation: pulse 1.5s infinite; }
.dot.pending { background:rgba(255,255,255,0.15); }
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }

/* Botones personalizados */
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    padding: 0.6rem 1.5rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* Chat bubbles */
.chat-user {
    background: rgba(102, 126, 234, 0.15);
    border: 1px solid rgba(102,126,234,0.3);
    border-radius: 12px 12px 2px 12px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    margin-left: 20%;
    color: #ccd6f6;
    font-size: 0.95rem;
}
.chat-ai {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 12px 12px 12px 2px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    margin-right: 20%;
    color: #e6f1ff;
    font-size: 0.95rem;
}
.chat-sender { font-size: 0.75rem; font-weight: 600; margin-bottom: 0.25rem; }
.chat-sender.user { color: #667eea; text-align: right; }
.chat-sender.ai   { color: #f093fb; }

/* Métricas */
.metric-box {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 12px;
    padding: 1rem;
    text-align: center;
}
.metric-value { font-size: 1.8rem; font-weight: 700; color: #ccd6f6; }
.metric-label { font-size: 0.8rem; color: #8892b0; margin-top: 0.25rem; }

/* Tabs */
div[data-testid="stTabs"] button {
    font-weight: 600 !important;
    color: #8892b0 !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #ccd6f6 !important;
    border-bottom-color: #667eea !important;
}

/* Inputs */
.stTextInput > div > div > input, .stTextArea textarea {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 10px !important;
    color: #e6f1ff !important;
}

/* Divider */
hr { border-color: rgba(255,255,255,0.08) !important; }
</style>
""", unsafe_allow_html=True)


# ─── Session state inicial ────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "pagina": "inicio",        # inicio | chat | generando | plan
        "profile_agent": None,
        "chat_history": [],        # [{role: user|ai, text: str}]
        "perfil": None,
        "calculos": None,
        "analisis": None,
        "menu_semana": None,
        "lista_compra": None,
        "user_id": None,
        "plan_id": None,
        "dia_seleccionado": "Lunes",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _macro_badges(kcal, prot, carb, fat):
    return (
        f'<span class="macro-badge kcal">🔥 {kcal} kcal</span>'
        f'<span class="macro-badge prot">🥩 {prot}g prot</span>'
        f'<span class="macro-badge carb">🌾 {carb}g carb</span>'
        f'<span class="macro-badge fat">🥑 {fat}g grasa</span>'
    )

def _dificultad_emoji(d):
    return {"facil": "🟢", "media": "🟡", "avanzada": "🔴"}.get(str(d).lower(), "⚪")

def _ir_a(pagina):
    st.session_state.pagina = pagina
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: INICIO
# ═══════════════════════════════════════════════════════════════════════════════

def pagina_inicio():
    st.markdown('<div class="hero-title">🥗 NutriAI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Tu nutricionista y dietista inteligente.<br>'
        'Un plan personalizado de 7 días en minutos.</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("### ¿Cómo funciona?")
        st.markdown("""
        **1. 💬 Chat con tu nutricionista** — Te hacemos unas preguntas sobre tu objetivo, 
        cuerpo y hábitos. Nada de formularios aburridos.
        
        **2. 🧠 Análisis clínico** — Calculamos tus calorías, proteínas, carbos y grasas 
        exactas para tu objetivo.
        
        **3. 🍽️ Menú semanal completo** — 7 días de comidas reales con recetas, 
        ingredientes y tiempos de preparación.
        
        **4. 🛒 Lista de la compra** — Todo lo que necesitas comprar esta semana, 
        organizado por categorías.
        """)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✨ Empezar mi plan personalizado", use_container_width=True):
            # Iniciar el agente de perfil
            st.session_state.profile_agent = ProfileAgent()
            st.session_state.chat_history = []
            # Primera pregunta automática
            primer_mensaje = st.session_state.profile_agent.chat("Hola")
            st.session_state.chat_history.append({
                "role": "ai",
                "text": primer_mensaje["respuesta"]
            })
            _ir_a("chat")

        st.markdown("<br>", unsafe_allow_html=True)

    # Características
    c1, c2, c3, c4 = st.columns(4)
    features = [
        ("🧬", "Personalizado", "Basado en tu perfil real"),
        ("⚡", "7 días completos", "Desayuno, comida y cena"),
        ("💰", "Respetuoso con tu bolsillo", "Ingredientes económicos"),
        ("⏱️", "Recetas rápidas", "Adaptadas a tu tiempo"),
    ]
    for col, (icon, title, desc) in zip([c1, c2, c3, c4], features):
        with col:
            st.markdown(
                f'<div class="metric-box">'
                f'<div style="font-size:2rem">{icon}</div>'
                f'<div style="font-weight:600;color:#ccd6f6;margin-top:.5rem">{title}</div>'
                f'<div style="color:#8892b0;font-size:.85rem;margin-top:.25rem">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: CHAT DE PERFIL
# ═══════════════════════════════════════════════════════════════════════════════

def pagina_chat():
    st.markdown('<div class="hero-title" style="font-size:2rem">💬 Cuéntame sobre ti</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle" style="margin-bottom:1rem">'
        'Responde con naturalidad, como si hablaras con tu nutricionista</div>',
        unsafe_allow_html=True,
    )

    # Historial de chat
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "ai":
                st.markdown(
                    f'<div class="chat-sender ai">🤖 NutriAI</div>'
                    f'<div class="chat-ai">{msg["text"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="chat-sender user">Tú 👤</div>'
                    f'<div class="chat-user">{msg["text"]}</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<br>", unsafe_allow_html=True)

    # Input del usuario
    agent = st.session_state.profile_agent
    if agent and not agent.perfil_completo:
        with st.form("chat_form", clear_on_submit=True):
            col_input, col_btn = st.columns([5, 1])
            with col_input:
                texto = st.text_input(
                    "Tu respuesta",
                    label_visibility="collapsed",
                    placeholder="Escribe tu respuesta aquí...",
                )
            with col_btn:
                enviado = st.form_submit_button("Enviar →")

        if enviado and texto.strip():
            # Añadir mensaje del usuario al historial
            st.session_state.chat_history.append({"role": "user", "text": texto})

            # Llamar al agente
            with st.spinner(""):
                resultado = agent.chat(texto)

            # Añadir respuesta al historial
            st.session_state.chat_history.append({
                "role": "ai",
                "text": resultado["respuesta"]
            })

            # Perfil completo → ir a generación
            if resultado["perfil_completo"]:
                st.session_state.perfil = resultado["datos"]
                _ir_a("generando")
            else:
                st.rerun()

    # Botón de reinicio
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("↩ Volver al inicio", type="secondary"):
        _ir_a("inicio")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: GENERANDO EL PLAN
# ═══════════════════════════════════════════════════════════════════════════════

def pagina_generando():
    st.markdown('<div class="hero-title" style="font-size:2rem">⚙️ Generando tu plan</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-subtitle">Estamos calculando tus macros y preparando 7 días de menú...</div>',
        unsafe_allow_html=True,
    )

    perfil = st.session_state.perfil
    if perfil is None:
        st.error("No se encontró perfil. Vuelve al chat.")
        if st.button("↩ Volver"):
            _ir_a("inicio")
        return

    placeholder = st.empty()

    def _status(msg: str, progress: int):
        with placeholder.container():
            st.progress(progress / 100, text=msg)

    try:
        # PASO 1: Cálculos
        _status("🔢 Calculando tus calorías y macros...", 10)
        calculos = calcular_todo(perfil).to_dict()
        st.session_state.calculos = calculos
        time.sleep(0.3)

        # PASO 2: Nutricionista
        _status("🧑‍⚕️ Analizando tu perfil clínico...", 25)
        analisis = NutritionAgent().analizar(perfil=perfil, calculos=calculos)
        st.session_state.analisis = analisis
        time.sleep(0.3)

        # PASO 3: Dietista — 7 días
        dietist = DietistAgent()
        menu_semana: dict = {}
        comidas_previas: list[str] = []
        PAUSA = 7  # segundos entre días

        for i, dia in enumerate(DIAS_SEMANA):
            pct = 30 + int(i * 8)
            _status(f"🍽️ Creando el menú del {dia}... ({i+1}/7)", pct)
            menu_dia = dietist.generar_dia(
                perfil=perfil,
                calculos=calculos,
                analisis=analisis,
                dia_semana=dia,
                comidas_previas=comidas_previas,
            )
            menu_semana[dia] = menu_dia
            nuevos = [
                v["nombre"] for v in menu_dia.get("comidas", {}).values()
                if isinstance(v, dict) and "nombre" in v
            ]
            comidas_previas.extend(nuevos)
            if i < len(DIAS_SEMANA) - 1:
                time.sleep(PAUSA)

        st.session_state.menu_semana = menu_semana

        # PASO 4: Lista de la compra
        _status("🛒 Generando tu lista de la compra...", 90)
        lista = generar_lista_compra(menu_semana)
        st.session_state.lista_compra = lista
        time.sleep(0.3)

        # PASO 5: Guardar en BD
        _status("💾 Guardando tu plan...", 96)
        nombre = perfil.get("nombre", "Usuario")
        email  = f"{nombre.lower().replace(' ', '.')}.nutriai@nutriai.com"

        with SessionLocal() as db:
            try:
                usuario = crear_usuario(db, nombre=nombre, email=email)
                user_id = int(usuario.id)
            except IntegrityError:
                db.rollback()
                usuario = db.query(User).filter(User.email == email).first()
                user_id = int(usuario.id)

            guardar_perfil(db, user_id=user_id, datos={
                **perfil,
                "presupuesto_semanal": perfil.get("presupuesto_semanal_eur", perfil.get("presupuesto_semanal")),
            })
            plan = guardar_plan(db, user_id=user_id, calculos=calculos, menu_semana=menu_semana)
            st.session_state.user_id = user_id
            st.session_state.plan_id = int(plan.id)

        _status("✅ ¡Plan listo!", 100)
        time.sleep(0.5)
        placeholder.empty()
        _ir_a("plan")

    except Exception as exc:
        placeholder.empty()
        st.error(f"❌ Error generando el plan: {exc}")
        if st.button("↩ Volver al inicio"):
            _ir_a("inicio")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: PLAN SEMANAL
# ═══════════════════════════════════════════════════════════════════════════════

def pagina_plan():
    perfil   = st.session_state.perfil or {}
    calculos = st.session_state.calculos or {}
    menu     = st.session_state.menu_semana or {}
    lista    = st.session_state.lista_compra or {}

    nombre = perfil.get("nombre", "")

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div class="hero-title" style="font-size:2.2rem">🥗 Tu plan semanal{", " + nombre if nombre else ""}</div>',
        unsafe_allow_html=True,
    )

    macros = calculos.get("macros", {})
    kcal   = round(calculos.get("calorias_objetivo", 0))
    prot   = round(macros.get("proteinas_g", 0))
    carb   = round(macros.get("carbos_g", 0))
    fat    = round(macros.get("grasas_g", 0))

    st.markdown(
        f'<div style="text-align:center;margin-bottom:1.5rem">{_macro_badges(kcal, prot, carb, fat)}</div>',
        unsafe_allow_html=True,
    )

    # ── Tabs principales ──────────────────────────────────────────────────────
    tab_menu, tab_lista = st.tabs(["🍽️ Menú semanal", "🛒 Lista de la compra"])

    # ════════ TAB 1: MENÚ ════════
    with tab_menu:
        if not menu:
            st.info("No hay menú generado aún.")
            return

        # Selector de día
        dia_sel = st.radio(
            "Selecciona el día",
            options=DIAS_SEMANA,
            horizontal=True,
            index=DIAS_SEMANA.index(st.session_state.dia_seleccionado),
            label_visibility="collapsed",
        )
        st.session_state.dia_seleccionado = dia_sel

        menu_dia = menu.get(dia_sel, {})
        totales  = menu_dia.get("totales_dia", {})

        # Totales del día
        st.markdown("<br>", unsafe_allow_html=True)
        col_t = st.columns(4)
        for col, (label, val, unit) in zip(col_t, [
            ("Calorías", totales.get("calorias", "—"), "kcal"),
            ("Proteínas", totales.get("proteinas_g", "—"), "g"),
            ("Carbos", totales.get("carbos_g", "—"), "g"),
            ("Grasas", totales.get("grasas_g", "—"), "g"),
        ]):
            with col:
                st.markdown(
                    f'<div class="metric-box">'
                    f'<div class="metric-value">{val}</div>'
                    f'<div class="metric-label">{label} ({unit})</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<br>", unsafe_allow_html=True)

        # Comidas del día
        TOMAS = [
            ("desayuno",     "☀️ Desayuno"),
            ("media_manana", "🍎 Media mañana"),
            ("comida",       "🍽️ Comida"),
            ("merienda",     "🫐 Merienda"),
            ("cena",         "🌙 Cena"),
        ]
        comidas = menu_dia.get("comidas", {})

        for key, label in TOMAS:
            comida = comidas.get(key, {})
            if not comida:
                continue

            with st.expander(
                f"{label} — **{comida.get('nombre', '')}**  "
                f"({comida.get('calorias', '—')} kcal · "
                f"{_dificultad_emoji(comida.get('dificultad', ''))} "
                f"{comida.get('dificultad', '')} · "
                f"⏱️ {comida.get('tiempo_preparacion_min', '—')} min)",
                expanded=(key == "desayuno"),
            ):
                col_izq, col_der = st.columns([1, 1])

                # Ingredientes
                with col_izq:
                    st.markdown("**🧺 Ingredientes**")
                    for ing in comida.get("ingredientes", []):
                        st.markdown(
                            f"- {ing.get('nombre', '')} — "
                            f"**{ing.get('cantidad', '')} {ing.get('unidad', '')}**"
                        )

                    sust = comida.get("sustituciones", {})
                    if sust:
                        st.markdown("**🔄 Sustituciones**")
                        for orig, alt in sust.items():
                            st.markdown(f"- ~~{orig}~~ → {alt}")

                # Pasos
                with col_der:
                    st.markdown("**📋 Preparación**")
                    pasos_html = ""
                    for i, paso in enumerate(comida.get("pasos", []), 1):
                        pasos_html += (
                            f'<div class="step-item">'
                            f'<div class="step-num">{i}</div>'
                            f'<div class="step-text">{paso}</div>'
                            f'</div>'
                        )
                    st.markdown(pasos_html, unsafe_allow_html=True)

                # Macros de la comida
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    _macro_badges(
                        comida.get("calorias", "—"),
                        comida.get("proteinas_g", "—"),
                        comida.get("carbos_g", "—"),
                        comida.get("grasas_g", "—"),
                    ),
                    unsafe_allow_html=True,
                )

    # ════════ TAB 2: LISTA DE LA COMPRA ════════
    with tab_lista:
        if not lista:
            st.info("No hay lista de la compra generada aún.")
            return

        total_items = sum(len(v) for v in lista.values())
        st.markdown(
            f'<div style="color:#8892b0;margin-bottom:1.5rem">'
            f'📦 {total_items} ingredientes · {len(lista)} categorías</div>',
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns(2)
        cats = list(lista.items())
        mitad = (len(cats) + 1) // 2

        for col, bloque in [(col_a, cats[:mitad]), (col_b, cats[mitad:])]:
            with col:
                for categoria, items in bloque:
                    st.markdown(
                        f'<div class="category-header">{categoria}</div>',
                        unsafe_allow_html=True,
                    )
                    filas_html = ""
                    for item in items:
                        filas_html += (
                            f'<div class="shopping-item">'
                            f'<span>{item["nombre"]}</span>'
                            f'<span class="qty">{item["cantidad_total"]} {item["unidad"]}</span>'
                            f'</div>'
                        )
                    st.markdown(filas_html, unsafe_allow_html=True)

        # Botón de exportación
        st.markdown("<br>", unsafe_allow_html=True)
        lista_texto = "🛒 LISTA DE LA COMPRA — NutriAI\n" + "=" * 40 + "\n\n"
        for categoria, items in lista.items():
            lista_texto += f"\n{categoria}\n" + "-" * 30 + "\n"
            for item in items:
                lista_texto += f"  • {item['nombre']}: {item['cantidad_total']} {item['unidad']}\n"

        st.download_button(
            label="⬇️ Descargar lista (.txt)",
            data=lista_texto,
            file_name="lista_compra_nutriai.txt",
            mime="text/plain",
        )

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown("<br><hr>", unsafe_allow_html=True)
    if st.button("🔄 Crear un plan nuevo"):
        for k in ["profile_agent", "chat_history", "perfil", "calculos",
                  "analisis", "menu_semana", "lista_compra", "user_id", "plan_id"]:
            st.session_state[k] = None
        st.session_state.chat_history = []
        _ir_a("inicio")


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

pagina = st.session_state.pagina

if pagina == "inicio":
    pagina_inicio()
elif pagina == "chat":
    pagina_chat()
elif pagina == "generando":
    pagina_generando()
elif pagina == "plan":
    pagina_plan()
else:
    _ir_a("inicio")

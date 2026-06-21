"""
app.py — NutriAI Frontend
=========================
Streamlit app que consume la API REST de FastAPI con JWT para:
  1. Autenticación (Login / Registro)
  2. Chat conversacional con el ProfileAgent para recoger el perfil.
  3. Generación del plan semanal en segundo plano (con polling).
  4. Vista del plan: menú semanal y lista de la compra.

Ejecución:
    streamlit run frontend/app.py
"""

from __future__ import annotations

import os
import time
import requests
import streamlit as st
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ─── Configuración global de la API ──────────────────────────────────────────
API_URL = "http://localhost:8000"

# Credenciales de Google OAuth
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:8501" # Puerto estándar de Streamlit

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

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
        "pagina": "login",         # login | registro | inicio | chat | generando | plan
        "token": None,
        "user_info": None,         # {"nombre": str, "email": str}
        "chat_history": [],        # [{role: user|ai, text: str}]
        "perfil": None,
        "calculos": None,
        "menu_semana": None,
        "lista_compra": None,
        "user_id": None,
        "plan_id": None,
        "dia_seleccionado": "Lunes",
        "tarea_id": None,
        "followup_chat_history": [],
        "followup_iniciado": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_headers() -> dict:
    headers = {}
    if st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    return headers

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


# ─── Sidebar de usuario ──────────────────────────────────────────────────────
if st.session_state.token and st.session_state.user_info:
    with st.sidebar:
        st.markdown("### 👤 Mi Perfil")
        st.write(f"**Nombre:** {st.session_state.user_info.get('nombre')}")
        st.write(f"**Email:** {st.session_state.user_info.get('email')}")
        st.markdown("---")
        
        if st.session_state.menu_semana:
            if st.button("🍽️ Ver mi Plan Activo", use_container_width=True):
                _ir_a("plan")
                
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            # Limpiar todo el estado de sesión
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            _init_state()
            _ir_a("login")


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: LOGIN
# ═══════════════════════════════════════════════════════════════════════════════

def pagina_login():
    st.markdown('<div class="hero-title">🥗 NutriAI</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Tu nutricionista y dietista inteligente.<br>Inicia sesión para continuar.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Iniciar Sesión</h3>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            email = st.text_input("Correo electrónico", placeholder="correo@ejemplo.com")
            password = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            
        if submitted:
            if not email.strip() or not password.strip():
                st.error("Por favor, introduce tu email y contraseña.")
            else:
                try:
                    with st.spinner("Iniciando sesión..."):
                        res = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.user_id = data["user_id"]
                        
                        # Obtener información del perfil de usuario
                        res_me = requests.get(f"{API_URL}/usuarios/me", headers=get_headers())
                        if res_me.status_code == 200:
                            st.session_state.user_info = res_me.json()
                            
                        # Verificar si cuenta con un plan activo
                        with st.spinner("Buscando plan activo..."):
                            res_plan = requests.get(f"{API_URL}/planes/activo", headers=get_headers())
                        if res_plan.status_code == 200:
                            plan_data = res_plan.json()
                            st.session_state.plan_id = plan_data.get("plan_id")
                            st.session_state.calculos = {
                                "calorias_objetivo": plan_data.get("calorias_objetivo"),
                                "macros": {
                                    "proteinas_g": plan_data.get("proteinas_g"),
                                    "carbos_g": plan_data.get("carbos_g"),
                                    "grasas_g": plan_data.get("grasas_g")
                                }
                            }
                            st.session_state.menu_semana = plan_data.get("plan_semanal")
                            
                            # Intentar cargar la lista de la compra asociada
                            res_lista = requests.get(f"{API_URL}/lista-compra", headers=get_headers())
                            if res_lista.status_code == 200:
                                st.session_state.lista_compra = res_lista.json().get("categorias")
                            
                            _ir_a("plan")
                        else:
                            _ir_a("inicio")
                    else:
                        st.error(f"Error: {res.json().get('detail', 'Credenciales incorrectas')}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
                    
        # Divisor y Botones de Google
        st.markdown("<div style='text-align: center; margin: 10px 0; color: #8892b0;'>ó</div>", unsafe_allow_html=True)
        
        google_url = f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={GOOGLE_CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=openid%20email%20profile"
        
        google_button_html = f"""
        <a href="{google_url}" target="_self" style="text-decoration: none;">
            <div style="
                display: flex;
                align-items: center;
                justify-content: center;
                background-color: #ffffff;
                color: #1f1f1f;
                border: 1px solid #dadce0;
                border-radius: 12px;
                padding: 0.65rem 1.5rem;
                font-family: 'Inter', sans-serif;
                font-weight: 600;
                font-size: 0.95rem;
                cursor: pointer;
                transition: background-color 0.2s, box-shadow 0.2s;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08);
                width: 100%;
                text-align: center;
                box-sizing: border-box;
                margin-bottom: 10px;
            " onmouseover="this.style.backgroundColor='#f8f9fa'; this.style.boxShadow='0 2px 6px rgba(0,0,0,0.12)';" 
               onmouseout="this.style.backgroundColor='#ffffff'; this.style.boxShadow='0 1px 3px rgba(0,0,0,0.08)';">
                <svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="18px" height="18px" viewBox="0 0 48 48" style="margin-right: 10px; display: block;">
                    <g>
                        <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"></path>
                        <path fill="#4285F4" d="M46.5 24c0-1.61-.15-3.16-.42-4.69H24v9.09h12.75c-.55 2.87-2.18 5.3-4.63 6.93l7.26 5.62C43.68 36.81 46.5 31.02 46.5 24z"></path>
                        <path fill="#FBBC05" d="M10.54 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.98-6.19z"></path>
                        <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.26-5.62c-2.03 1.37-4.63 2.18-8.63 2.18-6.26 0-11.57-4.22-13.46-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
                        <polygon points="0 0 48 0 48 48 0 48" fill="none"></polygon>
                    </g>
                </svg>
                Entrar con Google
            </div>
        </a>
        """
        st.markdown(google_button_html, unsafe_allow_html=True)
        
        if st.button("🔑 Simular Google Sign-In (Desarrollo)", use_container_width=True):
            try:
                with st.spinner("Simulando inicio de sesión con Google..."):
                    res = requests.post(f"{API_URL}/auth/login", json={
                        "email": "google.test.user@nutriai.com",
                        "password": "GoogleTestUserPassword123!"
                    })
                    if res.status_code != 200:
                        res_reg = requests.post(f"{API_URL}/auth/registro", json={
                            "nombre": "Marta Google Test",
                            "email": "google.test.user@nutriai.com",
                            "password": "GoogleTestUserPassword123!"
                        })
                        if res_reg.status_code == 200:
                            res = requests.post(f"{API_URL}/auth/login", json={
                                "email": "google.test.user@nutriai.com",
                                "password": "GoogleTestUserPassword123!"
                            })
                            
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.user_id = data["user_id"]
                    st.session_state.user_info = {
                        "id": data["user_id"],
                        "nombre": "Marta Google Test (Simulado)",
                        "email": "google.test.user@nutriai.com",
                        "auth_provider": "google"
                    }
                    
                    # Verificar si cuenta con un plan activo
                    res_plan = requests.get(f"{API_URL}/planes/activo", headers=get_headers())
                    if res_plan.status_code == 200:
                        plan_data = res_plan.json()
                        st.session_state.plan_id = plan_data.get("plan_id")
                        st.session_state.calculos = {
                            "calorias_objetivo": plan_data.get("calorias_objetivo"),
                            "macros": {
                                "proteinas_g": plan_data.get("proteinas_g"),
                                "carbos_g": plan_data.get("carbos_g"),
                                "grasas_g": plan_data.get("grasas_g")
                            }
                        }
                        st.session_state.menu_semana = plan_data.get("plan_semanal")
                        
                        res_lista = requests.get(f"{API_URL}/lista-compra", headers=get_headers())
                        if res_lista.status_code == 200:
                            st.session_state.lista_compra = res_lista.json().get("categorias")
                        _ir_a("plan")
                    else:
                        _ir_a("inicio")
                else:
                    st.error("Error al simular autenticación.")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.write("¿No tienes una cuenta aún?")
        if st.button("Crear una cuenta nueva", use_container_width=True):
            _ir_a("registro")
        st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PÁGINA: REGISTRO
# ═══════════════════════════════════════════════════════════════════════════════

def pagina_registro():
    st.markdown('<div class="hero-title">🥗 NutriAI</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Únete a NutriAI y empieza a comer sano hoy mismo.</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Crear Cuenta</h3>", unsafe_allow_html=True)
        
        with st.form("registro_form"):
            nombre = st.text_input("Nombre completo", placeholder="Tu nombre")
            email = st.text_input("Correo electrónico", placeholder="correo@ejemplo.com")
            password = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Registrarse", use_container_width=True)
            
        if submitted:
            if not nombre.strip() or not email.strip() or not password.strip():
                st.error("Por favor, completa todos los campos.")
            elif len(password) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            else:
                try:
                    with st.spinner("Registrando cuenta..."):
                        res = requests.post(f"{API_URL}/auth/registro", json={
                            "nombre": nombre,
                            "email": email,
                            "password": password
                        })
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.token = data["access_token"]
                        st.session_state.user_id = data["user_id"]
                        
                        # Obtener información básica de usuario
                        res_me = requests.get(f"{API_URL}/usuarios/me", headers=get_headers())
                        if res_me.status_code == 200:
                            st.session_state.user_info = res_me.json()
                            
                        st.success("¡Cuenta registrada con éxito!")
                        time.sleep(1)
                        _ir_a("inicio")
                    else:
                        st.error(f"Error: {res.json().get('detail', 'El correo ya está registrado')}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
                    
        st.markdown("<hr>", unsafe_allow_html=True)
        st.write("¿Ya tienes una cuenta registrada?")
        if st.button("Iniciar Sesión", use_container_width=True):
            _ir_a("login")
        st.markdown('</div>', unsafe_allow_html=True)


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
            st.session_state.chat_history = []
            try:
                with st.spinner("Iniciando chat con NutriAI..."):
                    res = requests.post(f"{API_URL}/chat/iniciar", headers=get_headers())
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.chat_history.append({
                        "role": "ai",
                        "text": data["respuesta"]
                    })
                    _ir_a("chat")
                else:
                    st.error(f"Error al iniciar chat: {res.text}")
            except Exception as e:
                st.error(f"Error de conexión con la API: {e}")

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

        # Llamar al agente en la API
        try:
            with st.spinner("NutriAI está pensando..."):
                res = requests.post(
                    f"{API_URL}/chat/mensaje",
                    json={"session_id": "ignorado", "mensaje": texto},
                    headers=get_headers()
                )
            if res.status_code == 200:
                resultado = res.json()
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
            else:
                st.error(f"Error al enviar mensaje: {res.text}")
        except Exception as e:
            st.error(f"Error de conexión con la API: {e}")

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

    # Iniciar generación si no hay tarea_id
    if not st.session_state.tarea_id:
        try:
            _status("🚀 Iniciando generación en segundo plano...", 5)
            res = requests.post(
                f"{API_URL}/planes/generar",
                json={"perfil": perfil},
                headers=get_headers()
            )
            if res.status_code == 200:
                st.session_state.tarea_id = res.json()["tarea_id"]
                _status("Tarea iniciada...", 10)
            else:
                st.error(f"Error al iniciar generación: {res.text}")
                if st.button("↩ Volver al inicio"):
                    _ir_a("inicio")
                return
        except Exception as e:
            st.error(f"Error al conectar con la API: {e}")
            if st.button("↩ Volver al inicio"):
                _ir_a("inicio")
            return

    # Polling de la tarea
    tarea_id = st.session_state.tarea_id
    error_ocurrido = False

    try:
        while True:
            res_estado = requests.get(f"{API_URL}/planes/estado/{tarea_id}", headers=get_headers())
            if res_estado.status_code == 200:
                estado_data = res_estado.json()
                progreso = estado_data.get("progreso", 0)
                estado = estado_data.get("estado", "iniciado")
                dia_actual = estado_data.get("dia_actual")
                error = estado_data.get("error")

                if estado == "error" or error:
                    st.error(f"❌ Error en la generación: {error or 'Error desconocido'}")
                    error_ocurrido = True
                    break
                elif estado == "completado":
                    _status("🎉 ¡Plan generado exitosamente!", 100)
                    time.sleep(1)
                    break
                else:
                    msg_prog = f"Generando plan... {progreso}%"
                    if dia_actual:
                        msg_prog += f" (Creando menú de: {dia_actual})"
                    _status(msg_prog, progreso)
            else:
                st.error(f"Error al verificar estado: {res_estado.text}")
                error_ocurrido = True
                break

            time.sleep(3)

        if error_ocurrido:
            st.session_state.tarea_id = None
            if st.button("↩ Volver al inicio"):
                _ir_a("inicio")
            return

        # Cargar plan y lista
        _status("📂 Cargando tu plan nutricional y lista de compra...", 95)
        
        res_plan = requests.get(f"{API_URL}/planes/activo", headers=get_headers())
        if res_plan.status_code == 200:
            plan_data = res_plan.json()
            st.session_state.plan_id = plan_data.get("plan_id")
            st.session_state.calculos = {
                "calorias_objetivo": plan_data.get("calorias_objetivo"),
                "macros": {
                    "proteinas_g": plan_data.get("proteinas_g"),
                    "carbos_g": plan_data.get("carbos_g"),
                    "grasas_g": plan_data.get("grasas_g")
                }
            }
            st.session_state.menu_semana = plan_data.get("plan_semanal")
        else:
            st.error("No se pudo obtener el plan activo.")
            
        res_lista = requests.get(f"{API_URL}/lista-compra", headers=get_headers())
        if res_lista.status_code == 200:
            st.session_state.lista_compra = res_lista.json().get("categorias")
        else:
            st.error("No se pudo obtener la lista de compra.")

        st.session_state.tarea_id = None
        placeholder.empty()
        _ir_a("plan")

    except Exception as exc:
        st.session_state.tarea_id = None
        placeholder.empty()
        st.error(f"❌ Error durante el polling del plan: {exc}")
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

    nombre = st.session_state.user_info.get("nombre", "") if st.session_state.user_info else ""

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
    tab_menu, tab_lista, tab_seguimiento = st.tabs(["🍽️ Menú semanal", "🛒 Lista de la compra", "💬 Seguimiento Semanal"])

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

    # ════════ TAB 3: SEGUIMIENTO SEMANAL ════════
    with tab_seguimiento:
        if not st.session_state.followup_iniciado:
            try:
                with st.spinner("Conectando con el asistente de seguimiento..."):
                    res = requests.post(f"{API_URL}/chat/seguimiento/iniciar", headers=get_headers())
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.followup_chat_history = [{
                        "role": "ai",
                        "text": data["respuesta"]
                    }]
                    st.session_state.followup_iniciado = True
                    st.rerun()
                else:
                    st.error(f"Error al iniciar chat de seguimiento: {res.text}")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

        # Mostrar historial de chat
        chat_followup_container = st.container()
        with chat_followup_container:
            for msg in st.session_state.followup_chat_history:
                if msg["role"] == "ai":
                    st.markdown(
                        f'<div class="chat-sender ai">🤖 NutriAI (Seguimiento)</div>'
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

        # Enviar mensaje
        with st.form("followup_form", clear_on_submit=True):
            col_input, col_btn = st.columns([5, 1])
            with col_input:
                texto_f = st.text_input(
                    "Tu mensaje",
                    label_visibility="collapsed",
                    placeholder="Cuéntale a NutriAI cómo te ha ido o qué quieres cambiar...",
                )
            with col_btn:
                enviado_f = st.form_submit_button("Enviar →")

        if enviado_f and texto_f.strip():
            st.session_state.followup_chat_history.append({"role": "user", "text": texto_f})

            try:
                with st.spinner("Procesando..."):
                    res = requests.post(
                        f"{API_URL}/chat/seguimiento/mensaje",
                        json={"mensaje": texto_f},
                        headers=get_headers()
                    )
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.followup_chat_history.append({
                        "role": "ai",
                        "text": data["respuesta"]
                    })

                    accion = data.get("accion")
                    tarea_id = data.get("tarea_id")

                    if accion == "regenerar_plan" and tarea_id:
                        st.session_state.tarea_id = tarea_id
                        st.session_state.followup_iniciado = False
                        st.session_state.followup_chat_history = []
                        st.session_state.menu_semana = None
                        st.session_state.lista_compra = None
                        st.success("¡Iniciando regeneración del plan!")
                        time.sleep(1)
                        _ir_a("generando")

                    elif accion in ("actualizar_perfil", "modificar_comida"):
                        st.toast(f"Plan actualizado con éxito: {accion} 🥗")
                        # Recargar plan
                        res_plan = requests.get(f"{API_URL}/planes/activo", headers=get_headers())
                        if res_plan.status_code == 200:
                            plan_data = res_plan.json()
                            st.session_state.plan_id = plan_data.get("plan_id")
                            st.session_state.calculos = {
                                "calorias_objetivo": plan_data.get("calorias_objetivo"),
                                "macros": {
                                    "proteinas_g": plan_data.get("proteinas_g"),
                                    "carbos_g": plan_data.get("carbos_g"),
                                    "grasas_g": plan_data.get("grasas_g")
                                }
                            }
                            st.session_state.menu_semana = plan_data.get("plan_semanal")

                        # Recargar lista
                        res_lista = requests.get(f"{API_URL}/lista-compra", headers=get_headers())
                        if res_lista.status_code == 200:
                            st.session_state.lista_compra = res_lista.json().get("categorias")

                        st.rerun()
                    else:
                        st.rerun()
                else:
                    st.error(f"Error: {res.text}")
            except Exception as e:
                st.error(f"Error de conexión: {e}")

    # ── Footer ─────────────────────────────────────────────────────────────────
    st.markdown("<br><hr>", unsafe_allow_html=True)
    if st.button("🔄 Crear un plan nuevo"):
        for k in ["perfil", "calculos", "menu_semana", "lista_compra", "plan_id", "tarea_id"]:
            st.session_state[k] = None
        st.session_state.chat_history = []
        _ir_a("inicio")


# ═══════════════════════════════════════════════════════════════════════════════
# Detectar callback de Google OAuth
if "code" in st.query_params:
    code = st.query_params["code"]
    st.query_params.clear()
    
    try:
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        res = requests.post(token_url, data=payload)
        if res.status_code == 200:
            id_token = res.json().get("id_token")
            
            res_backend = requests.post(f"{API_URL}/auth/google", json={"token": id_token})
            if res_backend.status_code == 200:
                data = res_backend.json()
                st.session_state.token = data["access_token"]
                st.session_state.user_id = data["user_id"]
                
                res_me = requests.get(f"{API_URL}/usuarios/me", headers=get_headers())
                if res_me.status_code == 200:
                    st.session_state.user_info = res_me.json()
                    
                res_plan = requests.get(f"{API_URL}/planes/activo", headers=get_headers())
                if res_plan.status_code == 200:
                    plan_data = res_plan.json()
                    st.session_state.plan_id = plan_data.get("plan_id")
                    st.session_state.calculos = {
                        "calorias_objetivo": plan_data.get("calorias_objetivo"),
                        "macros": {
                            "proteinas_g": plan_data.get("proteinas_g"),
                            "carbos_g": plan_data.get("carbos_g"),
                            "grasas_g": plan_data.get("grasas_g")
                        }
                    }
                    st.session_state.menu_semana = plan_data.get("plan_semanal")
                    
                    res_lista = requests.get(f"{API_URL}/lista-compra", headers=get_headers())
                    if res_lista.status_code == 200:
                        st.session_state.lista_compra = res_lista.json().get("categorias")
                    
                    st.session_state.pagina = "plan"
                else:
                    st.session_state.pagina = "inicio"
                
                st.toast("¡Sesión iniciada con Google! 🥗")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Error en backend NutriAI: {res_backend.json().get('detail', 'Error de autenticación')}")
        else:
            st.error("Error al obtener credenciales de Google.")
    except Exception as e:
        st.error(f"Error durante la autenticación con Google: {e}")

pagina = st.session_state.pagina

if pagina == "login":
    pagina_login()
elif pagina == "registro":
    pagina_registro()
elif pagina == "inicio":
    pagina_inicio()
elif pagina == "chat":
    pagina_chat()
elif pagina == "generando":
    pagina_generando()
elif pagina == "plan":
    pagina_plan()
else:
    _ir_a("login")

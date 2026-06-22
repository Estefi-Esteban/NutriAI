from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ObjetivoPrincipal(str, enum.Enum):
    perder_grasa = "perder_grasa"
    ganar_musculo = "ganar_musculo"
    mantenimiento = "mantenimiento"
    recomposicion_corporal = "recomposicion_corporal" 
    volumen = "volumen"

class VelocidadObjetivo(str, enum.Enum):
    lento = "lento"
    moderado = "moderado"
    rapido = "rapido"

class NivelActividad(str, enum.Enum):
    sedentario = "sedentario"
    ligero = "ligero"
    moderado = "moderado"
    activo = "activo"
    muy_activo = "muy_activo"

class TipoEntrenamiento(str, enum.Enum):
    fuerza = "fuerza"
    cardio = "cardio"
    mixto = "mixto"
    ninguno = "ninguno"

class DietaTipo(str, enum.Enum):
    omnivoro = "omnivoro"
    vegetariano = "vegetariano"
    vegano = "vegano"
    sin_gluten = "sin_gluten"
    cetogenica = "cetogenica"
    paleo = "paleo"
    otro = "otro"

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    
    password_hash = Column(String, nullable=True)   # now nullable (Google users don't have password)
    google_id     = Column(String, unique=True, nullable=True, index=True)
    auth_provider = Column(String, default="email")
    
    fecha_creacion = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    perfil = relationship("UserProfile", back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    planes_nutricionales = relationship("NutritionPlan", back_populates="usuario", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # Biométricos
    peso_kg = Column(Float, nullable=False)
    altura_cm = Column(Float, nullable=False)
    edad = Column(Integer, nullable=False)
    sexo = Column(String, nullable=False)
    porcentaje_grasa = Column(Float, nullable=True)

    # Objetivos
    objetivo_principal = Column(Enum(ObjetivoPrincipal), nullable=False)
    objetivo_secundario = Column(Text, nullable=True)
    velocidad_objetivo = Column(Enum(VelocidadObjetivo), nullable=True)

    # Actividad
    nivel_actividad = Column(Enum(NivelActividad), nullable=False)
    dias_entrenamiento = Column(Integer, nullable=False)
    tipo_entrenamiento = Column(Enum(TipoEntrenamiento), nullable=False)

    # Preferencias
    dieta_tipo = Column(Enum(DietaTipo), nullable=False)
    alergias = Column(JSON, default=list)
    intolerancias = Column(JSON, default=list)
    presupuesto_semanal = Column(Float, nullable=True)
    tiempo_cocina_min = Column(Integer, nullable=False)
    personas_en_casa = Column(Integer, nullable=False, default=1)

    # Estado de salud
    medicacion = Column(Text, nullable=True)
    patologias = Column(JSON, default=list, nullable=True)

    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    usuario = relationship("User", back_populates="perfil")


class NutritionPlan(Base):
    __tablename__ = 'nutrition_plans'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    calorias_objetivo = Column(Float, nullable=False)
    proteinas_g = Column(Float, nullable=False)
    carbos_g = Column(Float, nullable=False)
    grasas_g = Column(Float, nullable=False)
    
    plan_semanal = Column(JSON, nullable=False)
    
    fecha_generacion = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)

    # Relaciones
    usuario = relationship("User", back_populates="planes_nutricionales")


class ProtocoloNutricional(Base):
    __tablename__ = "protocolos_nutricionales"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Patologías detectadas/declaradas (lista JSON)
    patologias_activas = Column(JSON, default=list)

    # El protocolo generado — restricciones y prioridades
    restricciones = Column(JSON, default=list)
    # Ej: ["sin_gluten", "bajo_sodio", "bajo_indice_glucemico"]

    alimentos_prohibidos = Column(JSON, default=list)
    # Ej: ["trigo", "cebada", "centeno"]

    alimentos_prioritarios = Column(JSON, default=list)
    # Ej: ["hierro hem", "omega-3", "selenio"]

    notas_dietista = Column(Text, nullable=True)
    # Instrucciones en texto libre para el prompt del Dietista

    fecha_generacion = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("User")


class RecomendacionSuplementos(Base):
    __tablename__ = "recomendaciones_suplementos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)

    # Suplementos clasificados en tres categorías (listas de dicts JSON)
    suplementos_necesarios = Column(JSON, default=list)
    suplementos_opcionales = Column(JSON, default=list)
    suplementos_innecesarios = Column(JSON, default=list)

    notas = Column(Text, nullable=True)
    resumen = Column(Text, nullable=True)

    fecha_generacion = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("User")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rol = Column(String, nullable=False)       # "user" o "assistant"
    contenido = Column(Text, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("User")



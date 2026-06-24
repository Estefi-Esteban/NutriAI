import AsyncStorage from '@react-native-async-storage/async-storage';

// Base URL configuration
// Note: Use 'http://10.0.2.2:8000' for Android Emulator, or your local machine IP for physical devices.
const BASE_URL = 'https://nutriai-backend.up.railway.app';

export interface UserInfo {
  id: number;
  nombre: string;
  email: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: number;
}

// Helper to get headers with JWT token
async function getHeaders(isMultipart = false): Promise<HeadersInit> {
  const headers: Record<string, string> = {};
  if (!isMultipart) {
    headers['Content-Type'] = 'application/json';
  }
  const token = await AsyncStorage.getItem('user_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// General API request helper
async function request<T>(endpoint: string, options: RequestInit = {}, isMultipart = false): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const headers = await getHeaders(isMultipart);

  const config = {
    ...options,
    headers: {
      ...headers,
      ...(options.headers || {}),
    },
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = 'Error en la solicitud';
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch (e) {
      // JSON parsing failed
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // --- AUTH ---
  login: async (email: string, password: string): Promise<AuthResponse> => {
    return request<AuthResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  registro: async (nombre: string, email: string, password: string): Promise<AuthResponse> => {
    return request<AuthResponse>('/auth/registro', {
      method: 'POST',
      body: JSON.stringify({ nombre, email, password }),
    });
  },

  getMe: async (): Promise<UserInfo> => {
    return request<UserInfo>('/usuarios/me');
  },

  // --- PROFILE CHAT ---
  iniciarChatPerfil: async (): Promise<{ respuesta: string }> => {
    return request<{ respuesta: string }>('/chat/iniciar', { method: 'POST' });
  },

  enviarMensajePerfil: async (mensaje: string): Promise<{ respuesta: string; perfil_completo: boolean; datos: any }> => {
    return request<{ respuesta: string; perfil_completo: boolean; datos: any }>('/chat/mensaje', {
      method: 'POST',
      body: JSON.stringify({ session_id: 'ignorado', mensaje }),
    });
  },

  // --- NUTRITION PLANS ---
  generarPlan: async (perfil: any): Promise<{ tarea_id: string }> => {
    return request<{ tarea_id: string }>('/planes/generar', {
      method: 'POST',
      body: JSON.stringify({ perfil }),
    });
  },

  getEstadoTarea: async (tareaId: string): Promise<{ estado: string; progreso: number; dia_actual?: string; error?: string }> => {
    return request<{ estado: string; progreso: number; dia_actual?: string; error?: string }>(`/planes/estado/${tareaId}`);
  },

  getPlanActivo: async (): Promise<any> => {
    return request<any>('/planes/activo');
  },

  getListaCompra: async (): Promise<any> => {
    return request<any>('/lista-compra');
  },

  // --- CLINICAL MODULE ---
  analizarManual: async (valores: Record<string, number>): Promise<any> => {
    return request<any>('/analitica/manual', {
      method: 'POST',
      body: JSON.stringify({ valores }),
    });
  },

  analizarArchivo: async (uri: string, filename: string, mimeType: string): Promise<any> => {
    const formData = new FormData();
    // @ts-ignore
    formData.append('archivo', {
      uri,
      name: filename,
      type: mimeType,
    });

    return request<any>('/analitica/subir-archivo', {
      method: 'POST',
      body: formData,
    }, true);
  },

  // --- PATHOLOGY MODULE ---
  analizarPatologias: async (patologias: string[], alertasClinicas: string[] = []): Promise<any> => {
    return request<any>('/patologias/analizar', {
      method: 'POST',
      body: JSON.stringify({ patologias, alertas_clinicas: alertasClinicas }),
    });
  },

  getProtocoloActivo: async (): Promise<any> => {
    return request<any>('/patologias/mi-protocolo');
  },

  // --- SUPPLEMENTS MODULE ---
  generarSuplementos: async (incluirProtocolo: boolean): Promise<any> => {
    return request<any>('/suplementos/generar', {
      method: 'POST',
      body: JSON.stringify({ incluir_protocolo_patologias: incluirProtocolo }),
    });
  },

  getMisSuplementos: async (): Promise<any> => {
    return request<any>('/suplementos/mis-suplementos');
  },

  // --- GENERAL ASSISTANT (Fase 3.5) ---
  enviarMensajeAsistente: async (mensaje: string): Promise<{ respuesta: string; user_id: number }> => {
    return request<{ respuesta: string; user_id: number }>('/asistente/mensaje', {
      method: 'POST',
      body: JSON.stringify({ mensaje }),
    });
  },

  getHistorialAsistente: async (limite = 20): Promise<{ mensajes: any[]; total: number }> => {
    return request<{ mensajes: any[]; total: number }>(`/asistente/historial?limite=${limite}`);
  },

  limpiarHistorialAsistente: async (): Promise<{ mensaje: string }> => {
    return request<{ mensaje: string }>('/asistente/historial', {
      method: 'DELETE',
    });
  },

  // --- VISION AGENT (Fase 3.3) ---
  analizarPlato: async (base64Image: string): Promise<any> => {
    return request<any>('/vision/analizar-plato', {
      method: 'POST',
      body: JSON.stringify({ imagen_base64: base64Image }),
    });
  },

  registrarMacrosPlato: async (platoData: { nombre_plato: string; kcal: number; proteinas_g: number; carbos_g: number; grasas_g: number }): Promise<any> => {
    return request<any>('/vision/analizar-plato/registrar', {
      method: 'POST',
      body: JSON.stringify(platoData),
    });
  },

  // --- DAILY TRACKING (Fase 2.2) ---
  getSeguimientoDia: async (fecha: string): Promise<any> => {
    return request<any>(`/seguimiento/dia?fecha=${fecha}`);
  },

  registrarComida: async (comida: { nombre: string; comida_tipo: string; kcal: number; proteinas_g: number; carbos_g: number; grasas_g: number }): Promise<any> => {
    return request<any>('/seguimiento/comida', {
      method: 'POST',
      body: JSON.stringify(comida),
    });
  },

  registrarPeso: async (pesoKg: number): Promise<any> => {
    return request<any>('/seguimiento/peso', {
      method: 'POST',
      body: JSON.stringify({ peso_kg: pesoKg }),
    });
  },
};

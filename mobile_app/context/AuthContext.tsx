import React, { createContext, useState, useEffect, useContext } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { api, UserInfo } from '../services/api';

interface AuthContextType {
  token: string | null;
  user: UserInfo | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (nombre: string, email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // Check login status on boot
  useEffect(() => {
    const bootstrapAsync = async () => {
      try {
        const storedToken = await AsyncStorage.getItem('user_token');
        const storedRefreshToken = await AsyncStorage.getItem('user_refresh_token');

        if (storedToken) {
          try {
            setToken(storedToken);
            // Fetch user info
            const userInfo = await api.getMe();
            setUser(userInfo);
          } catch (getMeError) {
            // Si falla obtener los datos (probablemente token expirado), intentamos refrescar
            if (storedRefreshToken) {
              try {
                const refreshRes = await api.refreshSession(storedRefreshToken);
                await AsyncStorage.setItem('user_token', refreshRes.access_token);
                await AsyncStorage.setItem('user_refresh_token', refreshRes.refresh_token);
                setToken(refreshRes.access_token);

                const userInfo = await api.getMe();
                setUser(userInfo);
              } catch (refreshError) {
                // Si el refresco también falla, limpiamos la sesión
                await AsyncStorage.removeItem('user_token');
                await AsyncStorage.removeItem('user_refresh_token');
                setToken(null);
                setUser(null);
              }
            } else {
              // Sin token de refresco, limpiamos la sesión
              await AsyncStorage.removeItem('user_token');
              setToken(null);
              setUser(null);
            }
          }
        }
      } catch (e) {
        // Failed to load token or user info
        await AsyncStorage.removeItem('user_token');
        await AsyncStorage.removeItem('user_refresh_token');
      } finally {
        setLoading(false);
      }
    };

    bootstrapAsync();
  }, []);

  const signIn = async (email: string, password: string) => {
    setLoading(true);
    try {
      const res = await api.login(email, password);
      await AsyncStorage.setItem('user_token', res.access_token);
      await AsyncStorage.setItem('user_refresh_token', res.refresh_token);
      setToken(res.access_token);
      
      const userInfo = await api.getMe();
      setUser(userInfo);
    } catch (error) {
      setLoading(false);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const signUp = async (nombre: string, email: string, password: string) => {
    setLoading(true);
    try {
      const res = await api.registro(nombre, email, password);
      await AsyncStorage.setItem('user_token', res.access_token);
      await AsyncStorage.setItem('user_refresh_token', res.refresh_token);
      setToken(res.access_token);

      const userInfo = await api.getMe();
      setUser(userInfo);
    } catch (error) {
      setLoading(false);
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    setLoading(true);
    try {
      const storedRefreshToken = await AsyncStorage.getItem('user_refresh_token');
      if (storedRefreshToken) {
        try {
          await api.logout(storedRefreshToken);
        } catch (logoutError) {
          // Ignoramos errores de red al cerrar sesión para garantizar que el cliente se desloguee localmente
          console.warn('Error al revocar sesión en el servidor:', logoutError);
        }
      }
    } finally {
      await AsyncStorage.removeItem('user_token');
      await AsyncStorage.removeItem('user_refresh_token');
      setToken(null);
      setUser(null);
      setLoading(false);
    }
  };

  return (
    <AuthContext.Provider value={{ token, user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
};

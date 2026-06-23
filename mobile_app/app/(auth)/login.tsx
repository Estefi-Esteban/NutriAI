import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, Alert, KeyboardAvoidingView, Platform } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import { InputField } from '../../components/InputField';
import { PrimaryButton } from '../../components/PrimaryButton';
import { GlassCard } from '../../components/GlassCard';

const BACKEND_URL = 'http://172.21.20.184:8000';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [serverOk, setServerOk] = useState<boolean | null>(null);
  const { signIn } = useAuth();
  const router = useRouter();

  // Test connectivity on mount
  useEffect(() => {
    const checkServer = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/health`, { signal: AbortSignal.timeout(4000) });
        setServerOk(res.ok);
      } catch {
        setServerOk(false);
      }
    };
    checkServer();
  }, []);

  const handleLogin = async () => {
    if (!email.trim() || !password.trim()) {
      Alert.alert('Error', 'Por favor ingresa tu correo y contraseña.');
      return;
    }
    setLoading(true);
    try {
      await signIn(email, password);
    } catch (e: any) {
      const msg = e.message || 'Error desconocido';
      const isNetwork = msg.toLowerCase().includes('network') || msg.toLowerCase().includes('fetch');
      Alert.alert(
        isNetwork ? '❌ Sin conexión al servidor' : 'Error de inicio de sesión',
        isNetwork
          ? `No se puede conectar a:\n${BACKEND_URL}\n\nVerifica que:\n• El backend está corriendo\n• El móvil y PC están en el mismo WiFi`
          : msg
      );
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleMock = async () => {
    setLoading(true);
    try {
      // Sign in with the mock Google credentials (matches web simulation)
      await signIn('google.test.user@nutriai.com', 'GoogleTestUserPassword123!');
    } catch (e: any) {
      // If mock user doesn't exist, register them and sign in
      try {
        const { api } = require('../../services/api');
        await api.registro('Marta Google Test', 'google.test.user@nutriai.com', 'GoogleTestUserPassword123!');
        await signIn('google.test.user@nutriai.com', 'GoogleTestUserPassword123!');
      } catch (innerError: any) {
        Alert.alert('Error', 'No se pudo simular Google Sign-In.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.title}>🥗 NutriAI</Text>
          <Text style={styles.subtitle}>Tu nutricionista y dietista inteligente.</Text>
          <View style={styles.serverStatus}>
            <View style={[styles.statusDot, { backgroundColor: serverOk === null ? '#888' : serverOk ? '#4ade80' : '#f87171' }]} />
            <Text style={styles.statusText}>
              {serverOk === null ? 'Comprobando conexión...' : serverOk ? 'Servidor conectado ✓' : `Sin servidor · ${BACKEND_URL}`}
            </Text>
          </View>
        </View>

        <GlassCard style={styles.card}>
          <Text style={styles.cardTitle}>Iniciar Sesión</Text>
          
          <InputField
            label="Correo electrónico"
            placeholder="correo@ejemplo.com"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />

          <InputField
            label="Contraseña"
            placeholder="••••••••"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            autoCapitalize="none"
          />

          <PrimaryButton title="Entrar" loading={loading} onPress={handleLogin} />

          <Text style={styles.dividerText}>ó</Text>

          <PrimaryButton
            title="Entrar con Google (Mock)"
            onPress={handleGoogleMock}
            style={styles.googleBtn}
          />
        </GlassCard>

        <View style={styles.footer}>
          <Text style={styles.footerText}>¿No tienes una cuenta aún?</Text>
          <Text style={styles.linkText} onPress={() => router.push('/registro')}>
            Crear una cuenta nueva
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  scrollContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  serverStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 11,
    color: Colors.textMuted,
  },
  header: {
    alignItems: 'center',
    marginBottom: 32,
  },
  title: {
    fontSize: 36,
    fontWeight: '800',
    color: Colors.text,
    letterSpacing: -1,
  },
  subtitle: {
    fontSize: 14,
    color: Colors.textMuted,
    textAlign: 'center',
    marginTop: 4,
  },
  card: {
    paddingVertical: 24,
  },
  cardTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: Colors.text,
    textAlign: 'center',
    marginBottom: 20,
  },
  dividerText: {
    color: Colors.textMuted,
    textAlign: 'center',
    marginVertical: 12,
  },
  googleBtn: {
    backgroundColor: '#ffffff',
  },
  footer: {
    alignItems: 'center',
    marginTop: 24,
  },
  footerText: {
    color: Colors.textMuted,
    fontSize: 14,
  },
  linkText: {
    color: Colors.secondary,
    fontWeight: '700',
    fontSize: 14,
    marginTop: 6,
  },
});

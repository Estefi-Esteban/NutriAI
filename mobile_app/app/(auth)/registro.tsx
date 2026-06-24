import React, { useState } from 'react';
import { StyleSheet, Text, View, ScrollView, Alert, KeyboardAvoidingView, Platform, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import { InputField } from '../../components/InputField';
import { PrimaryButton } from '../../components/PrimaryButton';
import { GlassCard } from '../../components/GlassCard';

import { Ionicons } from '@expo/vector-icons';

export default function RegistroScreen() {
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Consent States
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptHealthConsent, setAcceptHealthConsent] = useState(false);

  const { signUp } = useAuth();
  const router = useRouter();

  const handleRegister = async () => {
    if (!nombre.trim() || !email.trim() || !password.trim()) {
      Alert.alert('Error', 'Por favor completa todos los campos.');
      return;
    }
    
    // Contraseñas: Mínimo 8 caracteres, una mayúscula, un número
    if (password.length < 8) {
      Alert.alert('Error', 'La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    const hasUppercase = /[A-Z]/.test(password);
    const hasNumber = /[0-9]/.test(password);
    if (!hasUppercase || !hasNumber) {
      Alert.alert('Error', 'La contraseña debe incluir al menos una mayúscula y un número.');
      return;
    }

    // Aceptar consentimientos explícitamente
    if (!acceptTerms || !acceptPrivacy || !acceptHealthConsent) {
      Alert.alert('Error', 'Debes aceptar los términos, la política de privacidad y el procesamiento de datos de salud.');
      return;
    }

    setLoading(true);
    try {
      await signUp(nombre, email, password);
    } catch (e: any) {
      Alert.alert('Error de registro', e.message || 'El correo electrónico ya está registrado.');
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
          <Text style={styles.subtitle}>Crea tu cuenta para empezar.</Text>
        </View>

        <GlassCard style={styles.card}>
          <Text style={styles.cardTitle}>Crear Cuenta</Text>
          
          <InputField
            label="Nombre completo"
            placeholder="Tu nombre"
            value={nombre}
            onChangeText={setNombre}
          />

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
            placeholder="•••••••• (mínimo 8, 1 mayús, 1 núm)"
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            autoCapitalize="none"
          />

          {/* RGPD / Consentimiento Checkboxes */}
          <View style={styles.consentContainer}>
            <TouchableOpacity 
              style={styles.checkboxRow} 
              onPress={() => setAcceptTerms(!acceptTerms)}
              activeOpacity={0.7}
            >
              <Ionicons 
                name={acceptTerms ? "checkbox" : "square-outline"} 
                size={20} 
                color={acceptTerms ? Colors.primary : Colors.textMuted} 
              />
              <Text style={styles.checkboxLabel}>Acepto los Términos de uso</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={styles.checkboxRow} 
              onPress={() => setAcceptPrivacy(!acceptPrivacy)}
              activeOpacity={0.7}
            >
              <Ionicons 
                name={acceptPrivacy ? "checkbox" : "square-outline"} 
                size={20} 
                color={acceptPrivacy ? Colors.primary : Colors.textMuted} 
              />
              <Text style={styles.checkboxLabel}>Acepto la Política de privacidad</Text>
            </TouchableOpacity>

            <TouchableOpacity 
              style={styles.checkboxRow} 
              onPress={() => setAcceptHealthConsent(!acceptHealthConsent)}
              activeOpacity={0.7}
            >
              <Ionicons 
                name={acceptHealthConsent ? "checkbox" : "square-outline"} 
                size={20} 
                color={acceptHealthConsent ? Colors.primary : Colors.textMuted} 
              />
              <Text style={styles.checkboxLabel}>Consiento el procesamiento de mis datos de salud (RGPD)</Text>
            </TouchableOpacity>
          </View>

          <PrimaryButton 
            title="Registrarse" 
            loading={loading} 
            disabled={!acceptTerms || !acceptPrivacy || !acceptHealthConsent}
            onPress={handleRegister} 
          />
        </GlassCard>


        <View style={styles.footer}>
          <Text style={styles.footerText}>¿Ya tienes una cuenta registrada?</Text>
          <Text style={styles.linkText} onPress={() => router.push('/login')}>
            Iniciar Sesión
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
  consentContainer: {
    marginVertical: 16,
    gap: 12,
    paddingHorizontal: 4,
  },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
  },
  checkboxLabel: {
    fontSize: 12.5,
    color: Colors.textSecondary,
    marginLeft: 8,
    flex: 1,
    lineHeight: 18,
  },
});

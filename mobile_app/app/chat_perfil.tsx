import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, ScrollView, TextInput, TouchableOpacity, ActivityIndicator, KeyboardAvoidingView, Platform, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { Colors } from '../constants/Colors';
import { api } from '../services/api';
import { GlassCard } from '../components/GlassCard';
import { Ionicons } from '@expo/vector-icons';
import { PrimaryButton } from '../components/PrimaryButton';

interface Message {
  role: 'user' | 'ai';
  text: string;
}

export default function ChatPerfilScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressText, setProgressText] = useState('');
  const scrollViewRef = useRef<ScrollView>(null);
  const router = useRouter();

  // Disclaimer Acceptance state
  const [disclaimerAceptado, setDisclaimerAceptado] = useState(false);

  useEffect(() => {
    if (!disclaimerAceptado) return;

    // Start chat session with ProfileAgent
    const startSession = async () => {
      setLoading(true);
      try {
        const res = await api.iniciarChatPerfil();
        setMessages([{ role: 'ai', text: res.respuesta }]);
      } catch (e: any) {
        Alert.alert('Error', 'No se pudo iniciar la sesión de chat.');
      } finally {
        setLoading(false);
      }
    };
    startSession();
  }, [disclaimerAceptado]);

  if (!disclaimerAceptado) {
    return (
      <View style={styles.disclaimerContainer}>
        <GlassCard style={styles.disclaimerCard}>
          <View style={styles.disclaimerIconWrap}>
            <Ionicons name="shield-checkmark-outline" size={48} color={Colors.primary} />
          </View>
          <Text style={styles.disclaimerTitle}>Aviso y Deslinde Médico</Text>
          
          <ScrollView style={styles.disclaimerTextScroll} showsVerticalScrollIndicator={false}>
            <Text style={styles.disclaimerText}>
              NutriAI es una herramienta de apoyo nutricional y un asistente inteligente basado en Inteligencia Artificial.
            </Text>
            <Text style={styles.disclaimerText}>
              La información, menús, planes y sugerencias de suplementación proporcionados por esta aplicación se ofrecen exclusivamente con fines educativos y de bienestar general.
            </Text>
            <Text style={[styles.disclaimerText, { fontWeight: '700' }]}>
              No constituyen, ni sustituyen en ningún caso, un diagnóstico, asesoramiento o tratamiento médico profesional.
            </Text>
            <Text style={styles.disclaimerText}>
              Antes de realizar cambios significativos en tu alimentación, entrenamiento o estilo de vida, o si padeces alguna condición médica preexistente (como diabetes, hipertensión o trastornos tiroideos), consulta siempre con un médico de cabecera o un dietista-nutricionista titulado.
            </Text>
          </ScrollView>

          <PrimaryButton 
            title="Entendido y acepto continuar" 
            onPress={() => setDisclaimerAceptado(true)} 
          />
          
          <TouchableOpacity 
            style={styles.disclaimerCancelBtn} 
            onPress={() => router.back()}
            activeOpacity={0.7}
          >
            <Text style={styles.disclaimerCancelText}>Cancelar y Volver</Text>
          </TouchableOpacity>
        </GlassCard>
      </View>
    );
  }

  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    const userText = inputValue.trim();
    setInputValue('');
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setLoading(true);

    try {
      const res = await api.enviarMensajePerfil(userText);
      setMessages(prev => [...prev, { role: 'ai', text: res.respuesta }]);

      if (res.perfil_completo) {
        // Trigger weekly plan generation
        triggerPlanGeneration(res.datos);
      }
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudo enviar el mensaje.');
    } finally {
      setLoading(false);
    }
  };

  const triggerPlanGeneration = async (perfil: any) => {
    setGenerating(true);
    setProgress(5);
    setProgressText('🚀 Iniciando generación de plan...');

    try {
      const { tarea_id } = await api.generarPlan(perfil);
      
      // Start polling
      const interval = setInterval(async () => {
        try {
          const resTask = await api.getEstadoTarea(tarea_id);
          setProgress(resTask.progreso);
          if (resTask.dia_actual) {
            setProgressText(`Generando menú: ${resTask.dia_actual} (${resTask.progreso}%)`);
          } else {
            setProgressText(`Generando plan... (${resTask.progreso}%)`);
          }

          if (resTask.estado === 'completado') {
            clearInterval(interval);
            setProgress(100);
            setProgressText('🎉 ¡Plan generado exitosamente!');
            setTimeout(() => {
              setGenerating(false);
              router.replace('/(tabs)');
            }, 1000);
          } else if (resTask.estado === 'error' || resTask.error) {
            clearInterval(interval);
            setGenerating(false);
            Alert.alert('Error', resTask.error || 'No se pudo generar el plan.');
          }
        } catch (pollError) {
          clearInterval(interval);
          setGenerating(false);
          Alert.alert('Error', 'Error de conexión al monitorear la tarea.');
        }
      }, 3000);

    } catch (e: any) {
      setGenerating(false);
      Alert.alert('Error', 'No se pudo iniciar la generación del plan.');
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      {generating ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.generatingTitle}>Creando tu plan personalizado</Text>
          <Text style={styles.generatingSubtitle}>{progressText}</Text>
          <View style={styles.progressBarBg}>
            <View style={[styles.progressBarFill, { width: `${progress}%` }]} />
          </View>
        </View>
      ) : (
        <>
          <ScrollView
            ref={scrollViewRef}
            contentContainerStyle={styles.messagesList}
            onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
          >
            {messages.map((msg, i) => (
              <View
                key={i}
                style={[
                  styles.msgContainer,
                  msg.role === 'user' ? styles.userContainer : styles.aiContainer
                ]}
              >
                <Text style={styles.senderLabel}>
                  {msg.role === 'user' ? 'Tú' : 'NutriAI 🤖'}
                </Text>
                <View
                  style={[
                    styles.bubble,
                    msg.role === 'user' ? styles.userBubble : styles.aiBubble
                  ]}
                >
                  <Text style={styles.msgText}>{msg.text}</Text>
                </View>
              </View>
            ))}
            {loading && (
              <View style={[styles.msgContainer, styles.aiContainer]}>
                <ActivityIndicator color={Colors.primary} size="small" style={styles.loader} />
              </View>
            )}
          </ScrollView>

          <View style={styles.inputContainer}>
            <TextInput
              style={styles.input}
              placeholder="Escribe tu respuesta aquí..."
              placeholderTextColor={Colors.textMuted}
              value={inputValue}
              onChangeText={setInputValue}
              onSubmitEditing={handleSend}
              editable={!loading}
            />
            <TouchableOpacity onPress={handleSend} style={styles.sendBtn} disabled={loading}>
              <Text style={styles.sendBtnText}>Enviar</Text>
            </TouchableOpacity>
          </View>
        </>
      )}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  messagesList: {
    padding: 16,
    paddingBottom: 24,
  },
  msgContainer: {
    marginBottom: 16,
    maxWidth: '80%',
  },
  userContainer: {
    alignSelf: 'flex-end',
    alignItems: 'flex-end',
  },
  aiContainer: {
    alignSelf: 'flex-start',
    alignItems: 'flex-start',
  },
  senderLabel: {
    fontSize: 11,
    color: Colors.textMuted,
    marginBottom: 4,
    fontWeight: '600',
  },
  bubble: {
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  userBubble: {
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    borderColor: 'rgba(99, 102, 241, 0.4)',
    borderWidth: 1,
    borderBottomRightRadius: 2,
  },
  aiBubble: {
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderBottomLeftRadius: 2,
  },
  msgText: {
    color: Colors.text,
    fontSize: 15,
    lineHeight: 20,
  },
  loader: {
    marginLeft: 12,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderTopColor: Colors.cardBorder,
    borderTopWidth: 1,
    backgroundColor: Colors.backgroundGradStart,
  },
  input: {
    flex: 1,
    backgroundColor: Colors.inputBg,
    borderColor: Colors.inputBorder,
    borderWidth: 1,
    borderRadius: 12,
    color: Colors.text,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    marginRight: 10,
  },
  sendBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  sendBtnText: {
    color: Colors.text,
    fontWeight: '700',
    fontSize: 14,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  generatingTitle: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '700',
    marginTop: 24,
  },
  generatingSubtitle: {
    color: Colors.textMuted,
    fontSize: 14,
    marginTop: 8,
    marginBottom: 24,
    textAlign: 'center',
  },
  progressBarBg: {
    height: 6,
    width: '80%',
    backgroundColor: Colors.inputBg,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: Colors.primary,
  },
  disclaimerContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    justifyContent: 'center',
    padding: 20,
  },
  disclaimerCard: {
    paddingVertical: 24,
    maxHeight: '90%',
  },
  disclaimerIconWrap: {
    alignItems: 'center',
    marginBottom: 12,
  },
  disclaimerTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: Colors.text,
    textAlign: 'center',
    marginBottom: 16,
  },
  disclaimerTextScroll: {
    marginBottom: 20,
  },
  disclaimerText: {
    fontSize: 14,
    color: Colors.textSecondary,
    lineHeight: 22,
    marginBottom: 12,
    textAlign: 'center',
  },
  disclaimerCancelBtn: {
    alignItems: 'center',
    paddingVertical: 12,
    marginTop: 8,
  },
  disclaimerCancelText: {
    color: Colors.textMuted,
    fontSize: 14,
    fontWeight: '600',
  },
});

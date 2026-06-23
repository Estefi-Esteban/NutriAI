import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, ScrollView, TextInput, TouchableOpacity, ActivityIndicator, Alert, KeyboardAvoidingView, Platform } from 'react-native';
import { Colors } from '../../constants/Colors';
import { api } from '../../services/api';
import { Ionicons } from '@expo/vector-icons';

interface Message {
  rol: 'user' | 'assistant';
  contenido: string;
}

export default function AsistenteScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const scrollViewRef = useRef<ScrollView>(null);

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await api.getHistorialAsistente(20);
      setMessages(res.mensajes || []);
    } catch (e: any) {
      Alert.alert('Error', 'No se pudo cargar el historial de chat.');
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    const userText = inputValue.trim();
    setInputValue('');
    setMessages(prev => [...prev, { rol: 'user', contenido: userText }]);
    setLoading(true);

    try {
      const res = await api.enviarMensajeAsistente(userText);
      setMessages(prev => [...prev, { rol: 'assistant', contenido: res.respuesta }]);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudo enviar el mensaje.');
    } finally {
      setLoading(false);
    }
  };

  const handleClearHistory = () => {
    Alert.alert(
      'Vaciar Historial',
      '¿Estás seguro de que quieres borrar todo el historial de conversación? Esto no se puede deshacer.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Borrar',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.limpiarHistorialAsistente();
              setMessages([]);
              Alert.alert('Borrado', 'El historial se ha vaciado.');
            } catch (e) {
              Alert.alert('Error', 'No se pudo borrar el historial.');
            }
          }
        }
      ]
    );
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 0}
    >
      <View style={styles.topHeader}>
        <Text style={styles.headerTitle}>Conversación Personal</Text>
        <TouchableOpacity onPress={handleClearHistory} style={styles.clearBtn}>
          <Ionicons name="trash-outline" size={18} color={Colors.danger} />
          <Text style={styles.clearBtnText}>Vaciar</Text>
        </TouchableOpacity>
      </View>

      {loadingHistory ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
        </View>
      ) : (
        <ScrollView
          ref={scrollViewRef}
          contentContainerStyle={styles.messagesList}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Ionicons name="chatbox-ellipses-outline" size={48} color={Colors.textMuted} />
              <Text style={styles.emptyText}>Conversación vacía.</Text>
              <Text style={styles.emptySubtext}>Pregúntame sobre sustituciones de alimentos, suplementos, o dudas sobre tu plan nutricional activo.</Text>
            </View>
          ) : (
            messages.map((msg, i) => (
              <View
                key={i}
                style={[
                  styles.msgContainer,
                  msg.rol === 'user' ? styles.userContainer : styles.aiContainer
                ]}
              >
                <Text style={styles.senderLabel}>
                  {msg.rol === 'user' ? 'Tú' : 'NutriAI'}
                </Text>
                <View
                  style={[
                    styles.bubble,
                    msg.rol === 'user' ? styles.userBubble : styles.aiBubble
                  ]}
                >
                  <Text style={styles.msgText}>{msg.contenido}</Text>
                </View>
              </View>
            ))
          )}
          {loading && (
            <View style={[styles.msgContainer, styles.aiContainer]}>
              <ActivityIndicator color={Colors.primary} size="small" style={styles.loader} />
            </View>
          )}
        </ScrollView>
      )}

      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Haz una pregunta a la IA..."
          placeholderTextColor={Colors.textMuted}
          value={inputValue}
          onChangeText={setInputValue}
          onSubmitEditing={handleSend}
          disabled={loading}
        />
        <TouchableOpacity onPress={handleSend} style={styles.sendBtn} disabled={loading}>
          <Text style={styles.sendBtnText}>Enviar</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
    backgroundColor: Colors.backgroundGradStart,
  },
  headerTitle: {
    color: Colors.text,
    fontWeight: '700',
    fontSize: 14,
  },
  clearBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: 'rgba(239, 68, 68, 0.2)',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  clearBtnText: {
    color: Colors.danger,
    fontSize: 12,
    fontWeight: '700',
    marginLeft: 4,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  messagesList: {
    padding: 16,
    paddingBottom: 24,
    flexGrow: 1,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 32,
    paddingVertical: 48,
  },
  emptyText: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginTop: 16,
  },
  emptySubtext: {
    color: Colors.textMuted,
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 18,
    marginTop: 8,
  },
  msgContainer: {
    marginBottom: 16,
    maxWidth: '85%',
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
});

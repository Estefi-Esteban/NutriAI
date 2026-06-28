import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet, Text, View, ScrollView, TextInput,
  TouchableOpacity, ActivityIndicator, Alert,
  KeyboardAvoidingView, Platform
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Colors } from '../../constants/Colors';
import { Spacing, Radius } from '../../constants/theme';
import { api } from '../../services/api';
import { Ionicons } from '@expo/vector-icons';

interface Message {
  rol: 'user' | 'assistant';
  contenido: string;
  timestamp?: Date;
}

// ─── Chat Bubble ──────────────────────────────────────────────────────────
function ChatBubble({ msg }: { msg: Message }) {
  const isUser = msg.rol === 'user';
  return (
    <View style={[styles.msgWrapper, isUser ? styles.wrapperUser : styles.wrapperAI]}>
      {!isUser && (
        <View style={styles.aiAvatar}>
          <Text style={styles.aiAvatarEmoji}>🤖</Text>
        </View>
      )}
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAI]}>
        <Text style={styles.msgText}>{msg.contenido}</Text>
      </View>
      {isUser && (
        <View style={styles.userAvatar}>
          <Ionicons name="person" size={14} color={Colors.primary} />
        </View>
      )}
    </View>
  );
}

// ─── Suggestion Chip ──────────────────────────────────────────────────────
function SuggestionChip({ text, onPress }: { text: string; onPress: () => void }) {
  return (
    <TouchableOpacity style={styles.chip} onPress={onPress} activeOpacity={0.7}>
      <Text style={styles.chipText}>{text}</Text>
    </TouchableOpacity>
  );
}

const SUGGESTIONS = [
  '¿Qué puedo comer si tengo hambre a media tarde?',
  '¿Puedo sustituir el pollo por tofu?',
  '¿Cuánta proteína necesito al día?',
];

// ─── Main Screen ──────────────────────────────────────────────────────────
export default function AsistenteScreen() {
  const insets = useSafeAreaInsets();
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
    } catch {
      Alert.alert('Error', 'No se pudo cargar el historial de chat.');
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => { loadHistory(); }, []);

  const handleSend = async (text?: string) => {
    const msgText = (text || inputValue).trim();
    if (!msgText || loading) return;

    setInputValue('');
    setMessages(prev => [...prev, { rol: 'user', contenido: msgText }]);
    setLoading(true);

    try {
      const res = await api.enviarMensajeAsistente(msgText);
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
      '¿Estás seguro de que quieres borrar toda la conversación?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Borrar',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.limpiarHistorialAsistente();
              setMessages([]);
            } catch {
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
      {/* Sub-header */}
      <View style={styles.subHeader}>
        <View style={styles.aiStatusRow}>
          <View style={styles.statusDot} />
          <Text style={styles.subHeaderText}>NutriAI · Activo</Text>
        </View>
        <TouchableOpacity onPress={handleClearHistory} style={styles.clearBtn}>
          <Ionicons name="trash-outline" size={16} color={Colors.danger} />
          <Text style={styles.clearBtnText}>Vaciar</Text>
        </TouchableOpacity>
      </View>

      {/* Messages */}
      {loadingHistory ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>Cargando historial...</Text>
        </View>
      ) : (
        <ScrollView
          ref={scrollViewRef}
          contentContainerStyle={styles.messagesList}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
          showsVerticalScrollIndicator={false}
        >
          {messages.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyEmoji}>🤖</Text>
              <Text style={styles.emptyTitle}>¿En qué puedo ayudarte?</Text>
              <Text style={styles.emptySubtitle}>
                Pregúntame sobre sustituciones, suplementos, o cualquier duda de tu plan.
              </Text>
              {/* Suggestions */}
              <View style={styles.suggestionsRow}>
                {SUGGESTIONS.map((s, i) => (
                  <SuggestionChip key={i} text={s} onPress={() => handleSend(s)} />
                ))}
              </View>
            </View>
          ) : (
            <>
              {messages.map((msg, i) => (
                <ChatBubble key={i} msg={msg} />
              ))}
              {loading && (
                <View style={styles.typingIndicator}>
                  <View style={styles.aiAvatar}>
                    <Text style={styles.aiAvatarEmoji}>🤖</Text>
                  </View>
                  <View style={styles.typingBubble}>
                    <ActivityIndicator size="small" color={Colors.primary} />
                    <Text style={styles.typingText}>NutriAI está escribiendo...</Text>
                  </View>
                </View>
              )}
            </>
          )}
        </ScrollView>
      )}

      {/* Input Area */}
      <View style={[styles.inputContainer, { paddingBottom: Math.max(insets.bottom, 12) }]}>
        <TextInput
          style={styles.input}
          placeholder="Pregunta algo sobre nutrición..."
          placeholderTextColor={Colors.textTertiary}
          value={inputValue}
          onChangeText={setInputValue}
          onSubmitEditing={() => handleSend()}
          multiline
          maxLength={500}
          editable={!loading}
        />
        <TouchableOpacity
          onPress={() => handleSend()}
          style={[styles.sendBtn, (!inputValue.trim() || loading) && styles.sendBtnDisabled]}
          disabled={!inputValue.trim() || loading}
          activeOpacity={0.8}
        >
          <Ionicons name="send" size={18} color={inputValue.trim() ? '#fff' : Colors.textTertiary} />
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

  // Sub-header
  subHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    backgroundColor: Colors.backgroundGradStart,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  aiStatusRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Colors.primary,
    marginRight: 8,
  },
  subHeaderText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '600',
  },
  clearBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.danger + '15',
    borderColor: Colors.danger + '30',
    borderWidth: 1,
    borderRadius: Radius.sm,
    paddingHorizontal: 10,
    paddingVertical: 5,
    gap: 4,
  },
  clearBtnText: {
    color: Colors.danger,
    fontSize: 12,
    fontWeight: '700',
  },

  // Loading
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    color: Colors.textSecondary,
    marginTop: 10,
    fontSize: 13,
  },

  // Messages
  messagesList: {
    padding: Spacing.md,
    paddingBottom: Spacing.lg,
    flexGrow: 1,
  },

  // Empty
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 48,
    paddingHorizontal: Spacing.lg,
  },
  emptyEmoji: {
    fontSize: 52,
    marginBottom: Spacing.md,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: Colors.text,
    marginBottom: 8,
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: Spacing.lg,
  },
  suggestionsRow: {
    width: '100%',
    gap: 8,
  },
  chip: {
    backgroundColor: Colors.backgroundGradStart,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
  },
  chipText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
    lineHeight: 18,
  },

  // Chat bubbles
  msgWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    marginBottom: Spacing.sm + 4,
    maxWidth: '88%',
  },
  wrapperUser: {
    alignSelf: 'flex-end',
    justifyContent: 'flex-end',
  },
  wrapperAI: {
    alignSelf: 'flex-start',
  },
  aiAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primaryFaint,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    flexShrink: 0,
  },
  aiAvatarEmoji: {
    fontSize: 14,
  },
  userAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primaryFaint,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
    flexShrink: 0,
  },
  bubble: {
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    maxWidth: '100%',
  },
  bubbleUser: {
    backgroundColor: Colors.primaryFaint,
    borderColor: Colors.primary + '40',
    borderWidth: 1,
    borderBottomRightRadius: 4,
  },
  bubbleAI: {
    backgroundColor: Colors.backgroundGradStart,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderBottomLeftRadius: 4,
  },
  msgText: {
    color: Colors.text,
    fontSize: 15,
    lineHeight: 21,
  },

  // Typing indicator
  typingIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    marginBottom: Spacing.sm,
  },
  typingBubble: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.backgroundGradStart,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: Radius.lg,
    borderBottomLeftRadius: 4,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    gap: 8,
  },
  typingText: {
    color: Colors.textSecondary,
    fontSize: 13,
    fontStyle: 'italic',
  },

  // Input
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: Spacing.sm + 4,
    paddingBottom: Spacing.md,
    borderTopColor: Colors.cardBorder,
    borderTopWidth: 1,
    backgroundColor: Colors.backgroundGradStart,
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: Colors.inputBg,
    borderColor: Colors.inputBorder,
    borderWidth: 1,
    borderRadius: Radius.lg,
    color: Colors.text,
    paddingHorizontal: Spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 100,
  },
  sendBtn: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  sendBtnDisabled: {
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
  },
});

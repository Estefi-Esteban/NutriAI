import React, { useState, useEffect } from 'react';
import {
  StyleSheet, Text, View, ScrollView,
  TouchableOpacity, ActivityIndicator, Alert, TextInput
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import { Theme, Spacing, Radius } from '../../constants/theme';
import { api } from '../../services/api';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

// ─── Macro Progress Ring (simple arc via border) ──────────────────────────
function MacroCard({
  emoji, label, current, goal, color,
}: {
  emoji: string; label: string; current: number; goal: number; color: string;
}) {
  const pct = goal > 0 ? Math.min(current / goal, 1) : 0;
  return (
    <View style={styles.macroCard}>
      <View style={[styles.macroIconWrap, { backgroundColor: color + '20' }]}>
        <Text style={styles.macroEmoji}>{emoji}</Text>
      </View>
      <Text style={styles.macroLabel}>{label}</Text>
      <Text style={[styles.macroValue, { color }]}>
        {current}
        <Text style={styles.macroGoal}>/{goal}g</Text>
      </Text>
      {/* Mini progress bar */}
      <View style={styles.macroBar}>
        <View style={[styles.macroBarFill, { width: `${pct * 100}%` as any, backgroundColor: color }]} />
      </View>
    </View>
  );
}

// ─── Calorie Ring Widget ──────────────────────────────────────────────────
function CalorieRing({ consumed, goal }: { consumed: number; goal: number }) {
  const pct = goal > 0 ? Math.min(consumed / goal, 1) : 0;
  const remaining = Math.max(goal - consumed, 0);
  return (
    <View style={styles.calorieRingSection}>
      {/* Left: big numbers */}
      <View style={styles.calNumbersCol}>
        <Text style={styles.calBig}>{consumed}</Text>
        <Text style={styles.calBigLabel}>Kcal consumidas</Text>
        <View style={styles.calDivider} />
        <Text style={styles.calRemaining}>{remaining}</Text>
        <Text style={styles.calRemainingLabel}>restantes</Text>
      </View>

      {/* Right: ring placeholder + goal */}
      <View style={styles.calRingCol}>
        <View style={styles.ringOuter}>
          <LinearGradient
            colors={[Colors.primary, Colors.primaryDark]}
            style={[styles.ringArc, { opacity: 0.15 + pct * 0.85 }]}
          />
          <View style={styles.ringInner}>
            <Text style={styles.ringPct}>{Math.round(pct * 100)}%</Text>
            <Text style={styles.ringPctLabel}>alcanzado</Text>
          </View>
        </View>
        <Text style={styles.calGoalText}>de {goal} Kcal</Text>
      </View>
    </View>
  );
}

// ─── Food Item Row ─────────────────────────────────────────────────────────
function FoodRow({ item }: { item: any }) {
  const typeColors: Record<string, string> = {
    desayuno: Colors.macroCarbs,
    comida: Colors.primary,
    cena: Colors.macroFat,
    snack: Colors.macroProtein,
  };
  const color = typeColors[item.comida_tipo] || Colors.textSecondary;
  return (
    <View style={styles.foodRow}>
      <View style={[styles.foodTypeDot, { backgroundColor: color }]} />
      <View style={styles.foodInfo}>
        <Text style={styles.foodName}>{item.nombre}</Text>
        <Text style={styles.foodType}>{item.comida_tipo.toUpperCase()}</Text>
      </View>
      <Text style={[styles.foodKcal, { color }]}>{item.kcal} kcal</Text>
    </View>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────
export default function DashboardScreen() {
  const { user, signOut } = useAuth();
  const [plan, setPlan] = useState<any>(null);
  const [tracking, setTracking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [weightInput, setWeightInput] = useState('');
  const [loggingWeight, setLoggingWeight] = useState(false);
  const router = useRouter();

  const todayFormatted = new Date().toLocaleDateString('es-ES', {
    weekday: 'long', day: 'numeric', month: 'long',
  });

  const loadData = async () => {
    setLoading(true);
    try {
      await api.getMe();
      try {
        await api.getProtocoloActivo();
        const activePlan = await api.getPlanActivo();
        setPlan(activePlan);
      } catch {}
      const todayStr = new Date().toISOString().split('T')[0];
      const trackingData = await api.getSeguimientoDia(todayStr);
      setTracking(trackingData);
      if (trackingData?.peso_actual) {
        setWeightInput(trackingData.peso_actual.toString());
      }
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { loadData(); }, []);

  const handleWeightLog = async () => {
    const peso = parseFloat(weightInput);
    if (isNaN(peso) || peso <= 0) {
      Alert.alert('Error', 'Por favor ingresa un peso válido.');
      return;
    }
    setLoggingWeight(true);
    try {
      await api.registrarPeso(peso);
      Alert.alert('✅ Éxito', 'Peso registrado correctamente.');
      loadData();
    } catch {
      Alert.alert('Error', 'No se pudo registrar el peso.');
    } finally { setLoggingWeight(false); }
  };

  if (loading) {
    return (
      <View style={Theme.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Cargando tu progreso...</Text>
      </View>
    );
  }

  // ─── Estado sin plan ───────────────────────────────────────────────────
  if (!plan) {
    return (
      <ScrollView contentContainerStyle={styles.scrollContainer}>
        {/* Greeting */}
        <View style={styles.greetingRow}>
          <View>
            <Text style={styles.greeting}>¡Hola, {user?.nombre || 'Usuario'}! 👋</Text>
            <Text style={styles.dateText}>{todayFormatted}</Text>
          </View>
        </View>

        {/* Onboarding CTA */}
        <LinearGradient
          colors={['#F0F4EE', '#D8F3DC']}
          style={styles.ctaCard}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
        >
          <View style={styles.ctaIconRow}>
            <Text style={styles.ctaBigEmoji}>🥗</Text>
          </View>
          <Text style={styles.ctaTitle}>Crea tu plan personalizado</Text>
          <Text style={styles.ctaSubtitle}>
            En solo 2 minutos calcula tus macros perfectos, genera tu menú semanal y descubre tu protocolo nutricional ideal.
          </Text>
          <TouchableOpacity
            style={styles.ctaBtn}
            onPress={() => router.push('/chat_perfil')}
            activeOpacity={0.85}
          >
            <LinearGradient
              colors={['#52B788', '#2D6A4F']}
              style={styles.ctaBtnInner}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
            >
              <Ionicons name="sparkles" size={18} color="#FFFFFF" style={{ marginRight: 8 }} />
              <Text style={styles.ctaBtnText}>Empezar Onboarding</Text>
            </LinearGradient>
          </TouchableOpacity>
        </LinearGradient>

        {/* Features preview */}
        {[
          { icon: 'calculator-outline', color: Colors.primary, title: 'Macros personalizados', sub: 'Basados en tu biometría y objetivos' },
          { icon: 'restaurant-outline', color: Colors.macroCarbs, title: 'Menú de 7 días', sub: 'Recetas detalladas con ingredientes' },
          { icon: 'cart-outline', color: Colors.macroProtein, title: 'Lista de compra', sub: 'Generada automáticamente' },
        ].map((feat, i) => (
          <View key={i} style={styles.featureRow}>
            <View style={[styles.featureIcon, { backgroundColor: feat.color + '18' }]}>
              <Ionicons name={feat.icon as any} size={22} color={feat.color} />
            </View>
            <View style={styles.featureText}>
              <Text style={styles.featureTitle}>{feat.title}</Text>
              <Text style={styles.featureSub}>{feat.sub}</Text>
            </View>
          </View>
        ))}

        <TouchableOpacity style={styles.logoutGhost} onPress={signOut}>
          <Text style={styles.logoutGhostText}>Cerrar Sesión</Text>
        </TouchableOpacity>
      </ScrollView>
    );
  }

  // ─── Estado con plan ───────────────────────────────────────────────────
  const calConsumed = tracking?.calorias_consumidas || 0;
  const calGoal = plan.calorias_objetivo || 2000;

  return (
    <ScrollView contentContainerStyle={styles.scrollContainer} showsVerticalScrollIndicator={false}>
      {/* Header */}
      <View style={styles.greetingRow}>
        <View>
          <Text style={styles.greeting}>Hola, {user?.nombre || 'Usuario'} 👋</Text>
          <Text style={styles.dateText}>{todayFormatted}</Text>
        </View>
        <TouchableOpacity onPress={loadData} style={Theme.iconBtn}>
          <Ionicons name="refresh" size={20} color={Colors.primary} />
        </TouchableOpacity>
      </View>

      {/* ── Calorie Card ── */}
      <View style={[styles.card, styles.calCard]}>
        <Text style={styles.cardTitle}>Calorías de hoy</Text>
        <CalorieRing consumed={calConsumed} goal={calGoal} />
      </View>

      {/* ── Macros Grid ── */}
      <View style={styles.macrosGrid}>
        <MacroCard
          emoji="🥩"
          label="Proteínas"
          current={tracking?.proteinas_consumidas || 0}
          goal={plan.proteinas_g}
          color={Colors.macroProtein}
        />
        <MacroCard
          emoji="🌾"
          label="Carbos"
          current={tracking?.carbos_consumidas || 0}
          goal={plan.carbos_g}
          color={Colors.macroCarbs}
        />
        <MacroCard
          emoji="🥑"
          label="Grasas"
          current={tracking?.grasas_consumidas || 0}
          goal={plan.grasas_g}
          color={Colors.macroFat}
        />
      </View>

      {/* ── Food Log ── */}
      <View style={styles.card}>
        <View style={styles.cardHeaderRow}>
          <Text style={styles.cardTitle}>Comidas de hoy</Text>
          <View style={[styles.countBadge]}>
            <Text style={styles.countBadgeText}>
              {tracking?.comidas?.length || 0}
            </Text>
          </View>
        </View>
        {tracking?.comidas && tracking.comidas.length > 0 ? (
          tracking.comidas.map((item: any, i: number) => (
            <FoodRow key={i} item={item} />
          ))
        ) : (
          <View style={styles.emptyState}>
            <Ionicons name="restaurant-outline" size={36} color={Colors.textTertiary} />
            <Text style={styles.emptyTitle}>Sin registros</Text>
            <Text style={styles.emptySubtitle}>
              Usa el Escáner de Plato para registrar tus comidas automáticamente.
            </Text>
          </View>
        )}
      </View>

      {/* ── Weight Log ── */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Peso de hoy</Text>
        <View style={styles.weightRow}>
          <TextInput
            style={styles.weightInput}
            keyboardType="numeric"
            placeholder="Ej: 75.5"
            placeholderTextColor={Colors.textTertiary}
            value={weightInput}
            onChangeText={setWeightInput}
          />
          <Text style={styles.weightUnit}>kg</Text>
          <TouchableOpacity
            style={styles.weightBtn}
            onPress={handleWeightLog}
            disabled={loggingWeight}
            activeOpacity={0.8}
          >
            {loggingWeight
              ? <ActivityIndicator size="small" color="#000" />
              : <Text style={styles.weightBtnText}>Registrar</Text>
            }
          </TouchableOpacity>
        </View>
      </View>

      {/* ── Quick Actions ── */}
      <View style={styles.quickActionsRow}>
        <TouchableOpacity
          style={styles.quickAction}
          onPress={() => router.push('/chat_perfil')}
          activeOpacity={0.8}
        >
          <Ionicons name="refresh-circle-outline" size={20} color="#6B7280" />
          <Text style={styles.quickActionText}>Re-hacer onboarding</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.quickActionDanger} onPress={signOut} activeOpacity={0.8}>
          <Ionicons name="log-out-outline" size={20} color={Colors.danger} />
          <Text style={styles.quickActionDangerText}>Cerrar Sesión</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scrollContainer: {
    flexGrow: 1,
    backgroundColor: '#F8FAF5',
    padding: Spacing.md,
    paddingBottom: 48,
  },
  loadingText: {
    color: Colors.textSecondary,
    marginTop: 12,
    fontSize: 14,
  },

  // Header
  greetingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginTop: Spacing.sm,
    marginBottom: Spacing.lg,
  },
  greeting: {
    fontSize: 28,
    fontWeight: '800',
    color: '#1A1A2E',
  },
  dateText: {
    fontSize: 13,
    color: '#6B7280',
    marginTop: 2,
    textTransform: 'capitalize',
  },

  // ── Onboarding CTA ─────────────────────────────────────────────────────────
  ctaCard: {
    borderRadius: Radius.xl,
    borderColor: Colors.primary + '30',
    borderWidth: 1,
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
    alignItems: 'center',
  },
  ctaIconRow: {
    marginBottom: Spacing.sm,
  },
  ctaBigEmoji: {
    fontSize: 52,
  },
  ctaTitle: {
    fontSize: 22,
    fontWeight: '800',
    color: '#1A1A2E',
    textAlign: 'center',
    marginBottom: 8,
  },
  ctaSubtitle: {
    fontSize: 14,
    color: Colors.textSecondary,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: Spacing.lg,
  },
  ctaBtn: {
    width: '100%',
    borderRadius: Radius.md,
    overflow: 'hidden',
  },
  ctaBtnInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    paddingHorizontal: Spacing.lg,
  },
  ctaBtnText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 16,
  },

  // Features
  featureRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFFFFF',
    borderRadius: Radius.lg,
    borderColor: '#E5E7EB',
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  featureIcon: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  featureText: { flex: 1 },
  featureTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1A1A2E',
  },
  featureSub: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginTop: 2,
  },

  // Logout ghost
  logoutGhost: {
    alignItems: 'center',
    paddingVertical: 14,
    marginTop: Spacing.sm,
  },
  logoutGhostText: {
    color: Colors.textTertiary,
    fontSize: 13,
    fontWeight: '600',
  },

  // ── Dashboard Cards ────────────────────────────────────────────────────────
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: Radius.xl,
    borderColor: '#E5E7EB',
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  calCard: {
    paddingBottom: Spacing.lg,
  },
  cardTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: Spacing.md,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  countBadge: {
    backgroundColor: Colors.primaryFaint,
    borderRadius: Radius.full,
    paddingHorizontal: 10,
    paddingVertical: 2,
  },
  countBadgeText: {
    color: Colors.primary,
    fontWeight: '700',
    fontSize: 12,
  },

  // ── Calorie Ring ───────────────────────────────────────────────────────────
  calorieRingSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  calNumbersCol: {
    flex: 1,
  },
  calBig: {
    fontSize: 48,
    fontWeight: '900',
    color: '#1A1A2E',
    letterSpacing: -1,
  },
  calBigLabel: {
    fontSize: 12,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
  },
  calDivider: {
    height: 1,
    backgroundColor: '#E5E7EB',
    marginBottom: Spacing.sm,
    width: '60%',
  },
  calRemaining: {
    fontSize: 24,
    fontWeight: '800',
    color: '#2D6A4F',
  },
  calRemainingLabel: {
    fontSize: 12,
    color: Colors.textSecondary,
  },
  calRingCol: {
    alignItems: 'center',
    marginLeft: Spacing.md,
  },
  ringOuter: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: '#F0F4EE',
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: '#2D6A4F50',
    borderWidth: 3,
  },
  ringArc: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    borderRadius: 50,
  },
  ringInner: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  ringPct: {
    fontSize: 22,
    fontWeight: '900',
    color: '#2D6A4F',
  },
  ringPctLabel: {
    fontSize: 9,
    color: Colors.textSecondary,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  calGoalText: {
    fontSize: 11,
    color: Colors.textSecondary,
    marginTop: 6,
  },

  // ── Macros Grid ────────────────────────────────────────────────────────────
  macrosGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
    gap: 8,
  },
  macroCard: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderRadius: Radius.lg,
    borderColor: '#E5E7EB',
    borderWidth: 1,
    padding: 12,
    alignItems: 'center',
  },
  macroIconWrap: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 6,
  },
  macroEmoji: {
    fontSize: 18,
  },
  macroLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.3,
    marginBottom: 4,
  },
  macroValue: {
    fontSize: 18,
    fontWeight: '800',
  },
  macroGoal: {
    fontSize: 11,
    fontWeight: '500',
    color: Colors.textTertiary,
  },
  macroBar: {
    width: '100%',
    height: 3,
    backgroundColor: '#F0F4EE',
    borderRadius: 2,
    marginTop: 6,
    overflow: 'hidden',
  },
  macroBarFill: {
    height: '100%',
    borderRadius: 2,
  },

  // ── Food Log ───────────────────────────────────────────────────────────────
  foodRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  foodTypeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 12,
  },
  foodInfo: { flex: 1 },
  foodName: {
    fontSize: 14,
    fontWeight: '600',
    color: Colors.text,
  },
  foodType: {
    fontSize: 10,
    color: Colors.textTertiary,
    fontWeight: '700',
    letterSpacing: 0.5,
    marginTop: 2,
  },
  foodKcal: {
    fontSize: 14,
    fontWeight: '700',
  },

  // Empty state
  emptyState: {
    alignItems: 'center',
    paddingVertical: Spacing.lg,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#6B7280',
    marginTop: 8,
  },
  emptySubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
    marginTop: 4,
    lineHeight: 17,
  },

  // ── Weight Input ───────────────────────────────────────────────────────────
  weightRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  weightInput: {
    flex: 1,
    backgroundColor: '#F8FAF5',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    borderRadius: Radius.md,
    color: '#1A1A2E',
    paddingHorizontal: Spacing.md,
    paddingVertical: 11,
    fontSize: 15,
  },
  weightUnit: {
    color: Colors.textSecondary,
    fontSize: 14,
    fontWeight: '700',
    marginHorizontal: 10,
  },
  weightBtn: {
    backgroundColor: '#52B788',
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.md,
    paddingVertical: 12,
    minWidth: 90,
    alignItems: 'center',
  },
  weightBtnText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 13,
  },

  // ── Quick Actions ──────────────────────────────────────────────────────────
  quickActionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 8,
  },
  quickAction: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFFFFF',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    borderRadius: Radius.md,
    paddingVertical: 12,
    gap: 6,
  },
  quickActionText: {
    color: '#6B7280',
    fontSize: 12,
    fontWeight: '600',
  },
  quickActionDanger: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.danger + '10',
    borderColor: Colors.danger + '25',
    borderWidth: 1,
    borderRadius: Radius.md,
    paddingVertical: 12,
    gap: 6,
  },
  quickActionDangerText: {
    color: Colors.danger,
    fontSize: 12,
    fontWeight: '600',
  },
});

import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator, Alert, TextInput } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import { api } from '../../services/api';
import { GlassCard } from '../../components/GlassCard';
import { PrimaryButton } from '../../components/PrimaryButton';
import { Ionicons } from '@expo/vector-icons';

export default function DashboardScreen() {
  const { user, signOut } = useAuth();
  const [profile, setProfile] = useState<any>(null);
  const [plan, setPlan] = useState<any>(null);
  const [tracking, setTracking] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [weightInput, setWeightInput] = useState('');
  const [loggingWeight, setLoggingWeight] = useState(false);
  const router = useRouter();

  const loadData = async () => {
    setLoading(true);
    try {
      // 1. Try to fetch profile
      const userProfile = await api.getMe(); // checks auth
      try {
        const fullProfile = await api.getProtocoloActivo(); // dummy endpoint check for active profiles
        // We fetch active plan
        const activePlan = await api.getPlanActivo();
        setPlan(activePlan);
      } catch (e) {
        // User may not have profile complete
      }

      // Fetch tracking for today (YYYY-MM-DD)
      const todayStr = new Date().toISOString().split('T')[0];
      const trackingData = await api.getSeguimientoDia(todayStr);
      setTracking(trackingData);
      
      if (trackingData && trackingData.peso_actual) {
        setWeightInput(trackingData.peso_actual.toString());
      }
    } catch (e: any) {
      // Profile not completed or not loaded
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleWeightLog = async () => {
    const peso = parseFloat(weightInput);
    if (isNaN(peso) || peso <= 0) {
      Alert.alert('Error', 'Por favor ingresa un peso válido.');
      return;
    }
    setLoggingWeight(true);
    try {
      await api.registrarPeso(peso);
      Alert.alert('Éxito', 'Peso registrado correctamente.');
      loadData();
    } catch (e: any) {
      Alert.alert('Error', 'No se pudo registrar el peso.');
    } finally {
      setLoggingWeight(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  // If user has no active plan, show a beautiful call-to-action
  if (!plan) {
    return (
      <ScrollView contentContainerStyle={styles.scrollContainer}>
        <View style={styles.header}>
          <Text style={styles.greeting}>¡Hola, {user?.nombre || 'Usuario'}! 👋</Text>
          <Text style={styles.subtitle}>Comencemos a diseñar tu camino nutricional.</Text>
        </View>

        <GlassCard style={styles.welcomeCard}>
          <Text style={styles.welcomeTitle}>Aún no tienes un plan activo</Text>
          <Text style={styles.welcomeText}>
            Para calcular tus macros y generar tu menú de 7 días, primero necesitamos conocer tus hábitos, peso y objetivos principales mediante un chat inteligente de 2 minutos.
          </Text>
          <PrimaryButton
            title="✨ Empezar Onboarding"
            onPress={() => router.push('/chat_perfil')}
          />
        </GlassCard>

        <PrimaryButton title="Cerrar Sesión" onPress={signOut} style={styles.logoutBtn} />
      </ScrollView>
    );
  }

  const caloriasConsumidas = tracking?.calorias_consumidas || 0;
  const caloriasObjetivo = plan.calorias_objetivo || 2000;
  const pctCalorias = Math.min(caloriasConsumidas / caloriasObjetivo, 1);

  return (
    <ScrollView contentContainerStyle={styles.scrollContainer}>
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.greeting}>Hola, {user?.nombre || 'Usuario'} 👋</Text>
          <Text style={styles.dateText}>Tu progreso de hoy</Text>
        </View>
        <TouchableOpacity onPress={loadData} style={styles.iconBtn}>
          <Ionicons name="refresh" size={20} color={Colors.text} />
        </TouchableOpacity>
      </View>

      {/* Calories Card */}
      <GlassCard style={styles.progressCard}>
        <View style={styles.calRow}>
          <View>
            <Text style={styles.calNumber}>{caloriasConsumidas}</Text>
            <Text style={styles.calLabel}>Kcal consumidas</Text>
          </View>
          <View style={styles.calDivider} />
          <View>
            <Text style={[styles.calNumber, { color: Colors.secondary }]}>{caloriasObjetivo}</Text>
            <Text style={styles.calLabel}>Kcal objetivo</Text>
          </View>
        </View>

        <View style={styles.progressBarBg}>
          <View style={[styles.progressBarFill, { width: `${pctCalorias * 100}%` }]} />
        </View>
        <Text style={styles.calPercentage}>{Math.round(pctCalorias * 100)}% alcanzado</Text>
      </GlassCard>

      {/* Macros Grid */}
      <View style={styles.macrosRow}>
        <GlassCard style={styles.macroCard}>
          <Text style={styles.macroEmoji}>🥩</Text>
          <Text style={styles.macroTitle}>Proteínas</Text>
          <Text style={styles.macroValue}>
            {tracking?.proteinas_consumidas || 0}g / {plan.proteinas_g}g
          </Text>
        </GlassCard>

        <GlassCard style={styles.macroCard}>
          <Text style={styles.macroEmoji}>🌾</Text>
          <Text style={styles.macroTitle}>Carbos</Text>
          <Text style={styles.macroValue}>
            {tracking?.carbos_consumidas || 0}g / {plan.carbos_g}g
          </Text>
        </GlassCard>

        <GlassCard style={styles.macroCard}>
          <Text style={styles.macroEmoji}>🥑</Text>
          <Text style={styles.macroTitle}>Grasas</Text>
          <Text style={styles.macroValue}>
            {tracking?.grasas_consumidas || 0}g / {plan.grasas_g}g
          </Text>
        </GlassCard>
      </View>

      {/* Food Log list */}
      <GlassCard>
        <Text style={styles.sectionTitle}>Comidas de hoy</Text>
        {tracking?.comidas && tracking.comidas.length > 0 ? (
          tracking.comidas.map((item: any, i: number) => (
            <View key={i} style={styles.foodItem}>
              <View>
                <Text style={styles.foodName}>{item.nombre}</Text>
                <Text style={styles.foodType}>{item.comida_tipo.toUpperCase()}</Text>
              </View>
              <Text style={styles.foodKcal}>{item.kcal} Kcal</Text>
            </View>
          ))
        ) : (
          <Text style={styles.emptyText}>No has registrado comidas hoy. Usa el Escáner de Plato o registra manualmente.</Text>
        )}
      </GlassCard>

      {/* Register Weight */}
      <GlassCard>
        <Text style={styles.sectionTitle}>Registrar peso diario</Text>
        <View style={styles.weightRow}>
          <TextInput
            style={styles.weightInput}
            keyboardType="numeric"
            placeholder="Ej: 75.5"
            placeholderTextColor={Colors.textMuted}
            value={weightInput}
            onChangeText={setWeightInput}
          />
          <Text style={styles.weightUnit}>kg</Text>
          <TouchableOpacity
            style={styles.weightBtn}
            onPress={handleWeightLog}
            disabled={loggingWeight}
          >
            <Text style={styles.weightBtnText}>Registrar</Text>
          </TouchableOpacity>
        </View>
      </GlassCard>

      <PrimaryButton title="Re-hacer onboarding" onPress={() => router.push('/chat_perfil')} style={styles.reOnboardBtn} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scrollContainer: {
    flexGrow: 1,
    backgroundColor: Colors.background,
    padding: 20,
    paddingBottom: 40,
  },
  header: {
    marginTop: 24,
    marginBottom: 24,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 16,
    marginBottom: 20,
  },
  greeting: {
    color: Colors.text,
    fontSize: 24,
    fontWeight: '800',
  },
  subtitle: {
    color: Colors.textMuted,
    fontSize: 14,
    marginTop: 4,
  },
  dateText: {
    color: Colors.textMuted,
    fontSize: 14,
    marginTop: 2,
  },
  iconBtn: {
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    padding: 10,
    borderRadius: 12,
  },
  welcomeCard: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  welcomeTitle: {
    color: Colors.text,
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 12,
  },
  welcomeText: {
    color: Colors.textMuted,
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 20,
  },
  progressCard: {
    paddingVertical: 20,
    alignItems: 'center',
  },
  calRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    width: '100%',
    marginBottom: 20,
  },
  calNumber: {
    color: Colors.text,
    fontSize: 28,
    fontWeight: '800',
    textAlign: 'center',
  },
  calLabel: {
    color: Colors.textMuted,
    fontSize: 12,
    textAlign: 'center',
    marginTop: 2,
  },
  calDivider: {
    width: 1,
    height: 40,
    backgroundColor: Colors.cardBorder,
  },
  progressBarBg: {
    height: 8,
    width: '100%',
    backgroundColor: Colors.inputBg,
    borderRadius: 4,
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: Colors.accent,
  },
  calPercentage: {
    color: Colors.textMuted,
    fontSize: 12,
    marginTop: 8,
    fontWeight: '600',
  },
  macrosRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  macroCard: {
    flex: 1,
    marginHorizontal: 4,
    alignItems: 'center',
    paddingVertical: 14,
  },
  macroEmoji: {
    fontSize: 20,
    marginBottom: 4,
  },
  macroTitle: {
    color: Colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
  },
  macroValue: {
    color: Colors.text,
    fontSize: 13,
    fontWeight: '700',
    marginTop: 4,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
  },
  foodItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  foodName: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  foodType: {
    color: Colors.textMuted,
    fontSize: 10,
    marginTop: 2,
    fontWeight: '700',
  },
  foodKcal: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  emptyText: {
    color: Colors.textMuted,
    fontSize: 13,
    textAlign: 'center',
    paddingVertical: 10,
  },
  weightRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  weightInput: {
    flex: 1,
    backgroundColor: Colors.inputBg,
    borderColor: Colors.inputBorder,
    borderWidth: 1,
    borderRadius: 12,
    color: Colors.text,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
  },
  weightUnit: {
    color: Colors.text,
    fontSize: 16,
    marginHorizontal: 12,
    fontWeight: '700',
  },
  weightBtn: {
    backgroundColor: Colors.primary,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 11,
  },
  weightBtnText: {
    color: Colors.text,
    fontWeight: '700',
    fontSize: 14,
  },
  reOnboardBtn: {
    backgroundColor: 'transparent',
    borderColor: Colors.cardBorder,
    borderWidth: 1,
  },
  logoutBtn: {
    backgroundColor: 'transparent',
    borderColor: Colors.danger,
    borderWidth: 1,
  },
});

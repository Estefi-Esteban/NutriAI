import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { Colors } from '../constants/Colors';
import { api } from '../services/api';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { Ionicons } from '@expo/vector-icons';

export default function SupplementsScreen() {
  const [loading, setLoading] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [recs, setRecs] = useState<any>(null);

  const loadSupplements = async () => {
    setLoadingInitial(true);
    try {
      const data = await api.getMisSuplementos();
      setRecs(data);
    } catch (e) {
      // Recommendations not generated yet
    } finally {
      setLoadingInitial(false);
    }
  };

  useEffect(() => {
    loadSupplements();
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const data = await api.generarSuplementos(true); // Include pathology protocols
      setRecs(data);
      Alert.alert('Éxito', 'Recomendaciones de suplementación generadas.');
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudieron generar recomendaciones.');
    } finally {
      setLoading(false);
    }
  };

  if (loadingInitial) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <GlassCard style={styles.headerCard}>
        <Text style={styles.cardTitle}>Suplementación Personalizada</Text>
        <Text style={styles.cardSub}>
          Nuestra IA analiza tu perfil, actividad física, analíticas de sangre y patologías activas para recomendarte únicamente lo que necesitas, ahorrándote gastos innecesarios.
        </Text>
        <PrimaryButton title="⚡ Generar / Actualizar Recomendaciones" loading={loading} onPress={handleGenerate} />
      </GlassCard>

      {recs ? (
        <View style={styles.recsContainer}>
          {/* Needed Supplements */}
          <GlassCard style={styles.neededCard}>
            <Text style={[styles.sectionTitle, { color: Colors.success }]}>🟢 Necesarios (Déficit / Alta Prioridad)</Text>
            {recs.suplementos_necesarios && recs.suplementos_necesarios.length > 0 ? (
              recs.suplementos_necesarios.map((sup: any, i: number) => (
                <View key={i} style={styles.supItem}>
                  <Text style={styles.supName}>{sup.nombre}</Text>
                  <Text style={styles.supDose}>Dosis: {sup.dosis}</Text>
                  <Text style={styles.supReason}>{sup.motivo}</Text>
                </View>
              ))
            ) : (
              <Text style={styles.emptyText}>Ninguno recomendado de alta prioridad.</Text>
            )}
          </GlassCard>

          {/* Optional Supplements */}
          <GlassCard style={styles.optionalCard}>
            <Text style={[styles.sectionTitle, { color: Colors.secondary }]}>🟡 Opcionales (Mejora de Rendimiento / Bienestar)</Text>
            {recs.suplementos_opcionales && recs.suplementos_opcionales.length > 0 ? (
              recs.suplementos_opcionales.map((sup: any, i: number) => (
                <View key={i} style={styles.supItem}>
                  <Text style={styles.supName}>{sup.nombre}</Text>
                  <Text style={styles.supDose}>Dosis: {sup.dosis}</Text>
                  <Text style={styles.supReason}>{sup.motivo}</Text>
                </View>
              ))
            ) : (
              <Text style={styles.emptyText}>Ninguno recomendado opcional.</Text>
            )}
          </GlassCard>

          {/* Unnecessary Supplements */}
          <GlassCard style={styles.unnecessaryCard}>
            <Text style={[styles.sectionTitle, { color: Colors.danger }]}>🔴 Innecesarios / Desaconsejados</Text>
            {recs.suplementos_innecesarios && recs.suplementos_innecesarios.length > 0 ? (
              recs.suplementos_innecesarios.map((sup: any, i: number) => (
                <View key={i} style={styles.supItem}>
                  <Text style={styles.supName}>{sup.nombre}</Text>
                  <Text style={styles.supReason}>{sup.motivo}</Text>
                </View>
              ))
            ) : (
              <Text style={styles.emptyText}>No hay lista de suplementos innecesarios.</Text>
            )}
          </GlassCard>

          {/* General Notes */}
          {recs.notas && (
            <GlassCard>
              <Text style={styles.notesTitle}>Notas y Advertencias</Text>
              <Text style={styles.notesText}>{recs.notas}</Text>
            </GlassCard>
          )}
        </View>
      ) : (
        <View style={styles.noRecsContainer}>
          <Ionicons name="leaf-outline" size={48} color={Colors.textMuted} />
          <Text style={styles.noRecsText}>Aún no tienes recomendaciones.</Text>
          <Text style={styles.noRecsSubtext}>Toca el botón superior para generarlas.</Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.background,
    padding: 20,
    paddingBottom: 40,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerCard: {
    borderColor: 'rgba(99, 102, 241, 0.2)',
  },
  cardTitle: {
    color: Colors.text,
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  cardSub: {
    color: Colors.textMuted,
    fontSize: 13,
    marginBottom: 16,
    lineHeight: 18,
  },
  recsContainer: {
    marginTop: 12,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
    paddingBottom: 6,
  },
  supItem: {
    paddingVertical: 10,
    borderBottomColor: 'rgba(255, 255, 255, 0.03)',
    borderBottomWidth: 1,
  },
  supName: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  supDose: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '600',
    marginTop: 4,
  },
  supReason: {
    color: Colors.textMuted,
    fontSize: 12,
    lineHeight: 16,
    marginTop: 4,
  },
  emptyText: {
    color: Colors.textMuted,
    fontSize: 13,
    paddingVertical: 8,
  },
  neededCard: { borderColor: 'rgba(16, 185, 129, 0.2)' },
  optionalCard: { borderColor: 'rgba(167, 139, 250, 0.2)' },
  unnecessaryCard: { borderColor: 'rgba(239, 68, 68, 0.2)' },
  notesTitle: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 8,
  },
  notesText: {
    color: Colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  noRecsContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
  },
  noRecsText: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginTop: 16,
  },
  noRecsSubtext: {
    color: Colors.textMuted,
    fontSize: 13,
    marginTop: 6,
  },
});

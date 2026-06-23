import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { Colors } from '../constants/Colors';
import { api } from '../services/api';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { Ionicons } from '@expo/vector-icons';

const PATOLOGIAS_SOPORTADAS = [
  { id: 'diabetes', label: 'Diabetes' },
  { id: 'prediabetes', label: 'Prediabetes / Resistencia Insulina' },
  { id: 'hipertension', label: 'Hipertensión arterial' },
  { id: 'hipotiroidismo', label: 'Hipotiroidismo' },
  { id: 'sop', label: 'Síndrome de Ovario Poliquístico (SOP)' },
  { id: 'gota', label: 'Ácido Úrico Alto / Gota' },
  { id: 'celiaquia', label: 'Celiaquía / Intolerancia al Gluten' },
  { id: 'colesterol_alto', label: 'Colesterol Alto / Dislipemia' },
  { id: 'anemia', label: 'Anemia / Deficiencia de Hierro' }
];

export default function PathologyScreen() {
  const [selectedPat, setSelectedPat] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [loadingProtocol, setLoadingProtocol] = useState(true);
  const [protocol, setProtocol] = useState<any>(null);

  const loadProtocol = async () => {
    setLoadingProtocol(true);
    try {
      const data = await api.getProtocoloActivo();
      if (data) {
        setProtocol(data);
        
        // Prep selected checkboxes
        const selectedMap: Record<string, boolean> = {};
        if (data.patologias_identificadas) {
          data.patologias_identificadas.forEach((p: string) => {
            selectedMap[p] = true;
          });
        }
        setSelectedPat(selectedMap);
      }
    } catch (e) {
      // No active protocol
    } finally {
      setLoadingProtocol(false);
    }
  };

  useEffect(() => {
    loadProtocol();
  }, []);

  const togglePatology = (id: string) => {
    setSelectedPat(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleSaveProtocol = async () => {
    const list = Object.keys(selectedPat).filter(k => selectedPat[k]);
    setLoading(true);
    try {
      const data = await api.analizarPatologias(list);
      setProtocol(data);
      Alert.alert('Éxito', 'Protocolo clínico actualizado.');
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudo guardar el protocolo.');
    } finally {
      setLoading(false);
    }
  };

  if (loadingProtocol) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <GlassCard>
        <Text style={styles.cardTitle}>Declarar Condiciones Médicas</Text>
        <Text style={styles.cardSub}>Selecciona cualquier patología diagnosticada para ajustar tu plan nutricional de forma segura.</Text>

        {PATOLOGIAS_SOPORTADAS.map(pat => {
          const isChecked = selectedPat[pat.id] || false;
          return (
            <TouchableOpacity
              key={pat.id}
              style={styles.checkboxRow}
              activeOpacity={0.8}
              onPress={() => togglePatology(pat.id)}
            >
              <Ionicons
                name={isChecked ? 'checkbox' : 'square-outline'}
                size={20}
                color={isChecked ? Colors.primary : Colors.textMuted}
              />
              <Text style={[styles.checkboxLabel, isChecked && styles.checkboxLabelChecked]}>
                {pat.label}
              </Text>
            </TouchableOpacity>
          );
        })}

        <PrimaryButton title="Guardar y Generar Protocolo" loading={loading} onPress={handleSaveProtocol} />
      </GlassCard>

      {/* Protocol active output */}
      {protocol && (
        <View style={styles.protocolContainer}>
          <GlassCard style={styles.protocolCard}>
            <Text style={styles.sectionTitle}>📋 Protocolo Clínico Activo</Text>
            
            <View style={styles.infoLine}>
              <Text style={styles.infoLabel}>Nivel Restricción:</Text>
              <View style={[
                styles.statusBadge,
                protocol.nivel_restriccion === 'alto' ? styles.statusHigh : styles.statusNormal
              ]}>
                <Text style={styles.statusText}>{protocol.nivel_restriccion.toUpperCase()}</Text>
              </View>
            </View>

            <Text style={styles.subTitle}>Notas del Dietista Clínico</Text>
            <Text style={styles.notesText}>{protocol.notas_dietista}</Text>

            {protocol.restricciones && protocol.restricciones.length > 0 && (
              <>
                <Text style={styles.subTitle}>Restricciones Generales</Text>
                {protocol.restricciones.map((r: string, i: number) => (
                  <Text key={i} style={styles.listLine}>• {r.replace(/_/g, ' ')}</Text>
                ))}
              </>
            )}

            {protocol.alimentos_prohibidos && protocol.alimentos_prohibidos.length > 0 && (
              <>
                <Text style={[styles.subTitle, { color: Colors.danger }]}>🚫 Alimentos Prohibidos</Text>
                <View style={styles.foodRow}>
                  {protocol.alimentos_prohibidos.map((f: string, i: number) => (
                    <View key={i} style={[styles.chip, styles.chipProhibited]}>
                      <Text style={styles.chipText}>{f}</Text>
                    </View>
                  ))}
                </View>
              </>
            )}

            {protocol.alimentos_prioritarios && protocol.alimentos_prioritarios.length > 0 && (
              <>
                <Text style={[styles.subTitle, { color: Colors.success }]}>⭐ Alimentos Prioritarios</Text>
                <View style={styles.foodRow}>
                  {protocol.alimentos_prioritarios.map((f: string, i: number) => (
                    <View key={i} style={[styles.chip, styles.chipPriority]}>
                      <Text style={styles.chipText}>{f}</Text>
                    </View>
                  ))}
                </View>
              </>
            )}
          </GlassCard>
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
  cardTitle: {
    color: Colors.text,
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 4,
  },
  cardSub: {
    color: Colors.textMuted,
    fontSize: 13,
    marginBottom: 20,
  },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomColor: 'rgba(255, 255, 255, 0.03)',
    borderBottomWidth: 1,
  },
  checkboxLabel: {
    color: Colors.text,
    fontSize: 14,
    marginLeft: 12,
  },
  checkboxLabelChecked: {
    fontWeight: '700',
    color: Colors.text,
  },
  protocolContainer: {
    marginTop: 16,
  },
  protocolCard: {
    borderColor: 'rgba(239, 68, 68, 0.2)',
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 16,
  },
  infoLine: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  infoLabel: {
    color: Colors.textMuted,
    fontSize: 13,
    marginRight: 10,
    fontWeight: '600',
  },
  subTitle: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
    marginTop: 16,
    marginBottom: 8,
  },
  notesText: {
    color: Colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  listLine: {
    color: Colors.textMuted,
    fontSize: 13,
    marginBottom: 4,
  },
  foodRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  chip: {
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    marginRight: 6,
    marginBottom: 6,
  },
  chipText: {
    color: Colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  chipProhibited: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: 'rgba(239, 68, 68, 0.3)',
    borderWidth: 1,
  },
  chipPriority: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: 'rgba(16, 185, 129, 0.3)',
    borderWidth: 1,
  },
  statusBadge: {
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  statusText: {
    color: Colors.text,
    fontSize: 10,
    fontWeight: '700',
  },
  statusNormal: { backgroundColor: Colors.success },
  statusHigh: { backgroundColor: Colors.danger },
});

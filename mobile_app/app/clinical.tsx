import React, { useState } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator, Alert, TextInput } from 'react-native';
import { Colors } from '../constants/Colors';
import { api } from '../services/api';
import { GlassCard } from '../components/GlassCard';
import { PrimaryButton } from '../components/PrimaryButton';
import { InputField } from '../components/InputField';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';

export default function ClinicalScreen() {
  const [activeTab, setActiveTab] = useState<'manual' | 'upload'>('manual');
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<any>(null);
  
  // Manual Input States
  const [glucosa, setGlucosa] = useState('');
  const [colesterol, setColesterol] = useState('');
  const [trigliceridos, setTrigliceridos] = useState('');
  const [ldl, setLdl] = useState('');
  const [hdl, setHdl] = useState('');
  const [ferritina, setFerritina] = useState('');
  const [tsh, setTsh] = useState('');

  // Upload States
  const [fileUri, setFileUri] = useState<string | null>(null);

  const handleManualSubmit = async () => {
    const values: Record<string, number> = {};
    if (glucosa) values.glucosa = parseFloat(glucosa);
    if (colesterol) values.colesterol_total = parseFloat(colesterol);
    if (trigliceridos) values.trigliceridos = parseFloat(trigliceridos);
    if (ldl) values.ldl = parseFloat(ldl);
    if (hdl) values.hdl = parseFloat(hdl);
    if (ferritina) values.ferritina = parseFloat(ferritina);
    if (tsh) values.tsh = parseFloat(tsh);

    if (Object.keys(values).length === 0) {
      Alert.alert('Error', 'Ingresa al menos un marcador clínico.');
      return;
    }

    setLoading(true);
    try {
      const data = await api.analizarManual(values);
      setReport(data);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudo analizar el reporte.');
    } finally {
      setLoading(false);
    }
  };

  const handlePickFile = async () => {
    try {
      const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permiso denegado', 'Necesitamos acceso a tu biblioteca.');
        return;
      }

      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        quality: 0.8,
      });

      if (!result.canceled && result.assets && result.assets.length > 0) {
        setFileUri(result.assets[0].uri);
        setReport(null);
      }
    } catch (e) {
      Alert.alert('Error', 'No se pudo seleccionar la imagen.');
    }
  };

  const handleUploadSubmit = async () => {
    if (!fileUri) return;
    setLoading(true);
    try {
      // Simulate file analysis endpoint
      const filename = fileUri.split('/').pop() || 'analitica.jpg';
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : 'image/jpeg';
      
      const data = await api.analizarArchivo(fileUri, filename, type);
      setReport(data);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'No se pudo extraer información del archivo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {/* Selector tab */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'manual' && styles.tabButtonActive]}
          onPress={() => { setActiveTab('manual'); setReport(null); }}
        >
          <Text style={[styles.tabText, activeTab === 'manual' && styles.tabTextActive]}>Manual</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'upload' && styles.tabButtonActive]}
          onPress={() => { setActiveTab('upload'); setReport(null); }}
        >
          <Text style={[styles.tabText, activeTab === 'upload' && styles.tabTextActive]}>Someter Archivo</Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'manual' ? (
        <GlassCard>
          <Text style={styles.cardTitle}>Marcadores de Sangre</Text>
          <Text style={styles.cardSub}>Completa los valores numéricos de tu analítica reciente.</Text>
          
          <InputField label="Glucosa (mg/dL)" keyboardType="numeric" value={glucosa} onChangeText={setGlucosa} />
          <InputField label="Colesterol Total (mg/dL)" keyboardType="numeric" value={colesterol} onChangeText={setColesterol} />
          <InputField label="Triglicéridos (mg/dL)" keyboardType="numeric" value={trigliceridos} onChangeText={setTrigliceridos} />
          <InputField label="LDL Colesterol (mg/dL)" keyboardType="numeric" value={ldl} onChangeText={setLdl} />
          <InputField label="HDL Colesterol (mg/dL)" keyboardType="numeric" value={hdl} onChangeText={setHdl} />
          <InputField label="Ferritina (ng/mL)" keyboardType="numeric" value={ferritina} onChangeText={setFerritina} />
          <InputField label="TSH (mUI/L)" keyboardType="numeric" value={tsh} onChangeText={setTsh} />

          <PrimaryButton title="Calcular Reporte Clínico" loading={loading} onPress={handleManualSubmit} />
        </GlassCard>
      ) : (
        <GlassCard style={{ alignItems: 'center' }}>
          <Text style={styles.cardTitle}>Escanear Reporte</Text>
          <Text style={styles.cardSub}>Toma una foto de tu reporte clínico impreso o PDF para extraer marcadores.</Text>
          
          <TouchableOpacity onPress={handlePickFile} style={styles.filePicker}>
            {fileUri ? (
              <Text style={styles.filePickerText}>Imagen Seleccionada: {fileUri.split('/').pop()}</Text>
            ) : (
              <>
                <Ionicons name="cloud-upload-outline" size={40} color={Colors.textMuted} />
                <Text style={styles.filePickerLabel}>Buscar analítica en Galería</Text>
              </>
            )}
          </TouchableOpacity>

          {fileUri && (
            <PrimaryButton title="Extraer y Analizar" loading={loading} onPress={handleUploadSubmit} />
          )}
        </GlassCard>
      )}

      {loading && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>La IA está analizando los valores clínicos...</Text>
        </View>
      )}

      {/* Report Output */}
      {report && (
        <View style={styles.reportContainer}>
          <GlassCard style={styles.summaryCard}>
            <Text style={styles.sectionTitle}>Análisis Clínico Realizado</Text>
            <Text style={styles.summaryText}>{report.resumen_general}</Text>
            
            {report.requiere_atencion_medica && (
              <View style={styles.warningBox}>
                <Ionicons name="warning" size={20} color={Colors.danger} />
                <Text style={styles.warningText}>
                  Atención Médica Sugerida: {report.motivo_atencion_medica}
                </Text>
              </View>
            )}
          </GlassCard>

          <GlassCard>
            <Text style={styles.sectionTitle}>Marcadores Analizados</Text>
            {report.marcadores && Object.entries(report.marcadores).map(([key, marker]: [string, any], idx) => (
              <View key={idx} style={styles.markerRow}>
                <View>
                  <Text style={styles.markerName}>{key.toUpperCase()}</Text>
                  <Text style={styles.markerExplanation}>{marker.explicacion}</Text>
                </View>
                <View style={styles.markerRight}>
                  <Text style={styles.markerVal}>{marker.valor}</Text>
                  <View style={[
                    styles.statusBadge,
                    marker.estado === 'normal' ? styles.statusNormal : styles.statusElevado
                  ]}>
                    <Text style={styles.statusText}>{marker.estado.toUpperCase()}</Text>
                  </View>
                </View>
              </View>
            ))}
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
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: 12,
    marginBottom: 20,
    overflow: 'hidden',
  },
  tabButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
  },
  tabButtonActive: {
    backgroundColor: Colors.primary,
  },
  tabText: {
    color: Colors.textMuted,
    fontWeight: '700',
    fontSize: 14,
  },
  tabTextActive: {
    color: Colors.text,
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
  filePicker: {
    width: '100%',
    height: 140,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    marginBottom: 16,
  },
  filePickerLabel: {
    color: Colors.textMuted,
    fontSize: 13,
    marginTop: 10,
    fontWeight: '600',
  },
  filePickerText: {
    color: Colors.text,
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
    paddingHorizontal: 16,
  },
  loadingBox: {
    alignItems: 'center',
    marginVertical: 24,
  },
  loadingText: {
    color: Colors.textMuted,
    fontSize: 14,
    marginTop: 12,
    fontWeight: '600',
  },
  reportContainer: {
    marginTop: 12,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 12,
  },
  summaryCard: {
    borderColor: 'rgba(99, 102, 241, 0.2)',
  },
  summaryText: {
    color: Colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
  warningBox: {
    flexDirection: 'row',
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: 'rgba(239, 68, 68, 0.2)',
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 16,
    alignItems: 'center',
  },
  warningText: {
    color: Colors.danger,
    fontSize: 13,
    fontWeight: '600',
    marginLeft: 8,
    flex: 1,
  },
  markerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomColor: 'rgba(255, 255, 255, 0.03)',
    borderBottomWidth: 1,
  },
  markerName: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  markerExplanation: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 4,
    lineHeight: 14,
    maxWidth: 200,
  },
  markerRight: {
    alignItems: 'flex-end',
  },
  markerVal: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '800',
  },
  statusBadge: {
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginTop: 6,
  },
  statusText: {
    color: Colors.text,
    fontSize: 9,
    fontWeight: '700',
  },
  statusNormal: { backgroundColor: Colors.success },
  statusElevado: { backgroundColor: Colors.warning },
});

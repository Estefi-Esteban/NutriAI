import React, { useState } from 'react';
import { StyleSheet, Text, View, ScrollView, Image, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Colors } from '../../constants/Colors';
import { api } from '../../services/api';
import { GlassCard } from '../../components/GlassCard';
import { PrimaryButton } from '../../components/PrimaryButton';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

export default function VisionScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [registering, setRegistering] = useState(false);
  const router = useRouter();

  const pickImage = async (useCamera: boolean) => {
    try {
      let result;
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      };

      if (useCamera) {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permiso denegado', 'Necesitamos acceso a tu cámara para tomar fotos.');
          return;
        }
        result = await ImagePicker.launchCameraAsync(options);
      } else {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert('Permiso denegado', 'Necesitamos acceso a tu galería.');
          return;
        }
        result = await ImagePicker.launchImageLibraryAsync(options);
      }

      if (!result.canceled && result.assets && result.assets.length > 0) {
        const asset = result.assets[0];
        setImageUri(asset.uri);
        setAnalysis(null); // Clear previous analysis
      }
    } catch (e) {
      Alert.alert('Error', 'No se pudo seleccionar la imagen.');
    }
  };

  const handleAnalyze = async () => {
    if (!imageUri) return;
    setLoading(true);
    try {
      const filename = imageUri.split('/').pop() || 'plato.jpg';
      const match = /\.(\w+)$/.exec(filename);
      const type = match ? `image/${match[1]}` : 'image/jpeg';

      const data = await api.analizarPlato(imageUri, filename, type);
      setAnalysis(data);
    } catch (e: any) {
      Alert.alert('Error de análisis', e.message || 'No se pudo analizar la imagen.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!analysis || !analysis.totales) return;
    setRegistering(true);
    try {
      const name = analysis.resumen_plato || 'Plato Detectado';
      const payload = {
        nombre_plato: name,
        kcal: analysis.totales.kcal,
        proteinas_g: analysis.totales.proteinas_g,
        carbos_g: analysis.totales.carbos_g,
        grasas_g: analysis.totales.grasas_g,
      };
      await api.registrarMacrosPlato(payload);
      Alert.alert('Registrado', 'Los macros del plato han sido añadidos a tu seguimiento diario.', [
        { text: 'OK', onPress: () => router.replace('/(tabs)') }
      ]);
    } catch (e: any) {
      Alert.alert('Error', 'No se pudo registrar el plato en el diario.');
    } finally {
      setRegistering(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>📸 Foto a Macros</Text>
      <Text style={styles.subtitle}>Haz una foto a tu plato de comida para identificar sus alimentos y estimar sus macronutrientes.</Text>

      {/* Image Preview Box */}
      <View style={styles.imageBox}>
        {imageUri ? (
          <Image source={{ uri: imageUri }} style={styles.previewImage} />
        ) : (
          <View style={styles.placeholderContainer}>
            <Ionicons name="image-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.placeholderText}>Sube una foto de tu plato</Text>
          </View>
        )}
      </View>

      {/* Buttons to Pick Image */}
      <View style={styles.btnRow}>
        <TouchableOpacity style={styles.actionBtn} onPress={() => pickImage(true)}>
          <Ionicons name="camera" size={20} color={Colors.text} />
          <Text style={styles.actionBtnText}>Cámara</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={() => pickImage(false)}>
          <Ionicons name="images" size={20} color={Colors.text} />
          <Text style={styles.actionBtnText}>Galería</Text>
        </TouchableOpacity>
      </View>

      {/* Action Button: Analyze */}
      {imageUri && !analysis && (
        <PrimaryButton
          title="⚡ Analizar Plato"
          loading={loading}
          onPress={handleAnalyze}
          style={styles.analyzeBtn}
        />
      )}

      {loading && (
        <View style={styles.loadingBox}>
          <ActivityIndicator size="large" color={Colors.primary} />
          <Text style={styles.loadingText}>La IA está analizando tu comida...</Text>
        </View>
      )}

      {/* Analysis Output */}
      {analysis && (
        <View style={styles.analysisContainer}>
          <GlassCard>
            <Text style={styles.sectionTitle}>Análisis del Plato</Text>
            <Text style={styles.plateSummary}>{analysis.resumen_plato}</Text>
            
            <Text style={styles.subTitle}>Totales Estimados</Text>
            <View style={styles.totalsRow}>
              <View style={[styles.badge, styles.badgeKcal]}>
                <Text style={styles.badgeLabel}>Kcal</Text>
                <Text style={styles.badgeVal}>{analysis.totales.kcal}</Text>
              </View>
              <View style={[styles.badge, styles.badgeProt]}>
                <Text style={styles.badgeLabel}>Prot</Text>
                <Text style={styles.badgeVal}>{analysis.totales.proteinas_g}g</Text>
              </View>
              <View style={[styles.badge, styles.badgeCarb]}>
                <Text style={styles.badgeLabel}>Carb</Text>
                <Text style={styles.badgeVal}>{analysis.totales.carbos_g}g</Text>
              </View>
              <View style={[styles.badge, styles.badgeFat]}>
                <Text style={styles.badgeLabel}>Grasa</Text>
                <Text style={styles.badgeVal}>{analysis.totales.grasas_g}g</Text>
              </View>
            </View>
          </GlassCard>

          <GlassCard>
            <Text style={styles.sectionTitle}>Ingredientes Detectados</Text>
            {analysis.alimentos && analysis.alimentos.map((food: any, i: number) => (
              <View key={i} style={styles.foodRow}>
                <View style={styles.foodRowLeft}>
                  <Ionicons
                    name={food.verificado_rag ? 'checkmark-circle-outline' : 'help-circle-outline'}
                    size={18}
                    color={food.verificado_rag ? Colors.success : Colors.warning}
                  />
                  <Text style={styles.foodName}>{food.nombre_detectado}</Text>
                </View>
                <Text style={styles.foodQty}>{food.cantidad_g}g</Text>
              </View>
            ))}
          </GlassCard>

          <PrimaryButton
            title="💾 Registrar en mi Diario de hoy"
            loading={registering}
            onPress={handleRegister}
            style={styles.registerBtn}
          />
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
    flexGrow: 1,
  },
  title: {
    color: Colors.text,
    fontSize: 24,
    fontWeight: '800',
  },
  subtitle: {
    color: Colors.textSecondary,
    fontSize: 14,
    marginTop: 4,
    marginBottom: 20,
    lineHeight: 20,
  },
  imageBox: {
    height: 220,
    width: '100%',
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: 16,
    overflow: 'hidden',
    marginBottom: 16,
  },
  previewImage: {
    width: '100%',
    height: '100%',
    resizeMode: 'cover',
  },
  placeholderContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  placeholderText: {
    color: Colors.textSecondary,
    marginTop: 10,
    fontSize: 14,
    fontWeight: '600',
  },
  btnRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 12,
    marginHorizontal: 4,
  },
  actionBtnText: {
    color: Colors.text,
    fontWeight: '700',
    fontSize: 14,
    marginLeft: 8,
  },
  analyzeBtn: {
    marginVertical: 12,
  },
  loadingBox: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  loadingText: {
    color: Colors.textSecondary,
    fontSize: 14,
    marginTop: 12,
    fontWeight: '600',
  },
  analysisContainer: {
    marginTop: 12,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
  },
  plateSummary: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
  },
  subTitle: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 8,
  },
  totalsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  badge: {
    flex: 1,
    borderRadius: 12,
    paddingVertical: 10,
    alignItems: 'center',
    marginHorizontal: 3,
  },
  badgeLabel: {
    color: Colors.text,
    fontSize: 10,
    fontWeight: '600',
    opacity: 0.8,
  },
  badgeVal: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '800',
    marginTop: 4,
  },
  badgeKcal: { backgroundColor: Colors.primary + '15' },
  badgeProt: { backgroundColor: Colors.macroProtein + '20' },
  badgeCarb: { backgroundColor: Colors.macroCarbs + '20' },
  badgeFat: { backgroundColor: Colors.macroFat + '20' },
  foodRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  foodRowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  foodName: {
    color: Colors.text,
    fontSize: 14,
    marginLeft: 8,
  },
  foodQty: {
    color: Colors.primary,
    fontWeight: '700',
    fontSize: 13,
  },
  registerBtn: {
    marginVertical: 16,
  },
});

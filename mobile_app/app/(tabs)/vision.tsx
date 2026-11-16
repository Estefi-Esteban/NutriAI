import React, { useMemo, useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  Image,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { Colors } from '../../constants/Colors';
import { api } from '../../services/api';
import { GlassCard } from '../../components/GlassCard';
import { PrimaryButton } from '../../components/PrimaryButton';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

type MacroKey = 'kcal' | 'proteinas_g' | 'carbos_g' | 'grasas_g';

type Macros = Partial<Record<MacroKey, number | null>> & {
  alimentos_incluidos?: string[];
  alimentos_sin_datos?: string[];
  macros_incompletos?: string[];
  es_parcial?: boolean;
};

type AlimentoAnalizado = {
  nombre_detectado: string;
  cantidad_g: number | null;
  confianza_vision?: string;
  notas_vision?: string | null;
  verificado_rag: boolean;
  nombre_rag?: string | null;
  similitud_rag?: number | null;
  origen_macros?: string | null;
  motivo_no_verificado?: string | null;
  macros_estimados?: Macros | null;
  macros_verificados?: Macros | null;
};

type AnalisisPlato = {
  descripcion_plato: string;
  calidad_imagen?: string;
  advertencia?: string | null;
  alimentos: AlimentoAnalizado[];
  totales: Macros;
  totales_estimados?: Macros | null;
  totales_verificados?: Macros | null;
  totales_combinados?: Macros | null;
  validacion_nutricional?: {
    alimentos_verificados?: number;
    total_alimentos?: number;
    totales_verificados_completos?: boolean;
    alimentos_con_error_rag?: string[];
  };
  disclaimer?: string;
};

const MACROS: { key: MacroKey; label: string; suffix: string; color: string }[] = [
  { key: 'kcal', label: 'Energía', suffix: ' kcal', color: Colors.primary },
  { key: 'proteinas_g', label: 'Proteínas', suffix: ' g', color: Colors.macroProtein },
  { key: 'carbos_g', label: 'Carbohidratos', suffix: ' g', color: Colors.macroCarbs },
  { key: 'grasas_g', label: 'Grasas', suffix: ' g', color: Colors.macroFat },
];

function formatMacro(value: number | null | undefined, suffix: string): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Sin datos';
  return `${Number(value.toFixed(1))}${suffix}`;
}

function getMotivoNoVerificado(motivo?: string | null): string {
  const motivos: Record<string, string> = {
    cantidad_no_valida: 'No se conoce una cantidad válida en gramos.',
    nombre_no_disponible: 'No se pudo identificar el alimento con suficiente detalle.',
    error_rag: 'No se pudo consultar la base nutricional.',
    similitud_insuficiente: 'La coincidencia con la base nutricional no es suficientemente fiable.',
    datos_rag_incompletos: 'La base nutricional no contiene todos los macros necesarios.',
    sin_coincidencia: 'No se encontró una coincidencia adecuada en la base nutricional.',
  };
  return motivos[motivo || ''] || 'Los macros de este alimento no están verificados por la base nutricional.';
}

function MacroGrid({ data }: { data?: Macros | null }) {
  return (
    <View style={styles.totalsGrid}>
      {MACROS.map((macro) => (
        <View key={macro.key} style={[styles.macroCard, { borderLeftColor: macro.color }]}>
          <Text style={styles.macroLabel}>{macro.label}</Text>
          <Text style={styles.macroValue}>{formatMacro(data?.[macro.key], macro.suffix)}</Text>
        </View>
      ))}
    </View>
  );
}

export default function VisionScreen() {
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AnalisisPlato | null>(null);
  const [registering, setRegistering] = useState(false);
  const router = useRouter();

  const totalesCombinados = analysis?.totales_combinados ?? analysis?.totales;

  const macrosCombinadosCompletos = useMemo(() => {
    if (!totalesCombinados) return false;
    return MACROS.every(({ key }) => {
      const value = totalesCombinados[key];
      return typeof value === 'number' && Number.isFinite(value) && value >= 0;
    });
  }, [totalesCombinados]);

  const pickImage = async (useCamera: boolean) => {
    try {
      const options: ImagePicker.ImagePickerOptions = {
        mediaTypes: ImagePicker.MediaTypeOptions.Images,
        allowsEditing: true,
        aspect: [4, 3],
        quality: 0.8,
      };

      let result: ImagePicker.ImagePickerResult;

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

      if (!result.canceled && result.assets?.length) {
        setImageUri(result.assets[0].uri);
        setAnalysis(null);
      }
    } catch {
      Alert.alert('Error', 'No se pudo seleccionar la imagen.');
    }
  };

  const handleAnalyze = async () => {
    if (!imageUri || loading) return;

    setLoading(true);
    try {
      const filename = imageUri.split('/').pop() || 'plato.jpg';
      const extension = filename.split('.').pop()?.toLowerCase();
      const mimeTypes: Record<string, string> = {
        jpg: 'image/jpeg',
        jpeg: 'image/jpeg',
        png: 'image/png',
        webp: 'image/webp',
      };
      const mimeType = mimeTypes[extension || ''] || 'image/jpeg';

      const data = (await api.analizarPlato(imageUri, filename, mimeType)) as AnalisisPlato;
      if (!data || !Array.isArray(data.alimentos) || !data.totales) {
        throw new Error('El servidor devolvió una respuesta de análisis incompleta.');
      }
      setAnalysis(data);
    } catch (error: any) {
      Alert.alert('Error de análisis', error?.message || 'No se pudo analizar la imagen.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!analysis || !totalesCombinados) return;

    if (!macrosCombinadosCompletos) {
      Alert.alert(
        'No se puede registrar todavía',
        'Faltan uno o más valores nutricionales. No vamos a guardar los datos incompletos como si fueran un total válido.'
      );
      return;
    }

    Alert.alert(
      'Registrar estimación',
      'El total combinado puede incluir valores estimados por IA y valores calculados con datos de Qdrant. Se guardará como una estimación nutricional, no como una medición exacta.',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Registrar',
          onPress: async () => {
            setRegistering(true);
            try {
              await api.registrarMacrosPlato({
                nombre_plato: analysis.descripcion_plato?.trim() || 'Plato analizado por visión',
                kcal: totalesCombinados.kcal as number,
                proteinas_g: totalesCombinados.proteinas_g as number,
                carbos_g: totalesCombinados.carbos_g as number,
                grasas_g: totalesCombinados.grasas_g as number,
              });
              Alert.alert('Registrado', 'La estimación nutricional se ha añadido a tu diario.', [
                { text: 'OK', onPress: () => router.replace('/(tabs)') },
              ]);
            } catch (error: any) {
              Alert.alert(
                'Error al registrar',
                error?.message || 'No se pudo registrar el plato en el diario.'
              );
            } finally {
              setRegistering(false);
            }
          },
        },
      ]
    );
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>📸 Foto a macros</Text>
      <Text style={styles.subtitle}>
        Haz una foto de tu plato para identificar los alimentos y consultar sus macronutrientes.
        Diferenciamos las estimaciones de IA de los datos contrastados con la base nutricional.
      </Text>

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

      <View style={styles.btnRow}>
        <TouchableOpacity style={styles.actionBtn} onPress={() => pickImage(true)} disabled={loading}>
          <Ionicons name="camera" size={20} color={Colors.text} />
          <Text style={styles.actionBtnText}>Cámara</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.actionBtn} onPress={() => pickImage(false)} disabled={loading}>
          <Ionicons name="images" size={20} color={Colors.text} />
          <Text style={styles.actionBtnText}>Galería</Text>
        </TouchableOpacity>
      </View>

      {imageUri && !analysis && (
        <PrimaryButton
          title="⚡ Analizar plato"
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

      {analysis && (
        <View style={styles.analysisContainer}>
          <GlassCard>
            <Text style={styles.sectionTitle}>Análisis del plato</Text>
            <Text style={styles.plateSummary}>
              {analysis.descripcion_plato || 'No se ha generado una descripción del plato.'}
            </Text>
            <View style={styles.metaRow}>
              <Text style={styles.metaText}>Calidad de imagen: {analysis.calidad_imagen || 'No indicada'}</Text>
              <Text style={styles.metaText}>
                Verificados: {analysis.validacion_nutricional?.alimentos_verificados ?? 0}/
                {analysis.validacion_nutricional?.total_alimentos ?? analysis.alimentos.length}
              </Text>
            </View>
          </GlassCard>

          <GlassCard>
            <Text style={styles.sectionTitle}>Totales combinados</Text>
            <Text style={styles.helperText}>
              Se utiliza una sola fuente por alimento: Qdrant cuando está verificado y estimación visual cuando no lo está.
            </Text>
            <MacroGrid data={totalesCombinados} />
            {!!totalesCombinados?.macros_incompletos?.length && (
              <Text style={styles.warningText}>
                Datos incompletos: {totalesCombinados.macros_incompletos.join(', ')}.
              </Text>
            )}
          </GlassCard>

          <GlassCard>
            <Text style={styles.sectionTitle}>Datos estimados por IA</Text>
            <Text style={styles.helperText}>
              Solo incluye alimentos no verificados para los que la IA ha proporcionado estimaciones.
            </Text>
            <MacroGrid data={analysis.totales_estimados} />
            {!!analysis.totales_estimados?.macros_incompletos?.length && (
              <Text style={styles.warningText}>
                No se pueden completar estos macros: {analysis.totales_estimados.macros_incompletos.join(', ')}.
              </Text>
            )}
          </GlassCard>

          <GlassCard>
            <Text style={styles.sectionTitle}>Datos verificados por Qdrant</Text>
            <Text style={styles.helperText}>
              Calculados con los valores nutricionales de referencia y la cantidad estimada en gramos.
            </Text>
            <MacroGrid data={analysis.totales_verificados} />
            {analysis.totales_verificados?.es_parcial && (
              <Text style={styles.warningText}>
                Es un subtotal: hay alimentos del plato que no se han podido verificar.
              </Text>
            )}
            {!!analysis.totales_verificados?.macros_incompletos?.length && (
              <Text style={styles.warningText}>
                No se pueden completar estos macros: {analysis.totales_verificados.macros_incompletos.join(', ')}.
              </Text>
            )}
          </GlassCard>

          <GlassCard>
            <Text style={styles.sectionTitle}>Ingredientes detectados</Text>
            {analysis.alimentos.length === 0 ? (
              <Text style={styles.helperText}>No se han detectado alimentos.</Text>
            ) : (
              analysis.alimentos.map((food, index) => {
                const macros = food.verificado_rag ? food.macros_verificados : food.macros_estimados;
                return (
                  <View key={`${food.nombre_detectado}-${index}`} style={styles.foodCard}>
                    <View style={styles.foodHeader}>
                      <View style={styles.foodTitleRow}>
                        <Ionicons
                          name={food.verificado_rag ? 'checkmark-circle' : 'alert-circle'}
                          size={19}
                          color={food.verificado_rag ? Colors.success : Colors.warning}
                        />
                        <Text style={styles.foodName}>{food.nombre_detectado}</Text>
                      </View>
                      <Text style={styles.foodQty}>
                        {typeof food.cantidad_g === 'number' ? `${food.cantidad_g} g` : 'Cantidad desconocida'}
                      </Text>
                    </View>

                    <Text style={food.verificado_rag ? styles.verifiedLabel : styles.unverifiedLabel}>
                      {food.verificado_rag
                        ? `Verificado por Qdrant${food.nombre_rag ? ` · ${food.nombre_rag}` : ''}`
                        : food.origen_macros === 'estimacion_visual'
                          ? 'Macros estimados por IA · No verificados'
                          : 'Sin datos nutricionales disponibles'}
                    </Text>

                    {!food.verificado_rag && (
                      <Text style={styles.reasonText}>
                        {getMotivoNoVerificado(food.motivo_no_verificado)}
                      </Text>
                    )}

                    <View style={styles.foodMacros}>
                      {MACROS.map((macro) => (
                        <Text key={macro.key} style={styles.foodMacroText}>
                          {macro.label}: {formatMacro(macros?.[macro.key], macro.suffix)}
                        </Text>
                      ))}
                    </View>

                    {!!food.notas_vision && (
                      <Text style={styles.reasonText}>{food.notas_vision}</Text>
                    )}
                  </View>
                );
              })
            )}
          </GlassCard>

          {!!analysis.advertencia && (
            <View style={styles.warningBox}>
              <Ionicons name="warning-outline" size={20} color={Colors.warning} />
              <Text style={styles.warningBoxText}>{analysis.advertencia}</Text>
            </View>
          )}

          {!!analysis.disclaimer && (
            <Text style={styles.disclaimer}>{analysis.disclaimer}</Text>
          )}

          <PrimaryButton
            title="💾 Registrar estimación en mi diario"
            loading={registering}
            onPress={handleRegister}
            disabled={!macrosCombinadosCompletos || registering}
            style={styles.registerBtn}
          />
          {!macrosCombinadosCompletos && (
            <Text style={styles.blockedText}>
              No se puede registrar: el total combinado contiene uno o más macros sin datos completos.
            </Text>
          )}

          <TouchableOpacity
            style={styles.retryBtn}
            onPress={() => {
              setAnalysis(null);
            }}
          >
            <Ionicons name="refresh-outline" size={18} color={Colors.primary} />
            <Text style={styles.retryText}>Analizar otra imagen</Text>
          </TouchableOpacity>
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
    gap: 12,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 8,
  },
  plateSummary: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 12,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 8,
  },
  metaText: {
    color: Colors.textMuted,
    fontSize: 12,
  },
  helperText: {
    color: Colors.textSecondary,
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 10,
  },
  totalsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  macroCard: {
    width: '48%',
    backgroundColor: Colors.cardBg,
    borderRadius: 10,
    borderLeftWidth: 3,
    padding: 10,
  },
  macroLabel: {
    color: Colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
  },
  macroValue: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '800',
    marginTop: 5,
  },
  warningText: {
    color: Colors.warning,
    fontSize: 12,
    marginTop: 10,
    lineHeight: 17,
  },
  foodCard: {
    paddingVertical: 12,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  foodHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  foodTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  foodName: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
    marginLeft: 7,
    flexShrink: 1,
  },
  foodQty: {
    color: Colors.primary,
    fontWeight: '700',
    fontSize: 12,
  },
  verifiedLabel: {
    color: Colors.success,
    fontSize: 12,
    marginTop: 6,
    fontWeight: '600',
  },
  unverifiedLabel: {
    color: Colors.warning,
    fontSize: 12,
    marginTop: 6,
    fontWeight: '600',
  },
  reasonText: {
    color: Colors.textSecondary,
    fontSize: 12,
    marginTop: 5,
    lineHeight: 17,
  },
  foodMacros: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 8,
  },
  foodMacroText: {
    color: Colors.text,
    fontSize: 11,
  },
  warningBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: Colors.cardBg,
    borderColor: Colors.warning,
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    gap: 8,
  },
  warningBoxText: {
    color: Colors.text,
    fontSize: 12,
    flex: 1,
    lineHeight: 18,
  },
  disclaimer: {
    color: Colors.textMuted,
    fontSize: 11,
    lineHeight: 17,
  },
  registerBtn: {
    marginTop: 8,
  },
  blockedText: {
    color: Colors.warning,
    fontSize: 12,
    lineHeight: 17,
    textAlign: 'center',
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
    gap: 7,
  },
  retryText: {
    color: Colors.primary,
    fontSize: 13,
    fontWeight: '700',
  },
});

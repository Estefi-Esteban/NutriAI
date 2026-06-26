import React, { useState, useEffect } from 'react';
import {
  StyleSheet, Text, View, ScrollView,
  TouchableOpacity, ActivityIndicator, Alert, Modal
} from 'react-native';
import { Colors } from '../../constants/Colors';
import { Spacing, Radius } from '../../constants/theme';
import { api } from '../../services/api';
import { GlassCard } from '../../components/GlassCard';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const DIAS_SHORT = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

const MEAL_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  desayuno: { label: 'Desayuno', icon: 'sunny-outline', color: Colors.macroCarbs },
  comida:   { label: 'Comida',   icon: 'restaurant-outline', color: Colors.primary },
  cena:     { label: 'Cena',     icon: 'moon-outline', color: '#A78BFA' },
  snack:    { label: 'Snack',    icon: 'nutrition-outline', color: Colors.macroProtein },
};

// ─── Meal Card ────────────────────────────────────────────────────────────
function MealCard({ mealKey, meal, onPress }: { mealKey: string; meal: any; onPress: () => void }) {
  const config = MEAL_CONFIG[mealKey] || { label: mealKey, icon: 'restaurant-outline', color: Colors.primary };
  return (
    <TouchableOpacity activeOpacity={0.85} onPress={onPress}>
      <View style={styles.mealCard}>
        {/* Colored left border */}
        <View style={[styles.mealAccentBar, { backgroundColor: config.color }]} />
        <View style={styles.mealCardContent}>
          <View style={styles.mealHeader}>
            <View style={[styles.mealTypeChip, { backgroundColor: config.color + '18' }]}>
              <Ionicons name={config.icon as any} size={13} color={config.color} />
              <Text style={[styles.mealTypeText, { color: config.color }]}>{config.label}</Text>
            </View>
            <View style={styles.timeChip}>
              <Ionicons name="time-outline" size={12} color={Colors.textTertiary} />
              <Text style={styles.timeChipText}>{meal.tiempo_preparacion || '15 min'}</Text>
            </View>
          </View>
          <Text style={styles.mealName}>{meal.nombre_plato}</Text>
          <View style={styles.macroBadgesRow}>
            <View style={[styles.badge, { backgroundColor: Colors.primary + '18' }]}>
              <Text style={[styles.badgeText, { color: Colors.primary }]}>{meal.kcal} kcal</Text>
            </View>
            <View style={[styles.badge, { backgroundColor: Colors.macroProtein + '18' }]}>
              <Text style={[styles.badgeText, { color: Colors.macroProtein }]}>{meal.proteinas_g}g P</Text>
            </View>
            <View style={[styles.badge, { backgroundColor: Colors.macroCarbs + '18' }]}>
              <Text style={[styles.badgeText, { color: Colors.macroCarbs }]}>{meal.carbos_g}g C</Text>
            </View>
            <View style={[styles.badge, { backgroundColor: Colors.macroFat + '18' }]}>
              <Text style={[styles.badgeText, { color: Colors.macroFat }]}>{meal.grasas_g}g G</Text>
            </View>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={18} color={Colors.textTertiary} style={styles.mealChevron} />
      </View>
    </TouchableOpacity>
  );
}

// ─── Main Screen ──────────────────────────────────────────────────────────
export default function PlanScreen() {
  const [activeTab, setActiveTab] = useState<'menu' | 'shopping'>('menu');
  const [selectedDay, setSelectedDay] = useState('Lunes');
  const [plan, setPlan] = useState<any>(null);
  const [shoppingList, setShoppingList] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedMeal, setSelectedMeal] = useState<any>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const activePlan = await api.getPlanActivo();
      setPlan(activePlan);
      const list = await api.getListaCompra();
      setShoppingList(list.categorias || []);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => { loadData(); }, []);

  const toggleCheckItem = (itemName: string) => {
    setCheckedItems(prev => ({ ...prev, [itemName]: !prev[itemName] }));
  };

  const openRecipeDetails = (meal: any, title: string) => {
    setSelectedMeal({ ...meal, title });
    setModalVisible(true);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
        <Text style={styles.loadingText}>Cargando tu plan...</Text>
      </View>
    );
  }

  if (!plan) {
    return (
      <View style={styles.noPlanContainer}>
        <Text style={styles.noPlanEmoji}>🍽️</Text>
        <Text style={styles.noPlanText}>Sin plan activo</Text>
        <Text style={styles.noPlanSubtext}>Ve al Inicio y completa el onboarding para generar tu menú semanal.</Text>
      </View>
    );
  }

  const mealsForDay = plan.plan_semanal?.[selectedDay] || {};

  return (
    <View style={styles.container}>
      {/* ── Tab Switcher ── */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabBtn, activeTab === 'menu' && styles.tabBtnActive]}
          onPress={() => setActiveTab('menu')}
        >
          <Ionicons
            name="restaurant-outline"
            size={16}
            color={activeTab === 'menu' ? Colors.primary : Colors.textSecondary}
          />
          <Text style={[styles.tabText, activeTab === 'menu' && styles.tabTextActive]}>
            Menú Semanal
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabBtn, activeTab === 'shopping' && styles.tabBtnActive]}
          onPress={() => setActiveTab('shopping')}
        >
          <Ionicons
            name="cart-outline"
            size={16}
            color={activeTab === 'shopping' ? Colors.primary : Colors.textSecondary}
          />
          <Text style={[styles.tabText, activeTab === 'shopping' && styles.tabTextActive]}>
            Lista de Compra
          </Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'menu' ? (
        <View style={{ flex: 1 }}>
          {/* ── Day Selector ── */}
          <View style={styles.daySelectorContainer}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.daySelectorScroll}>
              {DIAS.map((day, idx) => (
                <TouchableOpacity
                  key={day}
                  style={[styles.dayBadge, selectedDay === day && styles.dayBadgeActive]}
                  onPress={() => setSelectedDay(day)}
                >
                  <Text style={[styles.dayBadgeShort, selectedDay === day && styles.dayBadgeShortActive]}>
                    {DIAS_SHORT[idx]}
                  </Text>
                  <Text style={[styles.dayBadgeNum, selectedDay === day && styles.dayBadgeNumActive]}>
                    {idx + 1}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* ── Meals List ── */}
          <ScrollView contentContainerStyle={styles.scrollContent}>
            {['desayuno', 'comida', 'cena', 'snack'].map(mealKey => {
              const meal = mealsForDay[mealKey];
              if (!meal) return null;
              return (
                <MealCard
                  key={mealKey}
                  mealKey={mealKey}
                  meal={meal}
                  onPress={() => openRecipeDetails(meal, MEAL_CONFIG[mealKey]?.label || mealKey)}
                />
              );
            })}
            {Object.keys(mealsForDay).length === 0 && (
              <View style={styles.emptyDay}>
                <Ionicons name="calendar-outline" size={36} color={Colors.textTertiary} />
                <Text style={styles.emptyDayText}>No hay comidas para {selectedDay}</Text>
              </View>
            )}
          </ScrollView>
        </View>
      ) : (
        /* ── Shopping List ── */
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {shoppingList && shoppingList.length > 0 ? (
            shoppingList.map((cat: any, i: number) => {
              const checkedCount = cat.ingredientes.filter((ing: any) => checkedItems[ing.nombre]).length;
              return (
                <View key={i} style={styles.shoppingCategory}>
                  <View style={styles.shopCatHeader}>
                    <Text style={styles.shopCatTitle}>{cat.nombre_categoria}</Text>
                    <Text style={styles.shopCatCount}>
                      {checkedCount}/{cat.ingredientes.length}
                    </Text>
                  </View>
                  {cat.ingredientes.map((ing: any, idx: number) => {
                    const isChecked = checkedItems[ing.nombre] || false;
                    return (
                      <TouchableOpacity
                        key={idx}
                        style={styles.shoppingItem}
                        onPress={() => toggleCheckItem(ing.nombre)}
                        activeOpacity={0.7}
                      >
                        <Ionicons
                          name={isChecked ? 'checkmark-circle' : 'ellipse-outline'}
                          size={22}
                          color={isChecked ? Colors.primary : Colors.textTertiary}
                        />
                        <Text style={[styles.shoppingName, isChecked && styles.shoppingChecked]}>
                          {ing.nombre}
                        </Text>
                        <Text style={styles.shoppingQty}>
                          {ing.cantidad} {ing.unidad}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              );
            })
          ) : (
            <View style={styles.emptyDay}>
              <Ionicons name="cart-outline" size={36} color={Colors.textTertiary} />
              <Text style={styles.emptyDayText}>No hay lista de compra generada</Text>
            </View>
          )}
        </ScrollView>
      )}

      {/* ── Recipe Modal ── */}
      {selectedMeal && (
        <Modal
          animationType="slide"
          transparent
          visible={modalVisible}
          onRequestClose={() => setModalVisible(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalSheet}>
              {/* Handle */}
              <View style={styles.modalHandle} />

              {/* Modal Header */}
              <View style={styles.modalHeader}>
                <View>
                  <Text style={styles.modalCategory}>{selectedMeal.title}</Text>
                  <Text style={styles.modalTitle}>{selectedMeal.nombre_plato}</Text>
                </View>
                <TouchableOpacity onPress={() => setModalVisible(false)} style={styles.closeBtn}>
                  <Ionicons name="close" size={22} color={Colors.text} />
                </TouchableOpacity>
              </View>

              <ScrollView contentContainerStyle={styles.modalScroll} showsVerticalScrollIndicator={false}>
                {/* Meta row */}
                <View style={styles.metaRow}>
                  <View style={styles.metaBadge}>
                    <Ionicons name="flash" size={14} color={Colors.primary} />
                    <Text style={styles.metaText}>{selectedMeal.kcal} kcal</Text>
                  </View>
                  <View style={styles.metaBadge}>
                    <Ionicons name="time-outline" size={14} color={Colors.macroCarbs} />
                    <Text style={styles.metaText}>{selectedMeal.tiempo_preparacion || '15 min'}</Text>
                  </View>
                  <View style={styles.metaBadge}>
                    <Ionicons name="ribbon-outline" size={14} color={Colors.macroFat} />
                    <Text style={styles.metaText}>{selectedMeal.dificultad || 'Fácil'}</Text>
                  </View>
                </View>

                {/* Macros */}
                <Text style={styles.modalSectionTitle}>Macronutrientes</Text>
                <View style={styles.macrosBox}>
                  {[
                    { val: selectedMeal.proteinas_g, label: 'Proteína', color: Colors.macroProtein },
                    { val: selectedMeal.carbos_g, label: 'Carbos', color: Colors.macroCarbs },
                    { val: selectedMeal.grasas_g, label: 'Grasas', color: Colors.macroFat },
                  ].map((m, i) => (
                    <View key={i} style={styles.macroBox}>
                      <Text style={[styles.macroBoxVal, { color: m.color }]}>{m.val}g</Text>
                      <Text style={styles.macroBoxLabel}>{m.label}</Text>
                    </View>
                  ))}
                </View>

                {/* Ingredients */}
                {selectedMeal.ingredientes && (
                  <>
                    <Text style={styles.modalSectionTitle}>Ingredientes</Text>
                    {selectedMeal.ingredientes.map((ing: string, i: number) => (
                      <View key={i} style={styles.ingredientRow}>
                        <View style={styles.ingredientDot} />
                        <Text style={styles.ingredientText}>{ing}</Text>
                      </View>
                    ))}
                  </>
                )}

                {/* Steps */}
                {selectedMeal.pasos && (
                  <>
                    <Text style={styles.modalSectionTitle}>Preparación</Text>
                    {selectedMeal.pasos.map((step: string, i: number) => (
                      <View key={i} style={styles.stepRow}>
                        <View style={styles.stepCircle}>
                          <Text style={styles.stepNum}>{i + 1}</Text>
                        </View>
                        <Text style={styles.stepText}>{step}</Text>
                      </View>
                    ))}
                  </>
                )}
              </ScrollView>
            </View>
          </View>
        </Modal>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadingText: {
    color: Colors.textSecondary,
    marginTop: 12,
    fontSize: 14,
  },
  noPlanContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.lg,
  },
  noPlanEmoji: { fontSize: 52, marginBottom: Spacing.md },
  noPlanText: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
    textAlign: 'center',
  },
  noPlanSubtext: {
    color: Colors.textSecondary,
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
    lineHeight: 20,
  },

  // Tab bar
  tabBar: {
    flexDirection: 'row',
    backgroundColor: Colors.backgroundGradStart,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  tabBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 14,
    gap: 6,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabBtnActive: {
    borderBottomColor: Colors.primary,
  },
  tabText: {
    color: Colors.textSecondary,
    fontWeight: '600',
    fontSize: 14,
  },
  tabTextActive: {
    color: Colors.primary,
  },

  // Day selector
  daySelectorContainer: {
    backgroundColor: Colors.backgroundGradStart,
    paddingVertical: 12,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  daySelectorScroll: {
    paddingHorizontal: Spacing.md,
    gap: 8,
  },
  dayBadge: {
    alignItems: 'center',
    backgroundColor: '#F0F4EE',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    borderRadius: Radius.lg,
    paddingHorizontal: 14,
    paddingVertical: 8,
    minWidth: 52,
  },
  dayBadgeActive: {
    backgroundColor: '#D8F3DC',
    borderColor: '#52B788',
  },
  dayBadgeShort: {
    color: Colors.textSecondary,
    fontWeight: '700',
    fontSize: 11,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  dayBadgeShortActive: {
    color: Colors.primary,
  },
  dayBadgeNum: {
    color: Colors.textTertiary,
    fontSize: 11,
    marginTop: 2,
  },
  dayBadgeNumActive: {
    color: Colors.primary,
  },

  scrollContent: {
    padding: Spacing.md,
    paddingBottom: 40,
  },

  // Meal Card
  mealCard: {
    flexDirection: 'row',
    backgroundColor: Colors.backgroundGradStart,
    borderRadius: Radius.xl,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    marginBottom: Spacing.sm + 4,
    overflow: 'hidden',
    alignItems: 'stretch',
  },
  mealAccentBar: {
    width: 4,
    flexShrink: 0,
  },
  mealCardContent: {
    flex: 1,
    padding: Spacing.md,
  },
  mealHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  mealTypeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: Radius.full,
    paddingHorizontal: 10,
    paddingVertical: 4,
    gap: 4,
  },
  mealTypeText: {
    fontSize: 12,
    fontWeight: '700',
  },
  timeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
  },
  timeChipText: {
    color: Colors.textTertiary,
    fontSize: 12,
  },
  mealName: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: Spacing.sm,
    lineHeight: 22,
  },
  macroBadgesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
  },
  badge: {
    borderRadius: Radius.sm,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
  },
  mealChevron: {
    alignSelf: 'center',
    marginRight: Spacing.sm,
  },

  // Empty day
  emptyDay: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
  },
  emptyDayText: {
    color: Colors.textSecondary,
    fontSize: 14,
    marginTop: 10,
  },

  // Shopping
  shoppingCategory: {
    backgroundColor: Colors.backgroundGradStart,
    borderRadius: Radius.xl,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  shopCatHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.sm,
    paddingBottom: Spacing.sm,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  shopCatTitle: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '700',
  },
  shopCatCount: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '700',
    backgroundColor: Colors.primaryFaint,
    borderRadius: Radius.full,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  shoppingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomColor: Colors.cardBorder + '60',
    borderBottomWidth: 1,
    gap: 10,
  },
  shoppingName: {
    color: Colors.text,
    fontSize: 14,
    flex: 1,
  },
  shoppingChecked: {
    color: Colors.textTertiary,
    textDecorationLine: 'line-through',
  },
  shoppingQty: {
    color: Colors.primary,
    fontWeight: '700',
    fontSize: 13,
  },

  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.4)',
    justifyContent: 'flex-end',
  },
  modalSheet: {
    backgroundColor: Colors.backgroundGradStart,
    borderTopLeftRadius: Radius.xxl,
    borderTopRightRadius: Radius.xxl,
    height: '85%',
    borderColor: Colors.cardBorder,
    borderTopWidth: 1,
  },
  modalHandle: {
    width: 36,
    height: 4,
    backgroundColor: Colors.cardBorder,
    borderRadius: 2,
    alignSelf: 'center',
    marginTop: 10,
    marginBottom: 4,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  modalCategory: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  modalTitle: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
    maxWidth: 260,
  },
  closeBtn: {
    padding: 4,
    marginTop: 2,
  },
  modalScroll: {
    padding: Spacing.lg,
    paddingBottom: 48,
  },
  metaRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: Spacing.lg,
  },
  metaBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F0F4EE',
    borderRadius: Radius.full,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    gap: 5,
  },
  metaText: {
    color: Colors.text,
    fontSize: 12,
    fontWeight: '600',
  },
  modalSectionTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: Spacing.sm,
    marginTop: Spacing.md,
  },
  macrosBox: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#F8FAF5',
    borderColor: '#E5E7EB',
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  macroBox: {
    alignItems: 'center',
    flex: 1,
  },
  macroBoxVal: {
    fontSize: 22,
    fontWeight: '800',
  },
  macroBoxLabel: {
    color: Colors.textSecondary,
    fontSize: 11,
    marginTop: 3,
    fontWeight: '600',
  },
  ingredientRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 10,
  },
  ingredientDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.primary,
    flexShrink: 0,
  },
  ingredientText: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    flex: 1,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: Spacing.sm,
    gap: 12,
  },
  stepCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: Colors.primaryFaint,
    borderColor: Colors.primary + '40',
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 1,
  },
  stepNum: {
    color: Colors.primary,
    fontSize: 11,
    fontWeight: '800',
  },
  stepText: {
    color: Colors.textSecondary,
    fontSize: 14,
    lineHeight: 20,
    flex: 1,
  },
});

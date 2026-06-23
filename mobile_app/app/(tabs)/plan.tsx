import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity, ActivityIndicator, Alert, Modal } from 'react-native';
import { Colors } from '../../constants/Colors';
import { api } from '../../services/api';
import { GlassCard } from '../../components/GlassCard';
import { Ionicons } from '@expo/vector-icons';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

export default function PlanScreen() {
  const [activeTab, setActiveTab] = useState<'menu' | 'shopping'>('menu');
  const [selectedDay, setSelectedDay] = useState('Lunes');
  const [plan, setPlan] = useState<any>(null);
  const [shoppingList, setShoppingList] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  // Recipe Modal State
  const [selectedMeal, setSelectedMeal] = useState<any>(null);
  const [modalVisible, setModalVisible] = useState(false);

  // Checklist items
  const [checkedItems, setCheckedItems] = useState<Record<string, boolean>>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const activePlan = await api.getPlanActivo();
      setPlan(activePlan);
      const list = await api.getListaCompra();
      setShoppingList(list.categorias || []);
    } catch (e: any) {
      // User might not have generated a plan yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const toggleCheckItem = (itemName: string) => {
    setCheckedItems(prev => ({
      ...prev,
      [itemName]: !prev[itemName],
    }));
  };

  const openRecipeDetails = (meal: any, title: string) => {
    setSelectedMeal({ ...meal, title });
    setModalVisible(true);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  if (!plan) {
    return (
      <View style={styles.noPlanContainer}>
        <Text style={styles.noPlanText}>Aún no has generado ningún plan.</Text>
        <Text style={styles.noPlanSubtext}>Ve al Inicio para empezar tu onboarding.</Text>
      </View>
    );
  }

  // Get meals for selected day
  const mealsForDay = plan.plan_semanal?.[selectedDay] || {};

  return (
    <View style={styles.container}>
      {/* Tab Switcher */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'menu' && styles.tabButtonActive]}
          onPress={() => setActiveTab('menu')}
        >
          <Text style={[styles.tabText, activeTab === 'menu' && styles.tabTextActive]}>🍽️ Menú Semanal</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'shopping' && styles.tabButtonActive]}
          onPress={() => setActiveTab('shopping')}
        >
          <Text style={[styles.tabText, activeTab === 'shopping' && styles.tabTextActive]}>🛒 Lista de Compra</Text>
        </TouchableOpacity>
      </View>

      {activeTab === 'menu' ? (
        <View style={{ flex: 1 }}>
          {/* Day Selector */}
          <View style={styles.daySelectorContainer}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.daySelectorScroll}>
              {DIAS.map(day => (
                <TouchableOpacity
                  key={day}
                  style={[styles.dayBadge, selectedDay === day && styles.dayBadgeActive]}
                  onPress={() => setSelectedDay(day)}
                >
                  <Text style={[styles.dayBadgeText, selectedDay === day && styles.dayBadgeTextActive]}>
                    {day}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Meals List */}
          <ScrollView contentContainerStyle={styles.scrollContent}>
            {['desayuno', 'comida', 'cena', 'snack'].map(mealKey => {
              const meal = mealsForDay[mealKey];
              if (!meal) return null;

              const mealTitle = mealKey.charAt(0).toUpperCase() + mealKey.slice(1);
              return (
                <TouchableOpacity
                  key={mealKey}
                  activeOpacity={0.85}
                  onPress={() => openRecipeDetails(meal, mealTitle)}
                >
                  <GlassCard style={styles.mealCard}>
                    <View style={styles.mealHeader}>
                      <Text style={styles.mealType}>{mealTitle}</Text>
                      <View style={styles.timeContainer}>
                        <Ionicons name="time-outline" size={14} color={Colors.textMuted} />
                        <Text style={styles.timeText}>{meal.tiempo_preparacion || '15 min'}</Text>
                      </View>
                    </View>
                    <Text style={styles.mealName}>{meal.nombre_plato}</Text>
                    <View style={styles.macroBadgeRow}>
                      <View style={[styles.badge, styles.badgeKcal]}>
                        <Text style={styles.badgeText}>{meal.kcal} Kcal</Text>
                      </View>
                      <View style={[styles.badge, styles.badgeProt]}>
                        <Text style={styles.badgeText}>{meal.proteinas_g}g P</Text>
                      </View>
                      <View style={[styles.badge, styles.badgeCarb]}>
                        <Text style={styles.badgeText}>{meal.carbos_g}g C</Text>
                      </View>
                      <View style={[styles.badge, styles.badgeFat]}>
                        <Text style={styles.badgeText}>{meal.grasas_g}g G</Text>
                      </View>
                    </View>
                  </GlassCard>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>
      ) : (
        /* Shopping List */
        <ScrollView contentContainerStyle={styles.scrollContent}>
          {shoppingList && shoppingList.length > 0 ? (
            shoppingList.map((cat: any, i: number) => (
              <GlassCard key={i}>
                <Text style={styles.categoryTitle}>{cat.nombre_categoria}</Text>
                {cat.ingredientes.map((ing: any, idx: number) => {
                  const isChecked = checkedItems[ing.nombre] || false;
                  return (
                    <TouchableOpacity
                      key={idx}
                      style={styles.shoppingItem}
                      activeOpacity={0.7}
                      onPress={() => toggleCheckItem(ing.nombre)}
                    >
                      <View style={styles.shoppingItemLeft}>
                        <Ionicons
                          name={isChecked ? 'checkmark-circle' : 'ellipse-outline'}
                          size={20}
                          color={isChecked ? Colors.success : Colors.textMuted}
                        />
                        <Text style={[styles.shoppingItemName, isChecked && styles.shoppingItemChecked]}>
                          {ing.nombre}
                        </Text>
                      </View>
                      <Text style={styles.shoppingItemQty}>
                        {ing.cantidad} {ing.unidad}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </GlassCard>
            ))
          ) : (
            <Text style={styles.emptyText}>No hay lista de compra generada.</Text>
          )}
        </ScrollView>
      )}

      {/* Recipe Modal Details */}
      {selectedMeal && (
        <Modal
          animationType="slide"
          transparent={true}
          visible={modalVisible}
          onRequestClose={() => setModalVisible(false)}
        >
          <View style={styles.modalBg}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalSubtitle}>{selectedMeal.title}</Text>
                <TouchableOpacity onPress={() => setModalVisible(false)} style={styles.closeBtn}>
                  <Ionicons name="close" size={24} color={Colors.text} />
                </TouchableOpacity>
              </View>
              
              <ScrollView contentContainerStyle={styles.modalScroll}>
                <Text style={styles.modalTitle}>{selectedMeal.nombre_plato}</Text>
                
                {/* Meta stats */}
                <View style={styles.metaRow}>
                  <View style={styles.metaItem}>
                    <Ionicons name="flash-outline" size={16} color={Colors.accent} />
                    <Text style={styles.metaLabel}>{selectedMeal.kcal} kcal</Text>
                  </View>
                  <View style={styles.metaItem}>
                    <Ionicons name="time-outline" size={16} color={Colors.secondary} />
                    <Text style={styles.metaLabel}>{selectedMeal.tiempo_preparacion || '15 min'}</Text>
                  </View>
                  <View style={styles.metaItem}>
                    <Ionicons name="ribbon-outline" size={16} color={Colors.success} />
                    <Text style={styles.metaLabel}>Dificultad: {selectedMeal.dificultad || 'Fácil'}</Text>
                  </View>
                </View>

                {/* Macros Breakdown */}
                <Text style={styles.subTitle}>Macronutrientes</Text>
                <View style={styles.modalMacrosRow}>
                  <View style={styles.macroItem}>
                    <Text style={styles.macroItemValue}>{selectedMeal.proteinas_g}g</Text>
                    <Text style={styles.macroItemLabel}>Proteína</Text>
                  </View>
                  <View style={styles.macroItem}>
                    <Text style={styles.macroItemValue}>{selectedMeal.carbos_g}g</Text>
                    <Text style={styles.macroItemLabel}>Carbos</Text>
                  </View>
                  <View style={styles.macroItem}>
                    <Text style={styles.macroItemValue}>{selectedMeal.grasas_g}g</Text>
                    <Text style={styles.macroItemLabel}>Grasas</Text>
                  </View>
                </View>

                {/* Ingredients */}
                <Text style={styles.subTitle}>Ingredientes necesarios</Text>
                {selectedMeal.ingredientes && selectedMeal.ingredientes.map((ing: string, index: number) => (
                  <View key={index} style={styles.ingredientLine}>
                    <Text style={styles.bulletPoint}>•</Text>
                    <Text style={styles.ingredientText}>{ing}</Text>
                  </View>
                ))}

                {/* Instructions */}
                <Text style={styles.subTitle}>Pasos de preparación</Text>
                {selectedMeal.pasos && selectedMeal.pasos.map((step: string, index: number) => (
                  <View key={index} style={styles.stepContainer}>
                    <View style={styles.stepNumCircle}>
                      <Text style={styles.stepNumText}>{index + 1}</Text>
                    </View>
                    <Text style={styles.stepText}>{step}</Text>
                  </View>
                ))}
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
  noPlanContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  noPlanText: {
    color: Colors.text,
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
  },
  noPlanSubtext: {
    color: Colors.textMuted,
    fontSize: 14,
    marginTop: 8,
    textAlign: 'center',
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: Colors.backgroundGradStart,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 14,
    alignItems: 'center',
  },
  tabButtonActive: {
    borderBottomColor: Colors.primary,
    borderBottomWidth: 3,
  },
  tabText: {
    color: Colors.textMuted,
    fontWeight: '600',
    fontSize: 14,
  },
  tabTextActive: {
    color: Colors.text,
  },
  daySelectorContainer: {
    backgroundColor: Colors.backgroundGradStart,
    paddingVertical: 10,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  daySelectorScroll: {
    paddingHorizontal: 16,
  },
  dayBadge: {
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
    marginRight: 8,
  },
  dayBadgeActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primaryDark,
  },
  dayBadgeText: {
    color: Colors.textMuted,
    fontWeight: '600',
    fontSize: 13,
  },
  dayBadgeTextActive: {
    color: Colors.text,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 32,
  },
  mealCard: {
    padding: 16,
  },
  mealHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  mealType: {
    color: Colors.secondary,
    fontWeight: '700',
    fontSize: 12,
    letterSpacing: 0.5,
  },
  timeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timeText: {
    color: Colors.textMuted,
    fontSize: 12,
    marginLeft: 4,
    fontWeight: '500',
  },
  mealName: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 12,
  },
  macroBadgeRow: {
    flexDirection: 'row',
  },
  badge: {
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 6,
  },
  badgeText: {
    color: Colors.text,
    fontSize: 11,
    fontWeight: '600',
  },
  badgeKcal: { backgroundColor: 'rgba(167, 139, 250, 0.2)' },
  badgeProt: { backgroundColor: 'rgba(248, 113, 113, 0.2)' },
  badgeCarb: { backgroundColor: 'rgba(251, 191, 36, 0.2)' },
  badgeFat: { backgroundColor: 'rgba(52, 211, 153, 0.2)' },

  // Shopping List Styles
  categoryTitle: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
    paddingBottom: 6,
  },
  shoppingItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomColor: 'rgba(255, 255, 255, 0.03)',
    borderBottomWidth: 1,
  },
  shoppingItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
  },
  shoppingItemName: {
    color: Colors.text,
    fontSize: 14,
    marginLeft: 10,
  },
  shoppingItemChecked: {
    color: Colors.textMuted,
    textDecorationLine: 'line-through',
  },
  shoppingItemQty: {
    color: Colors.primary,
    fontWeight: '600',
    fontSize: 13,
  },
  emptyText: {
    color: Colors.textMuted,
    fontSize: 14,
    textAlign: 'center',
  },

  // Modal Styles
  modalBg: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: Colors.background,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    height: '80%',
    borderColor: Colors.cardBorder,
    borderTopWidth: 1,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 10,
    borderBottomColor: Colors.cardBorder,
    borderBottomWidth: 1,
  },
  modalSubtitle: {
    color: Colors.secondary,
    fontWeight: '700',
    fontSize: 13,
  },
  closeBtn: {
    padding: 4,
  },
  modalScroll: {
    padding: 24,
    paddingBottom: 48,
  },
  modalTitle: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
    marginBottom: 16,
  },
  metaRow: {
    flexDirection: 'row',
    marginBottom: 20,
  },
  metaItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 16,
    backgroundColor: Colors.cardBg,
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  metaLabel: {
    color: Colors.text,
    fontSize: 12,
    marginLeft: 6,
    fontWeight: '600',
  },
  subTitle: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
    marginTop: 20,
    marginBottom: 12,
  },
  modalMacrosRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: Colors.cardBg,
    borderRadius: 16,
    padding: 16,
  },
  macroItem: {
    alignItems: 'center',
    flex: 1,
  },
  macroItemValue: {
    color: Colors.text,
    fontSize: 16,
    fontWeight: '700',
  },
  macroItemLabel: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 4,
  },
  ingredientLine: {
    flexDirection: 'row',
    marginBottom: 6,
    paddingHorizontal: 4,
  },
  bulletPoint: {
    color: Colors.primary,
    fontSize: 16,
    marginRight: 8,
  },
  ingredientText: {
    color: Colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
    flex: 1,
  },
  stepContainer: {
    flexDirection: 'row',
    marginBottom: 14,
    alignItems: 'flex-start',
  },
  stepNumCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
    marginTop: 2,
  },
  stepNumText: {
    color: Colors.text,
    fontSize: 11,
    fontWeight: '700',
  },
  stepText: {
    color: Colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
    flex: 1,
  },
});

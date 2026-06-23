import React from 'react';
import { StyleSheet, Text, View, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import { GlassCard } from '../../components/GlassCard';
import { Ionicons } from '@expo/vector-icons';

export default function MasScreen() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  return (
    <ScrollView contentContainerStyle={styles.container}>
      {/* Profile Header card */}
      <GlassCard style={styles.profileCard}>
        <View style={styles.avatar}>
          <Text style={styles.avatarText}>
            {user?.nombre ? user.nombre.substring(0, 2).toUpperCase() : 'UA'}
          </Text>
        </View>
        <Text style={styles.userName}>{user?.nombre || 'Usuario de NutriAI'}</Text>
        <Text style={styles.userEmail}>{user?.email || ''}</Text>
      </GlassCard>

      {/* Menu List */}
      <GlassCard>
        <Text style={styles.sectionTitle}>Módulos Especializados</Text>

        <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/clinical')}>
          <View style={styles.menuItemLeft}>
            <View style={[styles.iconBg, { backgroundColor: 'rgba(167, 139, 250, 0.15)' }]}>
              <Ionicons name="pulse" size={20} color={Colors.secondary} />
            </View>
            <View>
              <Text style={styles.menuItemTitle}>Analítica Clínica</Text>
              <Text style={styles.menuItemSub}>Sube tus análisis de sangre para adaptar tu dieta.</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
        </TouchableOpacity>

        <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/patologia')}>
          <View style={styles.menuItemLeft}>
            <View style={[styles.iconBg, { backgroundColor: 'rgba(239, 68, 68, 0.15)' }]}>
              <Ionicons name="medical" size={20} color={Colors.danger} />
            </View>
            <View>
              <Text style={styles.menuItemTitle}>Patologías e Intolerancias</Text>
              <Text style={styles.menuItemSub}>Configura restricciones clínicas activas.</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
        </TouchableOpacity>

        <TouchableOpacity style={styles.menuItem} onPress={() => router.push('/suplementos')}>
          <View style={styles.menuItemLeft}>
            <View style={[styles.iconBg, { backgroundColor: 'rgba(16, 185, 129, 0.15)' }]}>
              <Ionicons name="leaf" size={20} color={Colors.success} />
            </View>
            <View>
              <Text style={styles.menuItemTitle}>Suplementación</Text>
              <Text style={styles.menuItemSub}>Ver tus recomendaciones nutricionales.</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
        </TouchableOpacity>
      </GlassCard>

      {/* Logout Card */}
      <TouchableOpacity style={styles.logoutBtn} onPress={signOut}>
        <Ionicons name="log-out-outline" size={20} color={Colors.danger} />
        <Text style={styles.logoutBtnText}>Cerrar Sesión</Text>
      </TouchableOpacity>
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
  profileCard: {
    alignItems: 'center',
    paddingVertical: 24,
    marginBottom: 20,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  avatarText: {
    color: Colors.text,
    fontSize: 22,
    fontWeight: '800',
  },
  userName: {
    color: Colors.text,
    fontSize: 18,
    fontWeight: '700',
  },
  userEmail: {
    color: Colors.textMuted,
    fontSize: 13,
    marginTop: 4,
  },
  sectionTitle: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: Colors.cardBorder,
    paddingBottom: 8,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomColor: 'rgba(255, 255, 255, 0.03)',
    borderBottomWidth: 1,
  },
  menuItemLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    paddingRight: 16,
  },
  iconBg: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
  },
  menuItemTitle: {
    color: Colors.text,
    fontSize: 14,
    fontWeight: '600',
  },
  menuItemSub: {
    color: Colors.textMuted,
    fontSize: 11,
    marginTop: 3,
    lineHeight: 14,
  },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: 'rgba(239, 68, 68, 0.2)',
    borderWidth: 1,
    backgroundColor: 'rgba(239, 68, 68, 0.05)',
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 12,
  },
  logoutBtnText: {
    color: Colors.danger,
    fontWeight: '700',
    fontSize: 14,
    marginLeft: 8,
  },
});

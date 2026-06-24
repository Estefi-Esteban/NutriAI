import React from 'react';
import {
  StyleSheet, Text, View, ScrollView,
  TouchableOpacity
} from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '../../context/AuthContext';
import { Colors } from '../../constants/Colors';
import { Spacing, Radius } from '../../constants/theme';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';

interface MenuItem {
  label: string;
  sub: string;
  icon: string;
  color: string;
  route: '/clinical' | '/patologia' | '/suplementos';
}

const MENU_ITEMS: MenuItem[] = [
  {
    label: 'Analítica Clínica',
    sub: 'Sube tus análisis de sangre para adaptar tu dieta.',
    icon: 'pulse',
    color: '#A78BFA',
    route: '/clinical',
  },
  {
    label: 'Patologías e Intolerancias',
    sub: 'Configura restricciones clínicas y alergias activas.',
    icon: 'medical',
    color: Colors.macroProtein,
    route: '/patologia',
  },
  {
    label: 'Suplementación',
    sub: 'Descubre tus recomendaciones personalizadas.',
    icon: 'leaf',
    color: Colors.primary,
    route: '/suplementos',
  },
];

export default function MasScreen() {
  const { user, signOut } = useAuth();
  const router = useRouter();

  const initials = user?.nombre
    ? user.nombre.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase()
    : 'UA';

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      showsVerticalScrollIndicator={false}
    >
      {/* ── Profile Card ── */}
      <LinearGradient
        colors={['#1A2E1A', '#0F1F14']}
        style={styles.profileCard}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      >
        <View style={styles.avatarRing}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{initials}</Text>
          </View>
        </View>
        <Text style={styles.userName}>{user?.nombre || 'Usuario de NutriAI'}</Text>
        <Text style={styles.userEmail}>{user?.email || ''}</Text>
        <View style={styles.planBadge}>
          <Ionicons name="checkmark-circle" size={13} color={Colors.primary} />
          <Text style={styles.planBadgeText}>Plan Activo</Text>
        </View>
      </LinearGradient>

      {/* ── Specialized Modules ── */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Módulos Especializados</Text>
      </View>

      <View style={styles.menuCard}>
        {MENU_ITEMS.map((item, i) => (
          <React.Fragment key={item.route}>
            <TouchableOpacity
              style={styles.menuItem}
              onPress={() => router.push(item.route)}
              activeOpacity={0.75}
            >
              <View style={[styles.iconBg, { backgroundColor: item.color + '18' }]}>
                <Ionicons name={item.icon as any} size={22} color={item.color} />
              </View>
              <View style={styles.menuTextCol}>
                <Text style={styles.menuItemTitle}>{item.label}</Text>
                <Text style={styles.menuItemSub}>{item.sub}</Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={Colors.textTertiary} />
            </TouchableOpacity>
            {i < MENU_ITEMS.length - 1 && <View style={styles.menuDivider} />}
          </React.Fragment>
        ))}
      </View>

      {/* ── App Info ── */}
      <View style={styles.infoCard}>
        <View style={styles.infoRow}>
          <Ionicons name="information-circle-outline" size={18} color={Colors.textSecondary} />
          <Text style={styles.infoText}>NutriAI v1.0</Text>
        </View>
        <View style={styles.infoRow}>
          <Ionicons name="shield-checkmark-outline" size={18} color={Colors.textSecondary} />
          <Text style={styles.infoText}>Datos seguros y encriptados</Text>
        </View>
      </View>

      {/* ── Logout ── */}
      <TouchableOpacity style={styles.logoutBtn} onPress={signOut} activeOpacity={0.8}>
        <Ionicons name="log-out-outline" size={20} color={Colors.danger} />
        <Text style={styles.logoutText}>Cerrar Sesión</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: Colors.background,
    padding: Spacing.md,
    paddingBottom: 48,
  },

  // Profile
  profileCard: {
    borderRadius: Radius.xxl,
    borderColor: Colors.primary + '25',
    borderWidth: 1,
    alignItems: 'center',
    paddingVertical: Spacing.xl,
    paddingHorizontal: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  avatarRing: {
    padding: 3,
    borderRadius: 999,
    borderColor: Colors.primary,
    borderWidth: 2,
    marginBottom: Spacing.md,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: Colors.primaryFaint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    color: Colors.primary,
    fontSize: 26,
    fontWeight: '900',
  },
  userName: {
    color: Colors.text,
    fontSize: 20,
    fontWeight: '800',
    marginBottom: 4,
  },
  userEmail: {
    color: Colors.textSecondary,
    fontSize: 13,
    marginBottom: Spacing.sm,
  },
  planBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.primaryFaint,
    borderColor: Colors.primary + '30',
    borderWidth: 1,
    borderRadius: Radius.full,
    paddingHorizontal: 12,
    paddingVertical: 5,
    gap: 5,
  },
  planBadgeText: {
    color: Colors.primary,
    fontSize: 12,
    fontWeight: '700',
  },

  // Section header
  sectionHeader: {
    marginBottom: Spacing.sm,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: Colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },

  // Menu
  menuCard: {
    backgroundColor: Colors.backgroundGradStart,
    borderRadius: Radius.xl,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    overflow: 'hidden',
    marginBottom: Spacing.md,
  },
  menuItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: Spacing.md,
  },
  menuDivider: {
    height: 1,
    backgroundColor: Colors.cardBorder,
    marginHorizontal: Spacing.md,
  },
  iconBg: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 14,
    flexShrink: 0,
  },
  menuTextCol: {
    flex: 1,
    paddingRight: Spacing.sm,
  },
  menuItemTitle: {
    color: Colors.text,
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 3,
  },
  menuItemSub: {
    color: Colors.textSecondary,
    fontSize: 12,
    lineHeight: 16,
  },

  // Info card
  infoCard: {
    backgroundColor: Colors.backgroundGradStart,
    borderRadius: Radius.xl,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    gap: 10,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  infoText: {
    color: Colors.textSecondary,
    fontSize: 13,
  },

  // Logout
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.danger + '0E',
    borderColor: Colors.danger + '30',
    borderWidth: 1,
    borderRadius: Radius.lg,
    paddingVertical: 14,
    gap: 8,
  },
  logoutText: {
    color: Colors.danger,
    fontWeight: '700',
    fontSize: 15,
  },
});

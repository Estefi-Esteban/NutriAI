// NutriAI — Design System / Theme
// Centraliza tipografías, espaciados, sombras, radios y estilos compartidos

import { StyleSheet } from 'react-native';
import { Colors } from './Colors';

// ─── Typography Scale ──────────────────────────────────────────────────────
export const Typography = {
  // Display — números grandes de calorías/macros
  display: {
    fontSize: 48,
    fontWeight: '900' as const,
    color: Colors.text,
    letterSpacing: -1,
  },
  displaySm: {
    fontSize: 32,
    fontWeight: '800' as const,
    color: Colors.text,
    letterSpacing: -0.5,
  },

  // Headings
  h1: { fontSize: 26, fontWeight: '800' as const, color: Colors.text },
  h2: { fontSize: 20, fontWeight: '700' as const, color: Colors.text },
  h3: { fontSize: 16, fontWeight: '700' as const, color: Colors.text },

  // Body
  body: { fontSize: 15, fontWeight: '400' as const, color: Colors.text, lineHeight: 22 },
  bodyBold: { fontSize: 15, fontWeight: '700' as const, color: Colors.text },
  bodyMuted: { fontSize: 15, fontWeight: '400' as const, color: Colors.textSecondary, lineHeight: 22 },

  // Labels
  label: { fontSize: 12, fontWeight: '600' as const, color: Colors.textSecondary, letterSpacing: 0.5 },
  labelBold: { fontSize: 12, fontWeight: '700' as const, color: Colors.text },
  caption: { fontSize: 11, fontWeight: '500' as const, color: Colors.textTertiary },
};

// ─── Spacing ───────────────────────────────────────────────────────────────
export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

// ─── Border Radius ─────────────────────────────────────────────────────────
export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  full: 999,
};

// ─── Shadows ───────────────────────────────────────────────────────────────
export const Shadows = {
  card: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 3,
  },
  glow: {
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 5,
  },
};

// ─── Reusable Component Styles ─────────────────────────────────────────────
export const Theme = StyleSheet.create({
  // Containers
  screen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  safeContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    padding: Spacing.md,
  },
  scrollContent: {
    flexGrow: 1,
    backgroundColor: Colors.background,
    padding: Spacing.md,
    paddingBottom: Spacing.xxl,
  },

  // Cards
  card: {
    backgroundColor: Colors.backgroundGradStart,
    borderRadius: Radius.lg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  cardElevated: {
    backgroundColor: Colors.cardElevated,
    borderRadius: Radius.lg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },

  // Buttons
  btnPrimary: {
    backgroundColor: Colors.primary,
    borderRadius: Radius.md,
    paddingVertical: 14,
    paddingHorizontal: Spacing.lg,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    flexDirection: 'row' as const,
  },
  btnPrimaryText: {
    color: '#FFFFFF',
    fontWeight: '800' as const,
    fontSize: 15,
    letterSpacing: 0.2,
  },
  btnOutline: {
    backgroundColor: 'transparent',
    borderRadius: Radius.md,
    paddingVertical: 14,
    paddingHorizontal: Spacing.lg,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    borderColor: Colors.primary,
    borderWidth: 1.5,
  },
  btnOutlineText: {
    color: Colors.primary,
    fontWeight: '700' as const,
    fontSize: 15,
  },
  btnGhost: {
    backgroundColor: Colors.cardBg,
    borderRadius: Radius.md,
    paddingVertical: 14,
    paddingHorizontal: Spacing.lg,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
  },

  // Macro badges
  badgeBase: {
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    marginRight: 6,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700' as const,
    color: Colors.text,
  },

  // Input
  input: {
    backgroundColor: Colors.inputBg,
    borderColor: Colors.inputBorder,
    borderWidth: 1,
    borderRadius: Radius.md,
    color: Colors.text,
    paddingHorizontal: Spacing.md,
    paddingVertical: 12,
    fontSize: 15,
  },

  // Section header row
  sectionRow: {
    flexDirection: 'row' as const,
    justifyContent: 'space-between' as const,
    alignItems: 'center' as const,
    marginBottom: Spacing.sm,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700' as const,
    color: Colors.text,
  },

  // Loading screen
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
  },

  // Icon button
  iconBtn: {
    backgroundColor: Colors.cardBg,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: Radius.md,
    padding: 10,
    alignItems: 'center' as const,
    justifyContent: 'center' as const,
  },
});

import React, { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Colors } from '../constants/Colors';

function RootLayoutNav() {
  const { token, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!token && !inAuthGroup) {
      // Redirect to login if not logged in and not in auth screens
      router.replace('/(auth)/login');
    } else if (token && inAuthGroup) {
      // Redirect to home if logged in and trying to access auth screens
      router.replace('/(tabs)');
    }
  }, [token, loading, segments]);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(auth)" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="chat_perfil" options={{ presentation: 'modal', headerShown: true, title: 'Perfil Onboarding', headerStyle: { backgroundColor: Colors.background }, headerTintColor: Colors.text }} />
        <Stack.Screen name="clinical" options={{ headerShown: true, title: 'Analítica Clínica', headerStyle: { backgroundColor: Colors.background }, headerTintColor: Colors.text }} />
        <Stack.Screen name="patologia" options={{ headerShown: true, title: 'Patologías y Protocolos', headerStyle: { backgroundColor: Colors.background }, headerTintColor: Colors.text }} />
        <Stack.Screen name="suplementos" options={{ headerShown: true, title: 'Suplementación Recomendada', headerStyle: { backgroundColor: Colors.background }, headerTintColor: Colors.text }} />
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <RootLayoutNav />
      </AuthProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});

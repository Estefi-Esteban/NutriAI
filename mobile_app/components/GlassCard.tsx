import React from 'react';
import { StyleSheet, View, ViewProps } from 'react-native';
import { Colors } from '../constants/Colors';

export const GlassCard: React.FC<ViewProps> = ({ children, style, ...props }) => {
  return (
    <View style={[styles.card, style]} {...props}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.backgroundGradStart,
    borderColor: Colors.cardBorder,
    borderWidth: 1,
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
  },
});


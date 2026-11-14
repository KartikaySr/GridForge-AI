import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSession } from '../session';
export const styles = StyleSheet.create({
  page: { padding: 20, gap: 16, backgroundColor: '#f2f5f3', flexGrow: 1 },
  title: { fontSize: 27, fontWeight: '700', color: '#123d2e' },
  text: { color: '#29493b', fontSize: 15, lineHeight: 23 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 18,
    gap: 10,
    borderWidth: 1,
    borderColor: '#d2dfd6',
  },
  input: {
    backgroundColor: '#fff',
    color: '#123d2e',
    padding: 14,
    borderRadius: 8,
    borderColor: '#789889',
    borderWidth: 1,
    minHeight: 48,
  },
  button: {
    backgroundColor: '#194e3e',
    padding: 14,
    borderRadius: 8,
    minHeight: 48,
  },
  buttonText: { color: '#fff', fontWeight: '600', textAlign: 'center' },
});
export function Button({
  title,
  onPress,
  disabled = false,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.button, disabled && { opacity: 0.5 }]}
    >
      <Text style={styles.buttonText}>{title}</Text>
    </Pressable>
  );
}
export function Page({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const { notice } = useSession();
  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      contentContainerStyle={styles.page}
    >
      <Text style={styles.text}>GRIDFORGE AI · SIMULATION</Text>
      <Text accessibilityRole="header" style={styles.title}>
        {title}
      </Text>
      {notice ? (
        <Text accessibilityRole="alert" style={styles.text}>
          {notice}
        </Text>
      ) : null}
      {children}
    </ScrollView>
  );
}
export function Card({ children }: { children: ReactNode }) {
  return <View style={styles.card}>{children}</View>;
}

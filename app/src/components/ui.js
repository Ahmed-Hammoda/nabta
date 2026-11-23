import { KeyboardAvoidingView, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { colors } from '../theme';

// Scrolling page. The padding behavior keeps text fields above the keyboard on edge-to-edge Android.
export function Screen({ children }) {
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView behavior="padding" style={styles.screen}>
      <ScrollView
        contentContainerStyle={[styles.screenContent, { paddingTop: insets.top + 12 }]}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

export function Header({ title, subtitle }) {
  return (
    <View style={styles.header}>
      <View>
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
      <Pill tone="muted">Example data</Pill>
    </View>
  );
}

export function Card({ children, style }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Label({ children }) {
  return <Text style={styles.label}>{children}</Text>;
}

const PILL_TONES = {
  leaf: [colors.leafSoft, colors.leaf],
  water: [colors.waterSoft, colors.water],
  warn: [colors.warnSoft, colors.warn],
  crit: [colors.critSoft, colors.crit],
  muted: [colors.track, colors.muted],
};

export function Pill({ tone = 'leaf', children }) {
  const [bg, fg] = PILL_TONES[tone];
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      <Text style={[styles.pillText, { color: fg }]}>{children}</Text>
    </View>
  );
}

export function Chips({ options, value, onChange }) {
  return (
    <View style={styles.chips}>
      {options.map((opt) => {
        const on = opt.value === value;
        return (
          <Pressable
            key={opt.value}
            onPress={() => onChange(opt.value)}
            style={[styles.chip, on && styles.chipOn]}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
          >
            <Text style={[styles.chipText, on && styles.chipTextOn]}>{opt.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Button({ label, icon, onPress, disabled, variant = 'solid' }) {
  const solid = variant === 'solid';
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.button,
        solid ? styles.buttonSolid : styles.buttonOutline,
        (pressed || disabled) && { opacity: 0.6 },
      ]}
    >
      {icon}
      <Text style={[styles.buttonText, { color: solid ? colors.surface : colors.leaf }]}>{label}</Text>
    </Pressable>
  );
}

export function Segmented({ options, value, onChange }) {
  return (
    <View style={styles.segmented}>
      {options.map((opt) => {
        const on = opt.value === value;
        return (
          <Pressable
            key={opt.value}
            onPress={() => onChange(opt.value)}
            style={[styles.segment, on && styles.segmentOn]}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
          >
            <Text style={[styles.segmentText, on && styles.segmentTextOn]}>{opt.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  screenContent: { paddingHorizontal: 16, paddingBottom: 28, gap: 12 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { fontSize: 28, fontWeight: '700', color: colors.fg },
  subtitle: { fontSize: 13, color: colors.muted, marginTop: 2 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 14,
  },
  label: {
    fontSize: 11,
    fontWeight: '600',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    color: colors.muted,
  },
  pill: { alignSelf: 'flex-start', borderRadius: 99, paddingHorizontal: 10, paddingVertical: 3 },
  pillText: { fontSize: 12, fontWeight: '600' },
  segmented: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 3,
  },
  segment: { flex: 1, paddingVertical: 9, borderRadius: 9, alignItems: 'center' },
  segmentOn: { backgroundColor: colors.leafSoft },
  segmentText: { fontSize: 14, color: colors.muted },
  segmentTextOn: { color: colors.leaf, fontWeight: '700' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    borderRadius: 99,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.surface,
    paddingHorizontal: 14,
    paddingVertical: 7,
  },
  chipOn: { borderColor: colors.leaf, backgroundColor: colors.leafSoft },
  chipText: { fontSize: 14, color: colors.muted },
  chipTextOn: { color: colors.leaf, fontWeight: '700' },
  button: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  buttonSolid: { backgroundColor: colors.leaf },
  buttonOutline: { borderWidth: 1.5, borderColor: colors.leaf, backgroundColor: colors.surface },
  buttonText: { fontSize: 16, fontWeight: '700' },
});

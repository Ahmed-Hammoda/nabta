import Ionicons from '@expo/vector-icons/Ionicons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Chips, Header, Label, Pill, Screen } from '../../components/ui';
import { explain, getDecisions } from '../../data/mock';
import { colors } from '../../theme';
import { formatDayLabel, formatTime, formatWhen } from '../../utils/format';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'water', label: 'Watered' },
  { value: 'wait', label: 'Waited' },
  { value: 'none', label: 'Checks' },
  { value: 'alert', label: 'Alerts' },
];

const ACTION = {
  water: { icon: 'water', color: colors.water, title: (d) => `Watered ${d.ml} ml` },
  wait: { icon: 'hourglass-outline', color: colors.leaf, title: () => 'Waited' },
  none: { icon: 'checkmark-circle-outline', color: colors.leaf, title: () => 'No water needed' },
  alert: { icon: 'warning-outline', color: colors.warn, title: () => 'Heat alert' },
};

const REASON_TONE = {
  DRY_BELOW_MIN: 'water',
  SOAKING_WAIT: 'leaf',
  IN_TARGET_BAND: 'leaf',
  HEAT_STRESS: 'warn',
};

export default function LogScreen() {
  const [filter, setFilter] = useState('all');
  const all = getDecisions();
  const shown = filter === 'all' ? all : all.filter((d) => d.action === filter);

  // Group by day, keeping newest first.
  const groups = [];
  for (const d of shown) {
    const label = formatDayLabel(d.t);
    if (groups.length === 0 || groups[groups.length - 1].label !== label) groups.push({ label, items: [] });
    groups[groups.length - 1].items.push(d);
  }

  const count = (action) => all.filter((d) => d.action === action).length;

  const askAbout = (d) =>
    router.push({
      pathname: '/ask',
      params: { q: `Explain the decision from ${formatWhen(d.t)}`, decision: String(d.t) },
    });

  return (
    <Screen>
      <Header title="Decision log" subtitle="Last 7 days" />

      <Card style={styles.summary}>
        <Summary value={count('water')} label="waterings" color={colors.water} />
        <Summary value={count('wait')} label="waits" color={colors.leaf} />
        <Summary value={count('alert')} label="alerts" color={colors.warn} />
      </Card>

      <Chips options={FILTERS} value={filter} onChange={setFilter} />

      {groups.length === 0 && <Text style={styles.empty}>Nothing of this type in the last 7 days.</Text>}

      {groups.map((g) => (
        <View key={g.label} style={styles.group}>
          <Label>{g.label}</Label>
          {g.items.map((d) => {
            const a = ACTION[d.action];
            return (
              <Pressable
                key={d.t}
                onPress={() => askAbout(d)}
                style={({ pressed }) => pressed && { opacity: 0.7 }}
                accessibilityRole="button"
                accessibilityHint="Opens Ask Nabta with this decision"
              >
                <Card style={styles.item}>
                  <View style={styles.row}>
                    <Ionicons name={a.icon} size={18} color={a.color} />
                    <Text style={styles.title}>{a.title(d)}</Text>
                    <Text style={styles.time}>{formatTime(d.t)}</Text>
                  </View>
                  <Pill tone={REASON_TONE[d.reason]}>{d.reason}</Pill>
                  <Text style={styles.sentence}>{explain(d)}</Text>
                  <Text style={styles.ask}>Ask Nabta about this ›</Text>
                </Card>
              </Pressable>
            );
          })}
        </View>
      ))}
    </Screen>
  );
}

function Summary({ value, label, color }) {
  return (
    <View style={styles.summaryItem}>
      <Text style={[styles.summaryValue, { color }]}>{value}</Text>
      <Text style={styles.time}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  summary: { flexDirection: 'row' },
  summaryItem: { flex: 1, alignItems: 'center', gap: 2 },
  summaryValue: { fontSize: 24, fontWeight: '700' },
  group: { gap: 8, marginTop: 4 },
  item: { gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  title: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.fg },
  time: { fontSize: 13, color: colors.muted },
  sentence: { fontSize: 14, lineHeight: 20, color: colors.fg },
  ask: { fontSize: 13, fontWeight: '600', color: colors.water },
  empty: { fontSize: 14, color: colors.muted, textAlign: 'center', paddingVertical: 24 },
});

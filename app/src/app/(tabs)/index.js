import Ionicons from '@expo/vector-icons/Ionicons';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Card, Header, Label, Pill, Screen } from '../../components/ui';
import MoistureGauge from '../../components/MoistureGauge';
import { getStatus } from '../../data/mock';
import { colors } from '../../theme';
import { notify } from '../../utils/dialog';
import { formatHours, formatLux, formatTime, formatWhen } from '../../utils/format';

const STATUS = {
  healthy: { tone: 'leaf', label: 'Healthy' },
  thirsty: { tone: 'warn', label: 'Thirsty' },
  stressed: { tone: 'crit', label: 'Stressed' },
};

export default function HomeScreen() {
  const s = getStatus();
  const status = STATUS[s.status];

  const waterNow = () =>
    notify(
      'Water now',
      `The pot will get ${s.doseMl} ml at the next reading, if the safety limits allow it.\n\nNo pot is connected yet, so nothing happens in this demo.`
    );

  return (
    <Screen>
      <Header title="Nabta" subtitle={`Updated ${formatTime(s.updatedAt)}`} />

      <Card style={styles.plantCard}>
        <MoistureGauge value={s.moisture} min={s.minPct} max={s.maxPct} />
        <View style={styles.plantInfo}>
          <Label>Soil moisture</Label>
          <Text style={styles.plantName}>{s.plant}</Text>
          <Pill tone={status.tone}>{status.label}</Pill>
          <Text style={styles.muted}>Next watering in {formatHours(s.nextWateringH)}</Text>
        </View>
      </Card>

      <View style={styles.tiles}>
        <Tile icon="thermometer-outline" label="Air temp" value={`${s.temp} °C`} />
        <Tile icon="water-outline" label="Humidity" value={`${s.humidity} %`} />
        <Tile icon="sunny-outline" label="Light" value={formatLux(s.light)} />
        <Tile
          icon="beaker-outline"
          label="Reservoir"
          value={s.reservoirOk ? 'OK' : 'Empty'}
          valueColor={s.reservoirOk ? colors.leaf : colors.crit}
        />
      </View>

      <Label>Alerts</Label>
      {s.alerts.length === 0 ? (
        <Card style={styles.row}>
          <Ionicons name="checkmark-circle" size={20} color={colors.leaf} />
          <Text style={styles.body}>No alerts. Everything is within limits.</Text>
        </Card>
      ) : (
        s.alerts.map((a) => (
          <View key={a.text} style={[styles.alert, a.level === 'crit' && styles.alertCrit]}>
            <Ionicons name="warning" size={18} color={a.level === 'crit' ? colors.crit : colors.warn} />
            <Text style={[styles.alertText, a.level === 'crit' && { color: colors.crit }]}>{a.text}</Text>
          </View>
        ))
      )}

      <Card style={[styles.row, styles.between]}>
        <Text style={styles.body}>Last watering</Text>
        <Text style={styles.muted}>
          {s.lastWatering ? `${formatWhen(s.lastWatering.t)} · ${s.lastWatering.ml} ml` : 'None yet'}
        </Text>
      </Card>

      <Pressable
        onPress={waterNow}
        style={({ pressed }) => [styles.button, pressed && { opacity: 0.8 }]}
        accessibilityRole="button"
      >
        <Ionicons name="water" size={18} color={colors.surface} />
        <Text style={styles.buttonText}>Water now</Text>
      </Pressable>
    </Screen>
  );
}

function Tile({ icon, label, value, valueColor = colors.fg }) {
  return (
    <Card style={styles.tile}>
      <View style={styles.row}>
        <Ionicons name={icon} size={16} color={colors.muted} />
        <Label>{label}</Label>
      </View>
      <Text style={[styles.tileValue, { color: valueColor }]}>{value}</Text>
    </Card>
  );
}

const styles = StyleSheet.create({
  plantCard: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  plantInfo: { flex: 1, gap: 6 },
  plantName: { fontSize: 22, fontWeight: '700', color: colors.fg },
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  tile: { width: '48.5%', flexGrow: 1, gap: 6, paddingVertical: 12 },
  tileValue: { fontSize: 22, fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  between: { justifyContent: 'space-between' },
  body: { fontSize: 15, color: colors.fg, flexShrink: 1 },
  muted: { fontSize: 13, color: colors.muted },
  alert: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
    backgroundColor: colors.warnSoft,
    borderRadius: 12,
    padding: 12,
  },
  alertCrit: { backgroundColor: colors.critSoft },
  alertText: { flex: 1, fontSize: 14, color: colors.warn, fontWeight: '500' },
  button: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.leaf,
    borderRadius: 14,
    paddingVertical: 15,
    marginTop: 4,
  },
  buttonText: { color: colors.surface, fontSize: 16, fontWeight: '700' },
});

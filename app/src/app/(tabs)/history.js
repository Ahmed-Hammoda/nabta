import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import LineChart from '../../components/LineChart';
import { Card, Header, Label, Screen, Segmented } from '../../components/ui';
import { getHistory, getWaterLast7Days, PROFILE } from '../../data/mock';
import { colors } from '../../theme';
import { formatDay, formatTime, formatWhen } from '../../utils/format';

const RANGES = [
  { value: '24h', label: '24 hours' },
  { value: '7d', label: '7 days' },
];

export default function HistoryScreen() {
  const [range, setRange] = useState('24h');
  const { points, waterings } = getHistory(range);
  const water = getWaterLast7Days();

  const formatX = range === '24h' ? formatTime : formatDay;
  const temps = points.map((p) => p.temp);
  const tMin = Math.floor(Math.min(...temps));
  const tMax = Math.ceil(Math.max(...temps));
  const rangeMl = waterings.reduce((sum, w) => sum + w.ml, 0);

  return (
    <Screen>
      <Header title="History" subtitle={PROFILE.plant} />
      <Segmented options={RANGES} value={range} onChange={setRange} />

      <Card style={styles.gap}>
        <View style={styles.between}>
          <Label>Soil moisture, %</Label>
          <Text style={styles.legend}>● watering</Text>
        </View>
        <LineChart
          points={points}
          valueKey="moisture"
          color={colors.water}
          yMin={0}
          yMax={100}
          yTicks={[0, PROFILE.minPct, PROFILE.maxPct, 100]}
          band={[PROFILE.minPct, PROFILE.maxPct]}
          markers={waterings}
          formatX={formatX}
        />
        <Text style={styles.caption}>Green band: target {PROFILE.minPct}–{PROFILE.maxPct} % for mint.</Text>
      </Card>

      <Card style={styles.gap}>
        <Label>Air temperature, °C</Label>
        <LineChart
          points={points}
          valueKey="temp"
          color={colors.warn}
          yMin={tMin - 1}
          yMax={tMax + 1}
          yTicks={[tMin, tMax]}
          formatX={formatX}
          height={130}
        />
      </Card>

      <Card style={styles.gap}>
        <Label>Water used, last 7 days</Label>
        <View style={styles.stats}>
          <Stat value={`${water.totalMl} ml`} label="total" />
          <Stat value={`${water.perDayMl} ml`} label="per day" />
          <Stat value={String(water.count)} label="waterings" />
        </View>
      </Card>

      <Card style={styles.gap}>
        <View style={styles.between}>
          <Label>Waterings</Label>
          <Text style={styles.caption}>
            {waterings.length} · {rangeMl} ml
          </Text>
        </View>
        {waterings.length === 0 ? (
          <Text style={styles.caption}>No watering in this period.</Text>
        ) : (
          waterings
            .slice(-8)
            .reverse()
            .map((w) => (
              <View key={w.t} style={[styles.between, styles.listRow]}>
                <Text style={styles.body}>{formatWhen(w.t)}</Text>
                <Text style={styles.body}>{w.ml} ml</Text>
              </View>
            ))
        )}
      </Card>
    </Screen>
  );
}

function Stat({ value, label }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.caption}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  gap: { gap: 10 },
  between: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  legend: { fontSize: 12, color: colors.water },
  caption: { fontSize: 12, color: colors.muted },
  body: { fontSize: 15, color: colors.fg },
  stats: { flexDirection: 'row', gap: 10 },
  stat: { flex: 1, backgroundColor: colors.waterSoft, borderRadius: 12, padding: 10, gap: 2 },
  statValue: { fontSize: 20, fontWeight: '700', color: colors.water },
  listRow: { paddingVertical: 6, borderTopWidth: 1, borderTopColor: colors.line },
});

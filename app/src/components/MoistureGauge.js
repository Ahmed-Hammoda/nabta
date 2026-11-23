import Svg, { Circle, Text as SvgText } from 'react-native-svg';
import { colors } from '../theme';

// Ring gauge: the colored arc covers `value` percent of the circle.
export default function MoistureGauge({ value, min, max, size = 128 }) {
  const stroke = 12;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const arc = (Math.min(100, Math.max(0, value)) / 100) * circumference;
  const color = value < min ? colors.warn : colors.water;
  const c = size / 2;

  return (
    <Svg width={size} height={size}>
      <Circle cx={c} cy={c} r={r} stroke={colors.track} strokeWidth={stroke} fill="none" />
      <Circle
        cx={c}
        cy={c}
        r={r}
        stroke={color}
        strokeWidth={stroke}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={`${arc} ${circumference}`}
        transform={`rotate(-90 ${c} ${c})`}
      />
      <SvgText x={c} y={c + 4} textAnchor="middle" fontSize={28} fontWeight="700" fill={colors.fg}>
        {`${Math.round(value)}%`}
      </SvgText>
      <SvgText x={c} y={c + 24} textAnchor="middle" fontSize={11} fill={colors.muted}>
        {`target ${min}–${max}`}
      </SvgText>
    </Svg>
  );
}

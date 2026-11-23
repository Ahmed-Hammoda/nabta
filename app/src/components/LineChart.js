import { useState } from 'react';
import { View } from 'react-native';
import Svg, { Circle, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
import { colors } from '../theme';

const PAD = { left: 32, right: 10, top: 10, bottom: 24 };

// Time-series line. `band` shades a target range, `markers` are events (waterings) drawn as dots.
export default function LineChart({
  points,
  valueKey,
  color,
  yMin,
  yMax,
  yTicks,
  band,
  markers = [],
  formatX,
  height = 180,
}) {
  const [width, setWidth] = useState(0);
  const t0 = points[0].t;
  const t1 = points[points.length - 1].t;
  const plotRight = width - PAD.right;
  const plotBottom = height - PAD.bottom;

  const x = (t) => PAD.left + ((t - t0) / (t1 - t0)) * (plotRight - PAD.left);
  const y = (v) => PAD.top + (1 - (v - yMin) / (yMax - yMin)) * (plotBottom - PAD.top);

  const d = points
    .map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p[valueKey]).toFixed(1)}`)
    .join(' ');
  const last = points[points.length - 1];
  const xTicks = [t0, (t0 + t1) / 2, t1];
  const anchors = ['start', 'middle', 'end'];

  return (
    <View style={{ height }} onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
      {width > 0 && (
        <Svg width={width} height={height}>
          {band && (
            <Rect
              x={PAD.left}
              y={y(band[1])}
              width={plotRight - PAD.left}
              height={y(band[0]) - y(band[1])}
              fill={colors.leafSoft}
            />
          )}
          {yTicks.map((v) => (
            <G key={v}>
              <Line x1={PAD.left} x2={plotRight} y1={y(v)} y2={y(v)} stroke={colors.line} strokeDasharray="3 4" />
              <SvgText x={PAD.left - 6} y={y(v) + 4} fontSize={10} fill={colors.muted} textAnchor="end">
                {String(v)}
              </SvgText>
            </G>
          ))}
          {xTicks.map((t, i) => (
            <SvgText key={i} x={x(t)} y={height - 6} fontSize={10} fill={colors.muted} textAnchor={anchors[i]}>
              {formatX(t)}
            </SvgText>
          ))}
          {markers.map((m) => (
            <G key={m.t}>
              <Line x1={x(m.t)} x2={x(m.t)} y1={PAD.top} y2={plotBottom} stroke={colors.water} strokeOpacity={0.25} />
              <Circle cx={x(m.t)} cy={plotBottom - 4} r={3.5} fill={colors.water} />
            </G>
          ))}
          <Path d={d} stroke={color} strokeWidth={2.2} fill="none" strokeLinejoin="round" strokeLinecap="round" />
          <Circle cx={x(last.t)} cy={y(last[valueKey])} r={4.5} fill={color} />
        </Svg>
      )}
    </View>
  );
}

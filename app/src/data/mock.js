// Example data until the ESP32 and the FastAPI server are running.
// getStatus / getHistory return the same shape the real endpoints will:
//   GET /api/pots/{id}/status
//   GET /api/pots/{id}/history?range=24h|7d

const HOUR = 3600 * 1000;
const STEP_H = 0.5; // one reading every 30 min in the simulation
const WEEK_H = 168;

export const PROFILE = {
  plant: 'Spearmint',
  minPct: 40,
  maxPct: 70,
  doseMl: 40,
  heatLimitC: 30,
};

// Small seeded random generator so the example data is the same on every run.
function makeRandom(seed) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

const round1 = (v) => Math.round(v * 10) / 10;

function simulateWeek() {
  const random = makeRandom(7);
  const now = new Date();
  now.setMinutes(now.getMinutes() < 30 ? 0 : 30, 0, 0);
  const start = now.getTime() - WEEK_H * HOUR;

  let moisture = 60;
  let lastWater = -Infinity;
  let heatAlertDay = null;
  const points = [];
  const waterings = [];
  const decisions = [];
  // One hot day three days ago, so the log shows a HEAT_STRESS alert.
  const hotDay = new Date(now.getTime() - 3 * 24 * HOUR).toDateString();

  for (let i = 0; i <= WEEK_H / STEP_H; i++) {
    const t = start + i * STEP_H * HOUR;
    const d = new Date(t);
    const hourOfDay = d.getHours() + d.getMinutes() / 60;
    const daylight = hourOfDay >= 7 && hourOfDay < 19;
    let temp = 21 + 5 * Math.sin(((hourOfDay - 9) / 24) * 2 * Math.PI) + (random() - 0.5) * 0.8;
    if (daylight && d.toDateString() === hotDay) temp += 7 * Math.sin(((hourOfDay - 7) / 12) * Math.PI);
    temp = round1(temp);

    // Soil dries faster during the day and when it is warm.
    if (i > 0) moisture -= (daylight ? 1.9 : 0.8) * (1 + (temp - 21) / 25) * STEP_H;

    // The decision engine's rules, as in the architecture doc.
    if (moisture < PROFILE.minPct && t - lastWater >= 0.75 * HOUR) {
      decisions.push({ t, action: 'water', reason: 'DRY_BELOW_MIN', ml: PROFILE.doseMl, moisture: round1(moisture) });
      moisture += 26;
      lastWater = t;
      waterings.push({ t, ml: PROFILE.doseMl });
    } else if (t - lastWater === 0.5 * HOUR) {
      decisions.push({ t, action: 'wait', reason: 'SOAKING_WAIT', moisture: round1(moisture) });
    } else if (hourOfDay === 12 && moisture >= PROFILE.minPct && moisture <= PROFILE.maxPct) {
      decisions.push({ t, action: 'none', reason: 'IN_TARGET_BAND', moisture: round1(moisture) });
    }
    if (temp > PROFILE.heatLimitC && heatAlertDay !== d.toDateString()) {
      heatAlertDay = d.toDateString();
      decisions.push({ t, action: 'alert', reason: 'HEAT_STRESS', temp });
    }
    moisture = Math.min(95, Math.max(10, moisture));

    points.push({
      t,
      moisture: round1(moisture + (random() - 0.5) * 0.6),
      temp,
      humidity: Math.round(62 - (temp - 21) * 2.5 + (random() - 0.5) * 2),
      light: daylight ? Math.round(9000 * Math.sin(((hourOfDay - 7) / 12) * Math.PI)) : 0,
    });
  }
  return { points, waterings, decisions };
}

let cache = null;
function week() {
  if (!cache) cache = simulateWeek();
  return cache;
}

export function getStatus() {
  const { points, waterings } = week();
  const last = points[points.length - 1];

  // Drying rate over the last 6 h, counting only drops so a watering doesn't hide it.
  const recent = points.slice(-(6 / STEP_H + 1));
  let dropped = 0;
  for (let i = 1; i < recent.length; i++) dropped += Math.max(0, recent[i - 1].moisture - recent[i].moisture);
  const dropPerHour = Math.max(0.3, dropped / 6);
  const nextWateringH = Math.max(0, (last.moisture - PROFILE.minPct) / dropPerHour);

  const alerts = [];
  if (last.moisture < PROFILE.minPct) {
    alerts.push({ level: 'warn', text: `Soil is at ${Math.round(last.moisture)} %, below the ${PROFILE.minPct} % minimum.` });
  }
  if (last.moisture > PROFILE.maxPct + 10) {
    alerts.push({ level: 'warn', text: 'Soil is very wet. Mint roots can rot if it stays like this.' });
  }
  if (last.temp > PROFILE.heatLimitC) {
    alerts.push({ level: 'crit', text: `Air is at ${last.temp} °C, above the ${PROFILE.heatLimitC} °C limit.` });
  }

  let status = 'healthy';
  if (last.moisture < PROFILE.minPct) status = 'thirsty';
  else if (last.temp > PROFILE.heatLimitC || last.moisture > PROFILE.maxPct + 10) status = 'stressed';

  return {
    ...PROFILE,
    updatedAt: last.t,
    moisture: last.moisture,
    temp: last.temp,
    humidity: last.humidity,
    light: last.light,
    reservoirOk: true,
    status,
    nextWateringH,
    lastWatering: waterings[waterings.length - 1] || null,
    alerts,
  };
}

export function getHistory(range) {
  const { points, waterings } = week();
  const hours = range === '24h' ? 24 : WEEK_H;
  const from = points[points.length - 1].t - hours * HOUR;
  let shown = points.filter((p) => p.t >= from);
  // 7 days: one point every 2 h is enough for a phone-width chart.
  if (range === '7d') shown = shown.filter((_, i) => i % 4 === 0 || i === shown.length - 1);
  return { points: shown, waterings: waterings.filter((w) => w.t >= from) };
}

// Water delivered over the last 7 days.
export function getWaterLast7Days() {
  const { waterings } = week();
  const totalMl = waterings.reduce((sum, w) => sum + w.ml, 0);
  return { totalMl, count: waterings.length, perDayMl: Math.round(totalMl / 7) };
}

// Decision log, newest first. Real endpoint: GET /api/pots/{id}/decisions
export function getDecisions() {
  return [...week().decisions].reverse();
}

// The fixed sentence for each reason code. The app falls back to these when no LLM answers.
export function explain(decision) {
  const { minPct, maxPct, plant, heatLimitC } = PROFILE;
  switch (decision.reason) {
    case 'DRY_BELOW_MIN':
      return `Soil moisture dropped to ${decision.moisture} %, below the ${minPct} % minimum for ${plant.toLowerCase()}, so I gave ${decision.ml} ml.`;
    case 'SOAKING_WAIT':
      return `I watered 30 min ago, so I'm waiting for the water to soak in. Soil is at ${Math.round(decision.moisture)} %.`;
    case 'IN_TARGET_BAND':
      return `Soil is at ${Math.round(decision.moisture)} %, inside the ${minPct}–${maxPct} % band. No water needed.`;
    case 'HEAT_STRESS':
      return `Air reached ${decision.temp} °C, above the ${heatLimitC} °C limit. Move the pot out of direct afternoon sun.`;
    default:
      return 'No explanation for this decision.';
  }
}

export const SUGGESTED_QUESTIONS = [
  'Is my plant okay?',
  'Why did you water?',
  'When is the next watering?',
  'How much water did we use?',
];

// Offline answers built from the same facts the LLM will get.
// Real endpoint: POST /api/chat → { answer, facts, provider, model, latency_ms }
export function answerQuestion(question, decisionT) {
  const s = getStatus();
  const water = getWaterLast7Days();
  // Match word beginnings, so "health" also matches "healthy" and "water" matches "watering".
  const q = ` ${question.toLowerCase().replace(/[^a-z0-9à-ÿ]+/g, ' ')} `;
  const words = q.trim().split(' ');
  const has = (...stems) =>
    stems.some((st) => (st.includes(' ') ? q.includes(st) : words.some((w) => w.startsWith(st))));
  const lastWater = week().decisions.filter((d) => d.reason === 'DRY_BELOW_MIN').pop();
  const target = `target = ${PROFILE.minPct}–${PROFILE.maxPct} %`;
  const pct = Math.round(s.moisture);
  const pad = (n) => String(n).padStart(2, '0');
  const clock = (t) => `${pad(new Date(t).getHours())}:${pad(new Date(t).getMinutes())}`;
  const nextText =
    s.nextWateringH < 1 ? 'at the next check' : `in about ${Math.round(s.nextWateringH)} h`;

  let text;
  let facts;
  const decision = decisionT && week().decisions.find((d) => d.t === Number(decisionT));

  if (decision) {
    text = explain(decision);
    facts = [`decision = ${decision.action}`, `reason = ${decision.reason}`, target];
    if (decision.moisture != null) facts.push(`moisture then = ${decision.moisture} %`);
    if (decision.temp != null) facts.push(`air temp then = ${decision.temp} °C`);
  } else if (has('why', 'pourquoi') && has('water', 'arros')) {
    text = lastWater ? explain(lastWater) : "I haven't watered in the last 7 days.";
    facts = lastWater
      ? [`last watering = ${new Date(lastWater.t).toLocaleString()}`, `moisture then = ${lastWater.moisture} %`, target, `reason = ${lastWater.reason}`]
      : ['waterings in 7 days = 0'];
  } else if (has('how much', 'combien', 'used', 'consum', 'consomm', 'total')) {
    text = `In the last 7 days I watered ${water.count} times and used ${water.totalMl} ml in total, about ${water.perDayMl} ml a day.`;
    facts = [`waterings in 7 days = ${water.count}`, `water in 7 days = ${water.totalMl} ml`, `dose = ${PROFILE.doseMl} ml`];
  } else if (has('next', 'when', 'soon', 'quand', 'prochain')) {
    text = s.nextWateringH < 1
      ? `Soil is at ${pct} %, so I'll water at the next check.`
      : `Soil is at ${pct} % and drying, so I expect to water ${nextText}, when it drops below ${PROFILE.minPct} %.`;
    facts = [`moisture now = ${s.moisture} %`, target, `estimated hours to minimum = ${s.nextWateringH.toFixed(1)}`];
  } else if (has('temp', 'hot', 'heat', 'warm', 'cold', 'air', 'humid', 'chaud', 'chaleur', 'froid')) {
    text = `Air is at ${s.temp} °C with ${s.humidity} % humidity. The heat limit for ${PROFILE.plant.toLowerCase()} is ${PROFILE.heatLimitC} °C${s.temp > PROFILE.heatLimitC ? ', so it is too hot right now.' : ', so it is fine.'}`;
    facts = [`air temp now = ${s.temp} °C`, `humidity now = ${s.humidity} %`, `heat limit = ${PROFILE.heatLimitC} °C`];
  } else if (has('light', 'sun', 'lux', 'dark', 'shade', 'lumi', 'soleil', 'ombre')) {
    text = s.light === 0
      ? "It's dark right now, which is normal at night. During the day the pot gets enough light."
      : `Light is ${s.light} lux right now. Mint likes bright light without hours of hot direct sun, so this is fine.`;
    facts = [`light now = ${s.light} lux`];
  } else if (has('reservoir', 'réservoir', 'tank', 'refill', 'remplir', 'empty', 'vide')) {
    text = s.reservoirOk
      ? 'The water reservoir is OK. I will warn you here as soon as it runs empty.'
      : "The reservoir is empty, so I can't water. Please refill it.";
    facts = [`reservoir = ${s.reservoirOk ? 'ok' : 'empty'}`];
  } else if (has('water', 'arros', 'irrig', 'soil', 'moist', 'dry', 'wet', 'thirst', 'soif', 'sec', 'sol')) {
    const state =
      s.moisture < PROFILE.minPct ? 'too dry, so I will water it at the next check'
        : s.moisture > PROFILE.maxPct ? 'wetter than it needs to be, so I will wait'
          : `inside the ${PROFILE.minPct}–${PROFILE.maxPct} % target, so it is well watered`;
    const last = s.lastWatering ? ` I last gave it ${s.lastWatering.ml} ml at ${clock(s.lastWatering.t)}.` : '';
    text = `Soil is at ${pct} %, ${state}.${last} Next watering ${nextText}.`;
    facts = [`moisture now = ${s.moisture} %`, target, `estimated hours to minimum = ${s.nextWateringH.toFixed(1)}`];
    if (s.lastWatering) facts.push(`last watering = ${clock(s.lastWatering.t)}, ${s.lastWatering.ml} ml`);
  } else if (has('health', 'ok', 'good', 'fine', 'well', 'alive', 'status', 'doing', 'dying', 'sick', 'sant', 'bien', 'va', 'plant', 'mint', 'menthe', 'how')) {
    const word = { healthy: 'healthy', thirsty: 'thirsty', stressed: 'stressed' }[s.status];
    text = `Your ${PROFILE.plant.toLowerCase()} looks ${word}. Soil is at ${pct} % (target ${PROFILE.minPct}–${PROFILE.maxPct} %), air is ${s.temp} °C and the reservoir is ${s.reservoirOk ? 'OK' : 'empty'}.${s.alerts.length ? ` ${s.alerts[0].text}` : ''}`;
    facts = [`moisture now = ${s.moisture} %`, target, `air temp now = ${s.temp} °C`, `humidity = ${s.humidity} %`, `reservoir = ${s.reservoirOk ? 'ok' : 'empty'}`, `alerts = ${s.alerts.length}`];
  } else if (has('hi', 'hello', 'hey', 'salut', 'bonjour', 'help', 'aide', 'what can', 'who')) {
    text = "Hi! I'm Nabta. Ask me how your mint is doing, why or when I water, how much water I used, or about temperature, light and the reservoir.";
    facts = [];
  } else {
    text = "I don't know that one. I only know your pot's data. Try “Is my plant okay?”, “Why did you water?” or “How warm is it?”";
    facts = [];
  }
  return { text, facts, provider: 'offline', model: 'fixed sentences' };
}

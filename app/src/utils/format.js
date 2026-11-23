const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const pad = (n) => String(n).padStart(2, '0');

export function formatTime(t) {
  const d = new Date(t);
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatDay(t) {
  return DAYS[new Date(t).getDay()];
}

export function formatWhen(t) {
  const isToday = new Date(t).toDateString() === new Date().toDateString();
  return isToday ? `Today ${formatTime(t)}` : `${formatDay(t)} ${formatTime(t)}`;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function formatDate(t) {
  const d = new Date(t);
  return `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

// "Today", "Yesterday" or "Mon 3 Nov", for grouping lists by day.
export function formatDayLabel(t) {
  const d = new Date(t).toDateString();
  if (d === new Date().toDateString()) return 'Today';
  if (d === new Date(Date.now() - 24 * 3600 * 1000).toDateString()) return 'Yesterday';
  return formatDate(t);
}

export function formatHours(h) {
  return h < 1 ? 'less than 1 h' : `about ${Math.round(h)} h`;
}

export function formatLux(lux) {
  return lux >= 1000 ? `${(lux / 1000).toFixed(1)}k lx` : `${lux} lx`;
}

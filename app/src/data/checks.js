import AsyncStorage from '@react-native-async-storage/async-storage';
import { Directory, File, Paths } from 'expo-file-system';
import { Platform } from 'react-native';

// Weekly plant checks for the study, saved on the phone.
// Later these also go to the server: POST /api/observations

const KEY = 'nabta.plantChecks.v1';
const DAY = 24 * 3600 * 1000;

export const STUDY_START = new Date(2026, 10, 9); // 9 Nov 2026
export const CHECK_EVERY_DAYS = 7;

export const WILTING = [
  { value: 0, label: '0 None' },
  { value: 1, label: '1 Slight' },
  { value: 2, label: '2 Clear' },
  { value: 3, label: '3 Severe' },
];

export function studyWeek(date = new Date()) {
  return Math.max(1, Math.floor((date - STUDY_START) / (7 * DAY)) + 1);
}

export async function loadChecks() {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

// The picker's photo lives in a cache folder Android can clear, so copy it to the app's documents.
// On the web it is already a data: URI saved with the check.
async function keepPhoto(uri) {
  if (Platform.OS === 'web') return uri;
  const source = new File(uri);
  const dir = new Directory(Paths.document, 'plant-checks');
  dir.create({ intermediates: true, idempotent: true });
  const target = new File(dir, `${Date.now()}-${source.name}`);
  await source.copy(target);
  return target.uri;
}

// Returns the full list, newest first.
export async function saveCheck(check) {
  const photoUri = check.photoUri ? await keepPhoto(check.photoUri) : null;
  const saved = { ...check, photoUri, id: String(Date.now()), date: Date.now(), week: studyWeek() };
  const checks = [saved, ...(await loadChecks())];
  await AsyncStorage.setItem(KEY, JSON.stringify(checks));
  return checks;
}

export async function deleteCheck(id) {
  const checks = await loadChecks();
  const removed = checks.find((c) => c.id === id);
  if (removed?.photoUri && Platform.OS !== 'web') {
    const file = new File(removed.photoUri);
    if (file.exists) file.delete();
  }
  const rest = checks.filter((c) => c.id !== id);
  await AsyncStorage.setItem(KEY, JSON.stringify(rest));
  return rest;
}

export function nextDue(checks) {
  if (checks.length === 0) return new Date();
  return new Date(checks[0].date + CHECK_EVERY_DAYS * DAY);
}

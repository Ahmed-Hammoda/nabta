import Ionicons from '@expo/vector-icons/Ionicons';
import * as ImagePicker from 'expo-image-picker';
import { useEffect, useState } from 'react';
import { Image, Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { Button, Card, Header, Label, Pill, Screen, Segmented } from '../../components/ui';
import { deleteCheck, loadChecks, nextDue, saveCheck, studyWeek, WILTING } from '../../data/checks';
import { colors } from '../../theme';
import { confirmAction } from '../../utils/dialog';
import { formatDate } from '../../utils/format';

const IS_WEB = Platform.OS === 'web';
// On the web the photo is kept as text in browser storage, so it is saved smaller.
const PHOTO_OPTIONS = { allowsEditing: true, aspect: [3, 4], quality: IS_WEB ? 0.3 : 0.6, base64: IS_WEB };

export default function CheckScreen() {
  const [checks, setChecks] = useState([]);
  const [height, setHeight] = useState('');
  const [leaves, setLeaves] = useState('');
  const [wilting, setWilting] = useState(0);
  const [photoUri, setPhotoUri] = useState(null);
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [savedMessage, setSavedMessage] = useState('');

  useEffect(() => {
    loadChecks().then(setChecks);
  }, []);

  const due = nextDue(checks);
  const isDue = due <= new Date();

  const pickPhoto = async (fromCamera) => {
    setErrors((e) => ({ ...e, photo: undefined }));
    if (fromCamera) {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) {
        setErrors((e) => ({
          ...e,
          photo: 'Camera access is off. Turn it on in Settings › Apps › Expo Go › Permissions, or choose a photo from the gallery.',
        }));
        return;
      }
    }
    const result = fromCamera
      ? await ImagePicker.launchCameraAsync(PHOTO_OPTIONS)
      : await ImagePicker.launchImageLibraryAsync({ ...PHOTO_OPTIONS, mediaTypes: ['images'] });
    if (result.canceled) return;
    const asset = result.assets[0];
    setPhotoUri(IS_WEB && asset.base64 ? `data:${asset.mimeType || 'image/jpeg'};base64,${asset.base64}` : asset.uri);
  };

  const save = async () => {
    const heightCm = parseFloat(height.replace(',', '.'));
    const leafCount = Number(leaves);
    const found = {};
    if (!(heightCm > 0 && heightCm < 200)) found.height = 'Enter the height in cm, for example 18.5.';
    if (!(Number.isInteger(leafCount) && leafCount >= 0 && leaves.trim() !== '')) {
      found.leaves = 'Enter the number of leaves as a whole number, for example 34.';
    }
    setErrors(found);
    setSavedMessage('');
    if (Object.keys(found).length) return;

    setSaving(true);
    try {
      const list = await saveCheck({ heightCm, leafCount, wilting, note: note.trim(), photoUri });
      setChecks(list);
      setHeight('');
      setLeaves('');
      setWilting(0);
      setPhotoUri(null);
      setNote('');
      setSavedMessage(`Saved. Next check due ${formatDate(nextDue(list))}.`);
    } catch {
      setErrors({ save: "Couldn't save the check on this phone. Try again." });
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = (check) =>
    confirmAction(
      'Delete this check?',
      `Week ${check.week}, ${formatDate(check.date)}. This can't be undone.`,
      'Delete',
      async () => setChecks(await deleteCheck(check.id))
    );

  return (
    <Screen>
      <Header title="Plant check" subtitle={`Study week ${studyWeek()} · ${formatDate(Date.now())}`} />

      <Card style={styles.due}>
        <Ionicons name="calendar-outline" size={20} color={isDue ? colors.warn : colors.leaf} />
        <Text style={styles.dueText}>
          {isDue ? 'A check is due today' : `Next check due ${formatDate(due)}`}
        </Text>
        <Pill tone={isDue ? 'warn' : 'leaf'}>{isDue ? 'Due' : 'Done'}</Pill>
      </Card>

      <Card style={styles.form}>
        <Field label="Height (cm)" error={errors.height}>
          <TextInput
            value={height}
            onChangeText={setHeight}
            keyboardType="decimal-pad"
            placeholder="18.5"
            placeholderTextColor={colors.muted}
            style={[styles.input, errors.height && styles.inputError]}
          />
        </Field>

        <Field label="Leaf count" error={errors.leaves}>
          <TextInput
            value={leaves}
            onChangeText={setLeaves}
            keyboardType="number-pad"
            placeholder="34"
            placeholderTextColor={colors.muted}
            style={[styles.input, errors.leaves && styles.inputError]}
          />
        </Field>

        <Field label="Wilting">
          <Segmented options={WILTING} value={wilting} onChange={setWilting} />
        </Field>

        <Field label="Photo" error={errors.photo}>
          {photoUri ? (
            <View style={styles.photoRow}>
              <Image source={{ uri: photoUri }} style={styles.photo} />
              <Pressable onPress={() => setPhotoUri(null)} hitSlop={8}>
                <Text style={styles.remove}>Remove photo</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.photoButtons}>
              <View style={styles.flex}>
                <Button
                  variant="outline"
                  label="Take photo"
                  icon={<Ionicons name="camera-outline" size={18} color={colors.leaf} />}
                  onPress={() => pickPhoto(true)}
                />
              </View>
              <View style={styles.flex}>
                <Button
                  variant="outline"
                  label="Gallery"
                  icon={<Ionicons name="images-outline" size={18} color={colors.leaf} />}
                  onPress={() => pickPhoto(false)}
                />
              </View>
            </View>
          )}
          <Text style={styles.hint}>Take it from the same spot every week so the photos compare.</Text>
        </Field>

        <Field label="Note (optional)">
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="New shoots at the base"
            placeholderTextColor={colors.muted}
            multiline
            style={[styles.input, styles.note]}
          />
        </Field>

        {errors.save && <Text style={styles.error}>{errors.save}</Text>}
        <Button
          label={saving ? 'Saving…' : 'Save check'}
          icon={<Ionicons name="checkmark" size={18} color={colors.surface} />}
          onPress={save}
          disabled={saving}
        />
        {savedMessage ? <Text style={styles.saved}>{savedMessage}</Text> : null}
      </Card>

      <Label>Past checks</Label>
      {checks.length === 0 ? (
        <Text style={styles.hint}>No checks yet. Do the first one today; it is the study's starting point.</Text>
      ) : (
        checks.map((c, i) => {
          const previous = checks[i + 1];
          const growth = previous ? Math.round((c.heightCm - previous.heightCm) * 10) / 10 : null;
          return (
            <Pressable key={c.id} onLongPress={() => confirmDelete(c)} accessibilityHint="Long press to delete">
              <Card style={styles.past}>
                {c.photoUri ? (
                  <Image source={{ uri: c.photoUri }} style={styles.thumb} />
                ) : (
                  <View style={[styles.thumb, styles.noPhoto]}>
                    <Ionicons name="leaf-outline" size={22} color={colors.muted} />
                  </View>
                )}
                <View style={styles.flex}>
                  <Text style={styles.pastTitle}>
                    Week {c.week} · {formatDate(c.date)}
                  </Text>
                  <Text style={styles.pastBody}>
                    {c.heightCm} cm · {c.leafCount} leaves · wilting {c.wilting}
                  </Text>
                  {growth !== null && (
                    <Text style={styles.hint}>
                      {growth >= 0 ? '+' : ''}
                      {growth} cm since the last check
                    </Text>
                  )}
                  {c.note ? <Text style={styles.hint}>{c.note}</Text> : null}
                </View>
              </Card>
            </Pressable>
          );
        })
      )}
      {checks.length > 0 && <Text style={styles.hint}>Long-press a check to delete it.</Text>}
    </Screen>
  );
}

function Field({ label, error, children }) {
  return (
    <View style={styles.field}>
      <Label>{label}</Label>
      {children}
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  due: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  dueText: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.fg },
  form: { gap: 16 },
  field: { gap: 6 },
  input: {
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    color: colors.fg,
    backgroundColor: colors.bg,
  },
  inputError: { borderColor: colors.crit },
  note: { minHeight: 72, textAlignVertical: 'top' },
  error: { fontSize: 13, color: colors.crit },
  hint: { fontSize: 13, color: colors.muted },
  saved: { fontSize: 14, color: colors.leaf, fontWeight: '600', textAlign: 'center' },
  photoButtons: { flexDirection: 'row', gap: 10 },
  photoRow: { flexDirection: 'row', alignItems: 'flex-end', gap: 12 },
  photo: { width: 120, height: 160, borderRadius: 10, backgroundColor: colors.track },
  remove: { fontSize: 14, color: colors.crit, fontWeight: '600' },
  past: { flexDirection: 'row', gap: 12, alignItems: 'center' },
  thumb: { width: 60, height: 80, borderRadius: 8, backgroundColor: colors.track },
  noPhoto: { alignItems: 'center', justifyContent: 'center' },
  pastTitle: { fontSize: 15, fontWeight: '700', color: colors.fg },
  pastBody: { fontSize: 14, color: colors.fg },
});

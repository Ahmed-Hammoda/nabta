import { Alert, Platform } from 'react-native';

// Alert.alert does nothing in a browser, so the web version uses the browser's own dialogs.

export function notify(title, message) {
  if (Platform.OS === 'web') window.alert(`${title}\n\n${message}`);
  else Alert.alert(title, message);
}

export function confirmAction(title, message, actionLabel, onConfirm) {
  if (Platform.OS === 'web') {
    if (window.confirm(`${title}\n\n${message}`)) onConfirm();
    return;
  }
  Alert.alert(title, message, [
    { text: 'Cancel', style: 'cancel' },
    { text: actionLabel, style: 'destructive', onPress: onConfirm },
  ]);
}

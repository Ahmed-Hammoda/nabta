# Nabta app

Phone app for the Nabta smart pot (CS496 AI Engineering, MedTech). Built with Expo SDK 58 and Expo Router.

The app has five tabs: Home, History, Ask Nabta, Decision log and Plant check. Sensor data is simulated in `src/data/mock.js` until the Raspberry Pi server is ready. Plant checks are saved on the phone.

## Run it on your phone

1. Install [Node.js LTS](https://nodejs.org) on your computer, and **Expo Go** from the Play Store or App Store on your phone.
2. Open a terminal in this folder and install the packages:
   ```
   npm install
   ```
   If the download fails on the MedTech network, use this mirror first (PowerShell):
   ```
   $env:npm_config_registry = "https://registry.yarnpkg.com/"
   ```
3. Start the app:
   ```
   npx expo start
   ```
4. Put your phone on the same Wi-Fi as the computer and scan the QR code with Expo Go (Android) or the Camera app (iPhone). If it doesn't load, run `npx expo start --tunnel` instead.

## Where things are

| Path | What it does |
|---|---|
| `src/app/(tabs)/` | One file per tab: `index.js` (Home), `history.js`, `ask.js`, `log.js`, `check.js` |
| `src/data/mock.js` | Simulated sensor data, decisions and the offline chat answers |
| `src/data/checks.js` | Saves the weekly plant checks on the phone |
| `src/components/` | Shared pieces: cards, chips, buttons, the moisture gauge, the line chart |
| `src/theme.js` | Colors |

## Build the Android APK

Needs an Expo account (free) with access to the project:

```
npx eas-cli@latest login
npx eas-cli@latest build -p android --profile preview
```

Run `npx expo-doctor` before building. Install packages with `npx expo install <package>`, not with `--legacy-peer-deps`.

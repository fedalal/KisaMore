# KisaMore Battle — Android

Native Android client for KisaMore Plant Battle.

## Current features

- public/spectator battle list;
- login with the existing KisaMore account;
- automatic server failover: `https://kisamore.farm` -> `https://ru.kisamore.farm`;
- player's battle dashboard;
- real rack photo and container numbers;
- water, nutrient and shade resource meters;
- real battle commands sent to the existing FastAPI backend;
- 24-hour / 3-day timelapse links;
- player's recent command history;
- winner prediction voting;
- local XP, streaks, daily missions and badges;
- visible app version on the login screen.

## Android / Google Play

- applicationId: `farm.kisamore.battle`
- minSdk: 26
- compileSdk: 36
- targetSdk: 36
- current version: 0.4.2 (versionCode 10)

Google Play publication material is in:
`../google-play/`

## Local debug build

```bash
gradle -p android-battle testDebugUnitTest assembleDebug
```

Debug APK:
`android-battle/app/build/outputs/apk/debug/app-debug.apk`

## Release AAB

An unsigned local smoke-test AAB can be built with:

```bash
gradle -p android-battle bundleRelease
```

For a signed Google Play AAB, use the GitHub Actions workflow:
**Android Battle — Google Play AAB**

Signing credentials are read only from environment variables / GitHub Actions secrets.
See `../google-play/signing-setup.md`.

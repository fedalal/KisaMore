# KisaMore Battle — Android MVP

First native Android client for KisaMore Plant Battle.

## MVP features

- public/spectator battle list;
- login with the existing KisaMore account;
- player's battle dashboard;
- real rack photo with the player's container highlighted;
- water, nutrient and shade resource meters;
- real battle commands sent to the existing FastAPI backend;
- 24-hour / 3-day timelapse links;
- player's recent command history;
- winner prediction voting for players and spectators;
- persistent session cookie and configurable server URL.

The default server is `https://kisamore.farm`. The login screen can be switched to
`https://ru.kisamore.farm` for testing the Russian endpoint.

## Open in Android Studio

Open the `android-battle` directory as a Gradle project, wait for Gradle sync, then run the
`app` configuration on an Android 8.0+ device/emulator.

## Command-line build

A local Gradle installation can build the project:

```bash
gradle -p android-battle testDebugUnitTest assembleDebug
```

The debug APK is created at:

```
android-battle/app/build/outputs/apk/debug/app-debug.apk
```

GitHub Actions also builds and uploads the APK artifact on pushes to
`feature/battle-android-mvp`.

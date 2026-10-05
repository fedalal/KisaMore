# KisaMore Battle — Google Play publication pack

This directory contains the technical and Play Console material for publishing
**KisaMore Battle**.

## App identity

- App name: **KisaMore Battle**
- Package / applicationId: **farm.kisamore.battle**
- App type: **Game**
- Suggested category: **Simulation**
- Current Play-ready version: **0.4.0 (versionCode 8)**
- Minimum Android: **Android 8.0 / API 26**
- Target Android: **Android 16 / API 36**
- Website: **https://kisamore.farm**
- Privacy policy: **https://kisamore.farm/privacy**
- Account deletion: **https://kisamore.farm/delete-account**
- Support email: **support@kisamore.farm**

## Files in this pack

- `store-listing-en.md` — English store listing text.
- `store-listing-ru.md` — Russian store listing text.
- `data-safety.md` — recommended Play Data safety answers based on the current Android client.
- `review-access.md` — reviewer access / test-account instructions.
- `release-checklist.md` — step-by-step Play Console checklist.
- `signing-setup.md` — GitHub Actions signing setup.

## Build workflows

Normal development CI:
`.github/workflows/android-battle.yml`

Google Play signed AAB:
`.github/workflows/android-battle-play.yml`

The Play workflow produces:
`android-battle/app/build/outputs/bundle/release/app-release.aab`

Never commit the upload keystore or its passwords.

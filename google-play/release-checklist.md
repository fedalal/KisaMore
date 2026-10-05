# KisaMore Battle — Play Console release checklist

## Developer account
- Create/verify Google Play developer account.
- If using an Organization account, complete organization verification and D-U-N-S requirements.
- If using a new Personal developer account, follow Play Console's current testing requirements before production access.

## Create app
- App name: KisaMore Battle
- Default language: English (United States)
- App or game: Game
- Free or paid: Free
- Suggested category: Simulation

## Store listing
Use:
- `store-listing-en.md`
- `store-listing-ru.md`

Upload:
- 512 x 512 Play Store icon (PNG)
- 1024 x 500 feature graphic
- real screenshots of the current Android app

Recommended screenshots:
1. Home screen with XP and daily missions.
2. Live arena with the rack photo.
3. Player resources and action buttons.
4. Spectator predictions / battle view.
5. Gardener profile and achievements.

Do not use fabricated UI screenshots. Capture them from the release build.

## App content
- Privacy policy URL: https://kisamore.farm/privacy
- Account deletion URL: https://kisamore.farm/delete-account
- Complete Data safety using `data-safety.md` as the starting point.
- Complete content rating questionnaire.
- Declare ads: No, unless advertising is later added.
- Complete target audience declaration.
- Complete App access using `review-access.md`.

## Release
- Configure GitHub signing secrets.
- Run **Android Battle — Google Play AAB**.
- Download the signed `app-release.aab` artifact.
- Create an Internal testing release first.
- Install from Google Play and verify login, failover, photos, battle actions, timelapses and icon.
- Move through Closed testing / Production according to the requirements shown for the developer account.

## Before every update
- Increase `versionCode`.
- Update `versionName`.
- Re-run CI.
- Review Data safety if functionality or SDKs changed.
- Keep the upload key backed up offline.

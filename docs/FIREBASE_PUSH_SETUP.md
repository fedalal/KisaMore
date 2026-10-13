# KisaMore Battle — Firebase Cloud Messaging

FCM supplements, but does **not** replace, the durable web/Android inbox,
Telegram notifications, or periodic Android inbox polling. Android uses a
high-priority *data-only* push with a receipt ID and fetches the message body
via the logged-in user's authenticated HTTPS API. A delayed notification
cannot reveal one account's message to another account on the same phone.

## 1. Connect the Android application

1. Open [Firebase Console](https://console.firebase.google.com/). Create a Firebase
   project (or choose an existing project for KisaMore).
2. Add an **Android app** with package name **`farm.kisamore.battle`**.
3. Download **`google-services.json`** from Project settings → Your apps.
   Do **not** rename the package or upload a different app's configuration.
4. For GitHub Actions builds, create the repository Actions secret
   **`KISAMORE_FIREBASE_ANDROID_JSON_B64`** containing base64 of the entire JSON.
   On Windows PowerShell, generate it locally:

   ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\path\google-services.json'))
   ```

   On Linux/macOS: `base64 -w 0 google-services.json` (on macOS: `base64 -i google-services.json | tr -d '\n'`).
   Do not paste the base64 into a source file or commit the JSON to Git.
5. Trigger a **fresh** Android Battle workflow; APKs built before the secret
   was configured still support only background polling, not FCM.

## 2. Enable server sending (VPS)

1. In the **same Firebase project**, under Project settings → Service accounts,
   generate a Firebase Admin SDK private key JSON. Keep it secret. Enable
   Firebase Cloud Messaging API (HTTP v1) if required by Google Cloud.
2. Place it on the VPS **outside the Git repository** at:

   `/etc/kisamore/firebase/firebase-service-account.json`

   The worker runs as user `kisamore` within Docker. Grant that user *read*
   access without granting other local users access, e.g. via a root-owned
   group-readable file with the matching in-container group ID. Verify with
   `docker exec kisamore-battle-push-worker-1 test -r /run/secrets/kisamore/firebase-service-account.json`.
3. Restart the worker:

   ```bash
   cd /home/alex/projects/KisaMore
   docker compose --env-file cloud/.env -f docker-compose.cloud.yml up -d --no-deps battle-push-worker
   ```

4. Install the newly-built APK; log in, grant notification permission, and
   ensure Google Play services are available on the phone. The app will post
   its installation token to `/api/v1/battles/push-devices`.
5. In `/admin` → Battles → Messages, send **one test message to your own
   container only**, with the Android app backgrounded. The worker should
   show a successful FCM send; Android should show the notification, with
   permanent message content available under Profile → Notifications.

## Diagnostic commands

```bash
# A missing key means FCM is disabled gracefully, not that the web inbox is broken.
docker logs --since 10m kisamore-battle-push-worker-1
# Inspect aggregate delivery states without exposing recipient tokens.
docker exec kisamore-postgres-1 sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT status,COUNT(*) FROM battle_push_deliveries GROUP BY status;"'
```

FCM is near-real-time when Google Play services and network conditions allow,
not a hard delivery-time guarantee. Power-saving modes and regional blocks can
still delay it. Pending messages are always available in the application inbox.

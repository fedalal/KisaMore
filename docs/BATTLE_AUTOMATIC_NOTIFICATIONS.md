# KisaMore Battle — automatic participant notifications

All messages are persisted and visible via authenticated /api/v1/battles/inbox.
The Android FCM push sends only a receipt ID, which is reauthorized via the inbox before its contents are shown.

Event | Trigger | Recipient | Deduplication
--- | --- | --- | ---
Start | All six plantings confirmed (planting → growing) | active members | once / battle / account
24h remaining | Within final day of scheduled end_date | active members | once / battle / account
Growing finished | Six plants harvested (growing → judging) | active members | once / battle / account
Winner announced | Admin chooses winner (judging → finished) | all members | once / battle / account
Resources low | Remaining available budget <= 20% upon action reservation | container owner | once / entry / resource
Action done | Admin confirms a physical action | action owner | once / action
New battle | Admin opens a new Battle | opted-in active users only | once / battle / account

All preferences default on except **New Battles**, which defaults off to prevent unwanted announcements.
Per-account controls: Android Profile → Notifications → Settings.
API: GET and PATCH /api/v1/battles/notification-preferences.

The end_date is a DATE, treated as the end of its local farm day (Europe/Moscow by default). If absent, the 24-hour notice is skipped. A single worker scans on a 5-minute interval while the Battle is growing.

Resources are reserved on user request, and returned on rejection. These notices report the available allowance (not the physical water tank). They do not instruct players when to water.

Durable, unique event keys and per-device outbox rows avoid duplicates across retries and server restarts. No historic events are backfilled. Telegram existing start/action/winner messages remain unchanged; the new event notifications do not duplicate those Telegram messages. Push requires Firebase and Android notification permissions; the inbox remains available independently.

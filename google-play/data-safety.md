# Google Play Data safety — current Android client

This is a preparation sheet, not a substitute for the final Play Console declaration.
Re-check it whenever analytics, ads, payments, crash reporting, location, camera, microphone,
contacts, or third-party SDKs are added.

## Android permissions

Current manifest:
- INTERNET

The app does **not** currently request:
- precise or approximate location;
- contacts;
- camera;
- microphone;
- photos/videos;
- device files.

## Data used by the app/service

### Personal info
**Email address**
- Collected: yes, for account login and account recovery.
- Purpose: account management / app functionality.
- Required for an account: yes.
- Encrypted in transit: yes (HTTPS).

**Name / display name**
- Collected: yes.
- Purpose: account identity and battle/certificate display.
- Encrypted in transit: yes.

**User IDs**
- Collected: yes.
- Purpose: account and battle association.
- Encrypted in transit: yes.

### App activity
**Gameplay / app interactions**
Examples: battle participation, resource commands, predictions, timestamps.
- Collected: yes.
- Purpose: app functionality, competition history, fraud/security and support.
- Encrypted in transit: yes.

### Authentication
The Android client stores a session token and basic account information locally.
Passwords are sent over HTTPS for authentication and are stored server-side as hashes,
not as plaintext passwords.

## Data sharing

The current Android app has no advertising SDK and no third-party analytics SDK.
Backend service providers may process data on KisaMore's behalf for hosting and email delivery.
Optional Telegram linking is a separate user-initiated integration.

Before submitting, confirm whether any provider relationship must be declared as "sharing"
under the current Google Play Data safety definitions.

## Security practices

- Data in transit: HTTPS.
- Account deletion information: https://kisamore.farm/delete-account
- Privacy policy: https://kisamore.farm/privacy

## Items that should currently be answered "No" unless the implementation changes

- Location
- Contacts
- Photos and videos uploaded from the device
- Audio files / microphone
- Health and fitness
- Messages collected from the Android client
- Advertising data
- Device advertising ID
- Crash analytics SDK data


## Account creation and deletion

The Android app now allows account creation using:
- display name;
- email address;
- password.

In Play Console, declare the account creation method as:
**Username and password**.

The app provides a readily discoverable account deletion path from Profile to:
https://kisamore.farm/delete-account

The external deletion resource remains available even after the app is uninstalled.

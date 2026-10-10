# KisaMore Battle: original Google Play upload certificate

KisaMore Battle Google Play update: package farm.kisamore.battle,
version 0.6.16 (versionCode 31). The ORIGINAL existing upload key was
recovered from the original KisaMore-Play-Signing.zip archive dated October 5.

Recovered JKS and PEM public certificate MATCH.
An Android App Bundle 0.6.16 was signed by that private key, verified with
jarsigner -verify, and its certificate fingerprint checked by keytool.

Pinned ORIGINAL UPLOAD certificate SHA-256:
13:CC:46:3F:9A:EE:39:28:BF:BA:AA:7A:9A:6C:94:46:B1:17:AE:F1:A6:4D:8F:C7:4B:48:B5:51:63:FE:DE:03

Every future release checks this fingerprint against
google-play/upload-certificate-sha256.txt. Before uploading, also compare
the existing application's Upload key certificate in Play Console against
this fingerprint. Live Play Console certificate has not been fetched.

IMPORTANT: never use the superseded NEW key from October 10; do not request
an upload-key reset in Play Console. Keep the existing app signing key and
upload key unchanged. Do not generate a new key for future releases.

PRIVATE KEY STORAGE
The original private JKS, alias and passwords remain in the old private
KisaMore-Play-Signing.zip archive. Keep two secure backup copies and NEVER
commit a private keystore or passwords to GitHub.

To ensure future releases use the SAME original key, configure repository
GitHub Actions secrets:
- KISAMORE_UPLOAD_KEYSTORE_BASE64: Base64 of kisamore-upload-key.jks from original ZIP
- KISAMORE_UPLOAD_STORE_PASSWORD: original README-SIGNING.txt store password
- KISAMORE_UPLOAD_KEY_ALIAS: kisamore-upload
- KISAMORE_UPLOAD_KEY_PASSWORD: original README-SIGNING.txt key password

The Android Battle - Google Play AAB workflow refuses signing without these
secrets or if the fingerprint does not match the pinned ORIGINAL key.

The signed 0.6.16 AAB was supplied separately in ChatGPT:
KisaMore-Battle-0.6.16-GooglePlay-ORIGINAL-key.aab

To publish, open the EXISTING app in Play Console, create an update
release, and upload that AAB. No key reset is needed when the Play
Console upload certificate matches.

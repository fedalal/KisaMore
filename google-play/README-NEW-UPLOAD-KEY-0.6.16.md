# KisaMore Battle: permanent Google Play upload key

Current Google Play version: 0.4.5, versionCode 13 (user-provided).
Prepared version: 0.6.16, versionCode 31.
Package: farm.kisamore.battle.

NEW upload certificate SHA-256:
F2:13:31:88:B8:C8:3C:0D:C4:B6:36:09:1F:5D:52:A7:14:A6:23:81:E7:A9:14:B2:DA:8F:F8:2E:D5:9C:B3:0A

The fingerprint is pinned in google-play/upload-certificate-sha256.txt.
Do not generate another key for any future release.

## ONE-TIME: Google Play Console upload-key reset

In the EXISTING KisaMore Battle listing open Setup > App integrity > App signing.
Request an UPLOAD KEY reset, supplying the public .pem certificate provided separately.
Wait until the new upload certificate is shown as active.

IMPORTANT: Do not change the APP SIGNING KEY itself. Google Play must continue
signing downloads with the original app signing key so installed versions update
in place. If Play App Signing is NOT enabled, an existing install cannot be updated
with a new signing key; you must recover the old signing key instead.

## Store key and credentials

Download the permanent new upload JKS file and private credentials text from the
conversation. Back them up in secure separate offline locations (password manager).
Do not commit private key, keystore, or passwords to the repo, even as Base64.

## Set repository Actions secrets ONCE

fedalal/KisaMore > Settings > Secrets and variables > Actions

KISAMORE_UPLOAD_KEYSTORE_BASE64: Base64 encoding of the PERMANENT JKS
KISAMORE_UPLOAD_STORE_PASSWORD: password from private credentials
KISAMORE_UPLOAD_KEY_ALIAS: kisamore-upload
KISAMORE_UPLOAD_KEY_PASSWORD: key password from private credentials

Windows PowerShell to copy keystore Base64:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("KisaMore-Battle-GooglePlay-NEW-Upload.jks")) | Set-Clipboard

Then run GitHub Actions: Android Battle - Google Play AAB.
It will use the exact JKS from the secrets, verify the upload certificate against
the pinned SHA-256, run tests, sign the AAB, and verify the bundle. Mismatched or
missing signing material causes FAILURE; never automatically generate another key.

The ordinary Android Battle MVP CI can also build an explicitly UNSIGNED AAB
for offline signing only. That artifact is not ready for Play until signed
with the same permanent upload key.

## Publish version 0.6.16

After the Play Console upload-key reset is approved, open the existing app's
Testing or Production section, create a new release, and upload the signed
KisaMore-Battle-0.6.16-GooglePlay.aab. VersionCode 31 is greater than 13.
Check the release is accepted by Google Play before rolling it out.

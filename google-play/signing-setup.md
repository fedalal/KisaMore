# Google Play upload signing

The repository is prepared for a private Google Play **upload key**.

Do not commit the keystore.

## Required GitHub Actions repository secrets

Create these in:
GitHub -> KisaMore -> Settings -> Secrets and variables -> Actions

- `KISAMORE_UPLOAD_KEYSTORE_BASE64`
- `KISAMORE_UPLOAD_STORE_PASSWORD`
- `KISAMORE_UPLOAD_KEY_ALIAS`
- `KISAMORE_UPLOAD_KEY_PASSWORD`

The prepared key uses alias:
`kisamore-upload`

The passwords are intentionally not stored in this repository.

## Convert the JKS to base64

Windows PowerShell:

```powershell
[Convert]::ToBase64String(
    [IO.File]::ReadAllBytes("kisamore-upload-key.jks")
) | Set-Clipboard
```

Paste the clipboard into `KISAMORE_UPLOAD_KEYSTORE_BASE64`.

## Build the signed AAB

After all four secrets are configured:

GitHub -> Actions -> **Android Battle — Google Play AAB** -> Run workflow

The workflow:
1. installs Android API 36;
2. restores the upload keystore only inside the temporary GitHub runner;
3. runs tests;
4. builds a signed release AAB;
5. verifies the AAB signature;
6. uploads `kisamore-battle-google-play-aab` as a workflow artifact.

Google Play App Signing should be enabled when the application is created in Play Console.

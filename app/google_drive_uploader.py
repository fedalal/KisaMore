import io
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveUploader:
    def __init__(self, credentials_file: str, folder_id: str, token_file: str):
        self.credentials_file = credentials_file
        self.folder_id = folder_id
        self.token_file = token_file
        self.service = None

    def _get_credentials(self):
        creds = None

        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                SCOPES,
            )

            creds = flow.run_local_server(
                host="0.0.0.0",
                port=8090,
                open_browser=False,
            )

            with open(self.token_file, "w", encoding="utf-8") as token:
                token.write(creds.to_json())

        return creds

    def _get_service(self):
        if self.service:
            return self.service

        creds = self._get_credentials()
        self.service = build("drive", "v3", credentials=creds)
        return self.service

    def upload_jpeg_bytes(self, jpeg_bytes: bytes, filename: str):
        service = self._get_service()

        media = MediaIoBaseUpload(
            io.BytesIO(jpeg_bytes),
            mimetype="image/jpeg",
            resumable=False,
        )

        body = {
            "name": filename,
            "parents": [self.folder_id],
        }

        return service.files().create(
            body=body,
            media_body=media,
            fields="id,name",
        ).execute()
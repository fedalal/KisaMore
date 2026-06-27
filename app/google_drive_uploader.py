import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveUploader:
    def __init__(self, credentials_file: str, folder_id: str):
        self.credentials_file = credentials_file
        self.folder_id = folder_id
        self.service = None

    def _get_service(self):
        if self.service:
            return self.service

        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=SCOPES,
        )

        self.service = build("drive", "v3", credentials=credentials)
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
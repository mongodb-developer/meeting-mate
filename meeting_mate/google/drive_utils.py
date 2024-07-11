from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import io

def get_doc_contents(doc, *, credentials:Credentials) -> tuple[dict, bytes]:    
    service = build('docs', 'v1', credentials=credentials)
    driveService = build("drive", "v3", credentials=credentials)

    print("Fetching doc", doc.get("doc_id"))
    jsonFormat = service.documents().get(documentId=doc["doc_id"]).execute()

    # check/update permissions
    permissions = driveService.permissions().list(fileId=doc["doc_id"]).execute()
    sharedWith = []
    for permission in permissions.get("permissions", []):
        email = permission.get("emailAddress")
        if email is not None:
            sharedWith.append(email)

    # add permissions if shared with people
    
    request = driveService.files().export_media(fileId=doc["doc_id"], mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    file = io.BytesIO()
    
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()

    bytes = file.getvalue()
    return jsonFormat, bytes
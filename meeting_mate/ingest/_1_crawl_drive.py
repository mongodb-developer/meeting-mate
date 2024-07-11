from datetime import datetime, timezone, timedelta
from time import sleep
from meeting_mate.mongo.mongo import INSTANCE as mongo
from dotenv import dotenv_values
from meeting_mate.google.google_auth import getUserCredentials
from googleapiclient.discovery import build
from argparse import ArgumentParser

env_values = dotenv_values()

mongo_uri = env_values.get("mongo_uri")
mongo_db = env_values.get("mongo_db","rag")

# connect to mongo
db = mongo.db

def check_doc(id, modifiedTime, user_id):
    doc = db.docs.find_one({"doc_id": id})

    if doc is None or doc.get("modifiedTime") != modifiedTime:
        doc = {
            "user_id": user_id,
            "doc_id": id,
            "modifiedTime": modifiedTime
        }
        print(f"New or modified doc found: {id}")
        db.docs.replace_one({"doc_id": id}, doc, upsert=True)    

def sync_user(user, last_sync):
    # check if access token is still valid
    print(f"Syncing for user {user.get('sub')}")
    credentials = getUserCredentials(user.get("sub"))
    service = build('drive', 'v3', credentials=credentials)

    # Call the Drive v3 API to list Google Docs
    page_token = None
    while True:
        results = service.files().list(
            pageSize=100,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            orderBy="modifiedTime desc",
            q="mimeType='application/vnd.google-apps.document'",
            pageToken=page_token).execute()
            
    
        for item in results.get('files', []):    
            id = item.get("id")
            modifiedTime = datetime.strptime(item.get("modifiedTime"), "%Y-%m-%dT%H:%M:%S.%fZ")
            
            #break the loop when we start getting docs from before the last sync
            if modifiedTime < (last_sync - timedelta(minutes=5)):
                break

            check_doc(id, modifiedTime, user.get("sub"))       

        page_token = results.get('nextPageToken')
        if page_token is None:
            break


def sync_all_users():
    last_sync = db.config.find_one({"_id": "last_sync"})
    last_sync = datetime.fromtimestamp(0) if last_sync is None else last_sync.get("last_sync")

    sync_start_time = datetime.now(tz=timezone.utc)

    for user in db.users.find():
        sync_user(user, last_sync)

    db.config.replace_one({"_id":"last_sync"}, {"_id": "last_sync", "last_sync": sync_start_time}, upsert=True)

if __name__ == "__main__":
    """
    Simple sync loop. A more sensible solution would be to use the changes API
    https://developers.google.com/drive/api/guides/manage-changes#python
    """

    args = ArgumentParser()
    args.add_argument("interval", nargs="?", type=int, default=60, help="Interval in seconds between syncs")
    args = args.parse_args()

    while True:
        print(f"{datetime.now()} Starting sync...")
        sync_all_users()
        print(f"{datetime.now()} Sync complete. Sleeping for {args.interval} seconds...")
        sleep(args.interval)

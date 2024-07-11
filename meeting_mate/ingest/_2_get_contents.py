import io
from time import sleep
from meeting_mate.mongo.mongo import INSTANCE as mongo
import meeting_mate.google.drive_utils as drive_utils
from dotenv import dotenv_values
from meeting_mate.google.google_auth import getUserCredentials
import mammoth

env_values = dotenv_values()

mongo_uri = env_values.get("mongo_uri")
mongo_db = env_values.get("mongo_db","rag")

# connect to mongo
db = mongo.db

def retrieve_contents(doc):
    user_id = doc.get("user_id")
    credentials = getUserCredentials(user_id)
    
    jsonFormat, bytes = drive_utils.get_doc_contents(doc, credentials=credentials)

    html = mammoth.convert_to_html(io.BytesIO(bytes)).value
    markdown = mammoth.convert_to_markdown(io.BytesIO(bytes)).value

    updateDoc = {"content": jsonFormat, "html": html, "markdown": markdown, "title": jsonFormat.get("title")}
    result = db.docs.update_one({"doc_id": doc.get("doc_id")}, {"$set": updateDoc})

    # print warning if nothing was updated
    if result.matched_count == 0:
        print("Warning: no document was updated")

if __name__ == "__main__":
    for doc in db.docs.find({"content": {"$exists": False}}):
        print(f"Syncing doc {doc.get('_id')}")
        retrieve_contents(doc)


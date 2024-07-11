from datetime import datetime
from dotenv import dotenv_values
from bs4 import BeautifulSoup
import re
import markdownify
from time import sleep
from hashlib import md5

from meeting_mate.mongo.mongo import INSTANCE as mongo

env_values = dotenv_values()

mongo_uri = env_values.get("mongo_uri")
mongo_db = env_values.get("mongo_db","rag")

# connect to mongo
db = mongo.db

# corresponds to May 6, 2024
date_format = "%b %d, %Y"

# native regex to match the date
date_regex = re.compile("[A-Z][a-z]{2} \\d{1,2}, \\d{4}")

def generate_checksum(chunk):
    bytes = chunk.encode("utf-8")
    return md5(bytes).hexdigest()

def getHeaderInfo(tag):
    date_string = date_regex.search(tag.text)
    date = datetime.strptime(date_string.group(), date_format) if date_string else None
    calendar_link = next((a['href'] for a in tag.select('a') if a.has_attr('href') and "www.google.com/calendar/event" in a['href']), None)

    if date and calendar_link:
        return date, calendar_link
    else:
        return None

def create_chunk(last_header, header, doc, date, calendar_link):
    chunk = last_header.prettify()
    sibling = None
    while True:        
        sibling = last_header.find_next_sibling()
        if sibling and sibling!=header:
            chunk += sibling.prettify()
            sibling.extract()
        else:
            break

    chunk = "<html><body>"+chunk+"</body></html>"
    
    asMarkdown = markdownify.markdownify(chunk)
    asMarkdown = re.sub(r'\n+', '\n', asMarkdown)
    asMarkdown = f"Document title: {doc['title']} \n\n{asMarkdown}"

    checksum = generate_checksum(asMarkdown)
        
    return {"doc_id": doc["doc_id"], 
            "user_id":doc["user_id"], 
            "html": chunk,
            "checksum": checksum,
            "markdown": asMarkdown,
            "date": date, 
            "calendar_link": calendar_link}

def sync_chunks(chunks):
    # remove non-existing chunks first to account for modified/deleted ones
    all_checksums = [chunk["checksum"] for chunk in chunks]
    delete_query = {
        "doc_id": chunks[0]["doc_id"],
        "checksum": {"$nin": all_checksums}
    }
    result = db["chunks"].delete_many(delete_query)
    deleted = result.deleted_count

    unchanged = 0
    inserted = 0
    for chunk in chunks:
        # check if chunk already exists
        count = db["chunks"].count_documents({"doc_id": chunk["doc_id"], "checksum": chunk["checksum"]})
        if count > 0:
            unchanged += 1
            continue

        # insert new chunk    
        db["chunks"].insert_one(chunk)
        inserted += 1

    db["docs"].update_one({"_id": doc["_id"]}, {"$set": {"chunked": True}})
    print(f"Inserted {inserted} chunks, deleted {deleted} chunks, {unchanged} unchanged")

def chunk_doc(doc):
    parsed = BeautifulSoup(doc["html"], "html.parser")
    headers = parsed.findAll("h2")

    chunks = []
    last_header = None

    for header in headers:
        header_info = getHeaderInfo(header)
        if header_info: # is a header
            date, calendar_link = header_info
            if last_header:
                chunks.append(create_chunk(last_header, header, doc, date, calendar_link))

            last_header = header

    if last_header:
        chunks.append(create_chunk(last_header, None, doc, date, calendar_link))

    #wrap in a transaction
    try:
        with db.client.start_session() as session:
            with session.start_transaction():            
                sync_chunks(chunks)
    except Exception as e:
        print(f"Error syncing chunks: {e}")

if __name__ == "__main__":
    print("Checking for docs to chunk...")
    for doc in db["docs"].find({"html":{"$exists": True}, "chunked": {"$ne": True}}):
        chunk_doc(doc)

        
    

            
            

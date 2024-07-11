from meeting_mate.mongo.mongo import PLAIN_INSTANCE as mongo
import meeting_mate.ingest._2_get_contents as crawl_docs
import meeting_mate.ingest._3_chunk_docs as chunk_docs
import meeting_mate.ingest._4_extract_facts as extract_facts
import meeting_mate.ingest._5_cluster_facts as cluster_docs

from threading import Timer, Lock

def handle_doc_change(change):
    if change["operationType"] in ["replace", "insert"]:
        # new document, fetch contents
        print("New document, fetching contents")
        crawl_docs.retrieve_contents(change["fullDocument"])
    elif change["operationType"] == "update":
        if "content" in change["updateDescription"]["updatedFields"]:
            print("Contents updated, chunking...")
            chunk_docs.chunk_doc(change["fullDocument"])

cluster_timers:dict[Timer] = {}

def cluster_doc(doc_id):
    if cluster_timers.pop(doc_id, None) is None:
        return # was already canceled

    # delete existing facts
    mongo.db["facts"].delete_many({"doc_id": doc_id})

    # cluster and embed the new facts
    cluster_docs.cluster_and_embed(doc_id)

def defer_clustering(doc_id):   
    timer = cluster_timers.pop(doc_id, None)
    if timer is not None:
        timer.cancel()

    timer = Timer(30, cluster_doc, [doc_id])
    timer.start()
    
    cluster_timers[doc_id] = timer

def handle_chunk_change(change):
    if change["operationType"] == "insert":
        print("New chunk, extracting facts")
        extract_facts.add_facts_and_embeddings(change["fullDocument"])
    elif change["operationType"] == "update":
        if "embeddings" in change["updateDescription"]["updatedFields"]:
            print("Embeddings added to chunk, deferring clustering")
            defer_clustering(change["fullDocument"]["doc_id"])

cs_filter = [
    {
        '$match': {
            'ns.db': mongo.db.name,
            'ns.coll': {'$in': ['docs', 'chunks']},
        }
    }
]

resume_token = None
while True:
    try:
        change_stream = mongo.db.watch(cs_filter, full_document='updateLookup')
        for change in change_stream:
            resume_token = change['_id']
            if change["ns"]["coll"] == "docs":
                handle_doc_change(change)
            elif change["ns"]["coll"] == "chunks":
                handle_chunk_change(change)            
    except Exception as e:
        print(e)
    
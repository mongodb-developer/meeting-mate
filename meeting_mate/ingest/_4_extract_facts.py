import json
from pymongo import MongoClient
from dotenv import dotenv_values
from meeting_mate.llm.prompts import Templates, facts_answer_schema
from jsonschema import validate
from meeting_mate.llm import models
from langchain_core.messages import SystemMessage, HumanMessage
from concurrent.futures import ThreadPoolExecutor
from argparse import ArgumentParser

llm = models.ChatModel(models.ChatModels.MIXTRAL_8x22B_INSTRUCT, temperature=0.7, max_tokens=8000)
embeddings = models.EmbeddingsModel(models.EmbeddingModels.NOMIC_EMBED_TEXT_1_5)

values = dotenv_values()
uri = values.get("mongo_uri")
db = values.get("mongo_db", "rag")

client = MongoClient(uri)
db = client[db]
chunks_coll = db["chunks"]

def add_facts(doc):
    print(f"Extracting facts from {doc['_id']}")
    user = doc["user_id"]
    content = doc["markdown"]
    
    system = SystemMessage(Templates.extract_facts_system_prompt())
    context = HumanMessage(Templates.extract_facts_context_prompt(content))

    response = llm.invoke([system, context], "fact_extraction", user)
    asJson = json.loads(response)
    
    validate(asJson, facts_answer_schema)

    facts_list = [fact for category in asJson["summary"].values() for fact in category]

    update = {
        "people": asJson["people"],
        "organizations": asJson["organizations"],
        "facts": facts_list
    }

    # update the document with the extracted facts
    chunks_coll.update_one({"_id": doc["_id"]}, {"$set": update})
    return facts_list

def add_fact_embeddings(id, facts):
    doc = chunks_coll.find_one({"_id": id})
    user_id = doc["user_id"]

    fact_embeddings = embeddings.invoke(facts, purpose="embed_facts", user=user_id)
    
    chunks_coll.update_one({"_id": id}, {"$set": {"embeddings": fact_embeddings}})

def add_facts_and_embeddings(doc):
    facts = add_facts(doc)
    add_fact_embeddings(doc["_id"], facts)

if __name__ == "__main__":
    """
    We probably want a queue-based system for this, so we can handle bursty behavior and handle provider limits/ have a deadletter queue
    """
    args = ArgumentParser(add_help=True)
    args.add_argument("-w", "--workers", type=int, default=10, help="Number of workers to use for fact extraction (parallelism)")
    args.add_argument("-f", "--facts", action="store_true", default=False, help="Rerun fact extraction - useful when you changed prompts")
    args = args.parse_args()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:  
        if args.facts:
            print("Re-extracting facts")
            docs = chunks_coll.find()
        else:    
            docs = chunks_coll.find({"facts": {"$exists": False}})

        futures = [executor.submit(add_facts_and_embeddings, doc) for doc in docs]

        # To catch/print exceptions
        for future in futures:
            try:
                future.result()  # This will raise exceptions if any occurred during function execution
            except Exception as e:
                print(f"An error occurred: {e}")

    print("Done")
    
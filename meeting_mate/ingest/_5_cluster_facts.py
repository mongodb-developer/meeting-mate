from meeting_mate.mongo.mongo import PLAIN_INSTANCE as mongo
from collections import defaultdict
from sklearn.preprocessing import normalize
from sklearn.cluster import AgglomerativeClustering, KMeans
from math import ceil
from meeting_mate.llm.models import EmbeddingModels, EmbeddingsModel
from argparse import ArgumentParser

group_facts_pipeline = [
    {
        '$match': {
            '$expr': {
                '$eq': [
                    '$doc_id', '$$doc_id'
                ]
            }
        }
    }, {
        '$group': {
            '_id': {
                'doc_id': '$doc_id', 
                'user_id': '$user_id'
            }, 
            'facts': {
                '$push': '$facts'
            }, 
            'embeddings': {
                '$push': '$embeddings'
            }, 
            'organizations': {
                '$push': '$organizations'
            }, 
            'people': {
                '$push': '$people'
            }
        }
    }, {
        '$project': {
            'facts': {
                '$reduce': {
                    'input': '$facts', 
                    'initialValue': [], 
                    'in': {
                        '$concatArrays': [
                            '$$value', '$$this'
                        ]
                    }
                }
            }, 
            'embeddings': {
                '$reduce': {
                    'input': '$embeddings', 
                    'initialValue': [], 
                    'in': {
                        '$concatArrays': [
                            '$$value', '$$this'
                        ]
                    }
                }
            }, 
            'organizations': {
                '$setUnion': {
                    '$reduce': {
                        'input': '$organizations', 
                        'initialValue': [], 
                        'in': {
                            '$concatArrays': [
                                '$$value', '$$this'
                            ]
                        }
                    }
                }
            }
        }
    }
]

def cluster_facts(documentId:str):
    print("Clustering facts for document", documentId)
    results = mongo.db["chunks"].aggregate(group_facts_pipeline, let={"doc_id": documentId}).next()
    
    clusters = agglomerative(results["facts"], results["embeddings"])
    clusters = [[fact["doc"] for fact in cluster] for cluster in clusters]
    
    result_docs = []

    for cluster in clusters:
        facts = "\n".join([f"* {fact}" for fact in cluster])

        doc = {
            "doc_id": documentId,
            "user_id": results["_id"]["user_id"],
            "organizations": results["organizations"],
            "facts": facts
        }

        result = mongo.db["facts"].insert_one(doc)
        doc.update({"_id": result.inserted_id})
        result_docs.append(doc)

    return result_docs

def kmeans(values, embeddings, n_clusters=2):
    # normalize embeddings
    norm_embeddings = normalize(embeddings)

    # cluster embeddings
    clustering = KMeans(n_clusters=n_clusters, random_state=0, n_init='auto')
    clustering.fit(norm_embeddings)

    clusters = defaultdict(list)
    for index, (label, doc) in enumerate(zip(clustering.labels_, values)):
        clusters[str(label)].append({"doc": doc, "embedding": embeddings[index]})

    return clusters

def agglomerative(values, embeddings, distance_threshold=0.5, max_size=10):
    # normalize embeddings
    norm_embeddings = normalize(embeddings)

    # cluster embeddings
    clustering = AgglomerativeClustering(metric='cosine', linkage='average', distance_threshold=distance_threshold, n_clusters=None)
    clustering.fit(norm_embeddings)

    clusters = defaultdict(list)

    for index, (label, doc) in enumerate(zip(clustering.labels_, values)):        
        clusters[str(label)].append({"doc": doc, "embedding": embeddings[index]})

    clusters = [cluster for cluster in clusters.values()]

    # if a cluster is too large, split it
    for cluster in clusters:
        if len(cluster) > max_size:
            # determine the number of subclusters
            n_subclusters = ceil(len(cluster) / max_size)
            subclusters = kmeans([doc["doc"] for doc in cluster], 
                                        [doc["embedding"] for doc in cluster],
                                        n_clusters=n_subclusters)
            subclusters = [subcluster for subcluster in subclusters.values()]
            clusters.remove(cluster)
            clusters.extend(subclusters)
            
    # just the docs, no embeddings
    return clusters

model = EmbeddingsModel(EmbeddingModels.NOMIC_EMBED_TEXT_1_5)
def add_embeddings(doc):
    embeddings = model.invoke(doc["facts"], purpose="embed_facts", user=doc["user_id"])[0]
    mongo.db["facts"].update_one({"_id": doc["_id"]}, {"$set": {"embedding": embeddings}})

def cluster_and_embed(doc_id: str):
    # remove old facts
    mongo.db["facts"].delete_many({"doc_id": doc_id})
    
    # cluster facts
    docs = cluster_facts(doc_id)

    # re-embed facts
    for doc in docs:
        add_embeddings(doc)

    pass

to_cluster_query = [
    {
        '$group': {
            '_id': '$doc_id'
        }
    }, {
        '$lookup': {
            'from': 'facts', 
            'localField': '_id', 
            'foreignField': 'doc_id', 
            'as': 'result'
        }
    }, {
        '$match': {
            'result': []
        }
    }
]
to_delete_query = [
    {
        '$group': {
            '_id': '$doc_id'
        }
    }, {
        '$lookup': {
            'from': 'chunks', 
            'localField': '_id', 
            'foreignField': 'doc_id', 
            'as': 'result'
        }
    }, {
        '$match': {
            'result': []
        }
    }
]

if __name__ == "__main__":
    args = ArgumentParser()
    args.add_argument("-f", "--force", action="store_true", required=False, default=False, help="Force recluster all facts")

    args = args.parse_args()

    if args.force:
        print("Forcing recluster of all facts")
        mongo.db["facts"].delete_many({})
        # basically everything
        tocluster = mongo.db["chunks"].aggregate([{
            '$group': {
                '_id': '$doc_id'
            }
        }])
    else:
        # figure out which ones to delete
        to_delete = list(mongo.db["facts"].aggregate(to_delete_query))
        print(f"Deleting {len(to_delete)} facts docs")
        for fact in to_delete:
            mongo.db["facts"].delete_many({"doc_id": fact["_id"]})

        # figure out which ones to cluster
        tocluster = mongo.db["chunks"].aggregate(to_cluster_query)

    for doc in tocluster:
        cluster_and_embed(doc["_id"])

    print("Done clustering facts")
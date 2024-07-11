from typing import Any
from meeting_mate.mongo.mongo import PLAIN_INSTANCE as mongo
from meeting_mate.llm.models import EmbeddingsModel
import json
from pydantic import BaseModel, Field

class Retriever(BaseModel):
    embeddingModel: EmbeddingsModel = Field(..., description="The embedding model to use for the retriever")
    vector_index: str
    text_index:str
    colname: str
    coll: Any = Field(init=False, default="", description="The collection to retrieve from")
    text_field:str
    embedding_field: str

    class Config:
        arbitrary_types_allowed = True

    def model_post_init(self, __context: Any):
        self.coll = mongo.get_db()[self.colname]

    def facet(self, user:str, field:str):
        pipeline = [
            {
                '$searchMeta': {
                    'index': 'text_index', 
                    'facet': {
                        'operator': {
                            'equals': {
                                'path': 'user_id', 
                                'value': user
                            }
                        }, 
                        'facets': {
                            'facet': {
                                'type': 'string', 
                                'path': field
                            }
                        }
                    }
                }
            }
        ]

        results = list(self.coll.aggregate(pipeline))
        values = [facet["_id"] for facet in results[0]["facet"]["facet"]["buckets"]]
        return values

    

    def vector_search(self, query: str, *, purpose:str, user:str, top_k: int = 5, numCandidates: int = 100, orgs: list[str]):
        queryVector, = self.embeddingModel.invoke(query, purpose=purpose, user=user)

        filter = {
            "organizations": {
                "$in": orgs
            },
            "user_id": user
        }

        pipeline = [
            {
                '$vectorSearch': {
                    'index': self.vector_index,
                    'path': self.embedding_field,
                    'queryVector': queryVector,
                    'limit': top_k,
                    'numCandidates': numCandidates,
                    'filter' : filter
                }
            },
            {
                '$addFields': {
                    'score': {
                        '$meta': 'vectorSearchScore'
                    }
                }
            },
            {
                '$project': {
                    f"{self.embedding_field}": 0,
                }
            }
        ]

        results = list(self.coll.aggregate(pipeline))
        return results, pipeline
    
    def keyword_search(self, query: str, *, user:str, top_k: int = 10, orgs: list[str]):
        filterStage = [
            {
                'equals': {
                    'path': 'user_id',
                    'value': user
                }
            }
        ]

        orgs_clauses = [{"equals": {"path": "organizations", "value": org}} for org in orgs]
        filterStage.append({"compound":{"should":orgs_clauses}})

        pipeline = [
            {
                "$search": {
                    "index": self.text_index,
                    "compound": {
                        "filter": filterStage,
                        "must": {
                            "text": {
                                "query": query,
                                "path": self.text_field
                            }
                        }
                    }
                }, 
            },
            {
                '$addFields': {
                    'score': {
                        '$meta': 'searchScore'
                    }
                }
            },
            {
                "$project": {
                    "embedding": 0
                }
            }
        ]

        results = list(self.coll.aggregate(pipeline))

        return results, pipeline
    
    def hybrid_search(self, query: str, *, purpose:str, user:str, top_k: int = 5, numCandidates: int = 100, orgs: list[str]):
        keyword_results, kv_pipeline = self.keyword_search(query, user=user, top_k=numCandidates, orgs=orgs)
        vector_results, vec_pipeline = self.vector_search(query, purpose=purpose, user=user, top_k=top_k, numCandidates=numCandidates, orgs=orgs)

        # normalize keyword scores to the 0-1 range
        max_score = max([result["score"] for result in keyword_results])
        keyword_scores = {}
        for result in keyword_results:
            keyword_scores[result["_id"]] = result["score"] / max_score

        # apply keyword boost to vector results
        for result in vector_results:
            result["score"] = result["score"]*0.7 + keyword_scores.get(result["_id"], 0)*0.3

        return vector_results, (kv_pipeline, vec_pipeline)
    
if __name__ == "__main__":
    from meeting_mate.llm.models import EmbeddingModels
    model = EmbeddingsModel(EmbeddingModels.NOMIC_EMBED_TEXT_1_5)
    retr = Retriever(embeddingModel=model, 
                     vector_index="vector_index", 
                     text_index="text", 
                     colname="facts", 
                     embedding_field="embeddings", 
                     text_field="facts")

    print(retr.keyword_search("postgres", user="106936893069932136953"))
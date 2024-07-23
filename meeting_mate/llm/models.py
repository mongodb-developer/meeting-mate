from datetime import datetime
from typing import Any, Dict, List, Sequence, Union
from meeting_mate.mongo.mongo import INSTANCE as mongo
from langchain_fireworks import ChatFireworks
from openai import OpenAI
import os
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage
from enum import Enum
from pydantic.v1 import BaseModel, Field, root_validator, validator
from langchain_core.embeddings import Embeddings
from dotenv import load_dotenv

load_dotenv(override=True)

class ModelProvider(Enum):
    FIREWORKS = "fireworks"

class ModelType(Enum):
    CHAT = "chat"
    EMBEDDING = "embedding"

class ChatModels(Enum):
    MIXTRAL_8x22B_INSTRUCT = {
        'id': "mixtral-8x22b-instruct",
        'provider': ModelProvider.FIREWORKS,
        'type': ModelType.CHAT,
        'price' : {
             'input': 0.9, 
             'completion': 0.9
        }}
    LLAMA3_8B_INSTRUCT = {
        'id': "llama-v3-8b-instruct",
        'provider': ModelProvider.FIREWORKS,
        'type': ModelType.CHAT,
        'price' : {
             'input': 0.2, 
             'completion': 0.2
        }
    }
    
class EmbeddingModels(Enum):
    NOMIC_EMBED_TEXT_1_5 = {
        'id': "nomic-ai/nomic-embed-text-v1.5",
        'provider': ModelProvider.FIREWORKS,
        'type': ModelType.EMBEDDING,
        'price' : {
             'input': 0.008
        }
    },
    MXBAI_LARGE = {
        'id': "mixedbread-ai/mxbai-embed-large-v1",
        'provider': ModelProvider.FIREWORKS,
        'type': ModelType.EMBEDDING,
        'price' : {
             'input': 0.016
        }
    }

def _calculate_costs(metadata, model: ChatModels)->float:
    usage = None
    if "usage" in metadata:
        usage = metadata["usage"]
    elif "token_usage" in metadata:
        usage = metadata["token_usage"]
    elif "token_count" in metadata:
        usage = metadata["token_count"]
    else:
        raise Exception("No usage found in response meta")
    
    input = usage["prompt_tokens"] if "prompt_tokens" in usage else usage["input_tokens"]
    input = model.value["price"]["input"] * input / 1000000

    if(model.value["type"] == ModelType.EMBEDDING):
        return input
    
    output = usage["completion_tokens"] if "completion_tokens" in usage else usage["output_tokens"]
    output = model.value["price"]["completion"] * output / 1000000

    return input + output

def _getChat(model: ChatModels, temperature:float, max_tokens:int):
    if model.value["provider"] == ModelProvider.FIREWORKS:
        fireworks_key = os.environ.get("fireworks_api_key")
        if not fireworks_key:
            raise Exception("No fireworks api key found")
        return ChatFireworks(fireworks_api_key=fireworks_key, model=f"accounts/fireworks/models/{model.value['id']}")
    else:
        raise Exception("Invalid provider")


class EmbeddingsModel():
    def __init__(self, model: EmbeddingModels):
        self._model = model
        
        if model.value["provider"] == ModelProvider.FIREWORKS:
            fireworks_key = os.environ.get("fireworks_api_key")
            if not fireworks_key:
                raise Exception("No fireworks api key found")
            
            self._client = OpenAI(
                base_url = "https://api.fireworks.ai/inference/v1",
                api_key=fireworks_key,
            )
            self._embed = self._embed_openai
        else:
            raise Exception("Invalid provider")
        
    def _embed_openai(self, input: Union[str, Sequence[str]]):
        response = self._client.embeddings.create(
            model=self._model.value["id"],
            input=input)
        
        embeddings = [data.embedding for data in response.data]
        metadata = {'usage': response.usage.model_dump()}

        return embeddings, metadata
    
    def invoke(self, input: Union[str, Sequence[str]], *,  purpose: str, user: str) -> Sequence[Sequence[float]]:
        start = datetime.now()
        results, metadata = self._embed(input)
        took = (datetime.now() - start).total_seconds()

        costs = _calculate_costs(metadata, self._model)

        mongo.db["protocol"].insert_one({
            "user": user,
            "timestamp":datetime.now(),
            "model": self._model.value["id"],
            "inputs": 1 if isinstance(input, str) else len(input),
            "took":took,
            "cost": costs,
            "task": purpose
        })

        return results
    
class LangchainEmbeddingsModel(BaseModel, Embeddings):
    model: EmbeddingsModel = Field(default=None, required=True)
    user: str
    purpose: str

    class Config:
        arbitrary_types_allowed = True

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.invoke(texts, purpose=self.purpose, user=self.user)
    
    def embed_query(self, text: str) -> List[float]:
        return self.model.invoke(text, purpose=self.purpose, user=self.user)[0]

class ChatModel:
    def __init__(self, model: ChatModels, temperature=0.7, max_tokens=2000):
        self._model = model
        self._chat = _getChat(model, temperature, max_tokens)

    def _toSerializable(self, input: LanguageModelInput):
        if isinstance(input, str):
            return input
        elif isinstance(input, BaseMessage ):
            return input.to_json()
        elif isinstance(input, Sequence):
            if all(isinstance(i, BaseMessage) for i in input):
                return [i.to_json() for i in input]
            else:
                raise Exception("Invalid input")
        else:
            raise Exception("Invalid input")
    
    def invoke(self, input: LanguageModelInput, purpose: str, user: str):
        start = datetime.now()
        chat_response = self._chat.invoke(input)            
        took = (datetime.now() - start).total_seconds()

        costs = _calculate_costs(chat_response.response_metadata, self._model)

        mongo.db["protocol"].insert_one({
            "user": user,
            "timestamp":datetime.now(),
            "model": self._model.value["id"],
            "chat": {
                "input": self._toSerializable(input),
                "response":chat_response.content,
                "metadata":chat_response.response_metadata
            },
            "took":took,
            "cost": costs,
            "task": purpose
        })

        return chat_response.content
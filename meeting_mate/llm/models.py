from datetime import datetime
from typing import Sequence, Union
from meeting_mate.mongo.mongo import INSTANCE as mongo
from openai import OpenAI
from enum import Enum
from dotenv import dotenv_values
from meeting_mate.llm.prompts import BaseMessage, UserMessage, SystemMessage

config = dotenv_values(".env")

class ModelProvider(Enum):
    FIREWORKS = "fireworks"
    OPENAI = "openai"

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

    GPT_4O_MINI = {
        'id': "gpt-4-turbo",
        "provider": ModelProvider.OPENAI,
        "type": ModelType.CHAT,
        "price": {
            "input": 0.15,
            "completion": 0.6
        }
    }

    GPT_4O = {
        'id': "gpt-4o",
        "provider": ModelProvider.OPENAI,
        "type": ModelType.CHAT,
        "price": {
            "input": 5,
            "completion": 15
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
    }
    MXBAI_LARGE = {
        'id': "mixedbread-ai/mxbai-embed-large-v1",
        'provider': ModelProvider.FIREWORKS,
        'type': ModelType.EMBEDDING,
        'price' : {
             'input': 0.016
        }
    }

def _calculate_costs(usage, model: ChatModels)->float:
    if usage is None:
        raise Exception("No usage found in response meta")
    
    input = usage["prompt_tokens"] if "prompt_tokens" in usage else usage["input_tokens"]
    input = model.value["price"]["input"] * input / 1000000

    if(model.value["type"] == ModelType.EMBEDDING):
        return input
    
    output = usage["completion_tokens"] if "completion_tokens" in usage else usage["output_tokens"]
    output = model.value["price"]["completion"] * output / 1000000

    return input + output



def _getChat(model: ChatModels, temperature:float, max_tokens:int)->OpenAI:
    if model.value["provider"] == ModelProvider.FIREWORKS:
        fireworks_key = config.get("fireworks_api_key")
        if not fireworks_key:
            raise Exception("No fireworks api key found")
        
        return OpenAI(api_key=fireworks_key, base_url="https://api.fireworks.ai/inference/v1")

    elif model.value["provider"] == ModelProvider.OPENAI:
        openai_key = config.get("openai_api_key")
        if not openai_key:
            raise Exception("No openai api key found")
        
        return OpenAI(openai_api_key=openai_key)
        
    else:
        raise Exception("Invalid provider")


class EmbeddingsModel():
    def __init__(self, model: EmbeddingModels):
        self._model = model
        
        if model.value["provider"] == ModelProvider.FIREWORKS:
            fireworks_key = config.get("fireworks_api_key")
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

        costs = _calculate_costs(metadata["usage"], self._model)

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
       
class ChatModel:
    def __init__(self, model: ChatModels, temperature=0.7, max_tokens=2000):
        self._model = model

        if(model.value["provider"] == ModelProvider.FIREWORKS):
            self._model_id = f"accounts/fireworks/models/{model.value['id']}"
        else:
            self._model_id = model.value["id"]

        self._chat = _getChat(model, temperature, max_tokens).chat
    
    def invoke(self, input: Sequence[BaseMessage], purpose: str, user: str):
        messages = [message.model_dump() for message in input]

        start = datetime.now()
        chat_response = self._chat.completions.create(messages=messages, model=self._model_id)
        took = (datetime.now() - start).total_seconds()

        costs = _calculate_costs(chat_response.usage.model_dump(), self._model)

        mongo.db["protocol"].insert_one({
            "user": user,
            "timestamp":datetime.now(),
            "model": self._model.value["id"],
            "chat": {
                "input": messages,
                "response": chat_response.model_dump(),
            },
            "took":took,
            "cost": costs,
            "task": purpose
        })

        return chat_response.choices[0].message.content
    
    async def invoke_async(self, input: Sequence[BaseMessage], purpose: str, user: str):
        messages = [message.model_dump() for message in input]
        start = datetime.now()

        chunks = []
        for resp in self._chat.completions.create(messages=messages, model=self._model_id, stream=True):
            chunks.append(resp.model_dump())
            yield resp.choices[0].delta.content

        took = (datetime.now() - start).total_seconds()
        last_chunk = chunks[-1]
        costs = _calculate_costs(last_chunk["usage"], self._model)

        mongo.db["protocol"].insert_one({
            "user": user,
            "timestamp":datetime.now(),
            "model": self._model.value["id"],
            "chat": {
                "input": messages,
                "response": chunks,
            },
            "took":took,
            "cost": costs,
            "task": purpose
        })

    def invoke_streaming(self, input: Sequence[BaseMessage], purpose: str, user: str):
        messages = [message.model_dump() for message in input]
        start = datetime.now()

        chunks = []
        for resp in self._chat.completions.create(messages=messages, model=self._model_id, stream=True):
            chunks.append(resp.model_dump())
            content = resp.choices[0].delta.content
            if content is not None:
                yield content

        took = (datetime.now() - start).total_seconds()
        last_chunk = chunks[-1]
        costs = _calculate_costs(last_chunk["usage"], self._model)

        mongo.db["protocol"].insert_one({
            "user": user,
            "timestamp":datetime.now(),
            "model": self._model.value["id"],
            "chat": {
                "input": messages,
                "response": chunks,
            },
            "took":took,
            "cost": costs,
            "task": purpose
        })
    
def testGeneration():
    chat = ChatModel(ChatModels.LLAMA3_8B_INSTRUCT)
    messages = [SystemMessage(content="You're a moody, passive-aggressive personal assistant. You're not very good at your job and you're being a dick about it."),
                UserMessage(content = "Tell me very short story about a young wizard. Make it a looong story with multiple exciting chapters!")]
    
    for chunk in chat.invoke_streaming(input=messages, purpose="test", user="root"):
        print(chunk, sep='', end='')
    print("\n")

if __name__ == "__main__":
    # test completions
    testGeneration()
import json
from time import time
from meeting_mate.mongo.mongo import INSTANCE as mongo
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from langchain_fireworks import ChatFireworks
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_mistralai.chat_models import ChatMistralAI
from enum import Enum
from jsonschema import validate
from meeting_mate.llm.prompts import Templates, facts_answer_schema
from concurrent.futures import ThreadPoolExecutor
from argparse import ArgumentParser

env_values = dotenv_values()
openai_key = env_values.get("openai_api_key")
fireworks_key = env_values.get("fireworks_api_key")
claude_key = env_values.get("anthropic_api_key")
cohere_key = env_values.get("cohere_api_key")
mistral_key = env_values.get("mistral_api_key")

source_collection = mongo.db.chunks
target_collection = mongo.db.benchmark

class ModelHost(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    FIREWORKS = "fireworks"
    COHERE = "cohere"
    MISTRAL = "mistral"

CHAT_MODELS = {
    ModelHost.ANTHROPIC: [
        {"name": "claude-3-opus-20240229", "price": {"input": 15, "output": 75}},
        {"name": "claude-3-sonnet-20240229", "price": {"input": 3, "output": 15}},
        {"name": "claude-3-5-sonnet-20240620", "price": {"input": 3, "output": 15}},
    ],
    ModelHost.COHERE: [
        {"name": "command-r-plus", "price": {"input": 3, "output": 15}},
        {"name": "command-r", "price": {"input": 0.5, "output": 1.5}},
        {"name": "command-nightly", "price": {"input": 15, "output": 15}},
        {"name": "command-light-nightly", "price": {"input": 0.3, "output": 0.6}}
    ],
    ModelHost.FIREWORKS: [
        {"name": "mixtral-8x22b-instruct", "price": {"input": 0.9, "output": 0.9}},
        {"name": "mixtral-8x7b-instruct", "price": {"input": 0.5, "output": 0.5}},  # Updated price
        {"name": "llama-v3-70b-instruct", "price": {"input": 0.9, "output": 0.9}},
        {"name": "hermes-2-pro-mistral-7b", "price": {"input": 0.9, "output": 0.9}},
        {"name": "llama-v3-70b-instruct-hf", "price": {"input": 0.9, "output": 0.9}},
        {"name": "mistral-7b-instruct-4k", "price": {"input": 0.2, "output": 0.2}},
        {"name": "mixtral-8x22b-instruct-hf", "price": {"input": 0.9, "output": 0.9}},
        {"name": "mixtral-8x7b-instruct-hf", "price": {"input": 0.5, "output": 0.5}},  # Updated price
        {"name": "nous-hermes-2-mixtral-8x7b-dpo-fp8", "price": {"input": 0.5, "output": 0.5}}  # Updated price
    ],
    ModelHost.OPENAI: [
        {"name": "gpt-4o", "price": {"input": 5, "output": 15}},
        {"name": "gpt-4-turbo", "price": {"input": 10, "output": 30}}
    ],
    ModelHost.MISTRAL: [
        {"name": "mistral-small-2402", "price": {"input": 0.98, "output": 3.04}},
        {"name": "mistral-medium", "price": {"input": 2.71, "output": 8.15}},
        {"name": "mistral-large-2402", "price": {"input": 4.13, "output": 11.3}}
    ]
}

def getChat(model_name:str, model_host:ModelHost, temperature=0.7, max_tokens=2000)->BaseChatModel:
    if model_host == ModelHost.ANTHROPIC:
        return ChatAnthropic(api_key=claude_key, model=model_name, temperature=temperature, max_tokens=max_tokens)
    elif model_host == ModelHost.OPENAI:
        return ChatOpenAI(api_key=openai_key, model=model_name, temperature=temperature, max_tokens=max_tokens)
    elif model_host == ModelHost.FIREWORKS:
        return ChatFireworks(api_key=fireworks_key, model=f"accounts/fireworks/models/{model_name}",temperature=temperature, max_tokens=max_tokens)
    elif model_host == ModelHost.COHERE:
        return ChatCohere(cohere_api_key=cohere_key, model=model_name, temperature=temperature, max_tokens=max_tokens)
    elif model_host == ModelHost.MISTRAL:
        return ChatMistralAI(api_key=mistral_key, model=model_name, temperature=temperature, max_tokens=max_tokens)

# token_usage will have prompt_tokens, completion_tokens (output) and total_tokens
# prices are per million tokens
def calculate_cost(model, token_usage):    
    price = model["price"]
    input = token_usage["prompt_tokens"] if "prompt_tokens" in token_usage else token_usage["input_tokens"]
    output = token_usage["completion_tokens"] if "completion_tokens" in token_usage else token_usage["output_tokens"]
    
    return (input*price["input"] + output*price["output"])/1000000

def get_usage(metadata):
    usage = None
    if "usage" in metadata:
        usage = metadata["usage"]
    elif "token_usage" in metadata:
        usage = metadata["token_usage"]
    elif "token_count" in metadata:
        usage = metadata["token_count"]
    else:
        raise Exception("No usage found in response meta")
    
    return usage

def getResponse(chat:BaseChatModel, system_message:SystemMessage, human_message:HumanMessage):
    start = time()
    
    response = chat.invoke([system_message, human_message])
    
    end = time()
    response_time = end - start

    content = response.content
    asJson = json.loads(content)
    validate(asJson, facts_answer_schema)

    token_usage = get_usage(response.response_metadata)

    return asJson, response_time, token_usage

def process_chunk(chunk):
    markdown = chunk.get("markdown")
    
    print(f"Entering chunk {chunk["_id"]} of doc {chunk["doc_id"]}")

    system_message = SystemMessage(content=Templates.extract_facts_system_prompt())
    
    context = Templates.extract_facts_context_prompt(markdown)
    human_message = HumanMessage(content=context)

    # for each key in CHAT_MODELS, we will run the models
    for host in CHAT_MODELS:
        for model in CHAT_MODELS[host]:
            # check if the model has already been processed
            count = target_collection.count_documents({"chunk_id":chunk["_id"], "model": model["name"], "host": host.value})
            if count > 0:
                print(f"Skipping {model['name']} on {host} as it has already been processed")
                continue

            print(f"Processing with {model['name']} on {host}")
            chat = getChat(model["name"], host)

            resultDoc = {**chunk, "chunk_id":chunk["_id"], "model": model["name"], "host": host.value}
            #remove _id to avoid duplicate key error
            resultDoc.pop("_id")

            attempt = 1            
            while(attempt<=5):
                try:
                    asJson, response_time, tokenUsage = getResponse(chat, system_message, human_message)
                    cost = calculate_cost(model, tokenUsage)
                    resultDoc.update({"result": asJson, "response_time": response_time, "cost": cost, "attempts": attempt})

                    target_collection.insert_one(resultDoc)

                    break
                except Exception as e:
                    print(f"Error with {model['name']} on {host} on attempt {attempt}")
                    print(e)
                    attempt += 1

args = ArgumentParser()
args.add_argument("docs",nargs="+", help="Sample size to process", type=str)
args.add_argument("-d","--delete", help="Delete all documents in the benchmark collection", action="store_true", required=False)

if __name__ == "__main__":
    #sample_docs = {"doc_id": "1CFx8g-OsnU3L-KJOE1Oe1jMwuvA6ZpGQqOn0nnhY0qA"}

    args = args.parse_args()
    
    if args.delete:
        # clear the benchmark collection?
        print("Clearing the benchmark collection...")
        target_collection.delete_many({})

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = []

        for id in args.docs:
            sample_docs = {"doc_id": id}
            for chunk in source_collection.find(sample_docs):
                futures.append(executor.submit(process_chunk, chunk))

        # Wait for all futures to finish
        for future in futures:
            future.result()

    print("Done!")
    SystemExit(0)
from typing import List
import streamlit as st
from meeting_mate.mongo.mongo import PLAIN_INSTANCE as mongo
from meeting_mate.llm.models import ChatModel, ChatModels
from st_combobox import st_combobox
import meeting_mate.mongo.retrieval as retrieval
from meeting_mate.llm.models import EmbeddingModels, EmbeddingsModel
from langchain_core.messages import HumanMessage, SystemMessage
from meeting_mate.llm.prompts import Templates
import os
import json
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(layout="wide")

def list_users():
    users = list(mongo.db["users"].find({},{"_id":0, "sub":1,"given_name":1}))
    return users

user_id = None
def user_select(callback):
    print(callback)
    return

head = st.empty()
headleft, headright = head.columns(2)

user_selection = headleft.selectbox("Select user", list_users(), format_func=lambda x: x["given_name"], on_change=user_select)
user_id = user_selection["sub"]

def search_customers(search_term: str) -> List[str]:
    pipeline = [
        {
            '$search': {
                'index': 'text_index', 
                'autocomplete': {
                    'path': 'organizations', 
                    'query': search_term
                }, 
                'highlight': {
                    'path': 'organizations'
                }
            }
        }, {
            '$project': {
                'highlights': {
                    '$meta': 'searchHighlights'
                }
            }
        }, {
            '$unwind': '$highlights'
        }
    ]
    
    results = list(mongo.db.facts.aggregate(pipeline))
    values = set()
    for result in results:
        text = " ".join([text["value"] for text in result["highlights"]["texts"]])
        values.add(text)

    return values

def submit_customer(customer: str):
    print(f"Selected customer: {customer}")
    return

if 'customers' not in st.session_state:
    st.session_state['customers'] = set()

with headright:
    selected_customer = st_combobox(search_customers, label="Search customers", key="search_customers", placeholder="Search customers...", clear_on_submit=True)
    if selected_customer:
        st.session_state.customers.add(selected_customer)

model = EmbeddingsModel(EmbeddingModels.NOMIC_EMBED_TEXT_1_5)
retriever = retrieval.Retriever(colname="facts", embeddingModel=model, vector_index="vector_index", embedding_field="embedding", text_index="text_index", text_field="facts", user_field="user_id")

def generate_answer(search_results: list, question: str):
    model = ChatModel(ChatModels.LLAMA3_8B_INSTRUCT)

    facts = [result["facts"] for result in search_results]
    context = Templates.build_qa_context(facts, question)

    prompt = [SystemMessage(Templates.answer_question_system_prompt()), HumanMessage(context)]
    
    response = model.invoke(prompt, "Document Q&A in streamlit", user_id)
    return response

if not st.session_state.customers:
    st.markdown("Please select customers to proceed.")
else:
    st.markdown(f"Selected customers: {', '.join(st.session_state.customers)}")

    if question := st.chat_input("Ask a question about the selected customers"):
        left, right = st.columns(2)
        results, pipe = retriever.vector_search(question, purpose="Document Q&A in streamlit", top_k=10, user=user_id, orgs=list(st.session_state.customers))        

        if not results or len(results) == 0:
            st.write(pipe)
            st.error("No results found.")
            st.stop()

        scores = [str(round(result["score"], 2)) for result in results]
        tabs = left.tabs(scores)

        for ix, item in enumerate(results):
            result = results[ix]
            facts = result["facts"]
            with tabs[ix]:
                st.write(facts)

        right.markdown(f"Question: {question}")

        st.spinner("Generating answer...")    
        answer = generate_answer(results, question)        
        right.markdown(answer)
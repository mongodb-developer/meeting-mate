import json
import streamlit as st
from meeting_mate.mongo.mongo import INSTANCE as mongo
import plotly.express as px
import pandas as pd

st.set_page_config(layout="wide")

all_docs = list(mongo.db["benchmark"].find({},{"chunk_id":1, "doc_id":1, "host":1,"model":1,"cost":1,"response_time":1, "result":1, "_id":0}))

df = pd.DataFrame(all_docs)
df['cost'] = df['cost'] * 1000  # Multiply cost by 1000

with st.expander("Costs and Response times"):
    left, right = st.columns(2)

    # Sort the DataFrame by cost in ascending order
    df_avg = df.groupby(['host','model']).agg({'cost':'mean', 'response_time':'mean'}).reset_index().sort_values(by='cost', ascending=True)

    # Create Plotly figures with models as x-axis and hosts for coloring
    fig_cost = px.bar(df_avg, x='model', y='cost', color='host', labels={'cost': 'Cost (x1000)', 'model': 'Model', 'host': 'Host'}, title="Mean cost for 1000 summaries per Model by Host")
    fig_cost.update_xaxes(categoryorder='total ascending')
    fig_cost.update_layout(height=800)

    fig_response_time = px.bar(df_avg, x='model', y='response_time', color='host', labels={'response_time': 'Response Time (seconds)', 'model': 'Model', 'host': 'Host'}, title="Response Time per Model by Host")
    fig_response_time.update_xaxes(categoryorder='total ascending')
    fig_response_time.update_layout(height=800)    

    # Display the figures in Streamlit, in the appropriate columns
    left.plotly_chart(fig_cost, use_container_width=True, height=800)
    right.plotly_chart(fig_response_time, use_container_width=True)

st.divider()

def to_html_list(arr: list):
    if arr is None:
        return ""
    if type(arr) is str:
        return arr
    return f"""<ul><li>{'</li><li>'.join(arr)}</li></ul>"""

def process_facts(facts: dict):
    summary = ""
    if facts.get('people'):
        summary += f"<b>People</b>{to_html_list(facts['people'])}"
    if facts.get('relationships'):
        summary += f"<b>relationships</b>{to_html_list(facts['relationships'])}"
    if facts.get('timeline'):
        summary += f"<b>Timeline</b>{to_html_list(facts['timeline'])}"
    if facts.get('misc'):
        summary += f"<b>Miscellaneous</b>{to_html_list(facts['misc'])}"
    if facts.get('tasks'):
        summary += f"<b>Tasks</b>{to_html_list(facts['tasks'])}"

    return summary

# Group the DataFrame by 'doc_id' and iterate over each group
for chunk_id, df_group in df.groupby('chunk_id'):
    doc = mongo.db["benchmark"].find_one({"chunk_id": chunk_id},{"markdown":1,"results":1})    

    with st.expander("Content"):
        st.markdown(doc["markdown"])

    with st.expander("Results", expanded=True):
        df_group = df_group[["host","model","cost","response_time","result"]]
        
        df_group['people'] = df_group['result'].apply(lambda x: to_html_list(x.get('people')) if isinstance(x, dict) else None)
        df_group['organizations'] = df_group['result'].apply(lambda x: to_html_list(x.get('organizations')) if isinstance(x, dict) else None)
        df_group['summary'] = df_group['result'].apply(lambda x: process_facts(x.get('summary')) if isinstance(x, dict) else None)

        df_group.drop(columns=['result'], inplace=True)

        df_group = df_group.sort_values(by='host')

        def toMarkdown(value):
            # is the value a json array?
            if isinstance(value, list):
                return ("\n* ".join(value)).strip()

        st.write(df_group.to_html(escape=False, index=False), unsafe_allow_html=True)

    st.divider()
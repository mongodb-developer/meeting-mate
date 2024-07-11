
import json
from jsonschema import validate
from datetime import datetime

facts_answer_schema = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "people": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "drescription": "List of people mentioned in the meeting minutes, with their full names whenever possible."
        },
        "organizations": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of organizations mentioned in the meeting minutes."
        },
        "summary": {
            "type": "object",
            "properties": {
                "people": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Information about people mentioned in the meeting minutes. Include their backgrounds, skills, positions, roles, stances, and views."
                },
                "relationships": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Information about relationships between people, companies, or other entities. For example: who reports to whom, who is part of which team? Who is whose boss or PO?"
                },
                "timeline": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Any captured information on deadlines, timelines, scheduling"
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Captured tasks and to do's from the meeting minutes. Always preface with TODO: "
                },
                "misc": {                    
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Information that doesn't fit into the above categories. For example: company background, businness case, technology or business-related information."
                }
            },
            "description": "Summarized information extracted from the meeting minutes. Use markdown formatting in string fields to make the output more readable and separate facts into bullet points.",
            "required": ["misc"]
        }
    },
    "required": ["summary"]
}

example = {
    "people": ["John Doe", "Jane Doe", "Bruce Wayne"],
    "organizations": ["Acme Inc.", "MongoDB"],
    "summary": {
        "people": ["John Doe (Acme Inc.) is a software engineer with 5 years of experience.","Jane Doe is a product manager with a background in marketing."],
        "relationships": [
                            "John Doe (Acme Inc.) works for Acme Inc.",
                            "Jane Doe (Acme Inc.) is the product owner of the MongoDB project.",
                            "Bruce Wayne works for Wayne Enterprises.",
                            "Bruce Wayne (Wayne Enterprises) is the product owner of the MongoDB project.",
                            "John Doe (Acme Inc.) reports to Bob Ross, but Jane Doe is the functional manager & lead of John Doe."],
        "timeline": ["From 2024-03-07: Acme Inc is planning a go-live in 6 months.", "From 2024-05-05: The architecture needs to be finalized by end of summer."],
        "misc": [
                    "Acme Inc. is a software company that specializes in cloud-based solutions.",
                    "Acme Inc is working on a new product to summarize meeting minutes automatically.",
                    "John Doe (Acme Inc.) suggests evaluating MongoDB Atlas as a back-end system to quickly launch the app"],
        "tasks": ["TODO from 2024-01-05: John Doe (Acme Inc.) will come back with a list of requirements for the new product.", "TODO from 2024-01-05: Steve Bobs (Wayne Enterprises s.A.) will set up a meeting with the MongoDB team."]
    }
}

# make sure my example doesn't suck
validate(example, facts_answer_schema)

system_prompt = f"""You're a summarization assistant. For the meeting minutes provided by USER, summarize the following things in your own words, with a focus on readability and explicit knowledge:

- Participants with their full names
- All information about people learned in this meeting - focus specifically on their backgrounds & skills, positions and roles, stances and views
- Relationships - any connections between people, companies, groups of pepple - NO OTHER INFO HERE
- Timelines and tasks. ALWAYS preface with the current date whenever points in time are mentioned. Each provided document has a date!!!
- All miscellaneous information, including company background, team set-up, anything related to technology or business
- Captured tasks and to do's

Reply using the following Json schema:
{json.dumps(example, indent=4)}

Follow the schema strictly and don't introduce additional properties.
"""

class Templates:
    @staticmethod
    def extract_facts_system_prompt()->str: 
        return system_prompt

    @staticmethod
    def extract_facts_context_prompt(context)->str:
        return f"""Meeting minutes:
            {context}
            -------------
            Extract facts from meeting minutes according to your instructions and follow the specified JSON schema.
            Try and extract a high number of facts, not leaving out ANY information. 
            Reply with JSON object only with no preambles. Don't quote the JSON object!!!"""
    
    @staticmethod
    def answer_question_system_prompt()->str:
        return """You are a question answering assistant. You will be provided with a set of facts extracted from documents, followed by a question.
                    Answer the question based on the provided facts. Disregard any facts or statements irrelevant to the question. Feel free to answer in markdown!"""
    
    

    @staticmethod
    def build_qa_context(snippets:list[str], question:str)->str:        
        adherence_reminder = f"""Please adhere to the specified JSON schema. Do not introduce additional properties. 
        Make sure to include the current (or prospective) date when talking about timelines, todos etc.
        Answer in markdown, using lists where necessary and emphasizing entities. Do not include information the user did not ask for.
        The current local time is {datetime.now().isoformat()}."""

        context = f"Facts:\n"
        context+= "\n".join(snippets)
        context+= f"""
        -------------
        Question: {question}
        -------------
        {adherence_reminder}
        """
        return context
    
    def mermaid_graph_system_prompt()->str:
        return """You are a chart creation assistant. USER will provide you with text input and a question.
    You will then create a mermaid "graph" (non directional) chart based on the text input and the question.
    Strictly adhere to the mermaid language syntax, including 
    - not introducing whitespaces and special characters outside of labels
    - not using special characters in node names or labels
    - labels should be enclosed in quotation marks - avoid double quote errors!
    - avoiding duplicate nodes for the same entity
    - use subgraphs sparingly and only when necessary to group unrelated entities
    
    Here's an example graph of the movie pump fiction as a reference:
    

    graph 
    subgraph Criminals
        M0["<b>Marsellus Wallace</b><br/>Crime Boss<br/><i>Ruthless</i>"]
        V0["<b>Vincent Vega</b><br/>Hitman<br/><i>Loyal, Philosophical</i>"]
        J0["<b>Jules Winnfield</b><br/>Hitman<br/><i>Reflective, Redeemed</i>"]
        B0["<b>Butch Coolidge</b><br/>Boxer<br/><i>Determined, Resourceful</i>"]
    end
    
    subgraph Associates
        M1["<b>Mia Wallace</b><br/>Wife<br/><i>Charming, Troubled</i>"]
        L0["<b>Lance</b><br/>Drug Dealer<br/><i>Laid-back</i>"]        
    end

    P0["<b>Pumpkin (Ringo)</b><br/>Thief<br/><i>Opportunistic</i>"]
    H0["<b>Honey Bunny (Yolanda)</b><br/>Thief<br/><i>Volatile</i>"]

    M0 -->|"Boss of"| V0
    M0 -->|"Boss of"| J0
    M0 -->|"Husband to"| M1
    M0 -->|"Employer of"| B0
    
    V0 -->|"Hitman partner with"| J0
    V0 -->|"Assigned to entertain"| M1
    J0 -.->|"Almost robbed by"| P0
    J0 -.->|"Almost robbed by"| H0
    
    V0 -->|"Buys from"| L0
    J0 -->|"Buys from"| L0
    
    B0 -->|"Attempts to betray"| M0
    P0 -->|"Partner in crime with"| H0
    H0 -->|"Partner in crime with"| P0

    Add information to nodes to understand the entity.
    Always add descriptive labels to edges.
    
    Respond with the chart definition ONLY and nothing else. Don't escape it in any way.
    """


    def build_mermaid_graph_context(snippets:list[str], question:str)->str:
        adherence_reminder = f"""Make sure to produce a valid mermaid chart paying attention to the provided instructions.
        Respond with the chart definition ONLY and nothing else."""

        context = f"Facts:\n"
        context+= "\n".join(snippets)
        context+= f"""
        -------------
        Question: {question}
        -------------
        {adherence_reminder}
        """
        return context
    
    




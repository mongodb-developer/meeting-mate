# Meeting-minutes RAG
With our final content collection set up, we can make use of keyword search and vector search.

## Configuring search

Navigate to your Atlas database and to the "Atlas Search" tab of your cluster. We need to create two indexes:
- A text search index called "text_index"
- A vector search index called "vector_index"

Search configuration:
```
{
  "mappings": {
    "dynamic": true,
    "fields":{
      "organizations":[
        {
          "type": "autocomplete",
          "tokenization": "edgeGram",
          "minGrams": 1,
          "maxGrams": 10
        },
        {
          "type": "token"
        }
      ],
      "user_id":[
        {
          "type": "token"
        }
      ]
    }
  }
}
```

Vector search configuration:
```
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 768,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "organizations"
    },
    {
      "type": "filter",
      "path": "user_id"
    }
  ]
}
```

## Running the remo app

Start the search demo app by running
```
python -m streamlit run meeting_mate/rag/streamlit_rag.py
```
This should launch our demo app in the browser
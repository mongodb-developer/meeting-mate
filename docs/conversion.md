# Document pre-processing

We're going to make use of several techiques to solve key problems of our dataset. Namely:
- Structure-based chunking. We will exploit the google meeting notes template, as well as HTML structure to split documents into individual "meeting minutes" subdocuments/chunks
- Fact extraction. Rather than embedding & search documents as is, we will prompt our model to extract a series of atomic statements. This will allow us to cluster & merge all "facts" on a given topic to conver questions than span many documents at once and account for information sprinkled throughout many meeting notes.
- Entity extraction. Documents don't necessarily have a 1:1 mapping and we need to have the ability to filter down to the specific account at hand in order to locate the right information. We will prompt the model to extract people and company names to demonstrate this
- Clustering. We will use clustering on embeddings of individual facts in order to group them semantically. This should result in chuks covering specific topics

## Chunking

Run `_3_chunk_docs.py` to process all documents that have an `html` field and haven't been chunked yet (as denoted by a boolean flag). This is done through BeautifulSoup as a few simple element filters.

We further calculate checksums on the markdown content of each chunk. We run a deletion query to remove all chunks with a checksum mismatch (namely all deprecated - modified or deleted) chunks. Finally, we filter out all existing chunks and insert the delta. This way, we establish an efficient update mechanism for chunk to minimize redundant LLM calls.

## Fact extraction

Run `_4_extract_facts.py` to process all new chunks. This script iterates over all chunks and for each chunk
- Prompts an LLM to extract information according to a JSON schema and instructions
- The JSON schema and prompts are found in [prompts.py](../meeting_mate/llm/prompts.py)
- Calls an embeddings endpoint to retrieve embeddings for each fact

While calculating a high number of embeddings might sound counterintuitive at first, keep in mind that embedding models are also priced per 1M tokens. Meaning in terms of spend (and speed as well, mostly), there's no difference between a single large chunk and the same chunk cut up into multiple facts.

## Clustering

Run `_5_cluster_facts.py` to re-cluster facts of changed documents. This will use the scikit-learn library to cluster embeddings. The resulting clusters are then concatenated and embedded, resulting in the final "facts" collection. This is what we will search on.
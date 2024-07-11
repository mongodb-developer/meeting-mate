from collections import defaultdict
from sklearn.preprocessing import normalize
from sklearn.cluster import AgglomerativeClustering


def cluster_embeddings(values, embeddings, distance_threshold=0.5):
    # normalize embeddings
    norm_embeddings = normalize(embeddings)

    # cluster embeddings
    clustering = AgglomerativeClustering(n_clusters=None, metric='cosine', linkage='average', distance_threshold=distance_threshold)
    clustering.fit(norm_embeddings)

    clusters = defaultdict(list)

    for label, doc in zip(clustering.labels_, values):
        clusters[str(label)].append(doc)

    return clusters
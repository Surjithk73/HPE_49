"""
FewShotRetriever for QueryCraft
ChromaDB-backed retriever for dynamic few-shot injection (RAG for Prompts).
"""
import hashlib
import sys
import os
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import chromadb

try:
    from pipeline import embeddings
except ImportError:
    import embeddings  # type: ignore


class FewShotRetriever:
    """
    Retrieves the most semantically relevant few-shot examples for a given query.
    Uses ChromaDB and the shared sentence-transformers embedding model.
    """

    COLLECTION_NAME = "querycraft_few_shots"

    def __init__(self, examples: List[Dict], persist_path: str = "cache_store"):
        """
        Initialize the few-shot retriever.

        Args:
            examples: List of example dictionaries (query, sql) to load.
            persist_path: Directory for ChromaDB persistent storage.
        """
        os.makedirs(persist_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_path)
        
        # We recreate the collection on startup to ensure it matches the 
        # provided examples list (which might have been edited in yaml).
        try:
            self.client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass

        self.collection = self.client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )

        embeddings.start_loading()
        self._load_examples(examples)

    @property
    def model(self):
        return embeddings.get()

    @property
    def is_model_ready(self) -> bool:
        return embeddings.is_ready()

    def _load_examples(self, examples: List[Dict]) -> None:
        """Embed and load examples into ChromaDB."""
        if not examples:
            print("[FewShotRetriever] No examples provided to load.")
            return

        print(f"[FewShotRetriever] Waiting for model to load {len(examples)} examples...")
        
        # Wait for the model to be ready since this happens during startup
        import time
        for _ in range(120): # 120 seconds timeout
            if self.is_model_ready:
                break
            time.sleep(1)
            
        if not self.is_model_ready:
            print("[FewShotRetriever] Warning: Model failed to load in time.")
            return

        queries = []
        metadatas = []
        ids = []

        for i, ex in enumerate(examples):
            query = ex.get('query', '').strip()
            sql = ex.get('sql', '').strip()
            if not query or not sql:
                continue

            doc_id = f"fs_{i}_{hashlib.md5(query.encode()).hexdigest()[:8]}"
            queries.append(query)
            metadatas.append({"sql": sql, "domain": ex.get('domain', 'multi')})
            ids.append(doc_id)

        if queries:
            print(f"[FewShotRetriever] Embedding {len(queries)} examples...")
            query_embeddings = self.model.encode(queries, normalize_embeddings=True).tolist()
            self.collection.add(
                ids=ids,
                embeddings=query_embeddings,
                metadatas=metadatas,
                documents=queries
            )
            print(f"[FewShotRetriever] Loaded {len(queries)} examples into ChromaDB.")

    def get_top_k(self, query: str, k: int = 3, domain: str = None) -> List[Dict]:
        """
        Retrieve the top K most relevant few-shot examples for the query.

        Uses two-stage retrieval when domain is provided:
          1. Filter ChromaDB to examples whose domain matches.
          2. Rank the filtered subset by cosine similarity and take top k.
        For 'multi' domain or if domain is None, searches across all examples.
        If a domain filter returns fewer than k results, fills remaining
        slots from a full similarity search (no domain filter).

        Args:
            query:  The normalized user query.
            k:      Number of examples to retrieve.
            domain: Domain label from the normalizer (e.g. 'cpu', 'disc').

        Returns:
            List of dicts with 'query' and 'sql'.
        """
        if not self.is_model_ready or self.collection.count() == 0:
            return []

        try:
            query_embedding = self.model.encode([query], normalize_embeddings=True).tolist()

            # Stage 1: try domain-filtered retrieval
            domain_results = []
            if domain and domain != 'multi':
                try:
                    filtered = self.collection.query(
                        query_embeddings=query_embedding,
                        n_results=k,
                        where={"domain": domain},
                        include=["metadatas", "documents"]
                    )
                    if filtered["ids"] and filtered["ids"][0]:
                        for i in range(len(filtered["ids"][0])):
                            domain_results.append({
                                "query": filtered["documents"][0][i],
                                "sql": filtered["metadatas"][0][i].get("sql", "")
                            })
                except Exception:
                    pass  # domain filter failed (e.g. no entries for this domain), fall through

            if len(domain_results) >= k:
                return domain_results[:k]

            # Stage 2: fill remaining slots from full search
            already_seen = {ex["query"] for ex in domain_results}
            need = k - len(domain_results)
            fetch = k + len(already_seen) + 2  # over-fetch to account for duplicates

            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=min(fetch, self.collection.count()),
                include=["metadatas", "documents"]
            )

            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    doc = results["documents"][0][i]
                    if doc in already_seen:
                        continue
                    domain_results.append({
                        "query": doc,
                        "sql": results["metadatas"][0][i].get("sql", "")
                    })
                    already_seen.add(doc)
                    if len(domain_results) >= k:
                        break

            return domain_results[:k]

        except Exception as e:
            print(f"[FewShotRetriever] Error retrieving examples: {e}")
            return []

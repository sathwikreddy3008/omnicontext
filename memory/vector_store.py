import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from core.config import DB_DIR, EMBEDDING_MODEL, COLLECTION_NAME
import uuid
from datetime import datetime

class MemoryStore:
    def __init__(self):
        # Initialize the ChromaDB local client with telemetry turned OFF
        self.client = chromadb.PersistentClient(
            path=str(DB_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # We use a fast, local embedding model
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
        
        # Get or create our memory collection
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )

    def add_memory(self, text: str, source: str = "clipboard", doc_id: str = None):
        """Adds a piece of text to the vector store."""
        if not text or len(text.strip()) == 0:
            return False

        if not doc_id:
            doc_id = str(uuid.uuid4())
            
        timestamp = datetime.now().isoformat()

        # upsert allows us to overwrite if the ID already exists (useful for file re-saves)
        self.collection.upsert(
            documents=[text],
            metadatas=[{"source": source, "timestamp": timestamp}],
            ids=[doc_id]
        )
        return True

    def search_memories(self, query: str, n_results: int = 3):
        """Searches for similar memories based on a query."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Format the results into a clean string
        memories = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i, doc in enumerate(results['documents'][0]):
                meta = results['metadatas'][0][i]
                time_str = meta.get('timestamp', 'unknown time')
                memories.append(f"[{time_str}] (Source: {meta.get('source')}): {doc}")
                
        return "\n\n".join(memories)

    def get_count(self) -> int:
        """Returns the number of items in the vector store."""
        return self.collection.count()

    def clear_collection(self):
        """Deletes all items from the collection."""
        # The easiest way to clear is to delete the collection and recreate it
        self.client.delete_collection(name=COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )

    def list_memories(self, limit: int = 50, offset: int = 0):
        """Returns a list of stored memories with their metadata."""
        try:
            results = self.collection.get(
                limit=limit,
                offset=offset,
                include=["documents", "metadatas"]
            )
            
            memories = []
            if results and results['ids']:
                for i, doc_id in enumerate(results['ids']):
                    doc = results['documents'][i] if results['documents'] else ""
                    doc = doc.strip()  # Remove leading/trailing whitespace
                    meta = results['metadatas'][i] if results['metadatas'] else {}
                    memories.append({
                        "id": doc_id,
                        "text": doc[:300] + "..." if len(doc) > 300 else doc,
                        "full_text": doc,
                        "source": meta.get("source", "unknown"),
                        "timestamp": meta.get("timestamp", "unknown")
                    })
            return memories
        except Exception:
            return []

    def delete_memory(self, doc_id: str):
        """Deletes a single memory by its ID."""
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def search_memories_detailed(self, query: str, n_results: int = 10):
        """Search memories and return structured results (for browser UI)."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        memories = []
        if results['documents'] and len(results['documents'][0]) > 0:
            for i, doc in enumerate(results['documents'][0]):
                doc = doc.strip()  # Remove leading/trailing whitespace
                meta = results['metadatas'][0][i]
                distance = results['distances'][0][i] if results.get('distances') else 0
                memories.append({
                    "id": results['ids'][0][i],
                    "text": doc[:300] + "..." if len(doc) > 300 else doc,
                    "full_text": doc,
                    "source": meta.get("source", "unknown"),
                    "timestamp": meta.get("timestamp", "unknown"),
                    "relevance": round(1 - distance, 3)
                })
        return memories

# ABOUTME: Semantic memory system using ChromaDB and OpenAI embeddings
# ABOUTME: Provides time-aware vector search for home automation message history
import os
import structlog
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from openai import OpenAI


class SemanticMemory:
    def __init__(
        self,
        collection_name: str = "houseagent_memory",
        persist_directory: str = "./chroma_data",
        time_window_hours: int = 2,
    ):
        self.logger = structlog.getLogger(__name__)
        self.time_window_hours = time_window_hours

        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )

        # Initialize OpenAI client for embeddings
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        self.logger.info(
            f"Initialized semantic memory with {self.collection.count()} existing entries"
        )

    def _get_embedding(self, text: str) -> List[float]:
        """Get OpenAI embedding for text"""
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Failed to get embedding: {e}")
            raise

    def _naturalize_message(self, message: Dict) -> str:
        """Convert message dict to natural language string"""
        # If it's already a string (like assistant responses), return as-is
        if isinstance(message, str):
            return message

        # Handle different message formats
        if "messages" in message:
            # Batch message format
            messages = message["messages"]
            if isinstance(messages, list):
                # Convert list of sensor readings to natural language
                parts = []
                for msg in messages:
                    parts.append(self._naturalize_single_message(msg))
                return " ".join(parts)
            else:
                return self._naturalize_single_message(messages)
        else:
            return self._naturalize_single_message(message)

    def _naturalize_single_message(self, msg: Dict) -> str:
        """Convert single sensor message to natural language"""
        if isinstance(msg, str):
            return msg

        # Common sensor patterns
        if "sensor" in msg:
            sensor_type = msg.get("sensor", "unknown")
            value = msg.get("value", msg.get("detected", "unknown"))
            room = msg.get("room", "unknown location")
            return f"{room} {sensor_type}: {value}"

        # Generic fallback - stringify the dict
        return str(msg)

    def add_message(
        self,
        message: Dict,
        role: str = "user",
        message_id: Optional[str] = None,
    ):
        """Add a message to semantic memory with timestamp"""
        try:
            now = datetime.now()
            timestamp_unix = now.timestamp()  # Unix timestamp for ChromaDB filtering
            timestamp_iso = now.isoformat()  # ISO string for display

            # Convert to natural language
            natural_text = self._naturalize_message(message)

            # Get embedding (may raise exception)
            embedding = self._get_embedding(natural_text)

            # Generate unique ID if not provided (use timestamp + microseconds)
            if message_id is None:
                message_id = f"{role}_{int(timestamp_unix * 1000000)}"

            # Store in ChromaDB (timestamp as float for filtering)
            self.collection.add(
                embeddings=[embedding],
                documents=[natural_text],
                ids=[message_id],
                metadatas=[
                    {
                        "timestamp": timestamp_unix,  # Store as Unix timestamp
                        "timestamp_iso": timestamp_iso,  # Also store ISO for display
                        "role": role,
                        "raw_message": str(message),
                    }
                ],
            )

            self.logger.debug(
                f"Added {role} message to semantic memory",
                message_id=message_id,
                text_preview=natural_text[:100],
            )
        except Exception as e:
            self.logger.error(f"Failed to add message to semantic memory: {e}")
            # Don't re-raise - semantic memory is optional, shouldn't crash the agent

    def search(
        self,
        query: str,
        n_results: int = 5,
        time_window_hours: Optional[int] = None,
    ) -> List[Dict]:
        """
        Search for semantically similar messages within time window

        Args:
            query: Natural language query
            n_results: Maximum number of results to return
            time_window_hours: Hours to look back (default: use instance default)

        Returns:
            List of matching messages with metadata (empty list on error)
        """
        try:
            if time_window_hours is None:
                time_window_hours = self.time_window_hours

            # Calculate time cutoff (Unix timestamp)
            cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
            cutoff_unix = cutoff_time.timestamp()

            # Get query embedding (may raise exception)
            query_embedding = self._get_embedding(query)

            # Search with time filter (using Unix timestamp)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where={"timestamp": {"$gte": cutoff_unix}},
            )

            # Format results
            formatted_results = []
            if results["documents"] and len(results["documents"][0]) > 0:
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append(
                        {
                            "content": doc,
                            "metadata": results["metadatas"][0][i],
                            "distance": results["distances"][0][i]
                            if "distances" in results
                            else None,
                        }
                    )

            self.logger.debug(
                f"Semantic search found {len(formatted_results)} results",
                query=query,
                time_window_hours=time_window_hours,
            )

            return formatted_results
        except Exception as e:
            self.logger.error(f"Semantic search failed: {e}")
            return []  # Return empty list on error

    def get_recent_context(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """Get all recent messages within time window (chronological order)"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        cutoff_unix = cutoff_time.timestamp()

        results = self.collection.get(
            where={"timestamp": {"$gte": cutoff_unix}},
            limit=limit,
        )

        # Format and sort by timestamp
        messages = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"]):
                messages.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][i],
                    }
                )

            # Sort by timestamp
            messages.sort(key=lambda x: x["metadata"]["timestamp"])

        return messages

    def clear_old_messages(self, days: int = 7):
        """Clear messages older than specified days"""
        cutoff_time = datetime.now() - timedelta(days=days)
        cutoff_unix = cutoff_time.timestamp()

        # Get old message IDs
        results = self.collection.get(
            where={"timestamp": {"$lt": cutoff_unix}},
        )

        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            self.logger.info(
                f"Cleared {len(results['ids'])} messages older than {days} days"
            )

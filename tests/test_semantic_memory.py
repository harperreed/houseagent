"""Tests for SemanticMemory class"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from houseagent.semantic_memory import SemanticMemory
import tempfile
import shutil


@pytest.fixture
def temp_chroma_dir():
    """Create temporary directory for ChromaDB"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings API"""
    with patch("houseagent.semantic_memory.OpenAI") as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock embedding response
        mock_embedding = [0.1] * 1536  # text-embedding-3-small dimensions
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=mock_embedding)]
        mock_client.embeddings.create.return_value = mock_response

        yield mock_client


class TestSemanticMemory:
    """Test suite for SemanticMemory"""

    def test_initialization(self, temp_chroma_dir, mock_openai_embeddings):
        """Test SemanticMemory initializes correctly"""
        memory = SemanticMemory(
            collection_name="test_collection",
            persist_directory=temp_chroma_dir,
            time_window_hours=2,
        )

        assert memory.time_window_hours == 2
        assert memory.collection.name == "test_collection"
        assert memory.collection.count() == 0

    def test_naturalize_single_sensor_message(
        self, temp_chroma_dir, mock_openai_embeddings
    ):
        """Test converting sensor message to natural language"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        message = {"sensor": "temperature", "value": 72, "room": "kitchen"}
        natural = memory._naturalize_single_message(message)

        assert "kitchen" in natural
        assert "temperature" in natural
        assert "72" in natural

    def test_naturalize_batch_message(self, temp_chroma_dir, mock_openai_embeddings):
        """Test converting batch message format"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        message = {
            "messages": [
                {"sensor": "temp", "value": 72, "room": "bedroom"},
                {"sensor": "humidity", "value": 45, "room": "bedroom"},
            ]
        }
        natural = memory._naturalize_message(message)

        assert "bedroom" in natural
        assert "temp" in natural
        assert "humidity" in natural

    def test_naturalize_string_message(self, temp_chroma_dir, mock_openai_embeddings):
        """Test handling string messages (assistant responses)"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        message = "The temperature is comfortable at 72 degrees."
        natural = memory._naturalize_message(message)

        assert natural == message

    def test_add_message_user(self, temp_chroma_dir, mock_openai_embeddings):
        """Test adding user message to memory"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        message = {"sensor": "temperature", "value": 72, "room": "kitchen"}
        memory.add_message(message, role="user")

        assert memory.collection.count() == 1

        # Verify OpenAI embedding was called
        mock_openai_embeddings.embeddings.create.assert_called_once()
        call_args = mock_openai_embeddings.embeddings.create.call_args
        assert call_args[1]["model"] == "text-embedding-3-small"

    def test_add_message_assistant(self, temp_chroma_dir, mock_openai_embeddings):
        """Test adding assistant response to memory"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        response = "The kitchen temperature is 72 degrees, which is comfortable."
        memory.add_message(response, role="assistant", message_id="test_response_1")

        assert memory.collection.count() == 1

        # Verify message stored correctly
        results = memory.collection.get(ids=["test_response_1"])
        assert len(results["documents"]) == 1
        assert results["metadatas"][0]["role"] == "assistant"

    def test_add_multiple_messages(self, temp_chroma_dir, mock_openai_embeddings):
        """Test adding multiple messages"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        messages = [
            {"sensor": "temp", "value": 70, "room": "bedroom"},
            {"sensor": "temp", "value": 72, "room": "kitchen"},
            {"sensor": "motion", "detected": True, "room": "hallway"},
        ]

        for i, msg in enumerate(messages):
            memory.add_message(msg, role="user", message_id=f"msg_{i}")

        assert memory.collection.count() == 3

    @patch("houseagent.semantic_memory.datetime")
    def test_search_with_time_window(
        self, mock_datetime, temp_chroma_dir, mock_openai_embeddings
    ):
        """Test searching with time window filter"""
        # Mock current time
        now = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        memory = SemanticMemory(persist_directory=temp_chroma_dir, time_window_hours=2)

        # Add messages with timestamps (Unix timestamps)
        recent_time_unix = (now - timedelta(minutes=30)).timestamp()

        # Mock collection query to test time filtering
        memory.collection.query = MagicMock(
            return_value={
                "documents": [["Recent message"]],
                "metadatas": [[{"timestamp": recent_time_unix, "role": "user"}]],
                "distances": [[0.1]],
            }
        )

        results = memory.search("temperature kitchen", n_results=5)

        # Verify time filter was applied
        call_args = memory.collection.query.call_args
        assert "where" in call_args[1]
        assert "timestamp" in call_args[1]["where"]
        assert "$gte" in call_args[1]["where"]["timestamp"]
        # Verify it's a numeric timestamp
        assert isinstance(call_args[1]["where"]["timestamp"]["$gte"], float)

        assert len(results) == 1
        assert results[0]["content"] == "Recent message"

    def test_search_no_results(self, temp_chroma_dir, mock_openai_embeddings):
        """Test search with no matching results"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        results = memory.search("nonexistent query")

        assert len(results) == 0

    @patch("houseagent.semantic_memory.datetime")
    def test_get_recent_context(
        self, mock_datetime, temp_chroma_dir, mock_openai_embeddings
    ):
        """Test retrieving recent context chronologically"""
        now = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        # Mock collection.get (Unix timestamps)
        time1_unix = (now - timedelta(hours=2)).timestamp()
        time2_unix = (now - timedelta(hours=1)).timestamp()
        time3_unix = (now - timedelta(minutes=30)).timestamp()

        memory.collection.get = MagicMock(
            return_value={
                "documents": ["Message 3", "Message 1", "Message 2"],
                "metadatas": [
                    {"timestamp": time3_unix, "role": "user"},
                    {"timestamp": time1_unix, "role": "user"},
                    {"timestamp": time2_unix, "role": "user"},
                ],
            }
        )

        results = memory.get_recent_context(hours=24, limit=50)

        # Verify results are sorted by timestamp
        assert len(results) == 3
        assert results[0]["metadata"]["timestamp"] == time1_unix
        assert results[1]["metadata"]["timestamp"] == time2_unix
        assert results[2]["metadata"]["timestamp"] == time3_unix

    @patch("houseagent.semantic_memory.datetime")
    def test_clear_old_messages(
        self, mock_datetime, temp_chroma_dir, mock_openai_embeddings
    ):
        """Test clearing messages older than specified days"""
        now = datetime(2024, 1, 10, 12, 0, 0)
        mock_datetime.now.return_value = now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        # Mock collection.get to return old message IDs
        old_ids = ["old_msg_1", "old_msg_2", "old_msg_3"]
        memory.collection.get = MagicMock(
            return_value={"ids": old_ids, "documents": [], "metadatas": []}
        )
        memory.collection.delete = MagicMock()

        memory.clear_old_messages(days=7)

        # Verify delete was called with old IDs
        memory.collection.delete.assert_called_once_with(ids=old_ids)

    def test_persistence_across_instances(
        self, temp_chroma_dir, mock_openai_embeddings
    ):
        """Test that messages persist across SemanticMemory instances"""
        # First instance - add messages
        memory1 = SemanticMemory(
            collection_name="persistent_test", persist_directory=temp_chroma_dir
        )
        memory1.add_message(
            {"sensor": "temp", "value": 72}, role="user", message_id="persist_msg_1"
        )
        assert memory1.collection.count() == 1

        # Second instance - should load existing data
        memory2 = SemanticMemory(
            collection_name="persistent_test", persist_directory=temp_chroma_dir
        )
        assert memory2.collection.count() == 1

        # Verify the message is accessible
        results = memory2.collection.get(ids=["persist_msg_1"])
        assert len(results["documents"]) == 1

    def test_custom_time_window(self, temp_chroma_dir, mock_openai_embeddings):
        """Test custom time window configuration"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir, time_window_hours=6)

        assert memory.time_window_hours == 6

    def test_message_id_generation(self, temp_chroma_dir, mock_openai_embeddings):
        """Test automatic message ID generation"""
        memory = SemanticMemory(persist_directory=temp_chroma_dir)

        message = {"sensor": "temp", "value": 72}
        memory.add_message(message, role="user")  # No message_id provided

        # Verify a message was added with generated ID
        assert memory.collection.count() == 1

        # Verify ID format (should contain role and timestamp)
        results = memory.collection.get()
        generated_id = results["ids"][0]
        assert "user_" in generated_id

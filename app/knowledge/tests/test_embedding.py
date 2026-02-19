"""Tests for embedding providers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.embedding import (
    LocalEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


async def test_openai_provider_single_batch():
    """OpenAI provider should embed a batch of texts."""
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1, 0.2, 0.3]

    mock_response = MagicMock()
    mock_response.data = [mock_embedding, mock_embedding]

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    provider = OpenAIEmbeddingProvider(model="text-embedding-3-large", api_key="test-key", dim=1024)
    provider._client = mock_client

    result = await provider.embed(["text1", "text2"])
    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    mock_client.embeddings.create.assert_called_once()


async def test_openai_provider_batch_splitting():
    """OpenAI provider should split >100 texts into batches."""
    mock_embedding = MagicMock()
    mock_embedding.embedding = [0.1]

    mock_response = MagicMock()
    mock_response.data = [mock_embedding] * 100

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)

    provider = OpenAIEmbeddingProvider(model="test", api_key="key", dim=1)
    provider._client = mock_client

    texts = [f"text{i}" for i in range(150)]

    mock_response_small = MagicMock()
    mock_response_small.data = [mock_embedding] * 50
    mock_client.embeddings.create = AsyncMock(side_effect=[mock_response, mock_response_small])

    result = await provider.embed(texts)
    assert len(result) == 150
    assert mock_client.embeddings.create.call_count == 2


async def test_local_provider_uses_to_thread():
    """Local provider should run encoding in asyncio.to_thread."""
    import numpy as np

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])

    provider = LocalEmbeddingProvider(model_name="test-model", dim=2)
    provider._model = mock_model

    with patch("app.knowledge.embedding.asyncio") as mock_asyncio:
        mock_asyncio.to_thread = AsyncMock(return_value=np.array([[0.1, 0.2], [0.3, 0.4]]))
        result = await provider.embed(["a", "b"])

    assert len(result) == 2
    mock_asyncio.to_thread.assert_called_once()


def test_get_provider_openai():
    """Factory should return OpenAI provider for 'openai' setting."""
    settings = MagicMock()
    settings.embedding_provider = "openai"
    settings.embedding_model = "text-embedding-3-large"
    settings.embedding_api_key = "key"
    settings.embedding_dimension = 1024
    settings.embedding_base_url = None

    provider = get_embedding_provider(settings)
    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_get_provider_local():
    """Factory should return Local provider for 'local' setting."""
    settings = MagicMock()
    settings.embedding_provider = "local"
    settings.embedding_model = "BAAI/bge-m3"
    settings.embedding_dimension = 1024

    provider = get_embedding_provider(settings)
    assert isinstance(provider, LocalEmbeddingProvider)


def test_get_provider_unknown_raises():
    """Factory should raise ValueError for unknown provider."""
    settings = MagicMock()
    settings.embedding_provider = "nonexistent"

    with pytest.raises(ValueError, match="Unknown embedding provider"):
        get_embedding_provider(settings)


def test_openai_provider_dimension():
    """OpenAI provider should report correct dimension."""
    provider = OpenAIEmbeddingProvider(model="test", api_key="key", dim=768)
    assert provider.dimension == 768


def test_local_provider_dimension():
    """Local provider should report correct dimension."""
    provider = LocalEmbeddingProvider(model_name="test", dim=1024)
    assert provider.dimension == 1024

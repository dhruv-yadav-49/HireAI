import tiktoken
from typing import Any
from app.models.enums import ChunkStrategy


class ChunkingService:
    """Chunks documents into sliding or fixed token-bounded paragraphs using tiktoken."""

    @classmethod
    def chunk_text(
        cls,
        text: str,
        strategy: ChunkStrategy = ChunkStrategy.SLIDING,
        chunk_size: int = 512,
        chunk_overlap: int = 128
    ) -> list[dict[str, Any]]:
        """Splits input text into sub-segments according to specified token boundaries."""
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode(text)
        
        chunks = []
        num_tokens = len(tokens)
        
        if num_tokens == 0:
            return []
            
        step = chunk_size - chunk_overlap
        if strategy == ChunkStrategy.FIXED:
            step = chunk_size
            
        chunk_index = 0
        start = 0
        while start < num_tokens:
            end = min(start + chunk_size, num_tokens)
            chunk_tokens = tokens[start:end]
            chunk_content = encoding.decode(chunk_tokens)
            
            # Simple paragraph indexing estimation
            chunks.append({
                "chunk_index": chunk_index,
                "content": chunk_content,
                "token_count": len(chunk_tokens),
                "metadata": {
                    "strategy": strategy.value,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap if strategy == ChunkStrategy.SLIDING else 0
                }
            })
            chunk_index += 1
            start += step
            
        return chunks

import re
from typing import Any


class Reranker:
    """Performs lexical and semantic score calculations to rank retrieved chunks."""

    @classmethod
    def rerank(cls, query: str, results: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
        # Compute lexical matching using Jaccard index
        query_words = set(re.findall(r"\w+", query.lower()))
        
        for r in results:
            content_words = set(re.findall(r"\w+", r["content"].lower()))
            if not query_words or not content_words:
                lexical_score = 0.0
            else:
                lexical_score = len(query_words.intersection(content_words)) / len(query_words.union(content_words))

            r["rerank_score"] = lexical_score
            # Hybrid combined score
            r["final_score"] = 0.7 * r["normalized_score"] + 0.3 * lexical_score
            
        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:limit]

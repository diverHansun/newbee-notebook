"""Elasticsearch search tool for Chat mode.

This module provides an Elasticsearch-based search tool that can be used
as a FunctionTool in the Chat mode FunctionAgent. It performs BM25 keyword
search against the document index.
"""

import os
from typing import Optional, List
from llama_index.core.tools import FunctionTool, ToolMetadata
from elasticsearch import Elasticsearch


def _es_search(
    query: str,
    index_name: str = "medimind_docs",
    max_results: int = 5,
    es_url: Optional[str] = None,
) -> str:
    """Search documents using Elasticsearch BM25.
    
    Args:
        query: Search query string
        index_name: Elasticsearch index name
        max_results: Maximum number of results to return
        es_url: Elasticsearch URL (defaults to ELASTICSEARCH_URL env var)
        
    Returns:
        Formatted search results as a string
    """
    es_url = es_url or os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    
    # Create Elasticsearch client
    es = Elasticsearch([es_url])
    
    # Check if index exists
    if not es.indices.exists(index=index_name):
        return f"Index '{index_name}' does not exist. Please index documents first."
    
    # Execute BM25 search
    response = es.search(
        index=index_name,
        body={
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["content", "text", "title^2"],
                    "type": "best_fields",
                }
            },
            "size": max_results,
            "_source": ["content", "text", "metadata"],
        },
    )
    
    # Format results
    hits = response.get("hits", {}).get("hits", [])
    
    if not hits:
        return "No documents found matching your query in the knowledge base."
    
    results = []
    for i, hit in enumerate(hits, 1):
        score = hit.get("_score", 0)
        source = hit.get("_source", {})
        
        # Get content from various possible fields
        content = (
            source.get("content") or 
            source.get("text") or 
            "No content available"
        )
        
        # Truncate long content
        if len(content) > 500:
            content = content[:500] + "..."
        
        metadata = source.get("metadata", {})
        doc_title = metadata.get("title", metadata.get("file_name", f"Document {i}"))
        
        results.append(
            f"{i}. [{doc_title}] (score: {score:.2f})\n"
            f"   {content}\n"
        )
    
    return "\n".join(results)


class ElasticsearchSearchTool:
    """Elasticsearch search tool wrapper.
    
    This class provides a clean interface for creating Elasticsearch search
    tools that can be used with LlamaIndex agents.
    
    Attributes:
        index_name: Name of the Elasticsearch index
        max_results: Maximum number of search results
        es_url: Elasticsearch URL
        _tool: Internal FunctionTool instance
    """
    
    def __init__(
        self,
        index_name: str = "medimind_docs",
        max_results: int = 5,
        es_url: Optional[str] = None,
    ):
        """Initialize ElasticsearchSearchTool.
        
        Args:
            index_name: Elasticsearch index name (default: medimind_docs)
            max_results: Maximum number of results (default: 5)
            es_url: Elasticsearch URL (default: from env)
        """
        self.index_name = index_name
        self.max_results = max_results
        self.es_url = es_url or os.getenv(
            "ELASTICSEARCH_URL", "http://localhost:9200"
        )
        self._tool: Optional[FunctionTool] = None
    
    def get_tool(self) -> FunctionTool:
        """Get the FunctionTool instance for use with agents.
        
        Returns:
            FunctionTool instance configured for ES search
        """
        if self._tool is None:
            self._tool = FunctionTool.from_defaults(
                fn=self._search,
                name="knowledge_base_search",
                description=(
                    "Search the internal knowledge base for medical documents, "
                    "guidelines, and reference materials. Use this when the user "
                    "asks about specific medical topics, treatments, or conditions "
                    "that might be covered in the indexed documents. "
                    "Input should be a search query string."
                ),
            )
        return self._tool
    
    def _search(self, query: str) -> str:
        """Internal search method.
        
        Args:
            query: Search query string
            
        Returns:
            Formatted search results
        """
        return _es_search(
            query=query,
            index_name=self.index_name,
            max_results=self.max_results,
            es_url=self.es_url,
        )


def build_es_search_tool(
    index_name: str = "medimind_docs",
    max_results: int = 5,
    es_url: Optional[str] = None,
) -> FunctionTool:
    """Build an Elasticsearch search FunctionTool.
    
    Convenience function for quickly creating an ES search tool.
    
    Args:
        index_name: Elasticsearch index name
        max_results: Maximum number of results
        es_url: Elasticsearch URL
        
    Returns:
        FunctionTool configured for ES BM25 search
        
    Example:
        >>> tool = build_es_search_tool(index_name="my_docs")
        >>> agent = FunctionAgent(tools=[tool], llm=llm)
    """
    return ElasticsearchSearchTool(
        index_name=index_name,
        max_results=max_results,
        es_url=es_url,
    ).get_tool()



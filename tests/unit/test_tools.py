"""Unit tests for tools layer components.

This test file validates:
- TavilySearchTool configuration and interface
- ElasticsearchSearchTool configuration and interface
- FunctionTool creation

Note: These tests don't require actual API keys or running services.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tools.tavily_tool import TavilySearchTool, build_tavily_tool
from src.tools.es_search_tool import ElasticsearchSearchTool, build_es_search_tool


class TestTavilySearchTool:
    """Test TavilySearchTool functionality."""
    
    def test_tool_creation(self):
        """Test TavilySearchTool instantiation."""
        tool = TavilySearchTool(max_results=3)
        assert tool.max_results == 3
    
    def test_get_tool_returns_function_tool(self):
        """Test that get_tool returns a FunctionTool."""
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test_key"}):
            tool = TavilySearchTool()
            function_tool = tool.get_tool()
            
            assert function_tool is not None
            assert function_tool.metadata.name == "web_search"
            assert "web" in function_tool.metadata.description.lower()
    
    def test_tool_is_cached(self):
        """Test that the same FunctionTool instance is returned."""
        tool = TavilySearchTool()
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test_key"}):
            ft1 = tool.get_tool()
            ft2 = tool.get_tool()
            assert ft1 is ft2  # Same instance
    
    def test_build_tavily_tool_convenience(self):
        """Test build_tavily_tool convenience function."""
        with patch.dict("os.environ", {"TAVILY_API_KEY": "test_key"}):
            function_tool = build_tavily_tool(max_results=5)
            assert function_tool.metadata.name == "web_search"


class TestElasticsearchSearchTool:
    """Test ElasticsearchSearchTool functionality."""
    
    def test_tool_creation_defaults(self):
        """Test ElasticsearchSearchTool with default values."""
        tool = ElasticsearchSearchTool()
        assert tool.index_name == "medimind_docs"
        assert tool.max_results == 5
        assert "localhost:9200" in tool.es_url
    
    def test_tool_creation_custom(self):
        """Test ElasticsearchSearchTool with custom values."""
        tool = ElasticsearchSearchTool(
            index_name="custom_index",
            max_results=10,
            es_url="http://es-server:9200",
        )
        assert tool.index_name == "custom_index"
        assert tool.max_results == 10
        assert tool.es_url == "http://es-server:9200"
    
    def test_get_tool_returns_function_tool(self):
        """Test that get_tool returns a FunctionTool."""
        tool = ElasticsearchSearchTool()
        function_tool = tool.get_tool()
        
        assert function_tool is not None
        assert function_tool.metadata.name == "knowledge_base_search"
        assert "knowledge base" in function_tool.metadata.description.lower()
    
    def test_build_es_search_tool_convenience(self):
        """Test build_es_search_tool convenience function."""
        function_tool = build_es_search_tool(
            index_name="test_index",
            max_results=3,
        )
        assert function_tool.metadata.name == "knowledge_base_search"

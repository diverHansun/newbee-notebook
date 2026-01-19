"""Configuration for Elasticsearch integration.

This module defines the configuration schema for Elasticsearch,
following the Single Responsibility Principle (SRP).
"""

from typing import Optional
from pydantic import BaseModel, Field


class ElasticsearchConfig(BaseModel):
    """Configuration for Elasticsearch connection and indexing.
    
    Attributes:
        url: Elasticsearch server URL
        index_name: Name of the index for documents
        api_key: Optional API key for authentication
        cloud_id: Optional cloud ID for Elastic Cloud
    """
    
    url: str = Field(
        default="http://localhost:9200",
        description="Elasticsearch server URL"
    )
    index_name: str = Field(
        default="medimind_docs",
        description="Name of the index for documents"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for authentication"
    )
    cloud_id: Optional[str] = Field(
        default=None,
        description="Optional cloud ID for Elastic Cloud"
    )
    
    class Config:
        """Pydantic config."""
        env_prefix = "ELASTICSEARCH_"



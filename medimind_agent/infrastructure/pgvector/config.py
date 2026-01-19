"""Configuration for PostgreSQL + pgvector vector store.

This module defines the configuration schema for pgvector integration,
following the Single Responsibility Principle (SRP).
"""

from typing import Optional
from pydantic import BaseModel, Field


class PGVectorConfig(BaseModel):
    """Configuration for PostgreSQL + pgvector vector store.
    
    Attributes:
        host: PostgreSQL server host
        port: PostgreSQL server port
        database: Database name
        user: Database user
        password: Database password
        table_name: Table name for storing vectors
        embedding_dimension: Dimension of embedding vectors
        distance_metric: Distance metric for similarity search
    """
    
    host: str = Field(default="localhost", description="PostgreSQL server host")
    port: int = Field(default=5432, description="PostgreSQL server port")
    database: str = Field(default="medimind", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="", description="Database password")
    
    table_name: str = Field(
        default="documents",
        description="Table name for storing vectors"
    )
    embedding_dimension: int = Field(
        default=1024,
        description="Dimension of embedding vectors"
    )
    distance_metric: str = Field(
        default="cosine",
        description="Distance metric: cosine, l2, or inner_product"
    )
    
    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return (
            f"postgresql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
        )
    
    class Config:
        """Pydantic config."""
        env_prefix = "POSTGRES_"



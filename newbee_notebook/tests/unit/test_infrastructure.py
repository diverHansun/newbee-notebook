"""Unit tests for infrastructure layer configuration objects."""

from newbee_notebook.infrastructure.elasticsearch.config import ElasticsearchConfig
from newbee_notebook.infrastructure.pgvector.config import PGVectorConfig


class TestPGVectorConfig:
    def test_default_config(self):
        config = PGVectorConfig()
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "newbee_notebook"
        assert config.user == "postgres"
        assert config.table_name == "documents"
        assert config.embedding_dimension == 1024
        assert config.distance_metric == "cosine"

    def test_connection_string(self):
        config = PGVectorConfig(
            user="testuser",
            password="testpass",
            host="testhost",
            port=5433,
            database="testdb",
        )
        assert config.connection_string == "postgresql://testuser:testpass@testhost:5433/testdb"

    def test_custom_config(self):
        config = PGVectorConfig(
            table_name="custom_docs",
            embedding_dimension=768,
            distance_metric="l2",
        )
        assert config.table_name == "custom_docs"
        assert config.embedding_dimension == 768
        assert config.distance_metric == "l2"


class TestElasticsearchConfig:
    def test_default_config(self):
        config = ElasticsearchConfig()
        assert config.url == "http://localhost:9200"
        assert config.index_name == "newbee_notebook_docs"
        assert config.api_key is None
        assert config.cloud_id is None

    def test_custom_config(self):
        config = ElasticsearchConfig(
            url="http://es-server:9200",
            index_name="custom_index",
            api_key="test_key",
            cloud_id="test_cloud",
        )
        assert config.url == "http://es-server:9200"
        assert config.index_name == "custom_index"
        assert config.api_key == "test_key"
        assert config.cloud_id == "test_cloud"

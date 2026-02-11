"""Elasticsearch integration module."""

from newbee_notebook.infrastructure.elasticsearch.store import ElasticsearchStore
from newbee_notebook.infrastructure.elasticsearch.config import ElasticsearchConfig

__all__ = ["ElasticsearchStore", "ElasticsearchConfig"]



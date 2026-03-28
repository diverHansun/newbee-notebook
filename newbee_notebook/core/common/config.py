"""Configuration management for Newbee Notebook.

Handles environment variables, YAML configuration files, and runtime configuration.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import yaml


# Base paths
CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"

# Load environment variables from .env file
load_dotenv()


def load_yaml_config(config_path: str) -> dict:
    """Load configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    if not os.path.exists(config_path):
        return {}
        
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file) or {}


def get_zhipu_api_key():
    """Get Zhipu API key from environment variables.
    
    Returns:
        str: API key for Zhipu services
    """
    return os.getenv("ZHIPU_API_KEY")


def get_embedding_provider():
    """Get embedding provider with priority: environment variable > YAML config > default.

    Priority order:
    1. EMBEDDING_PROVIDER environment variable
    2. configs/embeddings.yaml (embeddings.provider)
    3. Default: 'qwen3-embedding'

    Returns:
        str: Embedding provider (for example: 'qwen3-embedding', 'zhipu')
    """
    provider = os.getenv("EMBEDDING_PROVIDER")
    if provider and provider.strip():
        return provider.strip()

    # Try to get from YAML config
    embeddings_config = get_embeddings_config()
    if embeddings_config and 'embeddings' in embeddings_config:
        provider = embeddings_config['embeddings'].get('provider')
        if provider:
            return provider

    # Default to qwen3-embedding
    return "qwen3-embedding"


def get_embeddings_config():
    """Get embeddings configuration from YAML file.
    
    Returns:
        dict: Embeddings configuration
    """
    return load_yaml_config(CONFIG_DIR / "embeddings.yaml")

def get_llm_config():
    """Get LLM configuration from YAML file.
    
    Returns:
        dict: LLM configuration
    """
    return load_yaml_config(CONFIG_DIR / "llm.yaml")

def get_llm_provider() -> str:
    """Get LLM provider with priority: env > YAML > default."""
    provider = os.getenv("LLM_PROVIDER")
    if provider and provider.strip():
        return provider.strip().lower()

    llm_config = get_llm_config()
    if llm_config and "llm" in llm_config:
        provider = llm_config["llm"].get("provider")
        if provider and str(provider).strip():
            return str(provider).strip().lower()

    return "qwen"


def _get_llm_provider_config(provider: str | None = None) -> dict:
    """Get provider-specific config map under llm.*."""
    llm_config = get_llm_config()
    if not llm_config:
        return {}
    selected = provider or get_llm_provider()
    return llm_config.get("llm", {}).get(selected, {})


def get_llm_model():
    """Get LLM model name for current provider."""
    cfg = _get_llm_provider_config()
    if "model" in cfg:
        return cfg["model"]
    model = os.getenv("LLM_MODEL")
    if model:
        return model
    provider = get_llm_provider()
    if provider == "qwen":
        return "qwen-plus"
    if provider == "openai":
        return "gpt-4o-mini"
    return "glm-4.7"


def get_llm_temperature():
    """Get LLM temperature for current provider."""
    cfg = _get_llm_provider_config()
    if "temperature" in cfg:
        return float(cfg["temperature"])
    temp = os.getenv("LLM_TEMPERATURE")
    if temp:
        try:
            return float(temp)
        except ValueError:
            pass
    return 0.2


def get_llm_max_tokens():
    """Get LLM max tokens for current provider."""
    cfg = _get_llm_provider_config()
    if "max_tokens" in cfg:
        return int(cfg["max_tokens"])
    max_tokens = os.getenv("LLM_MAX_TOKENS")
    if max_tokens and max_tokens.isdigit():
        return int(max_tokens)
    return 2048


def get_llm_top_p():
    """Get LLM top_p for current provider."""
    cfg = _get_llm_provider_config()
    if "top_p" in cfg:
        return float(cfg["top_p"])
    top_p = os.getenv("LLM_TOP_P")
    if top_p:
        try:
            return float(top_p)
        except ValueError:
            pass
    return 0.7

def get_documents_directory():
    """Get documents directory from environment variable or default.
    
    Returns:
        str: Documents directory path
    """
    return os.getenv("DOCUMENTS_DIR", "data/documents")


def _resolve_env_var(value: str) -> str:
    """Resolve environment variable placeholder in format ${VAR:default}.
    
    Args:
        value: String that may contain ${VAR:default} format
        
    Returns:
        str: Resolved value (env var if exists, else default, else original)
    """
    import re
    
    # Pattern: ${VAR_NAME:default_value}
    # Note: default value can be empty, e.g. ${MINERU_API_KEY:}
    pattern = r'\$\{([^:}]+):([^}]*)\}'
    
    def replace_env(match):
        var_name = match.group(1)
        default_value = match.group(2)
        return os.getenv(var_name, default_value)
    
    # Replace all ${VAR:default} patterns
    resolved = re.sub(pattern, replace_env, value)
    
    # Also handle ${VAR} without default
    pattern_no_default = r'\$\{([^}]+)\}'
    resolved = re.sub(pattern_no_default, lambda m: os.getenv(m.group(1), ""), resolved)
    
    return resolved


def get_storage_config():
    """Get storage configuration from YAML file or defaults.
    
    Returns:
        dict: Storage configuration
    """
    config = load_yaml_config(CONFIG_DIR / "storage.yaml")
    
    # Apply environment variable overrides and resolve placeholders
    if config:
        if "postgresql" in config:
            pg_config = config["postgresql"]
            
            # Resolve placeholders first
            host = _resolve_env_var(str(pg_config.get("host", "localhost")))
            port_str = _resolve_env_var(str(pg_config.get("port", "5432")))
            database = _resolve_env_var(str(pg_config.get("database", "newbee_notebook")))
            user = _resolve_env_var(str(pg_config.get("user", "postgres")))
            password = _resolve_env_var(str(pg_config.get("password", "")))
            
            # Apply environment variable overrides (highest priority)
            pg_config["host"] = os.getenv("POSTGRES_HOST", host)
            try:
                pg_config["port"] = int(os.getenv("POSTGRES_PORT", port_str))
            except ValueError:
                pg_config["port"] = 5432  # Fallback to default
            pg_config["database"] = os.getenv("POSTGRES_DB", database)
            pg_config["user"] = os.getenv("POSTGRES_USER", user)
            pg_config["password"] = os.getenv("POSTGRES_PASSWORD", password)
        
        if "elasticsearch" in config:
            es_config = config["elasticsearch"]
            
            # Resolve placeholders
            url = _resolve_env_var(str(es_config.get("url", "http://localhost:9200")))
            api_key = _resolve_env_var(str(es_config.get("api_key", "")))
            cloud_id = _resolve_env_var(str(es_config.get("cloud_id", "")))
            
            # Apply environment variable overrides
            es_config["url"] = os.getenv("ELASTICSEARCH_URL", url)
            es_config["api_key"] = os.getenv("ELASTICSEARCH_API_KEY", api_key)
            es_config["cloud_id"] = os.getenv("ELASTICSEARCH_CLOUD_ID", cloud_id)
    
    return config


def get_pgvector_config_for_provider(provider: str = None) -> dict:
    """Get pgvector table configuration for a specific embedding provider.

    This function supports multi-provider vector storage by returning
    provider-specific table names and embedding dimensions.

    Args:
        provider: Embedding provider name (for example: 'qwen3-embedding', 'zhipu').
            If None, uses the current configured provider.

    Returns:
        dict: Configuration with keys:
            - table_name: Provider-specific table name (for example: 'documents_qwen3_embedding')
            - embedding_dimension: Vector dimension for this provider
            - distance_metric: Distance metric for similarity search

    Example:
        >>> config = get_pgvector_config_for_provider('qwen3-embedding')
        >>> print(config)
        {'table_name': 'documents_qwen3_embedding', 'embedding_dimension': 1024, 'distance_metric': 'cosine'}
    """
    if provider is None:
        provider = get_embedding_provider()

    storage_config = get_storage_config()
    pgvector_config = storage_config.get("pgvector", {})

    # Try to get provider-specific config from tables
    tables_config = pgvector_config.get("tables", {})
    provider_config = tables_config.get(provider, {})

    if provider_config:
        provider_table_fallback = f"documents_{provider.replace('-', '_')}"
        return {
            "table_name": provider_config.get("table_name", provider_table_fallback),
            "embedding_dimension": provider_config.get("embedding_dimension", 1024),
            "distance_metric": provider_config.get("distance_metric", "cosine"),
        }

    # Fallback to legacy single-table config with 1024-dim defaults
    return {
        "table_name": pgvector_config.get("table_name", "documents"),
        "embedding_dimension": pgvector_config.get("embedding_dimension", 1024),
        "distance_metric": pgvector_config.get("distance_metric", "cosine"),
    }


def get_document_processing_config() -> dict:
    """Get document processing configuration."""
    cfg = load_yaml_config(CONFIG_DIR / "document_processing.yaml")

    def _resolve_nested(value):
        if isinstance(value, str):
            return _resolve_env_var(value)
        if isinstance(value, dict):
            return {k: _resolve_nested(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_resolve_nested(v) for v in value]
        return value

    if cfg and "document_processing" in cfg:
        cfg["document_processing"] = _resolve_nested(cfg["document_processing"])
    return cfg


def get_zhipu_tools_config() -> dict:
    """Get built-in Zhipu search tool configuration."""
    return load_yaml_config(CONFIG_DIR / "zhipu_tools.yaml")


def get_config():
    """Get active runtime configuration as a dictionary."""
    return {
        "zhipu_api_key": get_zhipu_api_key(),
        "documents_directory": get_documents_directory(),
        "embedding_provider": get_embedding_provider(),
        "llm_provider": get_llm_provider(),
        "llm_model": get_llm_model(),
        "llm_temperature": get_llm_temperature(),
        "llm_max_tokens": get_llm_max_tokens(),
        "llm_top_p": get_llm_top_p(),
        "embeddings": get_embeddings_config(),
        "llm": get_llm_config(),
        "storage": get_storage_config(),
        "document_processing": get_document_processing_config(),
    }


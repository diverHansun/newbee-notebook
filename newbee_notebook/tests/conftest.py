"""Pytest configuration and shared fixtures for newbee-notebook tests.

This module provides:
- Path configuration to import src modules
- Common fixtures for tests
- Shared test utilities
"""

import sys
from pathlib import Path

import pytest

# Add project root to Python path for package imports
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root directory path."""
    return project_root


@pytest.fixture(scope="session")
def data_dir(project_root_path):
    """Return the data directory path."""
    return project_root_path / "data"


@pytest.fixture(scope="session")
def docs_dir(data_dir):
    """Return the documents directory path."""
    return data_dir / "documents"


@pytest.fixture(scope="session")
def index_dir(data_dir):
    """Return the index directory path."""
    return data_dir / "indexes" / "zhipu"


@pytest.fixture(scope="session")
def configs_dir(project_root_path):
    """Return the configs directory path."""
    return project_root_path / "newbee_notebook" / "configs"



"""
Test configuration for Discord Multi-Agent System

Phase 3.1: Database Foundation テスト設定
- テスト環境統一設定
- モック設定共通化
- fixture提供
"""
import pytest
import os
from unittest.mock import patch
from app.core.settings import reset_settings


@pytest.fixture(autouse=True)
def setup_test_environment():
    """
    全テスト共通の環境設定
    
    テスト実行時に必ずENV=testingを設定し、
    必須環境変数のバリデーションを無効化
    """
    test_env = {
        "ENV": "testing",
        "DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db",
        "REDIS_URL": "redis://localhost:6379",
        # テスト用ダミートークン
        "SPECTRA_TOKEN": "test_token_spectra",
        "LYNQ_TOKEN": "test_token_lynq", 
        "PAZ_TOKEN": "test_token_paz",
        "GEMINI_API_KEY": "test_api_key"
    }
    
    with patch.dict(os.environ, test_env):
        # 設定をリセットしてテスト環境で初期化
        reset_settings()
        yield
        # テスト後のクリーンアップ
        reset_settings()


@pytest.fixture
def clean_db_manager():
    """
    テスト間でDatabaseManagerインスタンスをクリーンアップ
    """
    from app.core.database import reset_db_manager
    
    # テスト前にリセット
    reset_db_manager()
    yield
    # テスト後にもリセット
    reset_db_manager()
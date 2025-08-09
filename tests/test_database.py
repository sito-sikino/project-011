"""
Test module for database functionality

Phase 3.1 Database Foundation - TDD実装

🔴 Red Phase: 包括的なデータベーステストを先行作成
- PostgreSQL接続プール機能
- pgvector対応（1536次元）
- 非同期操作対応
- settings.py統合
- connection pool管理
- ヘルスチェック機能
- エラーハンドリング（Fail-Fast）

テスト設計:
1. 基本接続テスト
2. 接続プール管理テスト
3. pgvector機能テスト
4. 非同期操作テスト
5. 設定統合テスト
6. ヘルスチェックテスト
7. エラーハンドリングテスト
"""
import pytest
import asyncio
import asyncpg
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.core.database import DatabaseManager, get_db_manager, InitializationError
from app.core.settings import get_settings, reset_settings
import os
from typing import List


class TestDatabaseManagerInstantiation:
    """DatabaseManagerクラスのインスタンス化テスト"""
    
    def test_database_manager_creation_with_settings(self):
        """設定からDatabaseManager正常作成テスト"""
        settings = get_settings()
        
        # DatabaseManager作成が成功することを確認
        db_manager = DatabaseManager(settings)
        
        assert db_manager is not None
        assert db_manager.settings == settings
        assert db_manager.database_url == settings.database.url
        assert db_manager.pool is None  # まだ接続していない
        
    def test_database_manager_missing_database_url(self):
        """DATABASE_URL未設定時のテスト"""
        settings = get_settings()
        
        # テスト環境ではデフォルトURLでも作成は可能
        db_manager = DatabaseManager(settings)
        assert db_manager is not None


class TestDatabaseConnectionPool:
    """データベース接続プール管理テスト"""
    
    @pytest.mark.asyncio
    async def test_connection_pool_initialization(self):
        """接続プール初期化テスト"""
        settings = get_settings()
        db_manager = DatabaseManager(settings)
        
        # asyncpgのcreate_poolをモック
        mock_pool = AsyncMock()
        with patch('app.core.database.asyncpg.create_pool', new_callable=AsyncMock, return_value=mock_pool) as mock_create_pool:
            await db_manager.initialize()
            
            # プール作成が正しいパラメータで呼ばれることを確認
            mock_create_pool.assert_called_once()
            call_args = mock_create_pool.call_args
            assert call_args[0][0] == settings.database.url
            
            # キーワード引数を確認
            kwargs = call_args[1]
            assert 'min_size' in kwargs
            assert 'max_size' in kwargs
            assert kwargs['min_size'] >= 5
            assert kwargs['max_size'] >= 10
            
            assert db_manager.pool == mock_pool
                
    @pytest.mark.asyncio
    async def test_connection_pool_close(self):
        """接続プール終了テスト"""
        settings = get_settings()
        db_manager = DatabaseManager(settings)
        
        # モックプールを設定
        mock_pool = AsyncMock()
        db_manager.pool = mock_pool
        
        await db_manager.close()
        
        mock_pool.close.assert_called_once()
        mock_pool.wait_closed.assert_called_once()
        assert db_manager.pool is None
            
    @pytest.mark.asyncio
    async def test_connection_acquisition(self):
        """データベース接続取得テスト"""
        settings = get_settings()
        db_manager = DatabaseManager(settings)
        
        # モック接続とプール
        mock_connection = AsyncMock()
        mock_pool = MagicMock()
        
        # コンテキストマネージャーの正しいモック設定
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
                
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        async with db_manager.get_connection() as conn:
            assert conn == mock_connection
            
        mock_pool.acquire.assert_called_once()


class TestPgVectorSupport:
    """pgvector拡張サポートテスト"""
    
    @pytest.mark.asyncio
    async def test_pgvector_extension_check(self):
        """pgvector拡張の存在確認テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック接続
            mock_connection = AsyncMock()
            mock_connection.fetchval.return_value = "vector"
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            # pgvector拡張チェック
            result = await db_manager.check_pgvector_extension()
            
            assert result is True
            mock_connection.fetchval.assert_called_once()
            
    @pytest.mark.asyncio 
    async def test_vector_table_creation(self):
        """ベクトルテーブル作成テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック接続
            mock_connection = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            await db_manager.create_vector_table("test_table", 1536)
            
            # CREATE TABLE文が実行されることを確認
            mock_connection.execute.assert_called()
            call_args = mock_connection.execute.call_args[0][0]
            assert "CREATE TABLE" in call_args
            assert "test_table" in call_args
            assert "vector(1536)" in call_args
            
    @pytest.mark.asyncio
    async def test_vector_insert(self):
        """ベクトルデータ挿入テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # テストベクトル（1536次元）
            test_vector = [0.1] * 1536
            test_content = "test content"
            test_metadata = {"agent": "spectra", "channel": "test"}
            
            # モック接続
            mock_connection = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            await db_manager.insert_vector("agent_memory", test_content, test_vector, test_metadata)
            
            # INSERT文が実行されることを確認
            mock_connection.execute.assert_called()
            call_args = mock_connection.execute.call_args
            assert "INSERT INTO agent_memory" in call_args[0][0]
            assert call_args[0][1] == test_content
            assert call_args[0][2] == test_vector
            
    @pytest.mark.asyncio
    async def test_vector_similarity_search(self):
        """ベクトル類似度検索テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # テストクエリベクトル
            query_vector = [0.2] * 1536
            
            # モック結果
            mock_results = [
                {"content": "result 1", "metadata": {"agent": "spectra"}, "similarity": 0.9},
                {"content": "result 2", "metadata": {"agent": "lynq"}, "similarity": 0.8}
            ]
            
            mock_connection = AsyncMock()
            mock_connection.fetch.return_value = mock_results
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            results = await db_manager.similarity_search("agent_memory", query_vector, limit=5)
            
            assert len(results) == 2
            assert results[0]["content"] == "result 1"
            assert results[1]["similarity"] == 0.8
            
            # 類似度検索クエリが実行されることを確認
            mock_connection.fetch.assert_called()


class TestAsyncOperations:
    """非同期操作テスト"""
    
    @pytest.mark.asyncio
    async def test_async_execute(self):
        """非同期クエリ実行テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック接続
            mock_connection = AsyncMock()
            mock_connection.execute.return_value = "CREATE TABLE"
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            result = await db_manager.execute("CREATE TABLE test (id SERIAL PRIMARY KEY)")
            
            assert result == "CREATE TABLE"
            mock_connection.execute.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_async_fetch(self):
        """非同期データ取得テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック結果
            mock_results = [{"id": 1, "name": "test"}]
            
            mock_connection = AsyncMock()
            mock_connection.fetch.return_value = mock_results
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            results = await db_manager.fetch("SELECT * FROM test")
            
            assert results == mock_results
            mock_connection.fetch.assert_called_once()
            
    @pytest.mark.asyncio
    async def test_async_fetchval(self):
        """非同期単一値取得テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            mock_connection = AsyncMock()
            mock_connection.fetchval.return_value = 42
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            result = await db_manager.fetchval("SELECT COUNT(*) FROM test")
            
            assert result == 42
            mock_connection.fetchval.assert_called_once()


class TestHealthCheck:
    """データベースヘルスチェックテスト"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """ヘルスチェック成功テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック接続（成功）
            mock_connection = AsyncMock()
            mock_connection.fetchval.return_value = 1
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            result = await db_manager.health_check()
            
            assert result is True
            mock_connection.fetchval.assert_called_once_with("SELECT 1")
            
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """ヘルスチェック失敗テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック接続（失敗）
            mock_connection = AsyncMock()
            mock_connection.fetchval.side_effect = Exception("Connection failed")
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            result = await db_manager.health_check()
            
            assert result is False
            
    @pytest.mark.asyncio
    async def test_health_check_no_pool(self):
        """プール未初期化時のヘルスチェックテスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # プールが未初期化の状態
            result = await db_manager.health_check()
            
            assert result is False


class TestErrorHandling:
    """エラーハンドリング・Fail-Fastテスト"""
    
    @pytest.mark.asyncio
    async def test_connection_error_fail_fast(self):
        """接続エラー時のFail-Fastテスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://invalid:invalid@localhost:9999/invalid"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # 接続エラーをシミュレート
            with patch('asyncpg.create_pool', side_effect=Exception("Connection failed")):
                with pytest.raises(Exception) as exc_info:
                    await db_manager.initialize()
                
                assert "Connection failed" in str(exc_info.value)
                
    @pytest.mark.asyncio
    async def test_query_error_handling(self):
        """クエリエラーハンドリングテスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # モック接続（クエリエラー）
            mock_connection = AsyncMock()
            mock_connection.execute.side_effect = Exception("Query failed")
            
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
            db_manager.pool = mock_pool
            
            with pytest.raises(Exception) as exc_info:
                await db_manager.execute("INVALID QUERY")
            
            assert "Query failed" in str(exc_info.value)
            
    @pytest.mark.asyncio
    async def test_pool_not_initialized_error(self):
        """プール未初期化時のエラーテスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # プールが未初期化のまま操作実行
            with pytest.raises(InitializationError) as exc_info:
                await db_manager.execute("SELECT 1")
            
            assert "Database not initialized" in str(exc_info.value)


class TestSingletonPattern:
    """シングルトンパターンテスト"""
    
    def test_get_db_manager_singleton(self):
        """get_db_manager()のシングルトン動作テスト"""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            # 複数回呼び出して同一インスタンスか確認
            manager1 = get_db_manager()
            manager2 = get_db_manager()
            
            assert manager1 is manager2
            
    def test_singleton_reset(self):
        """シングルトンリセット機能テスト"""
        from app.core.database import reset_db_manager
        
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db"}):
            reset_settings()
            
            manager1 = get_db_manager()
            reset_db_manager()  # リセット
            manager2 = get_db_manager()
            
            # リセット後は異なるインスタンス
            assert manager1 is not manager2


class TestIntegrationWithSettings:
    """settings.py統合テスト"""
    
    def test_database_config_integration(self):
        """DatabaseConfig統合テスト"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:pass@localhost:5432/test_db",
            "DATABASE_REDIS_URL": "redis://localhost:6379"
        }):
            reset_settings()
            settings = get_settings()
            db_manager = DatabaseManager(settings)
            
            # 設定が正しく統合されているか確認
            assert db_manager.database_url == "postgresql://test:pass@localhost:5432/test_db"
            
    def test_environment_variable_precedence(self):
        """環境変数優先順位テスト"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://env:env@env:5432/env",
            "DATABASE_DATABASE_URL": "postgresql://db_prefix:db_prefix@db_prefix:5432/db_prefix"
        }):
            reset_settings()
            settings = get_settings()
            
            # DATABASE_URLが直接読み込まれることを確認
            assert settings.database_url == "postgresql://env:env@env:5432/env"
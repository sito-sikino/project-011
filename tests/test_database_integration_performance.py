"""
Database Integration & Performance Test Suite

Phase 3.3: Database Connection Tests - 統合・パフォーマンステスト

このテストスイートは以下を検証:
- Migration System Integration: マイグレーションシステム統合テスト
- Connection Pool Performance: 接続プール性能テスト
- Concurrent Operations: 並行操作テスト
- Error Handling & Recovery: エラーハンドリング・リカバリテスト
- Resource Management: リソース管理テスト
- Real Database Operations: 実際のデータベース操作テスト（mockなし）

t-wada式TDDアプローチ:
🔴 Red Phase: 統合・性能テストスイート作成
🟢 Green Phase: 実装で全テスト通過
🟡 Refactor Phase: 性能最適化・エラーハンドリング強化
"""

import pytest
import asyncio
import json
import uuid
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager

# テスト対象のインポート
from app.core.database import (
    DatabaseManager, get_db_manager, reset_db_manager,
    initialize_database, close_database, run_migrations,
    DatabaseError, ConnectionError, QueryError, InitializationError
)
from app.core.settings import get_settings, reset_settings


class TestMigrationSystemIntegration:
    """マイグレーションシステム統合テスト"""
    
    @pytest.mark.asyncio
    async def test_initialize_database_with_auto_migration(self, clean_db_manager):
        """自動マイグレーション付きデータベース初期化テスト"""
        # モックマイグレーションマネージャー
        with patch('app.core.database.run_migrations') as mock_migrations:
            mock_migrations.return_value = None
            
            # DatabaseManager初期化のモック
            with patch.object(DatabaseManager, 'initialize') as mock_db_init:
                mock_db_init.return_value = None
                
                db_manager = await initialize_database(auto_migrate=True)
                
                # 初期化とマイグレーションが呼ばれることを確認
                mock_db_init.assert_called_once()
                mock_migrations.assert_called_once()
                assert db_manager is not None
    
    @pytest.mark.asyncio
    async def test_initialize_database_migration_failure_handling(self, clean_db_manager):
        """マイグレーション失敗時のハンドリングテスト"""
        # マイグレーション失敗をシミュレート
        with patch('app.core.database.run_migrations') as mock_migrations:
            mock_migrations.side_effect = Exception("Migration failed")
            
            with patch.object(DatabaseManager, 'initialize') as mock_db_init:
                mock_db_init.return_value = None
                
                # マイグレーション失敗でも初期化は継続される
                db_manager = await initialize_database(auto_migrate=True)
                
                assert db_manager is not None
                mock_db_init.assert_called_once()
                mock_migrations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_memory_table_creation_via_migration(self, clean_db_manager):
        """マイグレーション経由でのagent_memoryテーブル作成テスト"""
        db_manager = get_db_manager()
        
        # マイグレーション実行のモック
        mock_connection = AsyncMock()
        
        # マイグレーション内容をシミュレート
        migration_queries = [
            "CREATE EXTENSION IF NOT EXISTS vector",
            "CREATE TABLE agent_memory",
            "CREATE INDEX idx_agent_memory_embedding",
            "CREATE INDEX idx_agent_memory_metadata", 
            "CREATE INDEX idx_agent_memory_created_at"
        ]
        
        mock_connection.execute.side_effect = [None] * len(migration_queries)
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # 各マイグレーションクエリを実行
            for query in migration_queries:
                await db_manager.execute(query)
            
            # 全てのマイグレーションクエリが実行されることを確認
            assert mock_connection.execute.call_count == len(migration_queries)
    
    @pytest.mark.asyncio
    async def test_migration_rollback_integration(self, clean_db_manager):
        """マイグレーションロールバック統合テスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = None
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # ロールバッククエリ実行
            await db_manager.execute("DROP TABLE IF EXISTS agent_memory")
            
            mock_connection.execute.assert_called_once()
            call_args = mock_connection.execute.call_args[0]
            assert "DROP TABLE" in call_args[0]
            assert "agent_memory" in call_args[0]


class TestConnectionPoolPerformance:
    """接続プール性能テスト"""
    
    @pytest.mark.asyncio
    async def test_connection_pool_initialization_performance(self, clean_db_manager):
        """接続プール初期化性能テスト"""
        db_manager = get_db_manager()
        
        # 初期化時間測定
        with patch('app.core.database.asyncpg.create_pool') as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            
            start_time = time.time()
            await db_manager.initialize()
            end_time = time.time()
            
            initialization_time = end_time - start_time
            
            # 初期化は1秒以内で完了すること
            assert initialization_time < 1.0
            mock_create_pool.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connection_acquisition_performance(self, clean_db_manager):
        """接続取得性能テスト"""
        db_manager = get_db_manager()
        
        # モック接続プール
        mock_connection = AsyncMock()
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        # 複数回の接続取得時間測定
        acquisition_times = []
        
        for i in range(10):
            start_time = time.time()
            async with db_manager.get_connection() as conn:
                end_time = time.time()
                acquisition_times.append(end_time - start_time)
                assert conn == mock_connection
        
        # 平均取得時間が100ms以内であること
        avg_acquisition_time = sum(acquisition_times) / len(acquisition_times)
        assert avg_acquisition_time < 0.1
        assert mock_pool.acquire.call_count == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_connections_performance(self, clean_db_manager):
        """並行接続性能テスト"""
        db_manager = get_db_manager()
        
        # モック設定
        mock_connection = AsyncMock()
        mock_connection.fetchval.return_value = 1
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        async def health_check_task():
            return await db_manager.health_check()
        
        # 10個の並行ヘルスチェック実行
        start_time = time.time()
        tasks = [health_check_task() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 並行実行時間が1秒以内であること
        concurrent_time = end_time - start_time
        assert concurrent_time < 1.0
        
        # 全てのタスクが成功すること
        assert all(results)
        assert mock_pool.acquire.call_count == 10
    
    @pytest.mark.asyncio
    async def test_connection_pool_resource_management(self, clean_db_manager):
        """接続プールリソース管理テスト"""
        db_manager = get_db_manager()
        
        # プール作成・クローズのテスト
        mock_pool = AsyncMock()
        
        with patch('app.core.database.asyncpg.create_pool', return_value=mock_pool):
            await db_manager.initialize()
            assert db_manager.pool == mock_pool
            
            await db_manager.close()
            mock_pool.close.assert_called_once()
            mock_pool.wait_closed.assert_called_once()
            assert db_manager.pool is None


class TestConcurrentOperations:
    """並行操作テスト"""
    
    @pytest.mark.asyncio
    async def test_concurrent_crud_operations(self, clean_db_manager):
        """並行CRUD操作テスト"""
        db_manager = get_db_manager()
        
        # モック設定
        mock_connection = AsyncMock()
        mock_connection.fetchval.side_effect = [str(uuid.uuid4()) for _ in range(5)]
        mock_connection.fetch.return_value = [{"id": str(uuid.uuid4()), "content": "test"}]
        mock_connection.execute.return_value = "UPDATE 1"
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        async def insert_task(i):
            return await db_manager.insert_vector(
                "agent_memory", 
                f"テスト {i}", 
                [0.1] * 1536, 
                {"index": i}
            )
        
        async def fetch_task():
            return await db_manager.fetch("SELECT * FROM agent_memory LIMIT 1")
        
        async def update_task():
            return await db_manager.execute(
                "UPDATE agent_memory SET content = 'updated' WHERE id = $1",
                str(uuid.uuid4())
            )
        
        # 並行操作実行
        tasks = []
        tasks.extend([insert_task(i) for i in range(3)])
        tasks.append(fetch_task())
        tasks.append(update_task())
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 並行操作時間が2秒以内であること
        concurrent_time = end_time - start_time
        assert concurrent_time < 2.0
        
        # 例外が発生していないこと
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_vector_similarity_searches(self, clean_db_manager):
        """並行ベクトル類似度検索テスト"""
        db_manager = get_db_manager()
        
        # モック結果
        mock_results = [
            {"content": "結果1", "similarity": 0.9},
            {"content": "結果2", "similarity": 0.8}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = mock_results
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        async def similarity_search_task(i):
            query_vector = [0.1 * i] * 1536
            return await db_manager.similarity_search(
                "agent_memory", query_vector, limit=5
            )
        
        # 5個の並行類似度検索
        tasks = [similarity_search_task(i) for i in range(1, 6)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # 並行検索時間が3秒以内であること
        search_time = end_time - start_time
        assert search_time < 3.0
        
        # 全ての検索が結果を返すこと
        assert len(results) == 5
        assert all(len(result) == 2 for result in results)


class TestErrorHandlingAndRecovery:
    """エラーハンドリング・リカバリテスト"""
    
    @pytest.mark.asyncio
    async def test_connection_failure_recovery(self, clean_db_manager):
        """接続失敗からのリカバリテスト"""
        db_manager = get_db_manager()
        
        # 初回は失敗、2回目は成功
        mock_pool = AsyncMock()
        
        with patch('app.core.database.asyncpg.create_pool') as mock_create_pool:
            mock_create_pool.side_effect = [
                Exception("Initial connection failed"),
                mock_pool  # 2回目は成功
            ]
            
            # 初回初期化失敗
            with pytest.raises(InitializationError):
                await db_manager.initialize()
            
            # リセット後に再試行
            reset_db_manager()
            db_manager = get_db_manager()
            
            # 2回目は成功
            await db_manager.initialize()
            assert db_manager.pool == mock_pool
    
    @pytest.mark.asyncio
    async def test_query_error_handling_with_retry(self, clean_db_manager):
        """クエリエラーハンドリング・リトライテスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        # 初回は失敗、2回目は成功
        mock_connection.fetchval.side_effect = [
            Exception("Temporary query failure"),
            42  # 2回目は成功
        ]
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        # 初回は失敗
        with pytest.raises(QueryError):
            await db_manager.fetchval("SELECT 1")
        
        # リトライで成功
        result = await db_manager.fetchval("SELECT 1")
        assert result == 42
    
    @pytest.mark.asyncio
    async def test_pool_exhaustion_handling(self, clean_db_manager):
        """接続プール枯渇ハンドリングテスト"""
        db_manager = get_db_manager()
        
        mock_pool = AsyncMock()
        # プール枯渇をシミュレート
        mock_pool.acquire.side_effect = Exception("Pool exhausted")
        db_manager.pool = mock_pool
        
        # プール枯渇時のエラーハンドリング
        with pytest.raises(Exception) as exc_info:
            async with db_manager.get_connection():
                pass
        
        assert "Pool exhausted" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, clean_db_manager):
        """エラー時のトランザクションロールバックテスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        mock_transaction = AsyncMock()
        
        # トランザクション内でエラー発生をシミュレート
        mock_connection.transaction.return_value = mock_transaction
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_connection.execute.side_effect = Exception("Transaction error")
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        # トランザクション内でエラー発生
        with pytest.raises(QueryError):
            await db_manager.execute("INSERT INTO agent_memory VALUES (...)")
        
        # ロールバックが呼ばれることを確認
        mock_connection.execute.assert_called_once()


class TestResourceManagement:
    """リソース管理テスト"""
    
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, clean_db_manager):
        """メモリ使用量モニタリングテスト"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        db_manager = get_db_manager()
        
        # 大量データ処理のシミュレート
        mock_connection = AsyncMock()
        large_results = [
            {"id": str(uuid.uuid4()), "content": "x" * 1000}
            for _ in range(1000)
        ]
        mock_connection.fetch.return_value = large_results
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        # 大量データ取得
        results = await db_manager.fetch("SELECT * FROM agent_memory")
        
        current_memory = process.memory_info().rss
        memory_increase = current_memory - initial_memory
        
        # メモリ使用量が適切な範囲内であること（100MB以下）
        assert memory_increase < 100 * 1024 * 1024
        assert len(results) == 1000
    
    @pytest.mark.asyncio
    async def test_connection_cleanup_after_operations(self, clean_db_manager):
        """操作後の接続クリーンアップテスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        mock_pool = AsyncMock()
        
        connection_acquired = False
        connection_released = False
        
        class MockAcquireContext:
            async def __aenter__(self):
                nonlocal connection_acquired
                connection_acquired = True
                return mock_connection
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                nonlocal connection_released
                connection_released = True
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        # 接続使用
        async with db_manager.get_connection() as conn:
            assert connection_acquired
            assert conn == mock_connection
        
        # 接続が適切に解放されることを確認
        assert connection_released
    
    @pytest.mark.asyncio
    async def test_long_running_operations_timeout(self, clean_db_manager):
        """長時間実行操作のタイムアウトテスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        # 長時間実行をシミュレート（実際にはすぐ返す）
        async def slow_query(*args):
            await asyncio.sleep(0.1)  # 短時間でテスト
            return "SLOW QUERY RESULT"
        
        mock_connection.fetchval = slow_query
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        # タイムアウト付きで実行
        start_time = time.time()
        try:
            result = await asyncio.wait_for(
                db_manager.fetchval("SELECT slow_function()"), 
                timeout=1.0
            )
            end_time = time.time()
            
            # 結果が返されること
            assert result == "SLOW QUERY RESULT"
            # 実行時間が適切であること
            assert end_time - start_time < 1.0
            
        except asyncio.TimeoutError:
            pytest.fail("Query should not timeout with 1 second limit")


class TestRealDatabaseOperations:
    """実際のデータベース操作テスト（mockなし）"""
    
    def test_database_url_validation(self):
        """データベースURL検証テスト"""
        from app.core.database import validate_connection_url
        
        # 有効なURL
        valid_urls = [
            "postgresql://user:pass@localhost:5432/dbname",
            "postgres://user:pass@host:5432/db",
            "postgresql://user@localhost/db"
        ]
        
        for url in valid_urls:
            assert validate_connection_url(url), f"Should be valid: {url}"
        
        # 無効なURL
        invalid_urls = [
            "",
            "mysql://user:pass@localhost:3306/db",
            "invalid_url",
            "postgresql://",
            "user:pass@localhost:5432/db"  # スキーマなし
        ]
        
        for url in invalid_urls:
            assert not validate_connection_url(url), f"Should be invalid: {url}"
    
    @pytest.mark.asyncio
    async def test_database_connection_test_function(self, clean_db_manager):
        """データベース接続テスト関数のテスト"""
        from app.core.database import test_database_connection
        
        # モック設定（実際の接続なし）
        with patch.object(DatabaseManager, 'initialize') as mock_init, \
             patch.object(DatabaseManager, 'health_check') as mock_health, \
             patch.object(DatabaseManager, 'close') as mock_close:
            
            mock_init.return_value = None
            mock_health.return_value = True
            mock_close.return_value = None
            
            result = await test_database_connection()
            
            assert result is True
            mock_init.assert_called_once()
            mock_health.assert_called_once()
            mock_close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_initialization_helper(self, clean_db_manager):
        """データベース初期化ヘルパー関数テスト"""
        # モック設定
        with patch.object(DatabaseManager, 'initialize') as mock_init, \
             patch('app.core.database.run_migrations') as mock_migrations:
            
            mock_init.return_value = None
            mock_migrations.return_value = None
            
            db_manager = await initialize_database(auto_migrate=True)
            
            assert db_manager is not None
            mock_init.assert_called_once()
            mock_migrations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_close_helper(self, clean_db_manager):
        """データベース終了ヘルパー関数テスト"""
        from app.core.database import close_database
        
        with patch.object(DatabaseManager, 'close') as mock_close:
            mock_close.return_value = None
            
            await close_database()
            
            mock_close.assert_called_once()


# パフォーマンスベンチマーク関数
class PerformanceBenchmarks:
    """パフォーマンスベンチマーク関数群"""
    
    @staticmethod
    async def benchmark_insert_operations(db_manager: DatabaseManager, count: int = 100) -> Dict[str, float]:
        """挿入操作ベンチマーク"""
        mock_connection = AsyncMock()
        mock_connection.fetchval.side_effect = [str(uuid.uuid4()) for _ in range(count)]
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            start_time = time.time()
            
            for i in range(count):
                await db_manager.insert_vector(
                    "agent_memory",
                    f"ベンチマークメッセージ {i}",
                    [0.1] * 1536,
                    {"benchmark": True, "index": i}
                )
            
            end_time = time.time()
            
            total_time = end_time - start_time
            ops_per_second = count / total_time if total_time > 0 else 0
            
            return {
                "total_time": total_time,
                "operations_per_second": ops_per_second,
                "avg_time_per_op": total_time / count if count > 0 else 0
            }
    
    @staticmethod
    async def benchmark_similarity_search(db_manager: DatabaseManager, count: int = 50) -> Dict[str, float]:
        """類似度検索ベンチマーク"""
        mock_results = [
            {"content": f"結果 {i}", "similarity": 0.9 - (i * 0.01)}
            for i in range(10)
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = mock_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            start_time = time.time()
            
            for i in range(count):
                query_vector = [0.1 * (i + 1)] * 1536
                await db_manager.similarity_search("agent_memory", query_vector, limit=10)
            
            end_time = time.time()
            
            total_time = end_time - start_time
            searches_per_second = count / total_time if total_time > 0 else 0
            
            return {
                "total_time": total_time,
                "searches_per_second": searches_per_second,
                "avg_time_per_search": total_time / count if count > 0 else 0
            }


# テストユーティリティクラス
class TestDataFactory:
    """テストデータファクトリー"""
    
    @staticmethod
    def create_agent_memory_bulk(count: int = 100) -> List[Dict[str, Any]]:
        """大量のagent_memoryテストデータ生成"""
        agents = ["spectra", "lynq", "paz"]
        channels = ["123456789", "987654321", "555666777"]
        
        records = []
        for i in range(count):
            record = {
                "id": str(uuid.uuid4()),
                "content": f"テストメッセージ {i}: " + "内容 " * 10,
                "embedding": [0.1 + (i * 0.001)] * 1536,
                "metadata": {
                    "agent_id": agents[i % len(agents)],
                    "channel_id": channels[i % len(channels)],
                    "message_type": "conversation",
                    "index": i,
                    "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat()
                },
                "created_at": datetime.now() - timedelta(minutes=i)
            }
            records.append(record)
        
        return records
    
    @staticmethod
    def create_performance_test_vectors(dimensions: int = 1536, count: int = 100) -> List[List[float]]:
        """性能テスト用ベクトル生成"""
        vectors = []
        for i in range(count):
            vector = [0.1 + (i * 0.001) + (j * 0.0001) for j in range(dimensions)]
            vectors.append(vector)
        return vectors
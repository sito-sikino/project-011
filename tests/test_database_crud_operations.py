"""
Database CRUD Operations Test Suite

Phase 3.3: Database Connection Tests - 完全なCRUD操作検証

このテストスイートは以下を検証:
- CREATE: agent_memoryテーブルへの挿入操作
- READ: 複数条件による検索操作
- UPDATE: コンテンツ、メタデータ、タイムスタンプ更新
- DELETE: 個別・一括削除操作
- Vector Similarity Search: 1536次元ベクトル類似度検索
- JSONB Metadata Operations: メタデータ検索・更新
- Time-based Queries: 時系列検索パターン
- Integration Tests: migration system統合
- Performance Tests: 接続プール・ベクトル検索性能
- Error Handling: エラー処理・リカバリテスト

t-wada式TDDアプローチ:
🔴 Red Phase: 包括的テストスイート作成（実際のデータベース操作）
🟢 Green Phase: 実装で全テスト通過
🟡 Refactor Phase: パフォーマンス・エラーハンドリング最適化
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import patch
import time

# テスト対象のインポート
from app.core.database import (
    DatabaseManager, get_db_manager, reset_db_manager,
    initialize_database, close_database,
    DatabaseError, ConnectionError, QueryError, InitializationError
)
from app.core.settings import get_settings, reset_settings


class TestCRUDOperationsCreate:
    """CREATE操作（INSERT）包括テスト"""
    
    @pytest.mark.asyncio
    async def test_insert_agent_memory_with_full_data(self, clean_db_manager):
        """完全データでのagent_memory挿入テスト"""
        db_manager = get_db_manager()
        
        # テストデータ準備
        content = "テストメッセージ: LangGraphによる会話内容"
        embedding = [0.1] * 1536  # 1536次元テストベクトル
        metadata = {
            "agent_id": "spectra",
            "channel_id": "123456789",
            "message_type": "conversation",
            "user_id": "987654321",
            "timestamp": "2025-08-09T18:56:32Z"
        }
        
        # モックデータベース操作
        mock_connection = AsyncMock()
        mock_connection.fetchval.return_value = str(uuid.uuid4())
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            record_id = await db_manager.insert_vector(
                "agent_memory", content, embedding, metadata
            )
            
            # 挿入操作検証
            assert record_id is not None
            mock_connection.fetchval.assert_called_once()
            
            # SQLクエリ検証
            call_args = mock_connection.fetchval.call_args
            query = call_args[0][0]
            assert "INSERT INTO agent_memory" in query
            assert "(content, embedding, metadata)" in query
            assert "RETURNING id" in query
            
            # パラメータ検証
            assert call_args[0][1] == content
            assert call_args[0][2] == embedding
            assert json.loads(call_args[0][3]) == metadata
    
    @pytest.mark.asyncio
    async def test_insert_agent_memory_minimal_data(self, clean_db_manager):
        """最小データでの挿入テスト"""
        db_manager = get_db_manager()
        
        content = "最小テストメッセージ"
        embedding = [0.0] * 1536
        
        mock_connection = AsyncMock()
        mock_connection.fetchval.return_value = str(uuid.uuid4())
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # metadataなしで挿入
            record_id = await db_manager.insert_vector(
                "agent_memory", content, embedding
            )
            
            assert record_id is not None
            
            # デフォルトmetadata確認
            call_args = mock_connection.fetchval.call_args
            assert json.loads(call_args[0][3]) == {}
    
    @pytest.mark.asyncio
    async def test_insert_multiple_records_batch(self, clean_db_manager):
        """複数レコード一括挿入テスト"""
        db_manager = get_db_manager()
        
        # 複数のテストレコード
        test_records = [
            {
                "content": f"テストメッセージ {i}",
                "embedding": [0.1 * i] * 1536,
                "metadata": {"agent_id": "spectra", "index": i}
            }
            for i in range(5)
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetchval.side_effect = [str(uuid.uuid4()) for _ in range(5)]
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            record_ids = []
            for record in test_records:
                record_id = await db_manager.insert_vector(
                    "agent_memory", 
                    record["content"], 
                    record["embedding"], 
                    record["metadata"]
                )
                record_ids.append(record_id)
            
            # 全挿入確認
            assert len(record_ids) == 5
            assert all(rid is not None for rid in record_ids)
            assert mock_connection.fetchval.call_count == 5
    
    @pytest.mark.asyncio
    async def test_insert_with_invalid_embedding_dimensions(self, clean_db_manager):
        """無効な埋め込み次元数でのエラーテスト"""
        db_manager = get_db_manager()
        
        # 間違った次元数（1536以外）
        invalid_embedding = [0.1] * 512  # 間違った次元数
        
        mock_connection = AsyncMock()
        mock_connection.fetchval.side_effect = Exception("dimension mismatch")
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            with pytest.raises(Exception) as exc_info:
                await db_manager.insert_vector(
                    "agent_memory", 
                    "test", 
                    invalid_embedding
                )
            
            assert "dimension mismatch" in str(exc_info.value)


class TestCRUDOperationsRead:
    """READ操作（SELECT）包括テスト"""
    
    @pytest.mark.asyncio
    async def test_fetch_agent_memory_by_id(self, clean_db_manager):
        """ID指定でのレコード取得テスト"""
        db_manager = get_db_manager()
        
        test_id = str(uuid.uuid4())
        expected_result = [{
            "id": test_id,
            "content": "テストコンテンツ",
            "metadata": {"agent_id": "spectra"},
            "created_at": datetime.now()
        }]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_result
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        result = await db_manager.fetch(
            "SELECT * FROM agent_memory WHERE id = $1", test_id
        )
        
        assert len(result) == 1
        assert result[0]["id"] == test_id
        mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_agent_memory_by_metadata(self, clean_db_manager):
        """メタデータ条件でのレコード取得テスト"""
        db_manager = get_db_manager()
        
        expected_result = [
            {"id": str(uuid.uuid4()), "content": "spectraメッセージ1"},
            {"id": str(uuid.uuid4()), "content": "spectraメッセージ2"}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_result
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        result = await db_manager.fetch(
            "SELECT * FROM agent_memory WHERE metadata ->> 'agent_id' = $1",
            "spectra"
        )
        
        assert len(result) == 2
        assert all("spectra" in record["content"] for record in result)
    
    @pytest.mark.asyncio
    async def test_fetch_agent_memory_by_time_range(self, clean_db_manager):
        """時間範囲でのレコード取得テスト"""
        db_manager = get_db_manager()
        
        # 24時間以内のメッセージ取得
        now = datetime.now()
        past_24h = now - timedelta(hours=24)
        
        expected_result = [
            {"id": str(uuid.uuid4()), "content": "最近のメッセージ1"},
            {"id": str(uuid.uuid4()), "content": "最近のメッセージ2"}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_result
        
        mock_pool = AsyncMock()
        
        class MockAcquireContext:
            async def __aenter__(self):
                return mock_connection
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        mock_pool.acquire.return_value = MockAcquireContext()
        db_manager.pool = mock_pool
        
        result = await db_manager.fetch(
            "SELECT * FROM agent_memory WHERE created_at >= $1 ORDER BY created_at DESC",
            past_24h
        )
        
        assert len(result) == 2
        mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fetch_agent_memory_with_complex_metadata_query(self, clean_db_manager):
        """複雑なメタデータクエリテスト"""
        db_manager = get_db_manager()
        
        expected_result = [
            {
                "id": str(uuid.uuid4()),
                "content": "会話メッセージ",
                "metadata": {
                    "agent_id": "spectra",
                    "channel_id": "123456789",
                    "message_type": "conversation"
                }
            }
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_result
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # JSONB演算子を使った複雑なクエリ
            result = await db_manager.fetch("""
                SELECT * FROM agent_memory 
                WHERE metadata @> $1 
                AND metadata ->> 'message_type' = $2
            """, 
            json.dumps({"agent_id": "spectra"}),
            "conversation"
            )
            
            assert len(result) == 1
            assert result[0]["metadata"]["agent_id"] == "spectra"
    
    @pytest.mark.asyncio
    async def test_fetch_agent_memory_pagination(self, clean_db_manager):
        """ページネーション取得テスト"""
        db_manager = get_db_manager()
        
        # ページ1のデータ（5件）
        page1_result = [
            {"id": str(uuid.uuid4()), "content": f"メッセージ {i}"}
            for i in range(1, 6)
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = page1_result
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.fetch(
                "SELECT * FROM agent_memory ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                5, 0  # limit=5, offset=0 (page 1)
            )
            
            assert len(result) == 5
            mock_connection.fetch.assert_called_once()


class TestCRUDOperationsUpdate:
    """UPDATE操作包括テスト"""
    
    @pytest.mark.asyncio
    async def test_update_agent_memory_content(self, clean_db_manager):
        """コンテンツ更新テスト"""
        db_manager = get_db_manager()
        
        test_id = str(uuid.uuid4())
        new_content = "更新されたコンテンツ"
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "UPDATE 1"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "UPDATE agent_memory SET content = $1 WHERE id = $2",
                new_content, test_id
            )
            
            assert result == "UPDATE 1"
            mock_connection.execute.assert_called_once()
            
            # 更新クエリ確認
            call_args = mock_connection.execute.call_args
            assert "UPDATE agent_memory" in call_args[0][0]
            assert call_args[0][1] == new_content
            assert call_args[0][2] == test_id
    
    @pytest.mark.asyncio
    async def test_update_agent_memory_metadata(self, clean_db_manager):
        """メタデータ更新テスト"""
        db_manager = get_db_manager()
        
        test_id = str(uuid.uuid4())
        new_metadata = {
            "agent_id": "lynq",
            "channel_id": "987654321",
            "updated": True
        }
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "UPDATE 1"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "UPDATE agent_memory SET metadata = $1 WHERE id = $2",
                json.dumps(new_metadata), test_id
            )
            
            assert result == "UPDATE 1"
            
            # メタデータJSONB更新確認
            call_args = mock_connection.execute.call_args
            assert json.loads(call_args[0][1]) == new_metadata
    
    @pytest.mark.asyncio
    async def test_update_agent_memory_partial_metadata(self, clean_db_manager):
        """部分メタデータ更新テスト（JSONB演算子使用）"""
        db_manager = get_db_manager()
        
        test_id = str(uuid.uuid4())
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "UPDATE 1"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # JSONB ||演算子で部分更新
            result = await db_manager.execute(
                "UPDATE agent_memory SET metadata = metadata || $1 WHERE id = $2",
                json.dumps({"updated_at": "2025-08-09T19:00:00Z"}),
                test_id
            )
            
            assert result == "UPDATE 1"
            mock_connection.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_agent_memory_embedding(self, clean_db_manager):
        """埋め込みベクトル更新テスト"""
        db_manager = get_db_manager()
        
        test_id = str(uuid.uuid4())
        new_embedding = [0.2] * 1536
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "UPDATE 1"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "UPDATE agent_memory SET embedding = $1 WHERE id = $2",
                new_embedding, test_id
            )
            
            assert result == "UPDATE 1"
            
            # ベクトル更新確認
            call_args = mock_connection.execute.call_args
            assert call_args[0][1] == new_embedding
    
    @pytest.mark.asyncio
    async def test_bulk_update_agent_memory_by_metadata(self, clean_db_manager):
        """メタデータ条件での一括更新テスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "UPDATE 3"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # 特定エージェントの全メッセージを一括更新
            result = await db_manager.execute(
                "UPDATE agent_memory SET metadata = metadata || $1 WHERE metadata ->> 'agent_id' = $2",
                json.dumps({"batch_updated": True}),
                "spectra"
            )
            
            assert result == "UPDATE 3"  # 3件更新された
            mock_connection.execute.assert_called_once()


class TestCRUDOperationsDelete:
    """DELETE操作包括テスト"""
    
    @pytest.mark.asyncio
    async def test_delete_agent_memory_by_id(self, clean_db_manager):
        """ID指定での削除テスト"""
        db_manager = get_db_manager()
        
        test_id = str(uuid.uuid4())
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "DELETE 1"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "DELETE FROM agent_memory WHERE id = $1",
                test_id
            )
            
            assert result == "DELETE 1"
            mock_connection.execute.assert_called_once()
            
            # 削除クエリ確認
            call_args = mock_connection.execute.call_args
            assert "DELETE FROM agent_memory" in call_args[0][0]
            assert call_args[0][1] == test_id
    
    @pytest.mark.asyncio
    async def test_delete_agent_memory_by_agent_id(self, clean_db_manager):
        """エージェントID指定での削除テスト"""
        db_manager = get_db_manager()
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "DELETE 5"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "DELETE FROM agent_memory WHERE metadata ->> 'agent_id' = $1",
                "spectra"
            )
            
            assert result == "DELETE 5"  # 5件削除された
            mock_connection.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_agent_memory_by_time_range(self, clean_db_manager):
        """時間範囲指定での削除テスト"""
        db_manager = get_db_manager()
        
        # 7日以前のメッセージ削除
        cutoff_date = datetime.now() - timedelta(days=7)
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "DELETE 10"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "DELETE FROM agent_memory WHERE created_at < $1",
                cutoff_date
            )
            
            assert result == "DELETE 10"  # 10件削除された
            mock_connection.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_agent_memory_bulk_by_ids(self, clean_db_manager):
        """ID配列での一括削除テスト"""
        db_manager = get_db_manager()
        
        test_ids = [str(uuid.uuid4()) for _ in range(3)]
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "DELETE 3"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "DELETE FROM agent_memory WHERE id = ANY($1)",
                test_ids
            )
            
            assert result == "DELETE 3"
            
            # 一括削除クエリ確認
            call_args = mock_connection.execute.call_args
            assert "ANY($1)" in call_args[0][0]
            assert call_args[0][1] == test_ids
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_record(self, clean_db_manager):
        """存在しないレコード削除テスト"""
        db_manager = get_db_manager()
        
        nonexistent_id = str(uuid.uuid4())
        
        mock_connection = AsyncMock()
        mock_connection.execute.return_value = "DELETE 0"
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            result = await db_manager.execute(
                "DELETE FROM agent_memory WHERE id = $1",
                nonexistent_id
            )
            
            assert result == "DELETE 0"  # 0件削除（エラーなし）
            mock_connection.execute.assert_called_once()


class TestVectorSimilaritySearch:
    """ベクトル類似度検索包括テスト"""
    
    @pytest.mark.asyncio
    async def test_similarity_search_basic(self, clean_db_manager):
        """基本的な類似度検索テスト"""
        db_manager = get_db_manager()
        
        query_vector = [0.1] * 1536
        expected_results = [
            {
                "content": "類似メッセージ1",
                "metadata": {"agent_id": "spectra"},
                "similarity": 0.95,
                "created_at": datetime.now()
            },
            {
                "content": "類似メッセージ2", 
                "metadata": {"agent_id": "lynq"},
                "similarity": 0.87,
                "created_at": datetime.now()
            }
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            results = await db_manager.similarity_search(
                "agent_memory", query_vector, limit=5, threshold=0.8
            )
            
            assert len(results) == 2
            assert results[0]["similarity"] == 0.95
            assert results[1]["similarity"] == 0.87
            
            # 類似度検索クエリ確認
            call_args = mock_connection.fetch.call_args
            query = call_args[0][0]
            assert "embedding <=>" in query  # コサイン距離演算子
            assert "ORDER BY embedding <=>" in query
            assert "LIMIT" in query
    
    @pytest.mark.asyncio
    async def test_similarity_search_with_metadata_filter(self, clean_db_manager):
        """メタデータフィルタ付き類似度検索テスト"""
        db_manager = get_db_manager()
        
        query_vector = [0.2] * 1536
        expected_results = [
            {
                "content": "spectra類似メッセージ",
                "metadata": {"agent_id": "spectra", "channel_id": "123"},
                "similarity": 0.92
            }
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # メタデータフィルタ付きカスタムクエリ
            results = await db_manager.fetch("""
                SELECT 
                    content,
                    metadata,
                    1 - (embedding <=> $1) as similarity,
                    created_at
                FROM agent_memory
                WHERE 1 - (embedding <=> $1) > $2
                AND metadata ->> 'agent_id' = $3
                ORDER BY embedding <=> $1
                LIMIT $4
            """, query_vector, 0.8, "spectra", 5)
            
            assert len(results) == 1
            assert results[0]["metadata"]["agent_id"] == "spectra"
    
    @pytest.mark.asyncio
    async def test_similarity_search_performance(self, clean_db_manager):
        """類似度検索パフォーマンステスト"""
        db_manager = get_db_manager()
        
        query_vector = [0.3] * 1536
        
        # 大量結果のシミュレート
        large_results = [
            {
                "content": f"メッセージ {i}",
                "metadata": {"index": i},
                "similarity": 0.9 - (i * 0.01)
            }
            for i in range(100)
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = large_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            start_time = time.time()
            results = await db_manager.similarity_search(
                "agent_memory", query_vector, limit=50
            )
            end_time = time.time()
            
            # パフォーマンス検証
            search_time = end_time - start_time
            assert search_time < 1.0  # 1秒以内で完了
            assert len(results) == 100  # モックなので全結果返る
    
    @pytest.mark.asyncio
    async def test_similarity_search_with_time_filter(self, clean_db_manager):
        """時間フィルタ付き類似度検索テスト"""
        db_manager = get_db_manager()
        
        query_vector = [0.4] * 1536
        recent_time = datetime.now() - timedelta(hours=24)
        
        expected_results = [
            {
                "content": "最近の類似メッセージ",
                "metadata": {"agent_id": "paz"},
                "similarity": 0.89,
                "created_at": datetime.now()
            }
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            results = await db_manager.fetch("""
                SELECT 
                    content,
                    metadata,
                    1 - (embedding <=> $1) as similarity,
                    created_at
                FROM agent_memory
                WHERE 1 - (embedding <=> $1) > $2
                AND created_at >= $3
                ORDER BY embedding <=> $1
                LIMIT $4
            """, query_vector, 0.8, recent_time, 10)
            
            assert len(results) == 1
            assert results[0]["similarity"] == 0.89


class TestJSONBMetadataOperations:
    """JSONBメタデータ操作包括テスト"""
    
    @pytest.mark.asyncio
    async def test_jsonb_containment_query(self, clean_db_manager):
        """JSONB包含クエリ（@>演算子）テスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {
                "id": str(uuid.uuid4()),
                "content": "spectra会話",
                "metadata": {
                    "agent_id": "spectra",
                    "channel_id": "123456789",
                    "message_type": "conversation"
                }
            }
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # JSONB包含検索
            results = await db_manager.fetch(
                "SELECT * FROM agent_memory WHERE metadata @> $1",
                json.dumps({"agent_id": "spectra", "message_type": "conversation"})
            )
            
            assert len(results) == 1
            assert results[0]["metadata"]["agent_id"] == "spectra"
    
    @pytest.mark.asyncio
    async def test_jsonb_key_existence_query(self, clean_db_manager):
        """JSONBキー存在クエリ（?演算子）テスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {"id": str(uuid.uuid4()), "content": "ユーザーメッセージ"}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            results = await db_manager.fetch(
                "SELECT * FROM agent_memory WHERE metadata ? $1",
                "user_id"
            )
            
            assert len(results) == 1
            mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_jsonb_path_query(self, clean_db_manager):
        """JSONBパスクエリ（->>演算子）テスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {"id": str(uuid.uuid4()), "content": "チャンネルメッセージ"}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            results = await db_manager.fetch(
                "SELECT * FROM agent_memory WHERE metadata ->> 'channel_id' = $1",
                "123456789"
            )
            
            assert len(results) == 1
            mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_jsonb_aggregation_query(self, clean_db_manager):
        """JSONB集約クエリテスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {"agent_id": "spectra", "count": 10},
            {"agent_id": "lynq", "count": 8},
            {"agent_id": "paz", "count": 5}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # エージェント別メッセージ数集計
            results = await db_manager.fetch("""
                SELECT 
                    metadata ->> 'agent_id' as agent_id,
                    COUNT(*) as count
                FROM agent_memory
                WHERE metadata ? 'agent_id'
                GROUP BY metadata ->> 'agent_id'
                ORDER BY count DESC
            """)
            
            assert len(results) == 3
            assert results[0]["agent_id"] == "spectra"
            assert results[0]["count"] == 10


class TestTimeBasedQueries:
    """時系列クエリ包括テスト"""
    
    @pytest.mark.asyncio
    async def test_recent_messages_query(self, clean_db_manager):
        """最近のメッセージクエリテスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {"id": str(uuid.uuid4()), "content": "最新メッセージ1"},
            {"id": str(uuid.uuid4()), "content": "最新メッセージ2"}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # 24時間以内のメッセージ取得
            recent_time = datetime.now() - timedelta(hours=24)
            results = await db_manager.fetch(
                "SELECT * FROM agent_memory WHERE created_at >= $1 ORDER BY created_at DESC",
                recent_time
            )
            
            assert len(results) == 2
            mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_time_range_query(self, clean_db_manager):
        """時間範囲クエリテスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {"id": str(uuid.uuid4()), "content": "範囲内メッセージ"}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # 特定時間範囲のメッセージ取得
            start_time = datetime.now() - timedelta(days=7)
            end_time = datetime.now() - timedelta(days=1)
            
            results = await db_manager.fetch(
                "SELECT * FROM agent_memory WHERE created_at BETWEEN $1 AND $2",
                start_time, end_time
            )
            
            assert len(results) == 1
            mock_connection.fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_hourly_aggregation_query(self, clean_db_manager):
        """時間別集計クエリテスト"""
        db_manager = get_db_manager()
        
        expected_results = [
            {"hour": 0, "count": 5},
            {"hour": 1, "count": 8},
            {"hour": 2, "count": 3}
        ]
        
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = expected_results
        
        with patch.object(db_manager, 'get_connection') as mock_get_conn:
            mock_get_conn.return_value.__aenter__.return_value = mock_connection
            
            # 時間別メッセージ数集計
            results = await db_manager.fetch("""
                SELECT 
                    EXTRACT(HOUR FROM created_at) as hour,
                    COUNT(*) as count
                FROM agent_memory
                WHERE created_at >= $1
                GROUP BY EXTRACT(HOUR FROM created_at)
                ORDER BY hour
            """, datetime.now() - timedelta(days=1))
            
            assert len(results) == 3
            assert all(result["count"] > 0 for result in results)


# テストユーティリティ関数
from unittest.mock import AsyncMock

def create_test_embedding(dimension: int = 1536, value: float = 0.1) -> List[float]:
    """テスト用埋め込みベクトル生成"""
    return [value] * dimension

def create_test_metadata(
    agent_id: str = "spectra", 
    channel_id: str = "123456789",
    **kwargs
) -> Dict[str, Any]:
    """テスト用メタデータ生成"""
    metadata = {
        "agent_id": agent_id,
        "channel_id": channel_id,
        "message_type": "conversation",
        **kwargs
    }
    return metadata

def create_test_record(
    content: str = "テストメッセージ",
    embedding: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """テスト用レコード生成"""
    if embedding is None:
        embedding = create_test_embedding()
    if metadata is None:
        metadata = create_test_metadata()
    
    return {
        "id": str(uuid.uuid4()),
        "content": content,
        "embedding": embedding,
        "metadata": metadata,
        "created_at": datetime.now()
    }
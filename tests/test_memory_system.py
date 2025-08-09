"""
Test suite for OptimalMemorySystem

t-wada式TDD実装 - Red Phase
Phase 7: メモリシステム実装の包括的テストスイート

テスト対象:
- OptimalMemorySystem初期化・設定統合
- Redis短期記憶（RedisChatMessageHistory）
- PostgreSQL+pgvector長期記憶（PGVectorStore）
- メッセージ追加・取得・移行処理
- セマンティック検索機能
- 統計データ生成
- エラーハンドリング

Fail-Fast原則準拠、既存システム統合確認
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
from typing import List, Dict, Any

from app.core.memory import OptimalMemorySystem


class TestOptimalMemorySystemInitialization:
    """OptimalMemorySystem初期化テスト群"""
    
    @pytest.mark.asyncio
    async def test_memory_system_import(self):
        """OptimalMemorySystemクラスがインポートできることを確認"""
        assert OptimalMemorySystem is not None
    
    @pytest.mark.asyncio
    async def test_memory_system_initialization_with_settings(self):
        """設定統合による初期化テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings') as mock_embeddings, \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # Redis接続確認
            mock_redis.assert_called_once_with(
                session_id="discord_unified",
                redis_url="redis://test:6379",
                ttl=86400  # 24時間
            )
            
            # Gemini埋め込みサービス確認
            mock_embeddings.assert_called_once_with(
                model="models/gemini-embedding-001",
                google_api_key="test-api-key",
                client_options={"output_dimensionality": 1536}
            )
    
    @pytest.mark.asyncio
    async def test_memory_system_fail_fast_missing_redis_url(self):
        """Redis URL不足時のFail-Fast動作確認"""
        with patch('app.core.memory.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.database.redis_url = None
            mock_get_settings.return_value = mock_settings
            
            # Fail-Fast確認
            with pytest.raises((ValueError, TypeError)):
                OptimalMemorySystem()
    
    @pytest.mark.asyncio
    async def test_memory_system_fail_fast_missing_gemini_key(self):
        """Gemini APIキー不足時のFail-Fast動作確認"""
        with patch('app.core.memory.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = None
            mock_get_settings.return_value = mock_settings
            
            # Fail-Fast確認
            with pytest.raises((ValueError, TypeError)):
                OptimalMemorySystem()


class TestOptimalMemorySystemLongTermInitialization:
    """長期記憶初期化テスト群"""
    
    @pytest.mark.asyncio
    async def test_initialize_long_term_success(self):
        """長期記憶（PostgreSQL+pgvector）初期化成功テスト"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings, \
             patch('app.core.memory.PGEngine') as mock_engine, \
             patch('app.core.memory.PGVectorStore') as mock_vector_store:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.database.url = "postgresql://test:pass@localhost:5432/test"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            mock_pg_engine = MagicMock()
            mock_engine.from_connection_string.return_value = mock_pg_engine
            
            mock_store = MagicMock()
            mock_vector_store.create = AsyncMock(return_value=mock_store)
            
            # システム初期化と長期記憶セットアップ
            memory_system = OptimalMemorySystem()
            await memory_system.initialize_long_term()
            
            # PostgreSQL接続確認
            mock_engine.from_connection_string.assert_called_once_with(
                "postgresql://test:pass@localhost:5432/test"
            )
            
            # PGVectorStore作成確認
            mock_vector_store.create.assert_called_once_with(
                engine=mock_pg_engine,
                table_name="agent_memory",
                embedding_service=memory_system.embeddings,
                vector_dimension=1536
            )
            
            # 長期記憶設定確認
            assert memory_system.long_term == mock_store
    
    @pytest.mark.asyncio
    async def test_initialize_long_term_database_connection_error(self):
        """データベース接続エラー時のFail-Fast動作確認"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings, \
             patch('app.core.memory.PGEngine') as mock_engine:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.database.url = "postgresql://invalid"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            mock_engine.from_connection_string.side_effect = Exception("Database connection failed")
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # データベース接続エラー確認
            with pytest.raises(Exception, match="Database connection failed"):
                await memory_system.initialize_long_term()


class TestOptimalMemorySystemMessageOperations:
    """メッセージ操作テスト群"""
    
    @pytest.mark.asyncio
    async def test_add_message_success(self):
        """メッセージ追加成功テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings, \
             patch('app.core.memory.HumanMessage') as mock_message:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            
            mock_human_message = MagicMock()
            mock_message.return_value = mock_human_message
            
            # システム初期化とメッセージ追加
            memory_system = OptimalMemorySystem()
            await memory_system.add_message("Test message", "spectra", "command-center")
            
            # HumanMessage作成確認
            mock_message.assert_called_once()
            call_args = mock_message.call_args
            assert call_args[1]["content"] == "Test message"
            assert call_args[1]["additional_kwargs"]["agent"] == "spectra"
            assert call_args[1]["additional_kwargs"]["channel"] == "command-center"
            # タイムスタンプは現在時刻に近い値であることを確認
            timestamp_str = call_args[1]["additional_kwargs"]["timestamp"]
            timestamp = datetime.fromisoformat(timestamp_str)
            assert abs((datetime.now() - timestamp).total_seconds()) < 2
            
            # Redis追加確認
            mock_redis_instance.aadd_message.assert_called_once_with(mock_human_message)
    
    @pytest.mark.asyncio
    async def test_get_recent_context_success(self):
        """最近のコンテキスト取得成功テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # テストメッセージ作成
            mock_msg1 = MagicMock()
            mock_msg1.content = "Message 1"
            mock_msg1.additional_kwargs = {
                "agent": "spectra", 
                "channel": "command-center",
                "timestamp": "2025-08-09T10:00:00"
            }
            
            mock_msg2 = MagicMock()
            mock_msg2.content = "Message 2"
            mock_msg2.additional_kwargs = {
                "agent": "lynq",
                "channel": "creation", 
                "timestamp": "2025-08-09T10:01:00"
            }
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = [mock_msg1, mock_msg2]
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化とコンテキスト取得
            memory_system = OptimalMemorySystem()
            context = await memory_system.get_recent_context(limit=5)
            
            # 結果確認
            assert len(context) == 2
            assert context[0]["content"] == "Message 1"
            assert context[0]["agent"] == "spectra"
            assert context[0]["channel"] == "command-center"
            assert context[1]["content"] == "Message 2"
            assert context[1]["agent"] == "lynq"
            assert context[1]["channel"] == "creation"
    
    @pytest.mark.asyncio
    async def test_get_recent_context_with_limit(self):
        """制限付きコンテキスト取得テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # 複数メッセージ作成
            messages = []
            for i in range(10):
                mock_msg = MagicMock()
                mock_msg.content = f"Message {i}"
                mock_msg.additional_kwargs = {
                    "agent": "spectra",
                    "channel": "test",
                    "timestamp": f"2025-08-09T10:0{i:01d}:00"
                }
                messages.append(mock_msg)
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = messages
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化と制限付き取得
            memory_system = OptimalMemorySystem()
            context = await memory_system.get_recent_context(limit=3)
            
            # 結果確認（最新3件）
            assert len(context) == 3
            assert context[0]["content"] == "Message 7"  # messages[-3:]
            assert context[1]["content"] == "Message 8"
            assert context[2]["content"] == "Message 9"


class TestOptimalMemorySystemSemanticSearch:
    """セマンティック検索テスト群"""
    
    @pytest.mark.asyncio
    async def test_semantic_search_success(self):
        """セマンティック検索成功テスト"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings, \
             patch('app.core.memory.PGVectorStore') as mock_vector_store:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.database.url = "postgresql://test:pass@localhost:5432/test"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # 検索結果モック作成
            mock_doc1 = MagicMock()
            mock_doc1.page_content = "Test document 1"
            mock_doc1.metadata = {"agent": "spectra", "channel": "command-center", "score": 0.95}
            
            mock_doc2 = MagicMock()
            mock_doc2.page_content = "Test document 2"
            mock_doc2.metadata = {"agent": "lynq", "channel": "creation", "score": 0.87}
            
            mock_long_term = AsyncMock()
            mock_long_term.asimilarity_search.return_value = [mock_doc1, mock_doc2]
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            memory_system.long_term = mock_long_term
            
            # セマンティック検索実行
            results = await memory_system.semantic_search("test query", limit=5)
            
            # 検索実行確認
            mock_long_term.asimilarity_search.assert_called_once_with("test query", k=5)
            
            # 結果確認
            assert len(results) == 2
            assert results[0]["content"] == "Test document 1"
            assert results[0]["metadata"]["agent"] == "spectra"
            assert results[0]["similarity"] == 0.95
            assert results[1]["content"] == "Test document 2"
            assert results[1]["metadata"]["agent"] == "lynq"
            assert results[1]["similarity"] == 0.87
    
    @pytest.mark.asyncio
    async def test_semantic_search_no_long_term_initialized(self):
        """長期記憶未初期化時のセマンティック検索エラー"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # システム初期化（長期記憶未初期化）
            memory_system = OptimalMemorySystem()
            
            # long_termが未設定でのエラー確認
            with pytest.raises(AttributeError):
                await memory_system.semantic_search("test query")


class TestOptimalMemorySystemDailyMigration:
    """日報移行処理テスト群"""
    
    @pytest.mark.asyncio
    async def test_daily_report_migration_success(self):
        """日報移行処理成功テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings, \
             patch('app.core.memory.Document') as mock_document:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # テストメッセージ作成
            mock_msg1 = MagicMock()
            mock_msg1.content = "Daily message 1"
            mock_msg1.additional_kwargs = {
                "agent": "spectra",
                "channel": "command-center",
                "timestamp": "2025-08-09T10:00:00"
            }
            
            mock_msg2 = MagicMock()
            mock_msg2.content = "Daily message 2"
            mock_msg2.additional_kwargs = {
                "agent": "paz",
                "channel": "lounge",
                "timestamp": "2025-08-09T11:00:00"
            }
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = [mock_msg1, mock_msg2]
            mock_redis.return_value = mock_redis_instance
            
            mock_doc1 = MagicMock()
            mock_doc2 = MagicMock()
            mock_document.side_effect = [mock_doc1, mock_doc2]
            
            mock_long_term = AsyncMock()
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            memory_system.long_term = mock_long_term
            
            # 移行処理実行
            migrated_count = await memory_system.daily_report_migration()
            
            # Document作成確認
            assert mock_document.call_count == 2
            mock_document.assert_any_call(
                page_content="Daily message 1",
                metadata={
                    "agent": "spectra",
                    "channel": "command-center",
                    "timestamp": "2025-08-09T10:00:00"
                }
            )
            mock_document.assert_any_call(
                page_content="Daily message 2",
                metadata={
                    "agent": "paz",
                    "channel": "lounge",
                    "timestamp": "2025-08-09T11:00:00"
                }
            )
            
            # 長期記憶への保存確認
            mock_long_term.aadd_documents.assert_called_once_with([mock_doc1, mock_doc2])
            
            # 短期記憶クリア確認
            mock_redis_instance.clear.assert_called_once()
            
            # 返り値確認
            assert migrated_count == 2
    
    @pytest.mark.asyncio
    async def test_daily_report_migration_empty_messages(self):
        """空のメッセージでの移行処理テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = []  # 空のメッセージ
            mock_redis.return_value = mock_redis_instance
            
            mock_long_term = AsyncMock()
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            memory_system.long_term = mock_long_term
            
            # 移行処理実行
            migrated_count = await memory_system.daily_report_migration()
            
            # 長期記憶への保存が呼ばれないことを確認
            mock_long_term.aadd_documents.assert_not_called()
            
            # 短期記憶クリア確認
            mock_redis_instance.clear.assert_called_once()
            
            # 返り値確認
            assert migrated_count == 0


class TestOptimalMemorySystemStatistics:
    """統計データテスト群"""
    
    @pytest.mark.asyncio
    async def test_get_statistics_with_messages(self):
        """メッセージありでの統計データ取得テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # テストメッセージ作成
            messages = []
            # spectra: command-center x2, creation x1
            for i in range(2):
                msg = MagicMock()
                msg.additional_kwargs = {"agent": "spectra", "channel": "command-center"}
                messages.append(msg)
            
            msg = MagicMock()
            msg.additional_kwargs = {"agent": "spectra", "channel": "creation"}
            messages.append(msg)
            
            # lynq: creation x2
            for i in range(2):
                msg = MagicMock()
                msg.additional_kwargs = {"agent": "lynq", "channel": "creation"}
                messages.append(msg)
            
            # paz: lounge x1
            msg = MagicMock()
            msg.additional_kwargs = {"agent": "paz", "channel": "lounge"}
            messages.append(msg)
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = messages
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # 統計取得
            stats = await memory_system.get_statistics()
            
            # 統計確認
            assert stats["total"] == 6
            assert stats["by_channel"]["command-center"] == 2
            assert stats["by_channel"]["creation"] == 3  # spectra 1 + lynq 2
            assert stats["by_channel"]["lounge"] == 1
            assert stats["by_agent"]["spectra"] == 3  # command-center 2 + creation 1
            assert stats["by_agent"]["lynq"] == 2
            assert stats["by_agent"]["paz"] == 1
    
    @pytest.mark.asyncio
    async def test_get_statistics_empty_messages(self):
        """空のメッセージでの統計データ取得テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = []
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # 統計取得
            stats = await memory_system.get_statistics()
            
            # 空統計確認
            assert stats["total"] == 0
            assert stats["by_channel"] == {}
            assert stats["by_agent"] == {}
    
    @pytest.mark.asyncio
    async def test_get_statistics_missing_metadata(self):
        """メタデータ不足時の統計データ取得テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # メタデータ不足メッセージ作成
            msg1 = MagicMock()
            msg1.additional_kwargs = {"agent": "spectra"}  # channelなし
            
            msg2 = MagicMock()
            msg2.additional_kwargs = {"channel": "creation"}  # agentなし
            
            msg3 = MagicMock()
            msg3.additional_kwargs = {}  # 両方なし
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = [msg1, msg2, msg3]
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # 統計取得
            stats = await memory_system.get_statistics()
            
            # 不足メタデータ処理確認
            assert stats["total"] == 3
            assert stats["by_channel"]["unknown"] == 2  # msg1, msg3
            assert stats["by_channel"]["creation"] == 1  # msg2
            assert stats["by_agent"]["unknown"] == 2  # msg2, msg3  
            assert stats["by_agent"]["spectra"] == 1  # msg1


class TestOptimalMemorySystemErrorHandling:
    """エラーハンドリングテスト群"""
    
    @pytest.mark.asyncio
    async def test_redis_connection_error(self):
        """Redis接続エラーハンドリング"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://invalid:6379"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            mock_redis.side_effect = Exception("Redis connection failed")
            
            # Fail-Fast確認
            with pytest.raises(Exception, match="Redis connection failed"):
                OptimalMemorySystem()
    
    @pytest.mark.asyncio
    async def test_gemini_api_error(self):
        """Gemini API接続エラーハンドリング"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings') as mock_embeddings, \
             patch('app.core.memory.get_settings') as mock_get_settings:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.gemini.api_key = "invalid-key"
            mock_get_settings.return_value = mock_settings
            
            mock_embeddings.side_effect = Exception("Invalid API key")
            
            # Fail-Fast確認
            with pytest.raises(Exception, match="Invalid API key"):
                OptimalMemorySystem()


class TestOptimalMemorySystemIntegration:
    """システム統合テスト群"""
    
    @pytest.mark.asyncio
    async def test_full_workflow_integration(self):
        """完全ワークフロー統合テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.get_settings') as mock_get_settings, \
             patch('app.core.memory.PGEngine'), \
             patch('app.core.memory.PGVectorStore') as mock_vector_store, \
             patch('app.core.memory.HumanMessage') as mock_message, \
             patch('app.core.memory.Document') as mock_document:
            
            # モック設定
            mock_settings = MagicMock()
            mock_settings.database.redis_url = "redis://test:6379"
            mock_settings.database.url = "postgresql://test:pass@localhost:5432/test"
            mock_settings.gemini.api_key = "test-api-key"
            mock_get_settings.return_value = mock_settings
            
            # Redis モック
            mock_redis_instance = AsyncMock()
            mock_redis_instance.messages = []
            mock_redis.return_value = mock_redis_instance
            
            # PGVectorStore モック
            mock_store = AsyncMock()
            mock_vector_store.create = AsyncMock(return_value=mock_store)
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            await memory_system.initialize_long_term()
            
            # メッセージ追加
            await memory_system.add_message("Test integration", "spectra", "command-center")
            
            # 統計取得（空の場合）
            stats = await memory_system.get_statistics()
            assert stats["total"] == 0  # 実際のmessagesは空
            
            # モック呼び出し確認
            mock_redis_instance.aadd_message.assert_called_once()
            mock_vector_store.create.assert_called_once()
"""
Integration tests for OptimalMemorySystem with existing systems

Phase 7: メモリシステム統合テスト
既存システム（settings, database, report）との統合確認

統合テスト対象:
- settings.py: MemoryConfig統合確認
- database.py: PostgreSQL基盤との連携
- report.py: ModernReportGeneratorとの連携
- discord_manager: DiscordManager統合準備

t-wada式TDD - Refactor Phase: システム統合品質確保
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.core.memory import OptimalMemorySystem
from app.core.settings import get_settings, reset_settings
from app.core.report import ModernReportGenerator


class TestOptimalMemorySystemSettingsIntegration:
    """OptimalMemorySystemとsettings.pyの統合テスト"""
    
    def test_memory_system_uses_settings_redis_url(self):
        """設定からRedis URLを正しく取得することを確認"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'):
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            settings = get_settings()
            
            # 設定されたRedis URLが使用されることを確認
            mock_redis.assert_called_once_with(
                session_id="discord_unified",
                redis_url=settings.database.redis_url,
                ttl=86400
            )
    
    def test_memory_system_uses_settings_gemini_key(self):
        """設定からGemini APIキーを正しく取得することを確認"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings') as mock_embeddings:
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            settings = get_settings()
            
            # 設定されたGemini APIキーが使用されることを確認
            mock_embeddings.assert_called_once_with(
                model="models/gemini-embedding-001",
                google_api_key=settings.gemini.api_key,
                client_options={"output_dimensionality": 1536}
            )
    
    def test_memory_system_respects_memory_config(self):
        """MemoryConfig設定の活用確認"""
        settings = get_settings()
        
        # MemoryConfig設定確認
        assert hasattr(settings.memory, 'cleanup_hours')
        assert hasattr(settings.memory, 'recent_limit')
        assert settings.memory.cleanup_hours >= 1
        assert settings.memory.recent_limit >= 5


class TestOptimalMemorySystemDatabaseIntegration:
    """OptimalMemorySystemとdatabase.pyの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_memory_system_uses_database_url_for_long_term(self):
        """長期記憶初期化でdatabase URLを使用することを確認"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.PGEngine') as mock_engine, \
             patch('app.core.memory.PGVectorStore') as mock_vector_store:
            
            # モック設定
            mock_pg_engine = MagicMock()
            mock_engine.from_connection_string.return_value = mock_pg_engine
            mock_vector_store.create = AsyncMock()
            
            # システム初期化と長期記憶設定
            memory_system = OptimalMemorySystem()
            await memory_system.initialize_long_term()
            
            settings = get_settings()
            
            # database URLが使用されることを確認
            mock_engine.from_connection_string.assert_called_once_with(settings.database.url)
    
    @pytest.mark.asyncio
    async def test_memory_system_creates_agent_memory_table(self):
        """agent_memoryテーブルが正しく作成されることを確認"""
        with patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.PGEngine') as mock_engine, \
             patch('app.core.memory.PGVectorStore') as mock_vector_store:
            
            # モック設定
            mock_pg_engine = MagicMock()
            mock_engine.from_connection_string.return_value = mock_pg_engine
            mock_store = MagicMock()
            mock_vector_store.create = AsyncMock(return_value=mock_store)
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            await memory_system.initialize_long_term()
            
            # PGVectorStore作成確認
            mock_vector_store.create.assert_called_once_with(
                engine=mock_pg_engine,
                table_name="agent_memory",
                embedding_service=memory_system.embeddings,
                vector_dimension=1536
            )


class TestOptimalMemorySystemReportIntegration:
    """OptimalMemorySystemとreport.pyの統合テスト"""
    
    @pytest.mark.asyncio
    async def test_memory_statistics_compatible_with_report_data(self):
        """メモリ統計がレポートデータ形式と互換性があることを確認"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'):
            
            # テストメッセージ作成
            mock_msg1 = MagicMock()
            mock_msg1.additional_kwargs = {
                "agent": "spectra",
                "channel": "command-center"
            }
            
            mock_msg2 = MagicMock()
            mock_msg2.additional_kwargs = {
                "agent": "lynq", 
                "channel": "creation"
            }
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = [mock_msg1, mock_msg2]
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            stats = await memory_system.get_statistics()
            
            # レポートシステムが期待する形式であることを確認
            assert "total" in stats
            assert "by_channel" in stats
            assert "by_agent" in stats
            assert isinstance(stats["total"], int)
            assert isinstance(stats["by_channel"], dict)
            assert isinstance(stats["by_agent"], dict)
    
    @pytest.mark.asyncio
    async def test_memory_migration_count_for_report(self):
        """移行処理の戻り値がレポートで利用可能であることを確認"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.Document'):
            
            # テストメッセージ作成
            mock_msg = MagicMock()
            mock_msg.content = "Test message"
            mock_msg.additional_kwargs = {
                "agent": "spectra",
                "channel": "command-center",
                "timestamp": datetime.now().isoformat()
            }
            
            mock_redis_instance = MagicMock()
            mock_redis_instance.messages = [mock_msg, mock_msg, mock_msg]  # 3件
            mock_redis.return_value = mock_redis_instance
            
            mock_long_term = AsyncMock()
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            memory_system.long_term = mock_long_term
            
            # 移行処理実行
            migrated_count = await memory_system.daily_report_migration()
            
            # レポートで使用可能な数値であることを確認
            assert isinstance(migrated_count, int)
            assert migrated_count == 3


class TestOptimalMemorySystemChannelIntegration:
    """OptimalMemorySystemのDiscordチャンネル統合準備"""
    
    @pytest.mark.asyncio
    async def test_memory_system_supports_all_channels(self):
        """全Discordチャンネルのメッセージに対応することを確認"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.HumanMessage') as mock_message:
            
            # モック設定
            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            mock_human_message = MagicMock()
            mock_message.return_value = mock_human_message
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # 各チャンネルでのメッセージ追加テスト
            channels = ["command-center", "creation", "development", "lounge"]
            agents = ["spectra", "lynq", "paz"]
            
            for agent in agents:
                for channel in channels:
                    await memory_system.add_message(f"Test from {agent}", agent, channel)
            
            # 全ての組み合わせでメッセージが追加されることを確認
            assert mock_redis_instance.aadd_message.call_count == len(agents) * len(channels)
    
    @pytest.mark.asyncio 
    async def test_memory_system_metadata_completeness(self):
        """メタデータが完全であることを確認"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.HumanMessage') as mock_message:
            
            # モック設定
            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            mock_human_message = MagicMock()
            mock_message.return_value = mock_human_message
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            
            # メッセージ追加
            await memory_system.add_message("Test message", "spectra", "command-center")
            
            # メタデータの完全性確認
            call_args = mock_message.call_args
            metadata = call_args[1]["additional_kwargs"]
            
            # 必須フィールド確認
            assert "agent" in metadata
            assert "channel" in metadata  
            assert "timestamp" in metadata
            assert metadata["agent"] == "spectra"
            assert metadata["channel"] == "command-center"
            
            # タイムスタンプ形式確認
            timestamp = datetime.fromisoformat(metadata["timestamp"])
            assert isinstance(timestamp, datetime)


class TestOptimalMemorySystemWorkflowIntegration:
    """OptimalMemorySystemの完全ワークフロー統合テスト"""
    
    @pytest.mark.asyncio
    async def test_full_daily_workflow_integration(self):
        """日報生成ワークフロー全体の統合テスト"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.PGEngine'), \
             patch('app.core.memory.PGVectorStore') as mock_vector_store, \
             patch('app.core.memory.HumanMessage') as mock_message, \
             patch('app.core.memory.Document') as mock_document:
            
            # モック設定
            mock_redis_instance = AsyncMock()
            mock_redis_instance.messages = []  # 初期状態は空
            mock_redis.return_value = mock_redis_instance
            
            mock_store = AsyncMock()
            mock_vector_store.create = AsyncMock(return_value=mock_store)
            
            # システム初期化
            memory_system = OptimalMemorySystem()
            await memory_system.initialize_long_term()
            
            # 1. メッセージ追加フェーズ
            test_messages = [
                ("spectra", "command-center", "Daily standup completed"),
                ("lynq", "creation", "New design concepts ready"),
                ("paz", "lounge", "Team building activity planned")
            ]
            
            for agent, channel, content in test_messages:
                await memory_system.add_message(content, agent, channel)
            
            # メッセージが追加されたことを確認
            assert mock_redis_instance.aadd_message.call_count == 3
            
            # 2. 統計生成フェーズ
            # 実際のメッセージオブジェクト作成（統計用）
            mock_messages = []
            for agent, channel, content in test_messages:
                msg = MagicMock()
                msg.additional_kwargs = {"agent": agent, "channel": channel}
                mock_messages.append(msg)
            mock_redis_instance.messages = mock_messages
            
            stats = await memory_system.get_statistics()
            
            # 統計データ確認
            assert stats["total"] == 3
            assert stats["by_agent"]["spectra"] == 1
            assert stats["by_agent"]["lynq"] == 1
            assert stats["by_agent"]["paz"] == 1
            assert stats["by_channel"]["command-center"] == 1
            assert stats["by_channel"]["creation"] == 1
            assert stats["by_channel"]["lounge"] == 1
            
            # 3. 日報移行フェーズ
            # 移行用のメッセージオブジェクト作成
            mock_migration_messages = []
            for agent, channel, content in test_messages:
                msg = MagicMock()
                msg.content = content
                msg.additional_kwargs = {
                    "agent": agent,
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                }
                mock_migration_messages.append(msg)
            mock_redis_instance.messages = mock_migration_messages
            
            # 移行処理実行
            migrated_count = await memory_system.daily_report_migration()
            
            # 移行結果確認
            assert migrated_count == 3
            mock_store.aadd_documents.assert_called_once()
            mock_redis_instance.clear.assert_called_once()
            
            # Document作成確認
            assert mock_document.call_count == 3
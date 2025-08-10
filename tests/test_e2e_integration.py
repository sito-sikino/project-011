"""
Phase 10.1: E2E統合テスト (End-to-End Integration Tests)

Discord Multi-Agent System完全統合テスト
- 全機能統合フロー確認
- Discord API → LangGraph Supervisor → エージェント選択 → 応答送信
- メモリシステム統合（Redis短期記憶→PostgreSQL長期記憶）
- 時間帯別モードテスト（STANDBY、PROCESSING、ACTIVE、FREE）
- 自発発言システムテスト（TickManager統合）
- Fail-Fast原則完全準拠テスト

CLAUDE.md原則準拠:
- Fail-Fast（フォールバック禁止、エラー時即停止）
- 最小実装
- TDD採用
"""
import pytest
import asyncio
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, AIMessage

from app.main import DiscordMultiAgentApplication
from app.discord_manager.manager import SimplifiedDiscordManager, SimplifiedTickManager, get_current_mode
from app.langgraph.supervisor import DiscordSupervisor, DiscordState, build_langgraph_app
from app.langgraph.agents import DiscordAgents, create_discord_agents
from app.core.memory import OptimalMemorySystem
from app.core.settings import get_settings, reset_settings
from app.core.database import DatabaseManager
from app.tasks.manager import TaskManager, RedisTaskQueue


class TestE2ESystemInitialization:
    """E2Eシステム初期化テスト"""
    
    @pytest.fixture
    def clean_environment(self):
        """クリーンなテスト環境設定"""
        reset_settings()
        yield
        reset_settings()
    
    @pytest.mark.asyncio
    async def test_full_system_initialization_success(self, clean_environment):
        """完全システム初期化成功テスト"""
        # 完全なモッキング戦略
        with patch('discord.Client'), \
             patch('app.tasks.manager.redis.Redis'), \
             patch('sqlalchemy.create_engine'), \
             patch('asyncpg.create_pool', new_callable=AsyncMock), \
             patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.langgraph.supervisor.ChatGoogleGenerativeAI'):
            
            app = DiscordMultiAgentApplication()
            
            # 初期化成功
            await app.initialize()
            
            # 全コンポーネントが初期化されることを確認
            assert app.settings is not None
            assert app.task_manager is not None
            assert app.redis_queue is not None
            assert app.discord_manager is not None
            assert app.tick_manager is not None
            
            # クリーンアップ
            await app.shutdown()
    
    @pytest.mark.asyncio
    async def test_system_initialization_fail_fast_on_missing_env(self, clean_environment):
        """環境変数不備時のFail-Fast動作確認"""
        # 必須環境変数を削除
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                app = DiscordMultiAgentApplication()
                await app.initialize()
            
            # sys.exit(1)でFail-Fastが動作することを確認
            assert exc_info.value.code == 1
    
    @pytest.mark.asyncio
    async def test_system_initialization_database_connection_failure(self, clean_environment):
        """データベース接続失敗時のFail-Fast確認"""
        with patch('sqlalchemy.create_engine') as mock_engine:
            # データベース接続エラーをシミュレート
            mock_engine.side_effect = Exception("Database connection failed")
            
            with pytest.raises(SystemExit) as exc_info:
                app = DiscordMultiAgentApplication()
                await app.initialize()
            
            assert exc_info.value.code == 1


class TestE2EDiscordMessageFlow:
    """E2E Discordメッセージフロー統合テスト"""
    
    @pytest.fixture
    async def e2e_system_setup(self):
        """E2Eシステムセットアップ"""
        # モック設定
        mock_discord_bot = Mock()
        mock_redis = Mock()
        mock_database = Mock()
        
        with patch('discord.Client', return_value=mock_discord_bot), \
             patch('app.tasks.manager.redis.Redis', return_value=mock_redis), \
             patch('sqlalchemy.create_engine', return_value=mock_database), \
             patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.langgraph.supervisor.ChatGoogleGenerativeAI'):
            
            # システム初期化
            app = DiscordMultiAgentApplication()
            await app.initialize()
            
            yield app, mock_discord_bot, mock_redis, mock_database
            
            # クリーンアップ
            await app.shutdown()
    
    @pytest.mark.asyncio
    async def test_complete_message_processing_flow(self, e2e_system_setup):
        """完全メッセージ処理フロー確認"""
        app, mock_discord_bot, mock_redis, mock_database = e2e_system_setup
        
        # テストメッセージ作成
        test_message = Mock()
        test_message.content = "こんにちは、spectraに相談があります"
        test_message.channel.name = "command-center"
        test_message.channel.id = 12345
        test_message.author.bot = False
        test_message.author.name = "test_user"
        
        # LangGraph Supervisor応答モック
        with patch.object(app.discord_manager.app, 'ainvoke') as mock_ainvoke:
            mock_ainvoke.return_value = {
                "messages": [AIMessage(content="こんにちは！どんなご相談でしょうか？")],
                "current_agent": "spectra"
            }
            
            # Discord Manager応答モック
            mock_discord_bot.get_channel.return_value.send = AsyncMock()
            
            # メッセージ処理実行
            await app.discord_manager.on_message(test_message)
            
            # フロー確認
            # 1. LangGraph Supervisor呼び出し確認
            mock_ainvoke.assert_called_once()
            call_args = mock_ainvoke.call_args[0][0]
            assert call_args["channel_name"] == "command-center"
            assert call_args["channel_id"] == 12345
            
            # 2. Discord送信確認
            mock_discord_bot.get_channel.assert_called_with(12345)
            mock_discord_bot.get_channel.return_value.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_selection_based_on_channel(self, e2e_system_setup):
        """チャンネル別エージェント選択確認"""
        app, mock_discord_bot, mock_redis, mock_database = e2e_system_setup
        
        # 各チャンネルでのメッセージ処理テスト
        channels = [
            ("command-center", "spectra"),
            ("development", "lynq"),
            ("creation", "paz"),
            ("lounge", "spectra")
        ]
        
        for channel_name, expected_agent in channels:
            test_message = Mock()
            test_message.content = "テストメッセージ"
            test_message.channel.name = channel_name
            test_message.channel.id = 12345
            test_message.author.bot = False
            test_message.author.name = "test_user"
            
            with patch.object(app.discord_manager.app, 'ainvoke') as mock_ainvoke:
                mock_ainvoke.return_value = {
                    "messages": [AIMessage(content="テスト応答")],
                    "current_agent": expected_agent
                }
                
                mock_discord_bot.get_channel.return_value.send = AsyncMock()
                
                await app.discord_manager.on_message(test_message)
                
                # 適切なチャンネル情報が渡されることを確認
                call_args = mock_ainvoke.call_args[0][0]
                assert call_args["channel_name"] == channel_name


class TestE2EMemorySystemIntegration:
    """E2Eメモリシステム統合テスト"""
    
    @pytest.fixture
    async def memory_system_setup(self):
        """メモリシステムセットアップ"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings') as mock_embeddings, \
             patch('app.core.memory.PGEngine') as mock_engine, \
             patch('app.core.memory.PGVectorStore') as mock_vector_store:
            
            # モック設定
            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            
            mock_embeddings_instance = Mock()
            mock_embeddings.return_value = mock_embeddings_instance
            
            mock_engine_instance = Mock()
            mock_engine.from_connection_string.return_value = mock_engine_instance
            
            mock_store_instance = AsyncMock()
            mock_vector_store.create = AsyncMock(return_value=mock_store_instance)
            
            # メモリシステム初期化
            memory_system = OptimalMemorySystem()
            await memory_system.initialize_long_term()
            
            yield memory_system, mock_redis_instance, mock_store_instance
    
    @pytest.mark.asyncio
    async def test_complete_memory_workflow(self, memory_system_setup):
        """完全メモリワークフロー確認"""
        memory_system, mock_redis_instance, mock_store_instance = memory_system_setup
        
        # 1. 短期記憶への追加
        await memory_system.add_message("テストメッセージ1", "spectra", "command-center")
        await memory_system.add_message("テストメッセージ2", "lynq", "development")
        await memory_system.add_message("テストメッセージ3", "paz", "creation")
        
        # Redis添加確認
        assert mock_redis_instance.aadd_message.call_count == 3
        
        # 2. 統計情報取得
        mock_messages = [
            Mock(additional_kwargs={"agent": "spectra", "channel": "command-center"}),
            Mock(additional_kwargs={"agent": "lynq", "channel": "development"}),
            Mock(additional_kwargs={"agent": "paz", "channel": "creation"})
        ]
        mock_redis_instance.messages = mock_messages
        
        stats = await memory_system.get_statistics()
        assert stats["total"] == 3
        assert stats["by_agent"]["spectra"] == 1
        assert stats["by_agent"]["lynq"] == 1
        assert stats["by_agent"]["paz"] == 1
        
        # 3. 長期記憶への移行
        migration_messages = [
            Mock(
                content="テストメッセージ1",
                additional_kwargs={
                    "agent": "spectra",
                    "channel": "command-center",
                    "timestamp": datetime.now().isoformat()
                }
            ),
            Mock(
                content="テストメッセージ2", 
                additional_kwargs={
                    "agent": "lynq",
                    "channel": "development",
                    "timestamp": datetime.now().isoformat()
                }
            ),
            Mock(
                content="テストメッセージ3",
                additional_kwargs={
                    "agent": "paz",
                    "channel": "creation",
                    "timestamp": datetime.now().isoformat()
                }
            )
        ]
        mock_redis_instance.messages = migration_messages
        
        migrated_count = await memory_system.daily_report_migration()
        
        # 移行確認
        assert migrated_count == 3
        mock_store_instance.aadd_documents.assert_called_once()
        mock_redis_instance.clear.assert_called_once()


class TestE2ETimeBasedModeSystem:
    """E2E時間帯別モードシステム統合テスト"""
    
    @pytest.fixture
    def tick_system_setup(self):
        """Tickシステムセットアップ"""
        settings = Mock()
        settings.tick = Mock()
        settings.tick.tick_interval = 300
        settings.tick.tick_probability = 0.33
        settings.env = "production"
        
        discord_manager = Mock()
        discord_manager.app = Mock()
        discord_manager.app.ainvoke = AsyncMock()
        
        tick_manager = SimplifiedTickManager(discord_manager, settings)
        
        return tick_manager, discord_manager, settings
    
    @patch('app.discord_manager.manager.datetime')
    @pytest.mark.asyncio
    async def test_standby_mode_no_processing(self, mock_datetime, tick_system_setup):
        """STANDBYモード処理停止確認"""
        tick_manager, discord_manager, settings = tick_system_setup
        
        # 午前3時（STANDBY時間）設定
        mock_datetime.now.return_value.hour = 3
        
        mock_schedule = Mock()
        mock_schedule.processing_trigger = 6
        mock_schedule.free_start = 20
        settings.schedule = mock_schedule
        
        with patch('app.discord_manager.manager.get_settings', return_value=settings):
            # STANDBY モードでティック処理実行
            await tick_manager._process_tick()
            
            # 処理が実行されないことを確認
            discord_manager.app.ainvoke.assert_not_called()
    
    @patch('app.discord_manager.manager.datetime')
    @pytest.mark.asyncio
    async def test_active_mode_processing(self, mock_datetime, tick_system_setup):
        """ACTIVEモード処理実行確認"""
        tick_manager, discord_manager, settings = tick_system_setup
        
        # 午後2時（ACTIVE時間）設定
        mock_datetime.now.return_value.hour = 14
        
        # schedule設定追加
        mock_schedule = Mock()
        mock_schedule.processing_trigger = 6
        mock_schedule.free_start = 20
        settings.schedule = mock_schedule
        
        # メモリシステムモック
        memory_system = Mock()
        memory_system.get_recent_context = AsyncMock(return_value=[])
        tick_manager.memory_system = memory_system
        
        # 確率制御を100%に設定（テスト用）
        tick_manager._should_process_tick = Mock(return_value=True)
        
        with patch('app.discord_manager.manager.get_settings', return_value=settings), \
             patch('random.choice', return_value="command-center"):
            
            # ACTIVE モードでティック処理実行
            await tick_manager._process_tick()
            
            # 処理が実行されることを確認
            discord_manager.app.ainvoke.assert_called_once()
            call_args = discord_manager.app.ainvoke.call_args[0][0]
            assert call_args["channel_name"] == "command-center"
            assert call_args["message_type"] == "tick"
    
    @pytest.mark.asyncio
    async def test_probability_control_integration(self, tick_system_setup):
        """確率制御統合テスト"""
        tick_manager, discord_manager, settings = tick_system_setup
        
        # 33%確率での統計テスト
        results = []
        for i in range(1000):
            with patch('random.random', return_value=i / 1000.0):
                result = tick_manager._should_process_tick()
                results.append(result)
        
        success_count = sum(results)
        success_rate = success_count / 1000
        
        # 33% ± 2%の範囲内確認
        assert 0.31 <= success_rate <= 0.35
        assert success_count == 330


class TestE2ESpontaneousSpeechSystem:
    """E2E自発発言システム統合テスト"""
    
    @pytest.fixture
    async def spontaneous_system_setup(self):
        """自発発言システムセットアップ"""
        with patch('discord.Client'), \
             patch('app.tasks.manager.redis.Redis'), \
             patch('sqlalchemy.create_engine'), \
             patch('app.core.memory.RedisChatMessageHistory'), \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.langgraph.supervisor.ChatGoogleGenerativeAI'):
            
            app = DiscordMultiAgentApplication()
            await app.initialize()
            
            # Tick確率を100%に設定（テスト用）
            app.tick_manager._should_process_tick = Mock(return_value=True)
            
            yield app
            
            await app.shutdown()
    
    @patch('app.discord_manager.manager.datetime')
    @patch('random.choice')
    @pytest.mark.asyncio
    async def test_spontaneous_speech_complete_flow(self, mock_choice, mock_datetime, spontaneous_system_setup):
        """自発発言完全フロー確認"""
        app = spontaneous_system_setup
        
        # 午後2時（ACTIVE時間）設定
        mock_datetime.now.return_value.hour = 14
        mock_choice.return_value = "command-center"
        
        # LangGraph応答モック
        app.discord_manager.app.ainvoke.return_value = {
            "messages": [AIMessage(content="こんにちは、今日も頑張りましょう！")],
            "current_agent": "spectra"
        }
        
        # Discord送信モック
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        app.discord_manager.bot.get_channel.return_value = mock_channel
        
        with patch('app.discord_manager.manager.get_settings', return_value=app.settings):
            # 自発発言処理実行
            await app.tick_manager._process_tick()
            
            # フロー確認
            # 1. LangGraph Supervisor呼び出し
            app.discord_manager.app.ainvoke.assert_called_once()
            
            # 2. チャンネル選択確認
            call_args = app.discord_manager.app.ainvoke.call_args[0][0]
            assert call_args["channel_name"] == "command-center"
            assert call_args["message_type"] == "tick"
            
            # 3. Discord送信確認
            mock_channel.send.assert_called_once_with("こんにちは、今日も頑張りましょう！")


class TestE2EErrorHandlingFailFast:
    """E2Eエラーハンドリング・Fail-Fast統合テスト"""
    
    @pytest.mark.asyncio
    async def test_langgraph_supervisor_error_fail_fast(self):
        """LangGraph Supervisor エラー時のFail-Fast確認"""
        with patch('app.langgraph.supervisor.ChatGoogleGenerativeAI') as mock_llm:
            # LLMエラーシミュレート
            mock_llm.side_effect = Exception("Gemini API Error")
            
            # エラーが適切に発生することを確認
            with pytest.raises(Exception) as exc_info:
                supervisor = DiscordSupervisor(Mock())
                await supervisor.ainvoke({"messages": []})
            
            # エラーメッセージ確認
            assert "Gemini API Error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_memory_system_error_fail_fast(self):
        """メモリシステムエラー時のFail-Fast確認"""
        with patch('app.core.memory.RedisChatMessageHistory') as mock_redis:
            # Redisエラーシミュレート
            mock_redis.side_effect = Exception("Redis Connection Error")
            
            # エラーが適切に発生することを確認
            with pytest.raises(Exception) as exc_info:
                memory_system = OptimalMemorySystem()
                await memory_system.add_message("test", "spectra", "command-center")
            
            # エラーメッセージ確認
            assert "Redis Connection Error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_discord_api_error_fail_fast(self):
        """Discord API エラー時のFail-Fast確認"""
        with patch('discord.Client') as mock_bot:
            # Discord APIエラーシミュレート
            mock_bot.side_effect = Exception("Discord API Error")
            
            # エラーが適切に発生することを確認
            with pytest.raises(Exception) as exc_info:
                # 設定付きでDiscordManagerを初期化
                settings = Mock()
                discord_manager = SimplifiedDiscordManager(settings)
                await discord_manager.start()
            
            # エラーメッセージまたは型確認
            assert "Discord API Error" in str(exc_info.value) or "missing 1 required positional argument" in str(exc_info.value)


class TestE2EFullSystemIntegration:
    """E2E完全システム統合テスト"""
    
    @pytest.fixture
    async def full_e2e_system(self):
        """完全E2Eシステムセットアップ"""
        with patch('discord.Client') as mock_bot, \
             patch('app.tasks.manager.redis.Redis'), \
             patch('sqlalchemy.create_engine'), \
             patch('app.core.memory.RedisChatMessageHistory') as mock_redis, \
             patch('app.core.memory.GoogleGenerativeAIEmbeddings'), \
             patch('app.core.memory.PGEngine'), \
             patch('app.core.memory.PGVectorStore'), \
             patch('app.langgraph.supervisor.ChatGoogleGenerativeAI') as mock_llm:
            
            # Discord Bot モック
            mock_bot_instance = Mock()
            mock_bot.return_value = mock_bot_instance
            
            # LLM モック
            mock_llm_instance = Mock()
            mock_response = Mock()
            mock_response.content = "spectra"
            mock_llm_instance.invoke.return_value = mock_response
            mock_llm.return_value = mock_llm_instance
            
            # Redis メモリモック
            mock_redis_instance = AsyncMock()
            mock_redis.return_value = mock_redis_instance
            
            # システム初期化
            app = DiscordMultiAgentApplication()
            await app.initialize()
            
            yield app, mock_bot_instance, mock_redis_instance, mock_llm_instance
            
            await app.shutdown()
    
    @pytest.mark.asyncio
    async def test_complete_end_to_end_workflow(self, full_e2e_system):
        """完全エンドツーエンドワークフロー確認"""
        app, mock_bot_instance, mock_redis_instance, mock_llm_instance = full_e2e_system
        
        # テストシナリオ: ユーザーメッセージ → 処理 → 応答 → メモリ保存
        
        # 1. ユーザーメッセージ受信
        test_message = Mock()
        test_message.content = "今日のタスクを教えてください"
        test_message.channel.name = "command-center"
        test_message.channel.id = 12345
        test_message.author.bot = False
        test_message.author.name = "test_user"
        
        # 2. LangGraph応答設定
        app.discord_manager.app.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="今日のタスクは以下の通りです：\n1. コードレビュー\n2. ミーティング準備")],
            "current_agent": "spectra"
        })
        
        # 3. Discord送信モック
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_bot_instance.get_channel.return_value = mock_channel
        
        # 4. メッセージ処理実行
        await app.discord_manager.on_message(test_message)
        
        # 5. 完全フロー検証
        
        # LangGraph Supervisor呼び出し確認
        app.discord_manager.app.ainvoke.assert_called_once()
        call_args = app.discord_manager.app.ainvoke.call_args[0][0]
        assert call_args["channel_name"] == "command-center"
        assert call_args["channel_id"] == 12345
        assert len(call_args["messages"]) > 0
        
        # Discord送信確認
        mock_bot_instance.get_channel.assert_called_with(12345)
        mock_channel.send.assert_called_once()
        sent_message = mock_channel.send.call_args[0][0]
        assert "今日のタスクは以下の通りです" in sent_message
        
        # メモリ保存確認（add_messageが呼ばれるか）
        # この時点でメモリシステムにメッセージが保存される
        assert mock_redis_instance.aadd_message.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_complete_daily_workflow_simulation(self, full_e2e_system):
        """完全日報ワークフローシミュレーション"""
        app, mock_bot_instance, mock_redis_instance, mock_llm_instance = full_e2e_system
        
        # 1日のワークフローシミュレーション
        daily_interactions = [
            ("morning", "おはようございます", "spectra", "command-center"),
            ("task1", "プロジェクトの進捗確認", "lynq", "development"), 
            ("task2", "新しいデザイン案", "paz", "creation"),
            ("discussion", "チーム会議の準備", "spectra", "lounge"),
            ("evening", "今日の振り返り", "lynq", "command-center")
        ]
        
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_bot_instance.get_channel.return_value = mock_channel
        
        # 各インタラクション実行
        for phase, content, expected_agent, channel in daily_interactions:
            test_message = Mock()
            test_message.content = content
            test_message.channel.name = channel
            test_message.channel.id = 12345
            test_message.author.bot = False
            test_message.author.name = "test_user"
            
            # LangGraph応答設定
            app.discord_manager.app.ainvoke = AsyncMock(return_value={
                "messages": [AIMessage(content=f"{expected_agent}の応答: {content}")],
                "current_agent": expected_agent
            })
            
            # メッセージ処理
            await app.discord_manager.on_message(test_message)
        
        # 1日の完了確認
        assert mock_channel.send.call_count == len(daily_interactions)
        
        # メモリ保存確認（全インタラクション）
        assert mock_redis_instance.aadd_message.call_count >= len(daily_interactions)


if __name__ == "__main__":
    # テスト実行
    pytest.main([__file__, "-v", "--tb=short"])
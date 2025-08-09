"""
Discord Manager Tests for Discord Multi-Agent System

Phase 6: Discord Bot基盤実装
t-wada式TDD Red Phase - Discord Manager テスト作成

テスト範囲:
- SimplifiedDiscordManager初期化・接続
- 3つの独立Botクライアント管理
- メッセージ処理（キュー、エラー隔離）
- スラッシュコマンド処理
- OptimalMemorySystemとの連携
- LangGraph Supervisorとの統合
"""
import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from app.discord_manager.manager import (
    SimplifiedDiscordManager,
    SimplifiedTickManager,
    DiscordMessageProcessor,
    DiscordError,
    BotConnectionError,
    MessageProcessingError,
    SlashCommandProcessor
)
from app.core.settings import get_settings
from app.tasks.manager import TaskModel, TaskStatus, TaskPriority


class TestSimplifiedDiscordManager:
    """SimplifiedDiscordManager テストクラス"""
    
    @pytest.fixture
    async def mock_settings(self):
        """モック設定を作成"""
        settings = get_settings()
        settings.discord.spectra_token = "MOCK_SPECTRA_TOKEN"
        settings.discord.lynq_token = "MOCK_LYNQ_TOKEN" 
        settings.discord.paz_token = "MOCK_PAZ_TOKEN"
        settings.tick.tick_interval = 15  # テスト用に短縮
        settings.tick.tick_probability = 1.0  # テスト用に100%
        return settings
    
    @pytest.fixture
    def mock_discord_clients(self):
        """モック Discord クライアントを作成"""
        clients = {}
        for agent in ["spectra", "lynq", "paz"]:
            client = Mock()
            client.start = AsyncMock()
            client.close = AsyncMock()
            client.is_closed = Mock(return_value=False)
            client.get_channel = Mock()
            client.get_all_channels = Mock(return_value=[])
            clients[agent] = client
        return clients
    
    @pytest.fixture
    async def discord_manager(self, mock_settings, mock_discord_clients):
        """Discord Manager テスト用インスタンス"""
        with patch("app.discord_manager.manager.discord.Client") as mock_client_class:
            # クライアント生成時に mock_discord_clients を返すように設定
            mock_client_class.side_effect = lambda **kwargs: mock_discord_clients[
                list(mock_discord_clients.keys())[mock_client_class.call_count - 1]
            ]
            
            manager = SimplifiedDiscordManager(mock_settings)
            
            # モック設定
            manager.clients = mock_discord_clients
            manager.memory_system = AsyncMock()
            manager.app = AsyncMock()  # LangGraph app mock
            
            return manager
    
    def test_discord_manager_initialization(self, mock_settings):
        """Discord Manager 初期化テスト"""
        with patch("app.discord_manager.manager.discord.Client") as mock_client:
            manager = SimplifiedDiscordManager(mock_settings)
            
            # 基本属性確認
            assert manager.settings == mock_settings
            assert manager.primary_client == "spectra"
            assert len(manager.clients) == 3
            assert "spectra" in manager.clients
            assert "lynq" in manager.clients
            assert "paz" in manager.clients
            assert manager.running == False
            
            # Intents設定確認
            assert manager.intents.message_content == True
    
    def test_discord_manager_initialization_missing_tokens(self):
        """必須トークン不足時の初期化失敗テスト"""
        settings = get_settings()
        settings.discord.spectra_token = None
        
        with pytest.raises(BotConnectionError, match="Required Discord token missing"):
            SimplifiedDiscordManager(settings)
    
    async def test_discord_manager_startup(self, discord_manager, mock_discord_clients):
        """Discord Manager 起動テスト"""
        await discord_manager.start()
        
        # Primary client (Spectra) の start が呼ばれることを確認
        mock_discord_clients["spectra"].start.assert_called_once()
        assert discord_manager.running == True
    
    async def test_discord_manager_shutdown(self, discord_manager, mock_discord_clients):
        """Discord Manager 終了テスト"""
        discord_manager.running = True
        await discord_manager.close()
        
        # 全クライアントの close が呼ばれることを確認
        for client in mock_discord_clients.values():
            client.close.assert_called_once()
        assert discord_manager.running == False
    
    async def test_send_as_agent_success(self, discord_manager):
        """エージェント別送信テスト - 成功ケース"""
        # モックチャンネル設定
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_channel.name = "test-channel"
        discord_manager.clients["spectra"].get_channel.return_value = mock_channel
        
        # テスト実行
        await discord_manager.send_as_agent("spectra", 123456789, "Test message")
        
        # 送信確認
        mock_channel.send.assert_called_once_with("Test message")
        # メモリシステムへの記録確認
        discord_manager.memory_system.add_message.assert_called_once_with(
            content="Test message",
            agent="spectra",
            channel="test-channel"
        )
    
    async def test_send_as_agent_channel_not_found(self, discord_manager):
        """エージェント別送信テスト - チャンネル未発見ケース"""
        discord_manager.clients["spectra"].get_channel.return_value = None
        
        with pytest.raises(MessageProcessingError, match="Channel .+ not found"):
            await discord_manager.send_as_agent("spectra", 123456789, "Test message")
    
    async def test_send_as_agent_invalid_agent(self, discord_manager):
        """エージェント別送信テスト - 無効なエージェントケース"""
        with pytest.raises(MessageProcessingError, match="Invalid agent"):
            await discord_manager.send_as_agent("invalid_agent", 123456789, "Test message")
    
    def test_get_channel_id_success(self, discord_manager):
        """チャンネルID取得テスト - 成功ケース"""
        mock_channel = Mock()
        mock_channel.name = "command-center"
        mock_channel.id = 987654321
        
        discord_manager.clients["spectra"].get_all_channels.return_value = [mock_channel]
        
        result = discord_manager.get_channel_id("command-center")
        assert result == 987654321
    
    def test_get_channel_id_not_found(self, discord_manager):
        """チャンネルID取得テスト - 未発見ケース"""
        discord_manager.clients["spectra"].get_all_channels.return_value = []
        
        result = discord_manager.get_channel_id("nonexistent-channel")
        assert result is None


class TestDiscordMessageProcessor:
    """Discord メッセージ処理テストクラス"""
    
    @pytest.fixture
    async def message_processor(self):
        """メッセージプロセッサー テスト用インスタンス"""
        settings = get_settings()
        processor = DiscordMessageProcessor(settings)
        processor.memory_system = AsyncMock()
        processor.app = AsyncMock()  # LangGraph app mock
        return processor
    
    @pytest.fixture
    def mock_discord_message(self):
        """モック Discord メッセージ"""
        message = Mock()
        message.content = "Hello, test message"
        message.author.name = "test_user"
        message.author.bot = False
        message.channel.name = "test-channel"
        message.channel.id = 123456789
        return message
    
    async def test_process_message_user_input(self, message_processor, mock_discord_message):
        """ユーザーメッセージ処理テスト"""
        await message_processor.process_message(mock_discord_message)
        
        # メモリシステムへの記録確認
        message_processor.memory_system.add_message.assert_called_once_with(
            content="Hello, test message",
            agent="test_user",
            channel="test-channel"
        )
        
        # LangGraph app へのタスク送信確認
        message_processor.app.ainvoke.assert_called_once()
    
    async def test_process_message_bot_ignored(self, message_processor, mock_discord_message):
        """Bot メッセージの無視テスト"""
        mock_discord_message.author.bot = True
        
        await message_processor.process_message(mock_discord_message)
        
        # Bot メッセージは処理されない
        message_processor.memory_system.add_message.assert_not_called()
        message_processor.app.ainvoke.assert_not_called()
    
    async def test_process_message_error_isolation(self, message_processor, mock_discord_message):
        """メッセージ処理エラー隔離テスト"""
        # メモリシステムでエラーを発生させる
        message_processor.memory_system.add_message.side_effect = Exception("Memory error")
        
        # エラーが発生してもシステムは継続すること
        await message_processor.process_message(mock_discord_message)
        
        # LangGraph は呼ばれないが、システムは停止しない
        message_processor.app.ainvoke.assert_not_called()
    
    async def test_message_queue_fifo_processing(self, message_processor):
        """メッセージキューFIFO処理テスト"""
        # 複数メッセージを順次処理
        messages = []
        for i in range(3):
            message = Mock()
            message.content = f"Message {i}"
            message.author.name = "test_user"
            message.author.bot = False
            message.channel.name = "test-channel"
            messages.append(message)
        
        # メッセージを順次処理
        for message in messages:
            await message_processor.process_message(message)
        
        # 呼び出し順序確認（FIFO）
        assert message_processor.memory_system.add_message.call_count == 3
        calls = message_processor.memory_system.add_message.call_args_list
        for i, call in enumerate(calls):
            assert call[1]["content"] == f"Message {i}"


class TestSlashCommandProcessor:
    """スラッシュコマンド処理テストクラス"""
    
    @pytest.fixture
    def command_processor(self):
        """コマンドプロセッサー テスト用インスタンス"""
        settings = get_settings()
        processor = SlashCommandProcessor(settings)
        processor.task_manager = AsyncMock()
        return processor
    
    @pytest.fixture
    def mock_task_commit_interaction(self):
        """モック /task commit インタラクション"""
        interaction = Mock()
        interaction.command_name = "task"
        
        # オプションを正しく設定
        action_opt = Mock()
        action_opt.name = "action"
        action_opt.value = "commit"
        
        channel_opt = Mock()
        channel_opt.name = "channel"
        channel_opt.value = "creation"
        
        description_opt = Mock()
        description_opt.name = "description"
        description_opt.value = "Test task description"
        
        interaction.options = [action_opt, channel_opt, description_opt]
        interaction.response.send_message = AsyncMock()
        return interaction
    
    async def test_task_commit_new_task(self, command_processor, mock_task_commit_interaction):
        """/task commit 新規タスク作成テスト"""
        # task_managerが適切にモックされていることを確認
        assert command_processor.task_manager is not None
        
        # 既存タスクなし
        command_processor.task_manager.get_active_task.return_value = None
        
        # 新しいタスク作成をモック
        new_task = TaskModel(
            title="Discord Task",
            description="Test task description",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        command_processor.task_manager.create_task.return_value = new_task
        
        await command_processor.handle_slash_command(mock_task_commit_interaction)
        
        # タスク作成確認
        command_processor.task_manager.create_task.assert_called_once_with(
            title="Discord Task",
            description="Test task description",
            channel_id="creation"
        )
        
        # レスポンス確認
        mock_task_commit_interaction.response.send_message.assert_called_once()
    
    async def test_task_commit_update_existing(self, command_processor, mock_task_commit_interaction):
        """/task commit 既存タスク更新テスト"""
        # 既存タスクあり
        existing_task = TaskModel(
            id=uuid4(),
            title="Existing Task",
            description="Old description",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.MEDIUM
        )
        command_processor.task_manager.get_active_task.return_value = existing_task
        
        # タスク更新をモック
        updated_task = existing_task.model_copy(update={
            "description": "Test task description"
        })
        command_processor.task_manager.update_task.return_value = updated_task
        
        await command_processor.handle_slash_command(mock_task_commit_interaction)
        
        # タスク更新確認
        command_processor.task_manager.update_task.assert_called_once_with(
            task_id=existing_task.id,
            description="Test task description",
            channel_id="creation"
        )
    
    async def test_task_commit_invalid_channel(self, command_processor, mock_task_commit_interaction):
        """/task commit 無効なチャンネルテスト"""
        # 無効なチャンネル指定
        mock_task_commit_interaction.options[1].value = "invalid_channel"
        
        await command_processor.handle_slash_command(mock_task_commit_interaction)
        
        # エラーレスポンス確認
        mock_task_commit_interaction.response.send_message.assert_called_once()
        call_args = mock_task_commit_interaction.response.send_message.call_args
        assert "Invalid channel" in call_args.kwargs["content"]


class TestSimplifiedTickManager:
    """SimplifiedTickManager テストクラス"""
    
    @pytest.fixture
    def mock_discord_manager(self):
        """モック Discord Manager"""
        manager = Mock()
        manager.send_as_agent = AsyncMock()
        manager.app = AsyncMock()
        manager.get_channel_id = Mock(return_value=123456789)
        return manager
    
    @pytest.fixture
    def tick_manager(self, mock_discord_manager):
        """Tick Manager テスト用インスタンス"""
        settings = get_settings()
        settings.tick.tick_interval = 0.1  # テスト用に短縮
        manager = SimplifiedTickManager(mock_discord_manager, settings)
        manager.memory_system = AsyncMock()
        return manager
    
    async def test_tick_manager_initialization(self, tick_manager, mock_discord_manager):
        """Tick Manager 初期化テスト"""
        assert tick_manager.discord_manager == mock_discord_manager
        assert tick_manager.running == False
        assert tick_manager.settings.tick.tick_interval == 0.1
    
    @pytest.mark.asyncio
    async def test_tick_processing_active_mode(self, tick_manager):
        """アクティブモードでのティック処理テスト"""
        # アクティブモードをモック
        with patch("app.discord_manager.manager.get_current_mode", return_value="ACTIVE"):
            # 1回のティック処理を実行
            await tick_manager._process_tick()
            
            # LangGraph app が呼ばれることを確認
            tick_manager.discord_manager.app.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_tick_processing_standby_mode(self, tick_manager):
        """スタンバイモードでのティック処理テスト"""
        # スタンバイモードをモック
        with patch("app.discord_manager.manager.get_current_mode", return_value="STANDBY"):
            await tick_manager._process_tick()
            
            # 何も処理されないことを確認
            tick_manager.discord_manager.app.ainvoke.assert_not_called()
    
    async def test_daily_report_processing_mode(self, tick_manager):
        """日報処理モードテスト"""
        # 日報処理モードをモック
        with patch("app.discord_manager.manager.get_current_mode", return_value="PROCESSING"):
            # メモリシステム、レポート生成をモック
            tick_manager.memory_system.daily_archive_and_reset = AsyncMock()
            tick_manager.memory_system.get_recent_context = AsyncMock(return_value=[])
            
            with patch.object(tick_manager, "_generate_activity_summary_from_context") as mock_summary:
                mock_summary.return_value = "Daily summary test"
                
                await tick_manager._process_tick()
                
                # 日報処理が実行されることを確認
                tick_manager.memory_system.daily_archive_and_reset.assert_called_once()
                tick_manager.memory_system.get_recent_context.assert_called_once_with(limit=50)
                tick_manager.discord_manager.send_as_agent.assert_called_once()


class TestDiscordError:
    """Discord エラークラステスト"""
    
    def test_discord_error_hierarchy(self):
        """Discord エラー階層テスト"""
        # ベースエラー
        base_error = DiscordError("Base error")
        assert str(base_error) == "Base error"
        
        # 接続エラー
        connection_error = BotConnectionError("Connection failed")
        assert isinstance(connection_error, DiscordError)
        assert str(connection_error) == "Connection failed"
        
        # メッセージ処理エラー
        processing_error = MessageProcessingError("Processing failed")
        assert isinstance(processing_error, DiscordError)
        assert str(processing_error) == "Processing failed"


# Integration Tests
class TestDiscordIntegration:
    """Discord 統合テストクラス"""
    
    @pytest.mark.asyncio
    async def test_full_message_flow(self):
        """完全メッセージフロー統合テスト"""
        settings = get_settings()
        settings.discord.spectra_token = "MOCK_TOKEN"
        settings.discord.lynq_token = "MOCK_TOKEN"
        settings.discord.paz_token = "MOCK_TOKEN"
        
        with patch("app.discord_manager.manager.discord.Client") as mock_client:
            manager = SimplifiedDiscordManager(settings)
            
            # モック設定
            manager.memory_system = AsyncMock()
            manager.app = AsyncMock()
            
            # メッセージ作成
            message = Mock()
            message.content = "Test integration message"
            message.author.name = "integration_user"
            message.author.bot = False
            message.channel.name = "integration-test"
            message.channel.id = 999999999
            
            # メッセージ処理実行
            processor = DiscordMessageProcessor(settings)
            processor.memory_system = manager.memory_system
            processor.app = manager.app
            
            await processor.process_message(message)
            
            # 統合確認
            manager.memory_system.add_message.assert_called_once()
            manager.app.ainvoke.assert_called_once()
    
    @pytest.mark.asyncio  
    async def test_task_command_integration(self):
        """タスクコマンド統合テスト"""
        settings = get_settings()
        
        # コマンドプロセッサー作成
        processor = SlashCommandProcessor(settings)
        processor.task_manager = AsyncMock()
        
        # インタラクション作成
        interaction = Mock()
        interaction.command_name = "task"
        
        # オプションを正しく設定
        action_opt = Mock()
        action_opt.name = "action"
        action_opt.value = "commit"
        
        channel_opt = Mock()
        channel_opt.name = "channel" 
        channel_opt.value = "development"
        
        description_opt = Mock()
        description_opt.name = "description"
        description_opt.value = "Integration test task"
        
        interaction.options = [action_opt, channel_opt, description_opt]
        interaction.response.send_message = AsyncMock()
        
        # 既存タスクなし
        processor.task_manager.get_active_task.return_value = None
        
        # 新しいタスク作成
        new_task = TaskModel(
            title="Discord Task",
            description="Integration test task",
            status=TaskStatus.PENDING,
            priority=TaskPriority.MEDIUM
        )
        processor.task_manager.create_task.return_value = new_task
        
        # コマンド実行
        await processor.handle_slash_command(interaction)
        
        # 統合確認
        processor.task_manager.create_task.assert_called_once()
        interaction.response.send_message.assert_called_once()
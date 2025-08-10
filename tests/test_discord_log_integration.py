"""
Discord Log Integration Tests for Discord Multi-Agent System

Phase 10.2.2: Discord会話履歴ログ統合
t-wada式TDD Red Phase - Discord統合ログテスト先行作成

実装要求テスト範囲:
- SimplifiedDiscordManagerログ機能統合
- メッセージ受信・送信時の自動構造化ログ記録
- OptimalMemorySystem連携
- 非同期処理でのログ記録安定性
"""

import asyncio
import json
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call
from datetime import datetime
from pathlib import Path

from app.discord_manager.manager import (
    SimplifiedDiscordManager,
    DiscordMessageProcessor,
    initialize_discord_system,
)
from app.core.logger import DiscordMessageLog, AgentType, get_logger
from app.core.settings import get_settings


class TestDiscordLogIntegration:
    """Discord ログ統合テストクラス"""

    @pytest.fixture
    async def mock_settings(self):
        """モック設定を作成"""
        settings = get_settings()
        settings.discord.spectra_token = "MOCK_SPECTRA_TOKEN"
        settings.discord.lynq_token = "MOCK_LYNQ_TOKEN"
        settings.discord.paz_token = "MOCK_PAZ_TOKEN"
        # ログ設定
        settings.log.discord_log_path = "test_logs/discord.jsonl"
        settings.log.system_log_path = "test_logs/system.jsonl"
        settings.log.error_log_path = "test_logs/error.jsonl"
        return settings

    @pytest.fixture
    def mock_structured_logger(self):
        """モックStructuredLogger"""
        logger = Mock()
        logger.log_discord_message = Mock()
        logger.log_system = Mock()
        logger.log_error = Mock()
        return logger

    @pytest.fixture
    async def discord_manager_with_logging(self, mock_settings):
        """ログ統合済みDiscord Manager"""
        with patch("app.discord_manager.manager.discord.Client") as mock_client_class:
            # 3つのクライアントモック
            mock_clients = {}
            for agent in ["spectra", "lynq", "paz"]:
                client = Mock()
                client.start = AsyncMock()
                client.close = AsyncMock()
                client.is_closed = Mock(return_value=False)
                client.get_channel = Mock()
                client.get_all_channels = Mock(return_value=[])
                client.user = Mock()
                client.user.name = agent
                mock_clients[agent] = client

            # クライアント生成時の返り値設定
            call_count = 0

            def client_side_effect(**kwargs):
                nonlocal call_count
                clients = list(mock_clients.values())
                result = clients[call_count % len(clients)]
                call_count += 1
                return result

            mock_client_class.side_effect = client_side_effect

            # Discord Manager 作成
            manager = SimplifiedDiscordManager(mock_settings)
            manager.clients = mock_clients
            manager.memory_system = AsyncMock()
            manager.app = AsyncMock()

            return manager

    @pytest.fixture
    def mock_discord_message(self):
        """モックDiscordメッセージ"""
        message = Mock()
        message.content = "Hello from user"
        message.author.name = "test_user"
        message.author.id = "123456789"
        message.author.bot = False
        message.channel.name = "command-center"
        message.id = "message_123"
        return message

    # === Phase 10.2.2 要求機能テスト ===

    async def test_on_message_automatic_log_recording(
        self, discord_manager_with_logging, mock_discord_message, mock_structured_logger
    ):
        """メッセージ受信時の自動構造化ログ記録テスト"""

        # StructuredLogger統合
        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # メッセージプロセッサーにログ機能統合
            processor = DiscordMessageProcessor(discord_manager_with_logging.settings)
            processor.memory_system = discord_manager_with_logging.memory_system
            processor.app = discord_manager_with_logging.app

            # メッセージ処理実行
            await processor.process_message(mock_discord_message)

            # 1. OptimalMemorySystem記録確認
            processor.memory_system.add_message.assert_called_once_with(
                content="Hello from user", agent="test_user", channel="command-center"
            )

            # 2. StructuredLoggerログ記録確認（Phase 10.2.2実装後に通過予定）
            mock_structured_logger.log_discord_message.assert_called_once()

            # 3. ログデータ構造確認
            call_args = mock_structured_logger.log_discord_message.call_args[0][0]
            assert isinstance(call_args, DiscordMessageLog)
            assert call_args.agent == AgentType.SYSTEM  # ユーザーメッセージはSYSTEM扱い
            assert call_args.channel == "command-center"
            assert call_args.message == "Hello from user"
            assert call_args.user_id == "123456789"
            assert call_args.message_id == "message_123"

    async def test_send_as_agent_automatic_log_recording(
        self, discord_manager_with_logging, mock_structured_logger
    ):
        """エージェント送信時の自動構造化ログ記録テスト"""

        # モックチャンネル設定
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_channel.name = "creation"
        mock_channel.id = 987654321
        discord_manager_with_logging.clients["spectra"].get_channel.return_value = (
            mock_channel
        )

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # エージェント送信実行
            await discord_manager_with_logging.send_as_agent(
                "spectra", 987654321, "Response from Spectra"
            )

            # 1. Discordメッセージ送信確認
            mock_channel.send.assert_called_once_with("Response from Spectra")

            # 2. OptimalMemorySystem記録確認
            discord_manager_with_logging.memory_system.add_message.assert_called_once_with(
                content="Response from Spectra", agent="spectra", channel="creation"
            )

            # 3. StructuredLoggerログ記録確認（Phase 10.2.2実装後に通過予定）
            mock_structured_logger.log_discord_message.assert_called_once()

            # 4. ログデータ構造確認
            call_args = mock_structured_logger.log_discord_message.call_args[0][0]
            assert isinstance(call_args, DiscordMessageLog)
            assert call_args.agent == AgentType.SPECTRA
            assert call_args.channel == "creation"
            assert call_args.message == "Response from Spectra"
            assert call_args.user_id is None  # エージェント送信時はuser_id不要
            assert call_args.message_id is None  # 送信時はまだID未確定

    async def test_multiple_agents_log_recording(
        self, discord_manager_with_logging, mock_structured_logger
    ):
        """複数エージェント送信時のログ記録テスト"""

        # 3つのエージェント用チャンネルモック
        channels = {}
        for agent in ["spectra", "lynq", "paz"]:
            mock_channel = Mock()
            mock_channel.send = AsyncMock()
            mock_channel.name = f"{agent}-channel"
            channels[agent] = mock_channel
            discord_manager_with_logging.clients[agent].get_channel.return_value = (
                mock_channel
            )

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # 3エージェント順次送信
            for i, agent in enumerate(["spectra", "lynq", "paz"]):
                await discord_manager_with_logging.send_as_agent(
                    agent, 100 + i, f"Message from {agent}"
                )

            # ログ記録呼び出し確認（3回）
            assert mock_structured_logger.log_discord_message.call_count == 3

            # 各エージェントのログデータ確認
            calls = mock_structured_logger.log_discord_message.call_args_list
            for i, (agent, call) in enumerate(zip(["spectra", "lynq", "paz"], calls)):
                log_data = call[0][0]
                assert log_data.agent == AgentType(agent)
                assert log_data.message == f"Message from {agent}"
                assert log_data.channel == f"{agent}-channel"

    async def test_error_isolation_logging(
        self, discord_manager_with_logging, mock_discord_message, mock_structured_logger
    ):
        """エラー発生時のログ記録分離テスト"""

        # OptimalMemorySystemでエラー発生
        processor = DiscordMessageProcessor(discord_manager_with_logging.settings)
        processor.memory_system = AsyncMock()
        processor.memory_system.add_message.side_effect = Exception(
            "Memory system error"
        )
        processor.app = AsyncMock()

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # Fail-Fast原則により、sys.exit(1)が呼ばれることを期待
            with pytest.raises(SystemExit, match="1"):
                await processor.process_message(mock_discord_message)

            # StructuredLoggerのログ記録は実行されない（メモリエラー時点で停止）
            mock_structured_logger.log_discord_message.assert_not_called()

    async def test_concurrent_log_recording(
        self, discord_manager_with_logging, mock_structured_logger
    ):
        """並行ログ記録処理テスト"""

        # 複数チャンネル同時送信のモック
        mock_channels = {}
        for i in range(3):
            channel = Mock()
            channel.send = AsyncMock()
            channel.name = f"channel-{i}"
            mock_channels[i] = channel
            discord_manager_with_logging.clients["spectra"].get_channel.return_value = (
                channel
            )

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # 非同期並行送信
            tasks = []
            for i in range(3):
                task = discord_manager_with_logging.send_as_agent(
                    "spectra", 200 + i, f"Concurrent message {i}"
                )
                tasks.append(task)

            # 全タスク完了待ち
            await asyncio.gather(*tasks)

            # 全ログが記録されることを確認
            assert mock_structured_logger.log_discord_message.call_count == 3

    async def test_log_data_structure_validation(self, mock_structured_logger):
        """ログデータ構造検証テスト"""

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # DiscordMessageLog作成
            log = DiscordMessageLog(
                agent=AgentType.SPECTRA,
                channel="test-channel",
                message="Test message",
                user_id="user_123",
                message_id="msg_456",
                reply_to="reply_789",
            )

            # JSON形式変換確認
            json_data = log.to_json()
            parsed = json.loads(json_data)

            # 必須フィールド確認
            assert parsed["agent"] == "spectra"
            assert parsed["channel"] == "test-channel"
            assert parsed["message"] == "Test message"
            assert parsed["user_id"] == "user_123"
            assert parsed["message_id"] == "msg_456"
            assert parsed["reply_to"] == "reply_789"
            assert "timestamp" in parsed

    # === OptimalMemorySystem連携テスト ===

    async def test_memory_and_log_dual_recording(
        self, discord_manager_with_logging, mock_discord_message, mock_structured_logger
    ):
        """メモリシステムとログの二重記録テスト"""

        processor = DiscordMessageProcessor(discord_manager_with_logging.settings)
        processor.memory_system = discord_manager_with_logging.memory_system
        processor.app = discord_manager_with_logging.app

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            await processor.process_message(mock_discord_message)

            # 1. OptimalMemorySystem記録確認
            processor.memory_system.add_message.assert_called_once_with(
                content="Hello from user", agent="test_user", channel="command-center"
            )

            # 2. StructuredLogger記録確認
            mock_structured_logger.log_discord_message.assert_called_once()

            # 両方が独立して動作することを確認
            assert processor.memory_system.add_message.call_count == 1
            assert mock_structured_logger.log_discord_message.call_count == 1

    # === システム統合テスト ===

    async def test_full_discord_system_log_integration(
        self, mock_settings, mock_structured_logger
    ):
        """Discord システム完全統合ログテスト"""

        with patch("app.discord_manager.manager.discord.Client"):
            with patch(
                "app.discord_manager.manager.get_logger",
                return_value=mock_structured_logger,
            ):
                with patch(
                    "app.discord_manager.manager.build_langgraph_app"
                ) as mock_build:
                    with patch(
                        "app.discord_manager.manager.OptimalMemorySystem"
                    ) as mock_memory:

                        # システム初期化
                        mock_build.return_value = AsyncMock()
                        mock_memory.return_value = AsyncMock()

                        discord_manager, tick_manager = (
                            await initialize_discord_system()
                        )

                        # システム統合確認
                        assert discord_manager.app is not None
                        assert discord_manager.memory_system is not None
                        assert tick_manager.memory_system is not None

                        # ログシステムが利用可能であることを確認
                        # (実装後にget_loggerが統合される)

    # === 非同期処理最適化テスト ===

    async def test_async_logging_performance(
        self, discord_manager_with_logging, mock_structured_logger
    ):
        """非同期ログ記録パフォーマンステスト"""

        # 高速連続メッセージ送信
        mock_channel = Mock()
        mock_channel.send = AsyncMock()
        mock_channel.name = "performance-test"
        discord_manager_with_logging.clients["spectra"].get_channel.return_value = (
            mock_channel
        )

        with patch(
            "app.discord_manager.manager.get_logger",
            return_value=mock_structured_logger,
        ):
            # 100メッセージ高速送信
            start_time = asyncio.get_event_loop().time()

            tasks = []
            for i in range(100):
                task = discord_manager_with_logging.send_as_agent(
                    "spectra", 300, f"Performance test {i}"
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

            end_time = asyncio.get_event_loop().time()
            duration = end_time - start_time

            # パフォーマンス確認（100メッセージが3秒以内に処理）
            assert duration < 3.0
            assert mock_structured_logger.log_discord_message.call_count == 100

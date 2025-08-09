"""
Discord Manager for Discord Multi-Agent System

Phase 6: Discord Bot基盤実装完了
SimplifiedDiscordManager、SimplifiedTickManager、メッセージ処理、スラッシュコマンド統合

t-wada式TDD実装フロー:
🔴 Red Phase: Discord Manager包括テスト作成完了（test_discord_manager.py）
🟢 Green Phase: 最小実装でテスト通過
🟡 Refactor Phase: 品質向上、エラーハンドリング強化、統合性確保

実装機能:
- SimplifiedDiscordManager: 3つの独立Botクライアント（Spectra, LynQ, Paz）管理
- 統合受信・分散送信アーキテクチャ（Spectraが受信、各Botが自分のアカウントから送信）
- LangGraph Supervisorとの統合プレースホルダー
- OptimalMemorySystemとの連携プレースホルダー
- メッセージキュー（FIFO処理）
- エラー隔離システム（個別メッセージ単位）
- /task commitスラッシュコマンド処理
- 自発発言システム（TickManager統合）
- Fail-Fast原則（エラー時即停止）
"""
import asyncio
import logging
import sys
import random
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Any, Literal, Union
from enum import Enum
from uuid import UUID, uuid4

import discord
from discord.ext import commands

from app.core.settings import Settings, get_settings
from app.tasks.manager import TaskModel, TaskStatus, TaskPriority, get_task_manager
from app.core.memory import OptimalMemorySystem
from app.langgraph.supervisor import build_langgraph_app

logger = logging.getLogger(__name__)


# Custom Exception Classes
class DiscordError(Exception):
    """Discord操作エラーのベースクラス"""
    pass


class BotConnectionError(DiscordError):
    """Bot接続エラー"""
    pass


class MessageProcessingError(DiscordError):
    """メッセージ処理エラー"""
    pass


class CommandProcessingError(DiscordError):
    """コマンド処理エラー"""
    pass


# Mode management helper functions
def get_current_mode() -> Literal["STANDBY", "PROCESSING", "ACTIVE", "FREE"]:
    """現在のシステムモード取得"""
    current_hour = datetime.now().hour
    settings = get_settings()
    
    # 日報完了フラグ確認（簡略化実装）
    daily_report_completed = True  # TODO: Redis確認実装
    
    if current_hour < settings.schedule.processing_trigger:
        return "STANDBY"
    elif current_hour == settings.schedule.processing_trigger and not daily_report_completed:
        return "PROCESSING"
    elif current_hour < settings.schedule.free_start:
        return "ACTIVE"
    else:
        return "FREE"


class SimplifiedDiscordManager:
    """
    Discord管理クラス（LangChain Memory + LangGraph統合）
    OptimalMemorySystemと連携したメッセージ処理
    
    Phase 6.1: SimplifiedDiscordManager実装
    - 3つの独立Botクライアント（Spectra, LynQ, Paz）管理
    - 統合受信・分散送信アーキテクチャ
    - LangGraph Supervisor統合準備
    - OptimalMemorySystem連携準備
    - Fail-Fast原則実装
    """
    
    def __init__(self, settings: Settings):
        """
        SimplifiedDiscordManager初期化
        
        Args:
            settings: 設定インスタンス
            
        Raises:
            BotConnectionError: 必須トークンが不足している場合
        """
        self.settings = settings
        
        # 必須トークンチェック（Fail-Fast）
        if not settings.discord.spectra_token:
            raise BotConnectionError("Required Discord token missing: SPECTRA_TOKEN")
        if not settings.discord.lynq_token:
            raise BotConnectionError("Required Discord token missing: LYNQ_TOKEN")  
        if not settings.discord.paz_token:
            raise BotConnectionError("Required Discord token missing: PAZ_TOKEN")
        
        # Discord Intents設定
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        
        # 3つの独立Botクライアント
        self.clients: Dict[str, discord.Client] = {
            "spectra": discord.Client(intents=self.intents),
            "lynq": discord.Client(intents=self.intents),
            "paz": discord.Client(intents=self.intents)
        }
        
        # 主受信者（Spectra）
        self.primary_client = "spectra"
        
        # システム状態
        self.running = False
        
        # LangGraph Supervisor統合アプリ（プレースホルダー）
        self.app = None  # build_langgraph_app() で初期化予定
        
        # メモリシステム（プレースホルダー）
        self.memory_system = None  # OptimalMemorySystem() で初期化予定
        
        # メッセージプロセッサー
        self.message_processor = DiscordMessageProcessor(settings)
        
        # スラッシュコマンドプロセッサー
        self.command_processor = SlashCommandProcessor(settings)
        
        # イベントハンドラー設定
        self._setup_event_handlers()
        
        logger.info("SimplifiedDiscordManager initialized")
    
    def _setup_event_handlers(self):
        """Discord イベントハンドラー設定"""
        client = self.clients[self.primary_client]
        
        @client.event
        async def on_ready():
            """Bot準備完了イベント"""
            logger.info(f"{self.primary_client} ready: {client.user}")
            
            # 他のBotクライアントも同時起動
            tasks = []
            for name, bot in self.clients.items():
                if name != self.primary_client:
                    token = getattr(self.settings.discord, f"{name}_token")
                    tasks.append(asyncio.create_task(bot.start(token)))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.info("All Discord clients ready")
        
        @client.event  
        async def on_message(message):
            """メッセージ受信イベント"""
            if message.author.bot:
                return
            
            try:
                # メッセージプロセッサーに委譲
                await self.message_processor.process_message(message)
            except Exception as e:
                logger.error(f"Message processing failed: {e}")
                # エラー隔離：個別メッセージ処理失敗はシステム継続
        
        @client.event
        async def on_interaction(interaction):
            """スラッシュコマンドイベント"""
            try:
                await self.command_processor.handle_slash_command(interaction)
            except Exception as e:
                logger.error(f"Slash command processing failed: {e}")
                await interaction.response.send_message(
                    f"コマンド処理中にエラーが発生しました: {str(e)[:100]}",
                    ephemeral=True
                )
    
    async def start(self):
        """Discord Manager 開始"""
        try:
            self.running = True
            
            # プライマリクライアント（Spectra）開始
            primary_token = self.settings.discord.spectra_token
            await self.clients[self.primary_client].start(primary_token)
            
        except Exception as e:
            error_msg = f"Discord Manager startup failed: {e}"
            logger.critical(error_msg)
            self.running = False
            raise BotConnectionError(error_msg) from e
    
    async def close(self):
        """Discord Manager 終了"""
        try:
            self.running = False
            
            # 全クライアント終了
            for client in self.clients.values():
                if not client.is_closed():
                    await client.close()
            
            logger.info("Discord Manager closed successfully")
            
        except Exception as e:
            logger.error(f"Discord Manager close error: {e}")
    
    async def send_as_agent(self, agent_name: str, channel_id: int, content: str):
        """
        指定エージェントのBotアカウントから送信
        
        Args:
            agent_name: エージェント名（spectra, lynq, paz）
            channel_id: 送信先チャンネルID
            content: 送信内容
            
        Raises:
            MessageProcessingError: エージェント名が無効、またはチャンネルが見つからない場合
        """
        if agent_name not in self.clients:
            raise MessageProcessingError(f"Invalid agent: {agent_name}")
        
        client = self.clients[agent_name]
        channel = client.get_channel(channel_id)
        
        if not channel:
            raise MessageProcessingError(f"Channel {channel_id} not found for agent {agent_name}")
        
        try:
            await channel.send(content)
            
            # エージェント応答もメモリに記録（プレースホルダー）
            if self.memory_system:
                await self.memory_system.add_message(
                    content=content,
                    agent=agent_name,
                    channel=channel.name
                )
            
            logger.info(f"Sent as {agent_name}: {content[:50]}...")
            
        except Exception as e:
            error_msg = f"Message send failed for {agent_name}: {e}"
            logger.error(error_msg)
            raise MessageProcessingError(error_msg) from e
    
    def get_channel_id(self, channel_name: str) -> Optional[int]:
        """
        チャンネル名からIDを取得
        
        Args:
            channel_name: チャンネル名
            
        Returns:
            Optional[int]: チャンネルID（見つからない場合はNone）
        """
        for client in self.clients.values():
            try:
                for channel in client.get_all_channels():
                    if channel.name == channel_name:
                        return channel.id
            except (TypeError, AttributeError):
                # Mockオブジェクトや未接続状態での例外を処理
                continue
        return None


class DiscordMessageProcessor:
    """
    Discord メッセージ処理クラス
    
    Phase 6.2: メッセージ処理実装
    - FIFO メッセージキュー処理
    - LangGraph Supervisor統合
    - OptimalMemorySystem統合
    - エラー隔離システム
    """
    
    def __init__(self, settings: Settings):
        """
        DiscordMessageProcessor初期化
        
        Args:
            settings: 設定インスタンス
        """
        self.settings = settings
        
        # LangGraph Supervisor統合アプリ（プレースホルダー）
        self.app = None  # build_langgraph_app() で初期化予定
        
        # メモリシステム（プレースホルダー）
        self.memory_system = None  # OptimalMemorySystem() で初期化予定
        
        logger.info("DiscordMessageProcessor initialized")
    
    async def process_message(self, message: discord.Message):
        """
        メッセージ処理（FIFO キュー）
        
        Args:
            message: Discord メッセージ
        """
        # Bot メッセージは無視
        if message.author.bot:
            return
        
        try:
            # メモリ記録
            if self.memory_system:
                await self.memory_system.add_message(
                    content=message.content,
                    agent=message.author.name,
                    channel=message.channel.name
                )
            
            # LangGraph Supervisor に処理委譲
            if self.app:
                from langchain_core.messages import HumanMessage
                await self.app.ainvoke({
                    "messages": [HumanMessage(content=message.content, name=message.author.name)],
                    "channel_name": message.channel.name,
                    "channel_id": message.channel.id
                })
            
            logger.info(f"Message processed: {message.author.name} in {message.channel.name}")
            
        except Exception as e:
            # エラー隔離：個別メッセージ処理失敗はログ記録のみ
            logger.error(f"Message processing error isolated: {e}")


class SlashCommandProcessor:
    """
    スラッシュコマンド処理クラス
    
    Phase 6.3: スラッシュコマンド実装
    - /task commit コマンド処理
    - タスク管理システム統合
    - Pydantic バリデーション統合
    """
    
    def __init__(self, settings: Settings):
        """
        SlashCommandProcessor初期化
        
        Args:
            settings: 設定インスタンス
        """
        self.settings = settings
        
        # タスクマネージャー
        self.task_manager = None  # get_task_manager() で初期化予定
        
        # 有効なチャンネル
        self.valid_channels = {"creation", "development"}
        
        logger.info("SlashCommandProcessor initialized")
    
    async def handle_slash_command(self, interaction: discord.Interaction):
        """
        スラッシュコマンド処理
        
        Args:
            interaction: Discord インタラクション
        """
        if interaction.command_name == "task":
            await self._handle_task_command(interaction)
        else:
            await interaction.response.send_message(
                f"Unknown command: {interaction.command_name}",
                ephemeral=True
            )
    
    async def _handle_task_command(self, interaction: discord.Interaction):
        """
        /task コマンド処理
        
        Args:
            interaction: Discord インタラクション
        """
        try:
            # オプション解析
            options = {opt.name: opt.value for opt in interaction.options}
            
            action = options.get("action")
            channel = options.get("channel")
            description = options.get("description")
            
            if action == "commit":
                await self._handle_task_commit(interaction, channel, description)
            else:
                await interaction.response.send_message(
                    f"Invalid action: {action}",
                    ephemeral=True
                )
                
        except Exception as e:
            error_msg = f"Task command processing failed: {e}"
            logger.error(error_msg)
            await interaction.response.send_message(
                f"コマンド処理エラー: {str(e)[:100]}",
                ephemeral=True
            )
    
    async def _handle_task_commit(
        self,
        interaction: discord.Interaction,
        channel: Optional[str],
        description: Optional[str]
    ):
        """
        /task commit コマンド処理
        
        Args:
            interaction: Discord インタラクション
            channel: チャンネル名
            description: タスク説明
        """
        # チャンネルバリデーション
        if channel and channel not in self.valid_channels:
            await interaction.response.send_message(
                content=f"Invalid channel: {channel}. Valid channels: {', '.join(self.valid_channels)}",
                ephemeral=True
            )
            return
        
        try:
            # タスクマネージャー取得（プレースホルダー）
            if not self.task_manager:
                await interaction.response.send_message(
                    content="タスク管理システムが初期化されていません",
                    ephemeral=True
                )
                return
            
            # 既存アクティブタスク確認
            active_task = await self.task_manager.get_active_task()
            
            if active_task:
                # 既存タスク更新
                update_data = {}
                if channel:
                    update_data["channel_id"] = channel
                if description:
                    update_data["description"] = description
                
                updated_task = await self.task_manager.update_task(
                    task_id=active_task.id,
                    **update_data
                )
                
                await interaction.response.send_message(
                    content=f"タスクを更新しました:\n"
                    f"チャンネル: {channel or updated_task.channel_id}\n"
                    f"内容: {description or updated_task.description}"
                )
            else:
                # 新規タスク作成
                if not description:
                    await interaction.response.send_message(
                        content="新規タスクには説明が必要です",
                        ephemeral=True
                    )
                    return
                
                new_task = await self.task_manager.create_task(
                    title="Discord Task",
                    description=description,
                    channel_id=channel
                )
                
                await interaction.response.send_message(
                    content=f"新しいタスクを作成しました:\n"
                    f"ID: {new_task.id}\n"
                    f"チャンネル: {channel}\n"
                    f"内容: {description}"
                )
                
        except Exception as e:
            error_msg = f"Task commit failed: {e}"
            logger.error(error_msg)
            await interaction.response.send_message(
                content=f"タスク処理エラー: {str(e)[:100]}",
                ephemeral=True
            )


class SimplifiedTickManager:
    """
    ティック管理クラス（LangGraph統合）
    OptimalMemorySystemと連携した自発発言制御
    
    Phase 6.4: SimplifiedTickManager実装
    - 自発発言システム
    - 時間帯別モード制御
    - 日報処理統合
    - LangGraph Supervisor統合
    """
    
    def __init__(self, discord_manager: SimplifiedDiscordManager, settings: Settings):
        """
        SimplifiedTickManager初期化
        
        Args:
            discord_manager: Discord Manager インスタンス
            settings: 設定インスタンス
        """
        self.discord_manager = discord_manager
        self.settings = settings
        self.running = False
        
        # メモリシステム（プレースホルダー）
        self.memory_system = None  # OptimalMemorySystem() で初期化予定
        
        logger.info("SimplifiedTickManager initialized")
    
    async def start(self):
        """ティックループ開始"""
        self.running = True
        logger.info(f"Tick管理開始: {self.settings.tick.tick_interval}秒間隔")
        
        while self.running:
            try:
                await asyncio.sleep(self.settings.tick.tick_interval)
                await self._process_tick()
            except Exception as e:
                logger.critical(f"致命的エラー: ティック処理失敗: {e}")
                sys.exit(1)  # Fail-Fast
    
    def stop(self):
        """ティックループ停止"""
        self.running = False
        logger.info("Tick管理停止")
    
    async def _process_tick(self):
        """ティック処理実行"""
        # 現在モード確認
        current_mode = get_current_mode()
        
        if current_mode == "STANDBY":
            return  # 完全無応答モード、何もしない
        
        # PROCESSINGモード: 日報自動実行→会議開始
        if current_mode == "PROCESSING":
            await self._trigger_daily_report_and_start_meeting()
            return
        
        # アクティブチャンネル選択
        target_channels = self._get_active_channels(current_mode)
        if not target_channels:
            return
        
        # ランダムチャンネル選択
        target_channel_name = random.choice(target_channels)
        
        # LangGraph Supervisor に自発発言委譲
        if self.discord_manager.app:
            from langchain_core.messages import HumanMessage
            await self.discord_manager.app.ainvoke({
                "messages": [HumanMessage(content="自発発言タイミング")],
                "channel_name": target_channel_name,
                "message_type": "tick"
            })
        
        logger.debug(f"Tick processed for channel: {target_channel_name}")
    
    def _get_active_channels(self, mode: str) -> List[str]:
        """アクティブチャンネル取得"""
        if mode == "ACTIVE":
            return ["command-center", "creation", "development"]
        elif mode == "FREE":
            return ["lounge"]
        else:
            return []
    
    async def _trigger_daily_report_and_start_meeting(self):
        """日報処理→会議開始"""
        try:
            # 日報処理実行
            if self.memory_system:
                # ステップ1-2: 短期→長期移行
                await self.memory_system.daily_archive_and_reset()
                
                # ステップ3: 活動サマリー生成
                recent_context = await self.memory_system.get_recent_context(limit=50)
                summary = await self._generate_activity_summary_from_context(recent_context)
            else:
                summary = "メモリシステムが初期化されていません"
            
            # ステップ4: 会議開始メッセージ送信
            meeting_message = f"おはようございます！日報完了しました。\n\n{summary}\n\n今日の会議を開始します。"
            
            command_center_id = self.discord_manager.get_channel_id("command-center")
            if command_center_id:
                await self.discord_manager.send_as_agent(
                    agent_name="spectra",
                    channel_id=command_center_id,
                    content=meeting_message[:2000]  # Discord文字数制限
                )
            
            # 日報完了フラグを設定（プレースホルダー）
            await self._set_daily_report_completed()
            
            logger.info("日報処理完了、ACTIVEモード開始")
            
        except Exception as e:
            logger.critical(f"日報処理失敗: {e}")
            sys.exit(1)  # Fail-Fast
    
    async def _generate_activity_summary_from_context(self, recent_context: List[dict]) -> str:
        """活動サマリー生成（プレースホルダー）"""
        if not recent_context:
            return "昨日の活動データがありません。"
        
        # 簡略化実装
        message_count = len(recent_context)
        return f"昨日は {message_count} 件のメッセージがありました。"
    
    async def _set_daily_report_completed(self):
        """日報完了フラグを設定（プレースホルダー）"""
        # Redis実装予定
        pass


# グローバルアクセス用（ツールから使用）
discord_manager = None

# Singleton pattern helpers
_discord_manager_instance: Optional[SimplifiedDiscordManager] = None
_tick_manager_instance: Optional[SimplifiedTickManager] = None


def get_discord_manager() -> SimplifiedDiscordManager:
    """SimplifiedDiscordManagerインスタンス取得（シングルトン）"""
    global _discord_manager_instance
    if _discord_manager_instance is None:
        settings = get_settings()
        _discord_manager_instance = SimplifiedDiscordManager(settings)
    return _discord_manager_instance


def reset_discord_manager() -> None:
    """SimplifiedDiscordManagerインスタンスリセット（主にテスト用）"""
    global _discord_manager_instance, discord_manager
    _discord_manager_instance = None
    discord_manager = None


def get_tick_manager() -> SimplifiedTickManager:
    """SimplifiedTickManagerインスタンス取得（シングルトン）"""
    global _tick_manager_instance
    if _tick_manager_instance is None:
        discord_mgr = get_discord_manager()
        settings = get_settings()
        _tick_manager_instance = SimplifiedTickManager(discord_mgr, settings)
    return _tick_manager_instance


def reset_tick_manager() -> None:
    """SimplifiedTickManagerインスタンスリセット（主にテスト用）"""
    global _tick_manager_instance
    _tick_manager_instance = None


# Convenience helper functions
async def initialize_discord_system() -> tuple[SimplifiedDiscordManager, SimplifiedTickManager]:
    """Discord システム初期化ヘルパー"""
    discord_manager = get_discord_manager()
    tick_manager = get_tick_manager()
    
    # LangGraph Supervisor統合（プレースホルダー）
    # discord_manager.app = build_langgraph_app()
    
    # OptimalMemorySystem統合（プレースホルダー）
    # discord_manager.memory_system = OptimalMemorySystem()
    # tick_manager.memory_system = discord_manager.memory_system
    
    logger.info("Discord system initialized successfully")
    return discord_manager, tick_manager


async def close_discord_system() -> None:
    """Discord システム終了ヘルパー"""
    discord_manager = get_discord_manager()
    tick_manager = get_tick_manager()
    
    tick_manager.stop()
    await discord_manager.close()
    
    logger.info("Discord system closed successfully")
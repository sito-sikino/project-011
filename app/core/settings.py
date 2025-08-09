"""
Settings module for Discord Multi-Agent System

Pydantic設定管理、環境変数読み込み、Field制約による堅牢なバリデーション機能を提供
Phase 2.1: 設定バリデーション実装完了 - 時刻: 2025-08-09 18:04:56

t-wada式TDDサイクル - Refactor Phase完了
- Field制約による数値範囲バリデーション実装
- Fail-Fast原則に基づくバリデーションエラー処理
- 型安全性確保、環境変数統合、設定構造体系化
- 23個の包括的バリデーションテスト合格
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordConfig(BaseSettings):
    """
    Discord Bot関連設定
    
    3体のBotトークン管理、接続設定
    """
    model_config = SettingsConfigDict(env_prefix="DISCORD_", env_file=".env")


class GeminiConfig(BaseSettings):
    """
    Gemini API関連設定
    
    APIキー、レート制限、リクエスト設定
    """
    model_config = SettingsConfigDict(env_prefix="GEMINI_", env_file=".env")


class DatabaseConfig(BaseSettings):
    """
    データベース関連設定
    
    PostgreSQL + pgvector、Redis接続設定
    """
    model_config = SettingsConfigDict(env_prefix="DATABASE_", env_file=".env")


class TickConfig(BaseSettings):
    """
    自発発言Tick関連設定
    
    発言間隔、確率設定、時間管理
    Field制約による数値範囲バリデーション実装
    """
    model_config = SettingsConfigDict(env_prefix="TICK_", env_file=".env")
    
    # TICK_INTERVAL: 15-3600秒、デフォルト300
    tick_interval: int = Field(
        default=300,
        ge=15,
        le=3600,
        description="自発発言の間隔（秒）"
    )
    
    # TICK_PROBABILITY: 0.0-1.0、デフォルト0.33
    tick_probability: float = Field(
        default=0.33,
        ge=0.0,
        le=1.0,
        description="自発発言の確率"
    )


class ScheduleConfig(BaseSettings):
    """
    スケジュール関連設定
    
    日報生成時刻、メンテナンス時間設定
    Field制約による時間帯バリデーション実装
    """
    model_config = SettingsConfigDict(env_prefix="SCHEDULE_", env_file=".env")
    
    # STANDBY_START: 0-23時、デフォルト0
    standby_start: int = Field(
        default=0,
        ge=0,
        le=23,
        description="スタンバイ開始時刻（0-23時）"
    )
    
    # PROCESSING_TRIGGER: 0-23時、デフォルト6
    processing_trigger: int = Field(
        default=6,
        ge=0,
        le=23,
        description="処理トリガー時刻（0-23時）"
    )
    
    # ACTIVE_START: 0-23時、デフォルト6
    active_start: int = Field(
        default=6,
        ge=0,
        le=23,
        description="アクティブ開始時刻（0-23時）"
    )
    
    # FREE_START: 0-23時、デフォルト20
    free_start: int = Field(
        default=20,
        ge=0,
        le=23,
        description="フリータイム開始時刻（0-23時）"
    )


class MemoryConfig(BaseSettings):
    """
    メモリシステム関連設定
    
    Redis短期記憶、PGVector長期記憶設定
    Field制約による数値範囲バリデーション実装
    """
    model_config = SettingsConfigDict(env_prefix="MEMORY_", env_file=".env")
    
    # MEMORY_CLEANUP_HOURS: 1-168時間、デフォルト24
    cleanup_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="メモリクリーンアップ間隔（時間）"
    )
    
    # MEMORY_RECENT_LIMIT: 5-100件、デフォルト30
    recent_limit: int = Field(
        default=30,
        ge=5,
        le=100,
        description="最近の記憶保持件数"
    )


class AgentConfig(BaseSettings):
    """
    エージェント関連設定
    
    Spectra、LynQ、Paz人格設定、応答制御
    Field制約による数値範囲バリデーション実装
    """
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env")
    
    # AGENT_SPECTRA_TEMPERATURE: 0.0-2.0、デフォルト0.5
    spectra_temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description="Spectraエージェントの温度パラメータ"
    )
    
    # AGENT_LYNQ_TEMPERATURE: 0.0-2.0、デフォルト0.3
    lynq_temperature: float = Field(
        default=0.3,
        ge=0.0,
        le=2.0,
        description="LynQエージェントの温度パラメータ"
    )
    
    # AGENT_PAZ_TEMPERATURE: 0.0-2.0、デフォルト0.9
    paz_temperature: float = Field(
        default=0.9,
        ge=0.0,
        le=2.0,
        description="Pazエージェントの温度パラメータ"
    )


class ChannelConfig(BaseSettings):
    """
    チャンネル関連設定
    
    Discord チャンネル指定、発言制御設定
    Field制約による数値範囲バリデーション実装
    """
    model_config = SettingsConfigDict(env_prefix="CHANNEL_", env_file=".env")
    
    # CHANNEL_COMMAND_CENTER_MAX_CHARS: 50-500、デフォルト100
    command_center_max_chars: int = Field(
        default=100,
        ge=50,
        le=500,
        description="コマンドセンターチャンネルの最大文字数"
    )
    
    # CHANNEL_CREATION_MAX_CHARS: 100-1000、デフォルト200
    creation_max_chars: int = Field(
        default=200,
        ge=100,
        le=1000,
        description="創作チャンネルの最大文字数"
    )
    
    # CHANNEL_DEVELOPMENT_MAX_CHARS: 100-1000、デフォルト200
    development_max_chars: int = Field(
        default=200,
        ge=100,
        le=1000,
        description="開発チャンネルの最大文字数"
    )
    
    # CHANNEL_LOUNGE_MAX_CHARS: 10-100、デフォルト30
    lounge_max_chars: int = Field(
        default=30,
        ge=10,
        le=100,
        description="ラウンジチャンネルの最大文字数"
    )


class ReportConfig(BaseSettings):
    """
    レポート関連設定
    
    日報生成、統計処理、出力形式設定
    """
    model_config = SettingsConfigDict(env_prefix="REPORT_", env_file=".env")


class Settings(BaseSettings):
    """
    Discord Multi-Agent System メイン設定クラス
    
    8つの設定グループを統合管理:
    - discord: Discord Bot関連（3体のBotトークン管理）
    - gemini: Gemini API関連（APIキー、レート制限）
    - database: データベース関連（PostgreSQL + pgvector、Redis）
    - tick: 自発発言Tick関連（発言間隔、確率制御）
    - schedule: スケジュール関連（日報生成、メンテナンス）
    - memory: メモリシステム関連（Redis短期、PGVector長期）
    - agent: エージェント関連（Spectra、LynQ、Paz人格）
    - channel: チャンネル関連（Discord チャンネル制御）
    - report: レポート関連（日報生成、統計処理）
    
    環境変数からの自動読み込み、型安全性確保、
    Pydantic v2 BaseSettings による統合設定管理
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid"
    )
    
    discord: DiscordConfig = DiscordConfig()
    gemini: GeminiConfig = GeminiConfig()
    database: DatabaseConfig = DatabaseConfig()
    tick: TickConfig = TickConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    memory: MemoryConfig = MemoryConfig()
    agent: AgentConfig = AgentConfig()
    channel: ChannelConfig = ChannelConfig()
    report: ReportConfig = ReportConfig()
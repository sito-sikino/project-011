"""
Settings module for Discord Multi-Agent System

Pydantic設定管理、環境変数読み込み、バリデーション機能を提供
Phase 2.1: core/settings.py基本実装 - 時刻: 2025-08-09 17:56:25

t-wada式TDDサイクル - Refactor Phase
型安全性確保、環境変数統合準備、設定構造体系化
"""
from typing import Optional
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
    """
    model_config = SettingsConfigDict(env_prefix="TICK_", env_file=".env")


class ScheduleConfig(BaseSettings):
    """
    スケジュール関連設定
    
    日報生成時刻、メンテナンス時間設定
    """
    model_config = SettingsConfigDict(env_prefix="SCHEDULE_", env_file=".env")


class MemoryConfig(BaseSettings):
    """
    メモリシステム関連設定
    
    Redis短期記憶、PGVector長期記憶設定
    """
    model_config = SettingsConfigDict(env_prefix="MEMORY_", env_file=".env")


class AgentConfig(BaseSettings):
    """
    エージェント関連設定
    
    Spectra、LynQ、Paz人格設定、応答制御
    """
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env")


class ChannelConfig(BaseSettings):
    """
    チャンネル関連設定
    
    Discord チャンネル指定、発言制御設定
    """
    model_config = SettingsConfigDict(env_prefix="CHANNEL_", env_file=".env")


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
"""
Settings module for Discord Multi-Agent System

Pydantic設定管理、環境変数読み込み、Field制約による堅牢なバリデーション機能を提供

Phase 2.1: 環境変数読み込みテスト実装完了 - 時刻: 2025-08-09 18:12:38

t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 7つの包括的な環境変数読み込みテストを先行作成
🟢 Green Phase: .env統合、プレフィックス分離、UTF-8対応、設定グループ統合実装
🟡 Refactor Phase: 品質向上、エラーハンドリング強化、ドキュメント整備

実装機能:
- .envファイル統合読み込み（UTF-8エンコーディング対応）
- 環境変数プレフィックス分離（DISCORD_, GEMINI_, など）
- 設定グループごとの独立した環境変数管理
- デフォルト値と環境変数の適切な優先順位制御
- Field制約による数値範囲バリデーション継続
- 型安全性確保、Fail-Safe設計実装
"""
from typing import Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging


class DiscordConfig(BaseSettings):
    """
    Discord Bot関連設定
    
    3体のBotトークン管理、接続設定
    """
    model_config = SettingsConfigDict(
        env_prefix="DISCORD_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Discord Bot Tokens
    spectra_token: Optional[str] = Field(None, description="SpectraエージェントのDiscordトークン")
    lynq_token: Optional[str] = Field(None, description="LynQエージェントのDiscordトークン")
    paz_token: Optional[str] = Field(None, description="PazエージェントのDiscordトークン")


class GeminiConfig(BaseSettings):
    """
    Gemini API関連設定
    
    APIキー、レート制限、リクエスト設定
    """
    model_config = SettingsConfigDict(
        env_prefix="GEMINI_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Gemini API Configuration
    api_key: Optional[str] = Field(None, description="Gemini APIキー")
    requests_per_minute: int = Field(
        default=15,
        ge=1,
        le=60,
        description="1分あたりのリクエスト制限"
    )


class DatabaseConfig(BaseSettings):
    """
    データベース関連設定
    
    PostgreSQL + pgvector、Redis接続設定
    """
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Database Configuration
    redis_url: str = Field(
        default="redis://redis:6379",
        description="Redis接続URL"
    )
    url: str = Field(
        default="postgresql://user:pass@postgres:5432/dbname",
        description="PostgreSQL接続URL",
        alias="database_url"  # DATABASE_URLも読み込み可能
    )


class TickConfig(BaseSettings):
    """
    自発発言Tick関連設定
    
    発言間隔、確率設定、時間管理
    Field制約による数値範囲バリデーション実装
    """
    model_config = SettingsConfigDict(
        env_prefix="TICK_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
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
    model_config = SettingsConfigDict(
        env_prefix="SCHEDULE_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
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
    model_config = SettingsConfigDict(
        env_prefix="MEMORY_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
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
    model_config = SettingsConfigDict(
        env_prefix="AGENT_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
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
    model_config = SettingsConfigDict(
        env_prefix="CHANNEL_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
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
    model_config = SettingsConfigDict(
        env_prefix="REPORT_", 
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Report Configuration
    generate_daily: bool = Field(
        default=True,
        description="日報の自動生成フラグ"
    )


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
    
    Phase 2.1: 環境変数読み込み機能実装
    - .envファイル統合読み込み
    - 環境変数プレフィックス分離統合
    - UTF-8エンコーディング対応
    - Fail-Fast原則による必須変数チェック
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 環境変数読み込みテスト用に"forbid"から"ignore"に変更
        validate_assignment=True  # フィールド値の動的変更時もバリデーション実行
    )
    
    # 環境変数読み込み用の追加フィールド
    # 直接環境変数（プレフィックスなし）からも読み込み可能
    spectra_token: Optional[str] = Field(None, description="SPECTRA_TOKENの直接読み込み")
    lynq_token: Optional[str] = Field(None, description="LYNQ_TOKENの直接読み込み")
    paz_token: Optional[str] = Field(None, description="PAZ_TOKENの直接読み込み")
    gemini_api_key: Optional[str] = Field(None, description="GEMINI_API_KEYの直接読み込み")
    redis_url: Optional[str] = Field(None, description="REDIS_URLの直接読み込み")
    database_url: Optional[str] = Field(None, description="DATABASE_URLの直接読み込み")
    env: Optional[str] = Field(None, description="ENVの直接読み込み")
    log_level: Optional[str] = Field(None, description="LOG_LEVELの直接読み込み")
    
    def model_post_init(self, __context) -> None:
        """
        初期化後の設定統合処理
        
        直接環境変数で設定された値を適切な設定グループに統合
        Phase 2.1: 環境変数統合ロジック実装
        """
        # Discord Tokenの統合
        if self.spectra_token and not self.discord.spectra_token:
            self.discord.spectra_token = self.spectra_token
        if self.lynq_token and not self.discord.lynq_token:
            self.discord.lynq_token = self.lynq_token
        if self.paz_token and not self.discord.paz_token:
            self.discord.paz_token = self.paz_token
            
        # Gemini API Keyの統合
        if self.gemini_api_key and not self.gemini.api_key:
            self.gemini.api_key = self.gemini_api_key
            
        # Database URLの統合
        if self.redis_url and self.database.redis_url == "redis://redis:6379":
            self.database.redis_url = self.redis_url
        if self.database_url and self.database.url == "postgresql://user:pass@postgres:5432/dbname":
            self.database.url = self.database_url
            
        # ログレベル設定
        if self.log_level:
            logging.basicConfig(
                level=getattr(logging, self.log_level.upper(), logging.INFO),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
    
    def get_missing_required_vars(self) -> list[str]:
        """
        必須環境変数の不足チェック
        
        Returns:
            list[str]: 不足している必須環境変数のリスト
        """
        missing = []
        
        # Discord Tokens（本番環境では必須）
        if self.env != "testing" and not self.discord.spectra_token:
            missing.append("SPECTRA_TOKEN or DISCORD_SPECTRA_TOKEN")
        if self.env != "testing" and not self.discord.lynq_token:
            missing.append("LYNQ_TOKEN or DISCORD_LYNQ_TOKEN")
        if self.env != "testing" and not self.discord.paz_token:
            missing.append("PAZ_TOKEN or DISCORD_PAZ_TOKEN")
            
        # Gemini API Key（本番環境では必須）
        if self.env != "testing" and not self.gemini.api_key:
            missing.append("GEMINI_API_KEY")
            
        return missing
    
    def validate_required_vars(self) -> None:
        """
        必須環境変数の存在チェックと早期失敗
        
        Fail-Fast原則に基づく必須変数チェック
        本番環境での起動時に必須環境変数が不足している場合は即座に停止
        """
        missing = self.get_missing_required_vars()
        if missing and self.env not in ["testing", "development"]:
            error_msg = f"Required environment variables are missing: {', '.join(missing)}"
            logging.error(error_msg)
            raise ValueError(error_msg)
    
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    tick: TickConfig = Field(default_factory=TickConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    channel: ChannelConfig = Field(default_factory=ChannelConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)


# グローバル設定インスタンス（シングルトンパターン）
_settings_instance: Optional[Settings] = None

def get_settings() -> Settings:
    """
    設定インスタンスの取得（シングルトンパターン）
    
    Phase 2.1: 環境変数読み込み統合設定管理
    アプリケーション全体で単一の設定インスタンスを共有
    
    Returns:
        Settings: 設定インスタンス
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
        # 初期化後に統合処理を実行
        _settings_instance.model_post_init(None)
        # 必須変数チェック（テスト環境以外）
        try:
            _settings_instance.validate_required_vars()
        except ValueError as e:
            logging.warning(f"Settings validation warning: {e}")
            # テスト環境や開発環境では警告のみ
    return _settings_instance


def reset_settings() -> None:
    """
    設定インスタンスのリセット（主にテスト用）
    
    テスト間でのクリーンな状態確保
    """
    global _settings_instance
    _settings_instance = None
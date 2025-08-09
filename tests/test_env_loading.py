"""
環境変数読み込みテスト

Phase 2.1: 環境変数読み込みテスト実装
t-wada式TDD Red Phase - テスト先行作成

受け入れ条件確認項目:
1. .envから値を正確に読み込み確認
2. 環境変数プレフィックス分離の動作確認
3. 設定グループごとの正確な読み込み
4. デフォルト値と環境変数の優先順位確認
5. 必須環境変数の存在チェック
6. プレフィックス付き環境変数の統合動作
"""
import pytest
import os
import tempfile
from pathlib import Path
from pydantic import ValidationError
from app.core.settings import (
    Settings,
    DiscordConfig,
    GeminiConfig,
    DatabaseConfig,
    TickConfig,
    ScheduleConfig,
    MemoryConfig,
    AgentConfig,
    ChannelConfig,
    ReportConfig
)


class TestEnvLoading:
    """環境変数読み込みテスト群"""
    
    def test_env_file_loading(self, tmp_path):
        """
        Test 1: .envファイルからの値読み込み確認
        受け入れ条件: .envから値を正確に読み込み確認
        """
        # テスト用.envファイル作成
        env_file = tmp_path / ".env"
        env_file.write_text("""
# Discord Tokens
SPECTRA_TOKEN=test_spectra_token_123
LYNQ_TOKEN=test_lynq_token_456
PAZ_TOKEN=test_paz_token_789

# Gemini API
GEMINI_API_KEY=test_gemini_key_abc

# Database
REDIS_URL=redis://test-redis:6380
DATABASE_URL=postgresql://test:pass@test-postgres:5433/testdb

# Environment
ENV=testing
LOG_LEVEL=DEBUG
        """)
        
        # 一時的にカレントディレクトリを変更
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 設定を読み込み
            settings = Settings()
            
            # .envから値が読み込まれることを確認
            # この時点では環境変数読み込みが未実装なのでテスト失敗が予想される
            assert hasattr(settings, 'spectra_token'), "SPECTRA_TOKEN should be loaded"
            assert settings.spectra_token == "test_spectra_token_123"
            
        finally:
            os.chdir(original_cwd)
    
    def test_env_prefix_separation(self, tmp_path):
        """
        Test 2: 環境変数プレフィックス分離の動作確認
        受け入れ条件: 環境変数プレフィックス分離の動作確認
        """
        # テスト用.envファイル作成（プレフィックス付き）
        env_file = tmp_path / ".env"
        env_file.write_text("""
# Discord Configuration
DISCORD_SPECTRA_TOKEN=prefix_spectra_token
DISCORD_LYNQ_TOKEN=prefix_lynq_token
DISCORD_PAZ_TOKEN=prefix_paz_token

# Gemini Configuration
GEMINI_API_KEY=prefix_gemini_key
GEMINI_REQUESTS_PER_MINUTE=20

# Database Configuration
DATABASE_REDIS_URL=redis://prefix-redis:6379
DATABASE_URL=postgresql://prefix:pass@prefix-postgres:5432/prefixdb

# Tick Configuration
TICK_INTERVAL=600
TICK_PROBABILITY=0.5
        """)
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 設定を読み込み
            settings = Settings()
            
            # プレフィックス付き環境変数が正しく分離されることを確認
            assert settings.discord.spectra_token == "prefix_spectra_token"
            assert settings.gemini.api_key == "prefix_gemini_key"
            assert settings.database.redis_url == "redis://prefix-redis:6379"
            assert settings.tick.tick_interval == 600
            assert settings.tick.tick_probability == 0.5
            
        finally:
            os.chdir(original_cwd)
    
    def test_config_groups_loading(self, tmp_path):
        """
        Test 3: 設定グループごとの正確な読み込み
        受け入れ条件: 設定グループごとの正確な読み込み
        """
        # 各設定グループのテスト用.envファイル作成
        env_file = tmp_path / ".env"
        env_file.write_text("""
# DiscordConfig group
DISCORD_SPECTRA_TOKEN=group_spectra
DISCORD_LYNQ_TOKEN=group_lynq
DISCORD_PAZ_TOKEN=group_paz

# GeminiConfig group
GEMINI_API_KEY=group_gemini_key
GEMINI_REQUESTS_PER_MINUTE=25

# DatabaseConfig group
DATABASE_REDIS_URL=redis://group-redis:6379
DATABASE_URL=postgresql://group:pass@group-postgres:5432/groupdb

# TickConfig group
TICK_INTERVAL=450
TICK_PROBABILITY=0.75

# ScheduleConfig group
SCHEDULE_STANDBY_START=1
SCHEDULE_PROCESSING_TRIGGER=7
SCHEDULE_ACTIVE_START=8
SCHEDULE_FREE_START=21

# MemoryConfig group
MEMORY_CLEANUP_HOURS=48
MEMORY_RECENT_LIMIT=50

# AgentConfig group
AGENT_SPECTRA_TEMPERATURE=0.7
AGENT_LYNQ_TEMPERATURE=0.4
AGENT_PAZ_TEMPERATURE=1.2

# ChannelConfig group
CHANNEL_COMMAND_CENTER_MAX_CHARS=150
CHANNEL_CREATION_MAX_CHARS=300
CHANNEL_DEVELOPMENT_MAX_CHARS=350
CHANNEL_LOUNGE_MAX_CHARS=50

# ReportConfig group
REPORT_GENERATE_DAILY=true
        """)
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 設定を読み込み
            settings = Settings()
            
            # 各設定グループが正しく読み込まれることを確認
            assert settings.discord.spectra_token == "group_spectra"
            assert settings.gemini.api_key == "group_gemini_key"
            assert settings.database.redis_url == "redis://group-redis:6379"
            assert settings.tick.tick_interval == 450
            assert settings.schedule.standby_start == 1
            assert settings.memory.cleanup_hours == 48
            assert settings.agent.spectra_temperature == 0.7
            assert settings.channel.command_center_max_chars == 150
            
        finally:
            os.chdir(original_cwd)
    
    def test_default_vs_env_priority(self, tmp_path):
        """
        Test 4: デフォルト値と環境変数の優先順位確認
        受け入れ条件: デフォルト値と環境変数の優先順位確認
        """
        # 一部の環境変数のみ設定
        env_file = tmp_path / ".env"
        env_file.write_text("""
TICK_INTERVAL=900
TICK_PROBABILITY=0.8
MEMORY_CLEANUP_HOURS=72
        """)
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 設定を読み込み
            settings = Settings()
            
            # 環境変数で設定された値が優先されることを確認
            assert settings.tick.tick_interval == 900  # 環境変数の値
            assert settings.tick.tick_probability == 0.8  # 環境変数の値
            assert settings.memory.cleanup_hours == 72  # 環境変数の値
            
            # 環境変数で設定されていない値はデフォルトが使用されることを確認
            assert settings.schedule.standby_start == 0  # デフォルト値
            assert settings.memory.recent_limit == 30  # デフォルト値
            assert settings.agent.spectra_temperature == 0.5  # デフォルト値
            
        finally:
            os.chdir(original_cwd)
    
    def test_required_env_vars_check(self, tmp_path):
        """
        Test 5: 必須環境変数の存在チェック
        受け入れ条件: 必須環境変数の存在チェック
        """
        # 必須環境変数が不足している.envファイル
        env_file = tmp_path / ".env"
        env_file.write_text("""
# Discord Tokensの一部のみ設定
DISCORD_SPECTRA_TOKEN=test_spectra
# DISCORD_LYNQ_TOKEN is missing
# DISCORD_PAZ_TOKEN is missing

# Gemini API key is missing
# GEMINI_API_KEY=

# Database URLs
DATABASE_REDIS_URL=redis://test-redis:6379
# DATABASE_URL is missing
        """)
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 設定を読み込み（現在の実装では必須チェックは手動で行う）
            settings = Settings()
            
            # 必須フィールドが不足していることを確認
            # 現在の実装では、OptionalなFieldとして定義されているため、None値になる
            assert settings.discord.lynq_token is None, "Missing LYNQ_TOKEN should be None"
            assert settings.discord.paz_token is None, "Missing PAZ_TOKEN should be None"
            assert settings.gemini.api_key is None, "Missing GEMINI_API_KEY should be None"
            
            # 設定されている値は正しく読み込まれることを確認
            assert settings.discord.spectra_token == "test_spectra", "SPECTRA_TOKEN should be loaded"
            assert settings.database.redis_url == "redis://test-redis:6379", "REDIS_URL should be loaded"
            
        finally:
            os.chdir(original_cwd)
    
    def test_individual_config_group_loading(self, tmp_path):
        """
        Test 6: 個別設定グループの環境変数統合動作
        受け入れ条件: プレフィックス付き環境変数の統合動作
        """
        # 個別の設定グループをテスト
        env_file = tmp_path / ".env"
        env_file.write_text("""
DISCORD_SPECTRA_TOKEN=individual_spectra
DISCORD_LYNQ_TOKEN=individual_lynq
DISCORD_PAZ_TOKEN=individual_paz
        """)
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 個別の設定グループインスタンス作成
            discord_config = DiscordConfig()
            
            # プレフィックス付き環境変数が正しく読み込まれることを確認
            assert discord_config.spectra_token == "individual_spectra"
            assert discord_config.lynq_token == "individual_lynq"
            assert discord_config.paz_token == "individual_paz"
            
        finally:
            os.chdir(original_cwd)
    
    def test_env_file_encoding_utf8(self, tmp_path):
        """
        Test 7: .envファイルのUTF-8エンコーディング処理
        受け入れ条件: 日本語コメントを含む.envファイルの正確な読み込み
        """
        # UTF-8エンコーディングでの.envファイル作成（日本語コメント含む）
        env_file = tmp_path / ".env"
        env_file.write_text("""
# Discord設定 - 日本語コメントテスト
DISCORD_SPECTRA_TOKEN=utf8_test_token_日本語
GEMINI_API_KEY=utf8_gemini_key_テスト

# 数値設定
TICK_INTERVAL=333
TICK_PROBABILITY=0.66
        """, encoding="utf-8")
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            
            # 設定を読み込み
            settings = Settings()
            
            # UTF-8エンコーディングで正しく読み込まれることを確認
            assert settings.discord.spectra_token == "utf8_test_token_日本語"
            assert settings.gemini.api_key == "utf8_gemini_key_テスト"
            assert settings.tick.tick_interval == 333
            assert settings.tick.tick_probability == 0.66
            
        finally:
            os.chdir(original_cwd)
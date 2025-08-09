"""
core/settings.py のテスト

t-wada式TDDサイクル - Red Phase
Phase 2.1: core/settings.py基本実装
時刻: 2025-08-09 17:56:25
"""
import pytest
from pydantic_settings import BaseSettings


def test_settings_module_import():
    """Settings モジュールがインポートできることを確認"""
    from app.core.settings import Settings
    assert Settings is not None


def test_settings_inherits_base_settings():
    """Settings が BaseSettings を継承していることを確認"""
    from app.core.settings import Settings
    # pydantic-settings v2 対応
    assert issubclass(Settings, BaseSettings)


def test_settings_has_discord_config():
    """Settings に discord 設定グループが存在することを確認"""
    from app.core.settings import Settings, DiscordConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'discord')
    assert isinstance(settings_instance.discord, DiscordConfig)


def test_settings_has_gemini_config():
    """Settings に gemini 設定グループが存在することを確認"""
    from app.core.settings import Settings, GeminiConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'gemini')
    assert isinstance(settings_instance.gemini, GeminiConfig)


def test_settings_has_database_config():
    """Settings に database 設定グループが存在することを確認"""
    from app.core.settings import Settings, DatabaseConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'database')
    assert isinstance(settings_instance.database, DatabaseConfig)


def test_settings_has_tick_config():
    """Settings に tick 設定グループが存在することを確認"""
    from app.core.settings import Settings, TickConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'tick')
    assert isinstance(settings_instance.tick, TickConfig)


def test_settings_has_schedule_config():
    """Settings に schedule 設定グループが存在することを確認"""
    from app.core.settings import Settings, ScheduleConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'schedule')
    assert isinstance(settings_instance.schedule, ScheduleConfig)


def test_settings_has_memory_config():
    """Settings に memory 設定グループが存在することを確認"""
    from app.core.settings import Settings, MemoryConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'memory')
    assert isinstance(settings_instance.memory, MemoryConfig)


def test_settings_has_agent_config():
    """Settings に agent 設定グループが存在することを確認"""
    from app.core.settings import Settings, AgentConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'agent')
    assert isinstance(settings_instance.agent, AgentConfig)


def test_settings_has_channel_config():
    """Settings に channel 設定グループが存在することを確認"""
    from app.core.settings import Settings, ChannelConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'channel')
    assert isinstance(settings_instance.channel, ChannelConfig)


def test_settings_has_report_config():
    """Settings に report 設定グループが存在することを確認"""
    from app.core.settings import Settings, ReportConfig
    
    settings_instance = Settings()
    assert hasattr(settings_instance, 'report')
    assert isinstance(settings_instance.report, ReportConfig)


def test_all_config_groups_exist():
    """8つの設定グループがすべて存在することを確認"""
    from app.core.settings import Settings
    
    settings_instance = Settings()
    expected_configs = [
        'discord', 'gemini', 'database', 'tick', 
        'schedule', 'memory', 'agent', 'channel', 'report'
    ]
    
    for config_name in expected_configs:
        assert hasattr(settings_instance, config_name), f"{config_name} config is missing"
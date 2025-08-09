"""
Settings validation tests for Discord Multi-Agent System

Phase 2.1: 設定バリデーション実装のためのTDDテスト
t-wada式TDDサイクル - Red Phase: 失敗するテスト作成

時刻: 2025-08-09 18:04:56
テスト対象: app/core/settings.py Field制約、数値制約、文字列制約、バリデーション
"""

import pytest
from pydantic import ValidationError
from app.core.settings import (
    Settings,
    TickConfig,
    ScheduleConfig,
    MemoryConfig,
    AgentConfig,
    ChannelConfig
)


class TestTickConfigValidation:
    """Tick設定のバリデーションテスト"""
    
    def test_tick_interval_valid_range(self):
        """TICK_INTERVAL: 15-3600秒の範囲制約テスト"""
        # 有効な値
        config = TickConfig(tick_interval=300)
        assert config.tick_interval == 300
        
        config = TickConfig(tick_interval=15)  # 最小値
        assert config.tick_interval == 15
        
        config = TickConfig(tick_interval=3600)  # 最大値
        assert config.tick_interval == 3600
    
    def test_tick_interval_invalid_range(self):
        """TICK_INTERVAL: 無効値でのバリデーションエラーテスト"""
        # 最小値未満
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(tick_interval=14)
        assert "greater than or equal to 15" in str(exc_info.value)
        
        # 最大値超過
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(tick_interval=3601)
        assert "less than or equal to 3600" in str(exc_info.value)
    
    def test_tick_probability_valid_range(self):
        """TICK_PROBABILITY: 0.0-1.0の範囲制約テスト"""
        config = TickConfig(tick_probability=0.33)
        assert config.tick_probability == 0.33
        
        config = TickConfig(tick_probability=0.0)  # 最小値
        assert config.tick_probability == 0.0
        
        config = TickConfig(tick_probability=1.0)  # 最大値
        assert config.tick_probability == 1.0
    
    def test_tick_probability_invalid_range(self):
        """TICK_PROBABILITY: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(tick_probability=-0.1)
        assert "greater than or equal to 0" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(tick_probability=1.1)
        assert "less than or equal to 1" in str(exc_info.value)


class TestScheduleConfigValidation:
    """時間帯設定のバリデーションテスト"""
    
    def test_hour_range_validation(self):
        """時間設定: 0-23時の範囲制約テスト"""
        # 有効な値
        config = ScheduleConfig(
            standby_start=0,
            processing_trigger=6,
            active_start=6,
            free_start=20
        )
        assert config.standby_start == 0
        assert config.processing_trigger == 6
        assert config.active_start == 6
        assert config.free_start == 20
        
        # 境界値テスト
        config = ScheduleConfig(standby_start=23)  # 最大値
        assert config.standby_start == 23
    
    def test_hour_range_invalid_values(self):
        """時間設定: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            ScheduleConfig(standby_start=-1)
        assert "greater than or equal to 0" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            ScheduleConfig(processing_trigger=24)
        assert "less than or equal to 23" in str(exc_info.value)


class TestMemoryConfigValidation:
    """メモリ設定のバリデーションテスト"""
    
    def test_cleanup_hours_valid_range(self):
        """MEMORY_CLEANUP_HOURS: 1-168時間の範囲制約テスト"""
        config = MemoryConfig(cleanup_hours=24)
        assert config.cleanup_hours == 24
        
        config = MemoryConfig(cleanup_hours=1)  # 最小値
        assert config.cleanup_hours == 1
        
        config = MemoryConfig(cleanup_hours=168)  # 最大値(7日)
        assert config.cleanup_hours == 168
    
    def test_cleanup_hours_invalid_range(self):
        """MEMORY_CLEANUP_HOURS: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            MemoryConfig(cleanup_hours=0)
        assert "greater than or equal to 1" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            MemoryConfig(cleanup_hours=169)
        assert "less than or equal to 168" in str(exc_info.value)
    
    def test_recent_limit_valid_range(self):
        """MEMORY_RECENT_LIMIT: 5-100件の範囲制約テスト"""
        config = MemoryConfig(recent_limit=30)
        assert config.recent_limit == 30
        
        config = MemoryConfig(recent_limit=5)  # 最小値
        assert config.recent_limit == 5
        
        config = MemoryConfig(recent_limit=100)  # 最大値
        assert config.recent_limit == 100
    
    def test_recent_limit_invalid_range(self):
        """MEMORY_RECENT_LIMIT: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            MemoryConfig(recent_limit=4)
        assert "greater than or equal to 5" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            MemoryConfig(recent_limit=101)
        assert "less than or equal to 100" in str(exc_info.value)


class TestAgentConfigValidation:
    """エージェント設定のバリデーションテスト"""
    
    def test_temperature_valid_range(self):
        """AGENT_*_TEMPERATURE: 0.0-2.0の範囲制約テスト"""
        config = AgentConfig(
            spectra_temperature=0.5,
            lynq_temperature=0.3,
            paz_temperature=0.9
        )
        assert config.spectra_temperature == 0.5
        assert config.lynq_temperature == 0.3
        assert config.paz_temperature == 0.9
        
        # 境界値テスト
        config = AgentConfig(
            spectra_temperature=0.0,
            lynq_temperature=2.0,
            paz_temperature=1.0
        )
        assert config.spectra_temperature == 0.0
        assert config.lynq_temperature == 2.0
        assert config.paz_temperature == 1.0
    
    def test_temperature_invalid_range(self):
        """AGENT_*_TEMPERATURE: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(spectra_temperature=-0.1)
        assert "greater than or equal to 0" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            AgentConfig(lynq_temperature=2.1)
        assert "less than or equal to 2" in str(exc_info.value)


class TestChannelConfigValidation:
    """チャンネル設定のバリデーションテスト"""
    
    def test_command_center_max_chars_valid_range(self):
        """CHANNEL_COMMAND_CENTER_MAX_CHARS: 50-500の範囲制約テスト"""
        config = ChannelConfig(command_center_max_chars=100)
        assert config.command_center_max_chars == 100
        
        config = ChannelConfig(command_center_max_chars=50)  # 最小値
        assert config.command_center_max_chars == 50
        
        config = ChannelConfig(command_center_max_chars=500)  # 最大値
        assert config.command_center_max_chars == 500
    
    def test_command_center_max_chars_invalid_range(self):
        """CHANNEL_COMMAND_CENTER_MAX_CHARS: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            ChannelConfig(command_center_max_chars=49)
        assert "greater than or equal to 50" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            ChannelConfig(command_center_max_chars=501)
        assert "less than or equal to 500" in str(exc_info.value)
    
    def test_creation_max_chars_valid_range(self):
        """CHANNEL_CREATION_MAX_CHARS: 100-1000の範囲制約テスト"""
        config = ChannelConfig(creation_max_chars=200)
        assert config.creation_max_chars == 200
        
        config = ChannelConfig(creation_max_chars=100)  # 最小値
        assert config.creation_max_chars == 100
        
        config = ChannelConfig(creation_max_chars=1000)  # 最大値
        assert config.creation_max_chars == 1000
    
    def test_creation_max_chars_invalid_range(self):
        """CHANNEL_CREATION_MAX_CHARS: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            ChannelConfig(creation_max_chars=99)
        assert "greater than or equal to 100" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            ChannelConfig(creation_max_chars=1001)
        assert "less than or equal to 1000" in str(exc_info.value)
    
    def test_lounge_max_chars_valid_range(self):
        """CHANNEL_LOUNGE_MAX_CHARS: 10-100の範囲制約テスト"""
        config = ChannelConfig(lounge_max_chars=30)
        assert config.lounge_max_chars == 30
        
        config = ChannelConfig(lounge_max_chars=10)  # 最小値
        assert config.lounge_max_chars == 10
        
        config = ChannelConfig(lounge_max_chars=100)  # 最大値
        assert config.lounge_max_chars == 100
    
    def test_lounge_max_chars_invalid_range(self):
        """CHANNEL_LOUNGE_MAX_CHARS: 無効値でのバリデーションエラーテスト"""
        with pytest.raises(ValidationError) as exc_info:
            ChannelConfig(lounge_max_chars=9)
        assert "greater than or equal to 10" in str(exc_info.value)
        
        with pytest.raises(ValidationError) as exc_info:
            ChannelConfig(lounge_max_chars=101)
        assert "less than or equal to 100" in str(exc_info.value)


class TestDefaultValuesValidation:
    """デフォルト値のバリデーションテスト"""
    
    def test_tick_config_defaults(self):
        """TickConfig: デフォルト値の適切性テスト"""
        config = TickConfig()
        assert config.tick_interval == 300  # デフォルト5分
        assert config.tick_probability == 0.33  # デフォルト33%
    
    def test_memory_config_defaults(self):
        """MemoryConfig: デフォルト値の適切性テスト"""
        config = MemoryConfig()
        assert config.cleanup_hours == 24  # デフォルト24時間
        assert config.recent_limit == 30  # デフォルト30件


class TestFailFastBehavior:
    """Fail-Fast動作のテスト"""
    
    def test_validation_error_immediate_failure(self):
        """バリデーションエラー時の即座停止テスト"""
        # 複数の不正値を設定した場合、最初のエラーで即座停止
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(
                tick_interval=5,  # 不正: 最小値15未満
                tick_probability=2.0  # 不正: 最大値1.0超過
            )
        
        # 最初のフィールドエラーで停止することを確認
        error_str = str(exc_info.value)
        assert "tick_interval" in error_str
    
    def test_settings_integration_fail_fast(self):
        """Settings統合時のFail-Fast動作テスト"""
        # 無効な設定で Settings を初期化した場合の即座失敗
        with pytest.raises(ValidationError):
            Settings(
                tick=TickConfig(tick_interval=5),  # 不正値
                memory=MemoryConfig(cleanup_hours=0)  # 不正値
            )


class TestTypeValidation:
    """型制約のバリデーションテスト"""
    
    def test_integer_type_validation(self):
        """整数型フィールドの型制約テスト"""
        # 文字列を整数フィールドに設定した場合のエラー
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(tick_interval="invalid")
        assert "input should be a valid integer" in str(exc_info.value).lower()
    
    def test_float_type_validation(self):
        """浮動小数点型フィールドの型制約テスト"""
        # 文字列を浮動小数点フィールドに設定した場合のエラー  
        with pytest.raises(ValidationError) as exc_info:
            TickConfig(tick_probability="invalid")
        assert "input should be a valid number" in str(exc_info.value).lower()
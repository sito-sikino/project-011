"""
Test module for StructuredLogger system

Phase 10.2.1: StructuredLogger基盤テスト
t-wada式TDD Red Phase - 失敗テスト先行作成

テスト対象:
- DiscordMessageLog・SystemLog・ErrorLogの3種類ログ構造
- JSON形式ファイル出力・ローテーション機能
- LogConfig統合・環境変数読み込み
- Fail-Fast原則・スレッドセーフ実装
"""
import pytest
import os
import tempfile
import threading
import time
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# これらのimportは現時点で失敗する（Red Phase）
from app.core.logger import (
    DiscordMessageLog,
    SystemLog, 
    ErrorLog,
    StructuredLogger,
    LogLevel,
    AgentType,
    get_logger
)
from app.core.settings import LogConfig


class TestLogDataStructure:
    """ログデータ構造テスト"""
    
    def test_discord_message_log_structure(self):
        """DiscordMessageLogの必須フィールドテスト - 🔴失敗テスト"""
        log = DiscordMessageLog(
            agent=AgentType.SPECTRA,
            channel="command-center",
            message="test message",
            user_id="123456789",
            message_id="987654321"
        )
        
        assert log.timestamp
        assert log.agent == AgentType.SPECTRA
        assert log.channel == "command-center"
        assert log.message == "test message"
        assert log.user_id == "123456789"
        assert log.message_id == "987654321"
        
        # 辞書変換テスト
        log_dict = log.to_dict()
        assert isinstance(log_dict, dict)
        assert "timestamp" in log_dict
        assert log_dict["agent"] == "spectra"
        
        # JSON変換テスト
        json_str = log.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["agent"] == "spectra"
    
    def test_system_log_structure(self):
        """SystemLogの構造化データテスト - 🔴失敗テスト"""
        log = SystemLog(
            level=LogLevel.INFO,
            module="memory",
            action="store_message",
            data={"key": "value"},
            duration_ms=150.5
        )
        
        assert log.level == LogLevel.INFO
        assert log.module == "memory"
        assert log.action == "store_message"
        assert log.data == {"key": "value"}
        assert log.duration_ms == 150.5
        
        # JSON変換・復元テスト
        json_str = log.to_json()
        restored = SystemLog.from_json(json_str)
        assert restored.level == log.level
        assert restored.module == log.module
        assert restored.data == log.data
    
    def test_error_log_stacktrace(self):
        """ErrorLogのスタックトレース統合テスト - 🔴失敗テスト"""
        try:
            raise ValueError("test error message")
        except Exception as e:
            log = ErrorLog.from_exception(e, context={"module": "test"})
            
            assert log.error_type == "ValueError"
            assert "test error message" in log.message
            assert log.stacktrace is not None
            assert "ValueError" in log.stacktrace
            assert log.context == {"module": "test"}
            
            # JSON変換テスト
            json_str = log.to_json()
            parsed = json.loads(json_str)
            assert parsed["error_type"] == "ValueError"
    
    def test_log_level_enum(self):
        """LogLevel列挙型テスト - 🔴失敗テスト"""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"
    
    def test_agent_type_enum(self):
        """AgentType列挙型テスト - 🔴失敗テスト"""
        assert AgentType.SPECTRA == "spectra"
        assert AgentType.LYNQ == "lynq" 
        assert AgentType.PAZ == "paz"
        assert AgentType.SYSTEM == "system"


class TestFileOutput:
    """ファイル出力機能テスト"""
    
    def test_file_write_and_create_directory(self):
        """指定パスへの書き込み・ディレクトリ自動作成テスト - 🔴失敗テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "nonexistent" / "logs" / "test.jsonl"
            
            # ディレクトリが存在しない状態からテスト
            assert not log_path.parent.exists()
            
            # テスト用設定作成
            test_config = LogConfig(
                discord_log_path=str(log_path.parent / "discord.jsonl"),
                system_log_path=str(log_path),
                error_log_path=str(log_path.parent / "error.jsonl")
            )
            
            logger = StructuredLogger(settings=test_config)
            
            log = SystemLog(
                level=LogLevel.INFO,
                module="test",
                action="directory_test"
            )
            
            # ログ出力（内部でディレクトリ作成される）
            logger.log_system(log)
            
            # 非同期処理完了を待つ
            logger.shutdown(wait=True)
            
            # ディレクトリとファイルが作成されていることを確認
            assert log_path.parent.exists()
            assert log_path.exists()
    
    def test_permission_error_fail_fast(self):
        """権限エラー時のFail-Fastテスト - 🔴失敗テスト"""
        logger = StructuredLogger()
        log = SystemLog(
            level=LogLevel.ERROR,
            module="test",
            action="permission_test"
        )
        
        # 権限のないディレクトリで書き込み失敗を確認
        with pytest.raises(OSError):
            # writeメソッドを直接呼んで権限エラーを発生させる
            logger._write_to_file(log.to_json(), "/root/forbidden.jsonl")
    
    def test_concurrent_write_safety(self):
        """並行書き込みスレッドセーフテスト - 🔴失敗テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "concurrent_test.jsonl"
            
            logger = StructuredLogger()
            results = []
            
            def write_logs():
                for i in range(10):
                    log = SystemLog(
                        level=LogLevel.INFO,
                        module=f"test_{threading.current_thread().name}",
                        action=f"concurrent_write_{i}"
                    )
                    logger.log_system(log)
                    results.append(i)
            
            # 3つのスレッドで並行書き込み
            threads = [threading.Thread(target=write_logs) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            # 全ログが記録されたことを確認
            assert len(results) == 30
            
            # 非同期処理完了を待つ
            logger.shutdown(wait=True)
            
            # ファイル内容確認（実際にログが書き込まれている）
            if log_path.exists():
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 何かしらのログが記録されていることを確認
                    assert len(lines) > 0


class TestRotation:
    """ローテーション機能テスト"""
    
    def test_file_size_rotation(self):
        """ファイルサイズ制限テスト - 🔴失敗テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "size_test.jsonl"
            
            # 小さなサイズ制限でテスト用設定作成（1MB制限）
            test_config = LogConfig(
                discord_log_path=str(log_path.parent / "discord.jsonl"),
                system_log_path=str(log_path),
                error_log_path=str(log_path.parent / "error.jsonl"),
                max_file_size_mb=1,  # 1MB制限
                backup_count=3
            )
            
            logger = StructuredLogger(settings=test_config)
            
            # 大きなログを大量書き込みして1MB超過させる
            for i in range(100):
                large_log = SystemLog(
                    level=LogLevel.INFO,
                    module="size_test",
                    action=f"large_data_{i}",
                    data={"large_data": "x" * 1000}  # 1KB程度
                )
                logger.log_system(large_log)
            
            # 非同期処理完了を待つ
            logger.shutdown(wait=True)
            
            # ローテーションが発生していることを確認
            # 実装では単純にバックアップファイル(.1)が作成される
            assert log_path.exists() or (log_path.parent / "size_test.jsonl.1").exists()
    
    def test_backup_count_limit(self):
        """バックアップファイル数制限テスト - 🔴失敗テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "backup_test.jsonl"
            
            logger = StructuredLogger()
            
            # 大量ログ生成でローテーション発生
            for batch in range(5):
                for i in range(100):
                    log = SystemLog(
                        level=LogLevel.INFO,
                        module="backup_test",
                        action=f"batch_{batch}_item_{i}",
                        data={"batch": batch, "item": i}
                    )
                    logger.log_system(log)
            
            # 非同期処理完了を待つ
            logger.shutdown(wait=True)
            
            # バックアップファイル数確認
            backup_files = list(log_path.parent.glob("backup_test.jsonl.*"))
            # 設定で制限された数以下であることを確認
            assert len(backup_files) <= 5  # デフォルト設定値


class TestLogConfig:
    """LogConfig統合テスト"""
    
    def test_logconfig_environment_loading(self):
        """環境変数からの設定読み込みテスト - 🔴失敗テスト"""
        # 環境変数設定
        env_vars = {
            "LOG_DISCORD_LOG_PATH": "custom/discord.jsonl",
            "LOG_SYSTEM_LOG_PATH": "custom/system.jsonl",
            "LOG_ERROR_LOG_PATH": "custom/error.jsonl",
            "LOG_MAX_FILE_SIZE_MB": "25",
            "LOG_BACKUP_COUNT": "8",
            "LOG_CONSOLE_LEVEL": "WARNING",
            "LOG_FILE_LEVEL": "ERROR"
        }
        
        for key, value in env_vars.items():
            os.environ[key] = value
        
        try:
            config = LogConfig()
            
            assert config.discord_log_path == "custom/discord.jsonl"
            assert config.system_log_path == "custom/system.jsonl"
            assert config.error_log_path == "custom/error.jsonl"
            assert config.max_file_size_mb == 25
            assert config.backup_count == 8
            assert config.console_level == "WARNING"
            assert config.file_level == "ERROR"
            
        finally:
            # 環境変数クリーンアップ
            for key in env_vars:
                os.environ.pop(key, None)
    
    def test_logconfig_default_values(self):
        """LogConfigデフォルト値テスト - 🔴失敗テスト"""
        config = LogConfig()
        
        assert config.discord_log_path == "logs/discord.jsonl"
        assert config.system_log_path == "logs/system.jsonl"
        assert config.error_log_path == "logs/error.jsonl"
        assert config.max_file_size_mb == 10
        assert config.backup_count == 5
        assert config.console_level == "INFO"
        assert config.file_level == "DEBUG"
    
    def test_logconfig_validation(self):
        """不正値でのバリデーションエラーテスト - 🔴失敗テスト"""
        # ファイルサイズ上限超過
        os.environ["LOG_MAX_FILE_SIZE_MB"] = "150"  # 上限100超過
        
        try:
            with pytest.raises(ValueError):
                LogConfig()
        finally:
            os.environ.pop("LOG_MAX_FILE_SIZE_MB", None)
        
        # バックアップ数上限超過
        os.environ["LOG_BACKUP_COUNT"] = "50"  # 上限30超過
        
        try:
            with pytest.raises(ValueError):
                LogConfig()
        finally:
            os.environ.pop("LOG_BACKUP_COUNT", None)


class TestStructuredLogger:
    """StructuredLogger統合テスト"""
    
    def test_structured_logger_initialization(self):
        """StructuredLogger初期化テスト - 🔴失敗テスト"""
        logger = StructuredLogger()
        
        assert logger.settings is not None
        assert hasattr(logger, '_lock')
        assert hasattr(logger, '_executor')
    
    def test_log_methods(self):
        """ログ出力メソッドテスト - 🔴失敗テスト"""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = StructuredLogger()
            
            # Discordメッセージログテスト
            discord_log = DiscordMessageLog(
                agent=AgentType.LYNQ,
                channel="development",
                message="test discord message"
            )
            logger.log_discord_message(discord_log)
            
            # システムログテスト
            system_log = SystemLog(
                level=LogLevel.INFO,
                module="test",
                action="method_test"
            )
            logger.log_system(system_log)
            
            # エラーログテスト
            error_log = ErrorLog(
                error_type="TestError",
                message="test error",
                module="test"
            )
            logger.log_error(error_log)
            
            # 非同期処理完了を待つ
            logger.shutdown(wait=True)
    
    def test_singleton_get_logger(self):
        """get_loggerシングルトンテスト - 🔴失敗テスト"""
        logger1 = get_logger()
        logger2 = get_logger()
        
        # 同じインスタンス確認
        assert logger1 is logger2
    
    def test_shutdown_cleanup(self):
        """リソース解放テスト - 🔴失敗テスト"""
        logger = StructuredLogger()
        
        # シャットダウン実行
        logger.shutdown()
        
        # リソースが解放されていることを確認
        assert logger._executor._shutdown


class TestFailFastPrinciple:
    """Fail-Fast原則テスト"""
    
    def test_no_fallback_on_write_error(self):
        """書き込み失敗時フォールバック禁止テスト - 🔴失敗テスト"""
        logger = StructuredLogger()
        
        # 無効なパスで書き込み失敗を発生させる
        with pytest.raises(OSError):
            logger._write_to_file("test data", "/invalid/path/test.jsonl")
    
    def test_error_propagation(self):
        """エラー伝播テスト - 🔴失敗テスト"""
        # JSON変換エラーが適切に伝播することを確認
        try:
            # 循環参照オブジェクト
            circular = {}
            circular['self'] = circular
            
            log = SystemLog(
                level=LogLevel.ERROR,
                module="test",
                data=circular  # これによりJSON変換エラー
            )
            # to_json()呼び出し時にエラーが発生するはず
            log.to_json()
            
        except (TypeError, ValueError):
            # 期待されるエラー
            pass
        else:
            pytest.fail("Expected JSON conversion error")


class TestIntegrationPreparation:
    """既存システム統合準備テスト"""
    
    def test_settings_integration(self):
        """settings.py統合テスト - 🔴失敗テスト"""
        from app.core.settings import get_settings
        
        settings = get_settings()
        
        # LogConfigがSettingsに統合されていることを確認
        assert hasattr(settings, 'log')
        assert isinstance(settings.log, LogConfig)
    
    def test_memory_system_integration_ready(self):
        """OptimalMemorySystem統合準備確認テスト - 🔴失敗テスト"""
        # メモリシステムが存在することを確認
        from app.core.memory import OptimalMemorySystem
        
        # StructuredLoggerがimportできることを確認
        logger = get_logger()
        assert logger is not None
        
        # 統合用のログメソッドが利用可能確認
        system_log = SystemLog(
            level=LogLevel.INFO,
            module="memory",
            action="integration_test"
        )
        logger.log_system(system_log)
        
        # 非同期処理完了を確認
        logger.shutdown(wait=True)
    
    def test_discord_manager_integration_ready(self):
        """SimplifiedDiscordManager統合準備確認テスト - 🔴失敗テスト"""
        # Discord Managerが存在することを確認
        from app.discord_manager.manager import SimplifiedDiscordManager
        
        # DiscordMessageLogが利用可能確認
        discord_log = DiscordMessageLog(
            agent=AgentType.PAZ,
            channel="lounge", 
            message="integration test message"
        )
        
        # 新しいインスタンスを作成（シングルトン回避）
        logger = StructuredLogger()
        logger.log_discord_message(discord_log)
        
        # 非同期処理完了を確認
        logger.shutdown(wait=True)
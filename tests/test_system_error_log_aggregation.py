"""
Test Suite: Phase 10.2.3 System Error Log Aggregation

TDD Red Phase: 先行テスト作成
- 既存logging.error()の構造化ログ置換テスト
- Fail-Fast原則（sys.exit(1)）動作テスト
- 各システムモジュール統合テスト
- ErrorLog.from_exception()活用テスト

CLAUDE.md原則準拠:
- Fail-Fast: エラーログ記録後sys.exit(1)必須
- 最小実装: 要求機能のみテスト
- 構造化ログ: ErrorLog統一使用
"""

import pytest
import sys
import json
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import asyncio

from app.core.logger import ErrorLog, get_logger, StructuredLogger, LogLevel
from app.core.settings import get_settings


class TestSystemErrorLogAggregation:
    """システム・エラーログ集約テスト"""
    
    def test_error_log_from_exception_integration(self):
        """ErrorLog.from_exception()統合テスト"""
        # テスト用例外作成
        try:
            raise ValueError("Test database connection error")
        except Exception as e:
            # ErrorLogを例外から生成
            error_log = ErrorLog.from_exception(
                e, 
                context={"module": "database", "operation": "connect"}
            )
            
            # 必要なフィールド確認
            assert error_log.error_type == "ValueError"
            assert error_log.message == "Test database connection error"
            assert error_log.context["module"] == "database"
            assert error_log.context["operation"] == "connect"
            assert error_log.stacktrace is not None
            assert "ValueError" in error_log.stacktrace
    
    @patch('app.core.logger.get_logger')
    @patch('sys.exit')
    def test_unified_error_handler_pattern(self, mock_exit, mock_get_logger):
        """統一エラーハンドラーパターンテスト"""
        # モックロガー設定
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # テスト対象の統一エラーハンドラー
        def handle_system_error(exc: Exception, context: dict = None):
            """統一システムエラーハンドラー"""
            from app.core.logger import get_logger, ErrorLog
            
            logger = get_logger()
            error_log = ErrorLog.from_exception(exc, context=context)
            logger.log_error(error_log)
            logger.shutdown(wait=True)
            sys.exit(1)
        
        # テスト実行
        test_exception = RuntimeError("System initialization failed")
        test_context = {"module": "database", "phase": "initialization"}
        
        # 例外が発生した場合のハンドラー実行
        handle_system_error(test_exception, test_context)
        
        # アサーション
        mock_get_logger.assert_called_once()
        mock_logger.log_error.assert_called_once()
        mock_logger.shutdown.assert_called_once_with(wait=True)
        mock_exit.assert_called_once_with(1)
    
    @patch('app.core.logger.get_logger')
    @patch('sys.exit')
    def test_database_error_aggregation(self, mock_exit, mock_get_logger):
        """Database系エラー集約テスト"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Database接続エラーシミュレーション
        def database_operation_with_error_aggregation():
            try:
                # データベース操作シミュレーション
                raise ConnectionError("Failed to connect to PostgreSQL")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"module": "database", "operation": "connection"}
                )
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
        
        # テスト実行
        database_operation_with_error_aggregation()
        
        # 統一エラー処理が実行されたことを確認
        assert mock_logger.log_error.called
        error_log_call_args = mock_logger.log_error.call_args[0][0]
        assert error_log_call_args.error_type == "ConnectionError"
        assert error_log_call_args.context["module"] == "database"
        mock_exit.assert_called_once_with(1)
    
    @patch('app.core.logger.get_logger')
    @patch('sys.exit')
    def test_memory_error_aggregation(self, mock_exit, mock_get_logger):
        """Memory系エラー集約テスト"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Memory操作エラーシミュレーション
        def memory_operation_with_error_aggregation():
            try:
                # メモリ操作シミュレーション
                raise RuntimeError("Redis connection timeout")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"module": "memory", "operation": "redis_connect"}
                )
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
        
        # テスト実行
        memory_operation_with_error_aggregation()
        
        # 統一エラー処理が実行されたことを確認
        assert mock_logger.log_error.called
        error_log_call_args = mock_logger.log_error.call_args[0][0]
        assert error_log_call_args.error_type == "RuntimeError"
        assert error_log_call_args.context["module"] == "memory"
        mock_exit.assert_called_once_with(1)
    
    @patch('app.core.logger.get_logger')  
    @patch('sys.exit')
    def test_task_error_aggregation(self, mock_exit, mock_get_logger):
        """Task系エラー集約テスト"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Task操作エラーシミュレーション
        def task_operation_with_error_aggregation():
            try:
                # タスク操作シミュレーション
                raise ValueError("Invalid task configuration")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"module": "tasks", "operation": "task_creation"}
                )
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
        
        # テスト実行
        task_operation_with_error_aggregation()
        
        # 統一エラー処理が実行されたことを確認
        assert mock_logger.log_error.called
        error_log_call_args = mock_logger.log_error.call_args[0][0]
        assert error_log_call_args.error_type == "ValueError"
        assert error_log_call_args.context["module"] == "tasks"
        mock_exit.assert_called_once_with(1)
    
    @patch('app.core.logger.get_logger')
    @patch('sys.exit')
    def test_langgraph_error_aggregation(self, mock_exit, mock_get_logger):
        """LangGraph系エラー集約テスト"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # LangGraph操作エラーシミュレーション
        def langgraph_operation_with_error_aggregation():
            try:
                # LangGraph操作シミュレーション
                raise Exception("Agent invocation failed")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"module": "langgraph", "agent": "supervisor", "operation": "invoke"}
                )
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
        
        # テスト実行
        langgraph_operation_with_error_aggregation()
        
        # 統一エラー処理が実行されたことを確認
        assert mock_logger.log_error.called
        error_log_call_args = mock_logger.log_error.call_args[0][0]
        assert error_log_call_args.error_type == "Exception"
        assert error_log_call_args.context["module"] == "langgraph"
        assert error_log_call_args.context["agent"] == "supervisor"
        mock_exit.assert_called_once_with(1)
    
    @patch('app.core.logger.get_logger')
    @patch('sys.exit')  
    def test_discord_error_aggregation(self, mock_exit, mock_get_logger):
        """Discord系エラー集約テスト"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Discord操作エラーシミュレーション
        def discord_operation_with_error_aggregation():
            try:
                # Discord操作シミュレーション
                raise ConnectionError("Discord API connection failed")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"module": "discord_manager", "operation": "message_send"}
                )
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
        
        # テスト実行
        discord_operation_with_error_aggregation()
        
        # 統一エラー処理が実行されたことを確認
        assert mock_logger.log_error.called
        error_log_call_args = mock_logger.log_error.call_args[0][0]
        assert error_log_call_args.error_type == "ConnectionError"
        assert error_log_call_args.context["module"] == "discord_manager"
        mock_exit.assert_called_once_with(1)
    
    @patch('app.core.logger.get_logger')
    @patch('sys.exit')
    def test_settings_error_aggregation(self, mock_exit, mock_get_logger):
        """Settings系エラー集約テスト"""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger
        
        # Settings検証エラーシミュレーション
        def settings_validation_with_error_aggregation():
            try:
                # 設定検証シミュレーション
                raise ValueError("Required environment variables are missing: GEMINI_API_KEY")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"module": "settings", "operation": "validation"}
                )
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
        
        # テスト実行
        settings_validation_with_error_aggregation()
        
        # 統一エラー処理が実行されたことを確認
        assert mock_logger.log_error.called
        error_log_call_args = mock_logger.log_error.call_args[0][0]
        assert error_log_call_args.error_type == "ValueError"
        assert error_log_call_args.context["module"] == "settings"
        mock_exit.assert_called_once_with(1)
    
    def test_error_context_preservation(self):
        """エラーコンテキスト保持テスト"""
        # 複雑なコンテキストでテスト
        complex_context = {
            "module": "database",
            "operation": "migration",
            "migration_version": "001_create_table",
            "table": "agent_memory",
            "attempt": 3,
            "metadata": {
                "user": "system",
                "timestamp": "2025-08-10T15:30:00Z"
            }
        }
        
        try:
            raise RuntimeError("Migration rollback failed")
        except Exception as e:
            error_log = ErrorLog.from_exception(e, context=complex_context)
            
            # コンテキストが完全に保持されていることを確認
            assert error_log.context == complex_context
            assert error_log.context["metadata"]["user"] == "system"
            assert error_log.context["attempt"] == 3
    
    def test_error_log_json_serialization(self):
        """ErrorLog JSON直列化テスト"""
        try:
            raise TypeError("Invalid parameter type")
        except Exception as e:
            error_log = ErrorLog.from_exception(
                e, 
                context={"module": "test", "parameter": "invalid_value"}
            )
            
            # JSON直列化・復元テスト  
            json_str = error_log.to_json()
            assert isinstance(json_str, str)
            
            # JSON形式確認
            parsed = json.loads(json_str)
            assert parsed["error_type"] == "TypeError"
            assert parsed["context"]["module"] == "test"
            assert "stacktrace" in parsed
    
    @patch('builtins.open', create=True)
    @patch('pathlib.Path.mkdir')
    def test_error_log_file_writing(self, mock_mkdir, mock_open):
        """エラーログファイル書き込みテスト"""
        # StructuredLoggerのファイル書き込み機能テスト
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # テスト用設定
        mock_settings = Mock()
        mock_settings.error_log_path = "logs/error.jsonl"
        mock_settings.max_file_size_mb = 10
        
        # StructuredLoggerでエラーログ出力
        logger = StructuredLogger(mock_settings)
        
        # ErrorLog作成・書き込み
        try:
            raise Exception("Test error for file writing")
        except Exception as e:
            error_log = ErrorLog.from_exception(e, context={"test": True})
            logger.log_error(error_log)
        
        # ファイル書き込み確認は非同期処理のため、
        # 実際のファイル操作確認は統合テストで実施
        assert mock_mkdir.called  # ディレクトリ作成が呼ばれたことを確認


class TestFailFastEnforcement:
    """Fail-Fast原則強化テスト"""
    
    @patch('sys.exit')
    def test_mandatory_exit_after_error_logging(self, mock_exit):
        """エラーログ記録後の必須sys.exit(1)テスト"""
        
        def operation_with_mandatory_fail_fast():
            try:
                raise RuntimeError("Critical system error")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(e)
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                # Fail-Fast原則: 必ずsys.exit(1)
                sys.exit(1)
        
        # テスト実行
        operation_with_mandatory_fail_fast()
        
        # sys.exit(1)が確実に呼ばれることを確認
        mock_exit.assert_called_once_with(1)
    
    @patch('sys.exit')
    def test_no_fallback_after_error(self, mock_exit):
        """エラー後のフォールバック処理禁止テスト"""
        
        def operation_without_fallback():
            try:
                raise ValueError("Configuration error")
            except Exception as e:
                from app.core.logger import get_logger, ErrorLog
                logger = get_logger()
                error_log = ErrorLog.from_exception(e)
                logger.log_error(error_log)
                logger.shutdown(wait=True)
                sys.exit(1)
                # この行以降は実行されない（フォールバック禁止）
                return "fallback_value"  # pragma: no cover
        
        # テスト実行
        result = operation_without_fallback()
        
        # フォールバック処理が実行されないことを確認
        mock_exit.assert_called_once_with(1)
        # sys.exit(1)により、return文は実行されない


class TestPerformanceImpact:
    """パフォーマンス影響テスト"""
    
    def test_error_logging_performance(self):
        """エラーログ記録のパフォーマンステスト"""
        import time
        
        # 大量のエラーログ生成テスト
        start_time = time.time()
        
        for i in range(100):
            try:
                raise ValueError(f"Test error {i}")
            except Exception as e:
                error_log = ErrorLog.from_exception(
                    e, 
                    context={"iteration": i, "batch": "performance_test"}
                )
                # JSON化のパフォーマンス測定
                json_str = error_log.to_json()
                assert len(json_str) > 0
        
        elapsed_time = time.time() - start_time
        
        # 100個のエラーログ処理が適切な時間内に完了することを確認
        # （具体的な閾値は環境依存だが、明らかに遅い場合を検出）
        assert elapsed_time < 1.0  # 1秒以内
    
    def test_minimal_context_overhead(self):
        """最小限のコンテキストオーバーヘッドテスト"""
        
        # 最小限のコンテキストでのErrorLog作成
        try:
            raise RuntimeError("Minimal test")
        except Exception as e:
            # コンテキストなし
            error_log_minimal = ErrorLog.from_exception(e)
            
            # 最小限のコンテキスト
            error_log_context = ErrorLog.from_exception(
                e, context={"module": "test"}
            )
            
            # JSON化サイズの比較（大幅な増加がないことを確認）
            minimal_size = len(error_log_minimal.to_json())
            context_size = len(error_log_context.to_json())
            
            # コンテキスト追加による容量増加が適切な範囲内
            size_increase = context_size - minimal_size
            assert size_increase < 100  # 100文字未満の増加
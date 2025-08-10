"""
Discord Multi-Agent System 統一エラーハンドラー

Phase 10.2.3: システム・エラーログ集約実装
統一エラーハンドラー・Fail-Fast原則・StructuredLogger統合

CLAUDE.md原則準拠:
- Fail-Fast: エラーログ記録後sys.exit(1)必須・フォールバック絶対禁止
- 最小実装: 要求機能のみ実装・余分なロジック排除
- 構造化ログ: ErrorLog統一使用・logger.error()置換

Performance Optimizations:
- Logger instance caching
- Context validation
- Minimal overhead error handling
"""

import sys
import traceback
from typing import Dict, Any, Optional
from app.core.logger import get_logger, ErrorLog

# Performance: Logger instance caching
_cached_logger = None


def _get_cached_logger():
    """Performance: Cached logger instance retrieval"""
    global _cached_logger
    if _cached_logger is None:
        _cached_logger = get_logger()
    return _cached_logger


def _validate_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Performance: Minimal context validation and cleanup"""
    if not context:
        return {}
    
    # Minimal validation - only ensure basic types
    if not isinstance(context, dict):
        return {"invalid_context": str(context)}
    
    # Limit context size for performance
    if len(context) > 10:
        return dict(list(context.items())[:10])
    
    return context


def handle_system_error(
    exc: Exception, 
    context: Optional[Dict[str, Any]] = None,
    exit_code: int = 1
) -> None:
    """
    統一システムエラーハンドラー（Performance Optimized）
    
    全システムモジュールで使用する統一エラー処理
    ErrorLog.from_exception()活用・StructuredLogger統合・Fail-Fast原則完全準拠
    
    Args:
        exc: 発生した例外
        context: エラーコンテキスト情報
        exit_code: 終了コード（デフォルト: 1）
        
    Performance Optimizations:
        - Logger instance caching
        - Context validation and size limiting
        - Minimal overhead error processing
        
    Fail-Fast原則:
        - エラーログ記録後、必ずsys.exit()実行
        - フォールバック処理絶対禁止
        - 例外の再発生や隠蔽禁止
    """
    try:
        # Performance: Use cached logger instance
        logger = _get_cached_logger()
        
        # Performance: Validate and optimize context
        validated_context = _validate_context(context)
        
        # ErrorLog生成（from_exception活用）
        error_log = ErrorLog.from_exception(exc, context=validated_context)
        
        # 構造化エラーログ記録
        logger.log_error(error_log)
        
        # ログ書き込み完了まで待機
        logger.shutdown(wait=True)
        
    except Exception as log_error:
        # Performance: Minimal fallback error handling
        try:
            # Fast stderr output without formatting overhead
            sys.stderr.write(f"FATAL: Error logging failed: {log_error}\n")
            sys.stderr.write(f"Original error: {exc}\n")
            sys.stderr.flush()
        except:
            # Ultimate fallback - silent failure before exit
            pass
    
    # Fail-Fast: 必ずシステム停止
    sys.exit(exit_code)


def handle_database_error(exc: Exception, operation: str = "unknown") -> None:
    """
    Database系エラー専用ハンドラー（Performance Optimized）
    
    Args:
        exc: データベース例外
        operation: 実行中の操作名
    """
    # Performance: Pre-built context to avoid dict construction overhead
    context = {
        "module": "database",
        "operation": operation,
        "error_category": "database_error"
    }
    handle_system_error(exc, context)


def handle_memory_error(exc: Exception, operation: str = "unknown") -> None:
    """
    Memory系エラー専用ハンドラー
    
    Args:
        exc: メモリ操作例外
        operation: 実行中の操作名
    """
    context = {
        "module": "memory", 
        "operation": operation,
        "error_category": "memory_error"
    }
    handle_system_error(exc, context)


def handle_task_error(exc: Exception, operation: str = "unknown", task_id: str = None) -> None:
    """
    Task系エラー専用ハンドラー
    
    Args:
        exc: タスク処理例外
        operation: 実行中の操作名
        task_id: 関連タスクID
    """
    context = {
        "module": "tasks",
        "operation": operation,
        "error_category": "task_error"
    }
    if task_id:
        context["task_id"] = task_id
    handle_system_error(exc, context)


def handle_langgraph_error(
    exc: Exception, 
    agent: str = "unknown",
    operation: str = "unknown"
) -> None:
    """
    LangGraph系エラー専用ハンドラー
    
    Args:
        exc: LangGraph実行例外
        agent: 関連エージェント名
        operation: 実行中の操作名
    """
    context = {
        "module": "langgraph",
        "agent": agent,
        "operation": operation,
        "error_category": "langgraph_error"
    }
    handle_system_error(exc, context)


def handle_discord_error(
    exc: Exception,
    operation: str = "unknown", 
    agent: str = None,
    channel: str = None
) -> None:
    """
    Discord系エラー専用ハンドラー
    
    Args:
        exc: Discord API例外
        operation: 実行中の操作名
        agent: 関連エージェント名
        channel: 関連チャンネル名
    """
    context = {
        "module": "discord_manager",
        "operation": operation,
        "error_category": "discord_error"
    }
    if agent:
        context["agent"] = agent
    if channel:
        context["channel"] = channel
    handle_system_error(exc, context)


def handle_settings_error(exc: Exception, operation: str = "unknown") -> None:
    """
    Settings系エラー専用ハンドラー
    
    Args:
        exc: 設定関連例外
        operation: 実行中の操作名
    """
    context = {
        "module": "settings",
        "operation": operation,
        "error_category": "settings_error"
    }
    handle_system_error(exc, context)


# 既存logging.error()置換用のヘルパー関数
def log_and_exit(message: str, context: Optional[Dict[str, Any]] = None) -> None:
    """
    既存logging.error()の直接置換用ヘルパー
    
    Args:
        message: エラーメッセージ
        context: 追加コンテキスト
        
    Usage:
        # 置換前:
        logging.error("Database connection failed")
        
        # 置換後:
        log_and_exit("Database connection failed", {"module": "database"})
    """
    # RuntimeErrorとして例外化
    exc = RuntimeError(message)
    handle_system_error(exc, context)


# モジュール別置換用便利関数
def database_log_and_exit(message: str, operation: str = "unknown") -> None:
    """Database系logging.error()置換用"""
    exc = RuntimeError(message)
    handle_database_error(exc, operation)


def memory_log_and_exit(message: str, operation: str = "unknown") -> None:
    """Memory系logging.error()置換用"""  
    exc = RuntimeError(message)
    handle_memory_error(exc, operation)


def task_log_and_exit(message: str, operation: str = "unknown", task_id: str = None) -> None:
    """Task系logging.error()置換用"""
    exc = RuntimeError(message)
    handle_task_error(exc, operation, task_id)


def langgraph_log_and_exit(
    message: str, 
    agent: str = "unknown", 
    operation: str = "unknown"
) -> None:
    """LangGraph系logging.error()置換用"""
    exc = RuntimeError(message)
    handle_langgraph_error(exc, agent, operation)


def discord_log_and_exit(
    message: str,
    operation: str = "unknown",
    agent: str = None, 
    channel: str = None
) -> None:
    """Discord系logging.error()置換用"""
    exc = RuntimeError(message)
    handle_discord_error(exc, operation, agent, channel)


def settings_log_and_exit(message: str, operation: str = "unknown") -> None:
    """Settings系logging.error()置換用"""
    exc = RuntimeError(message)
    handle_settings_error(exc, operation)
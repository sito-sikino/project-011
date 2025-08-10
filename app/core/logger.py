"""
Discord Multi-Agent System 構造化ログシステム

Phase 10.2.1: StructuredLogger基盤実装
t-wada式TDD Green Phase - 最小実装でテスト通過

CLAUDE.md原則準拠:
- Fail-Fast: ログ書き込み失敗時即停止・フォールバック禁止
- 最小実装: 要求機能のみ実装・余分なコード排除
- 設定一元管理: LogConfig経由設定制御
"""

import json
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class LogLevel(str, Enum):
    """ログレベル列挙"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AgentType(str, Enum):
    """エージェント種別列挙"""

    SPECTRA = "spectra"
    LYNQ = "lynq"
    PAZ = "paz"
    SYSTEM = "system"


class DiscordMessageLog(BaseModel):
    """
    Discordメッセージログ構造

    エージェント発言・ユーザー応答の記録
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    agent: AgentType
    channel: str
    message: str
    user_id: Optional[str] = None
    message_id: Optional[str] = None
    reply_to: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式変換"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent.value,
            "channel": self.channel,
            "message": self.message,
            "user_id": self.user_id,
            "message_id": self.message_id,
            "reply_to": self.reply_to,
        }

    def to_json(self) -> str:
        """JSON形式変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class SystemLog(BaseModel):
    """
    システムログ構造

    処理状況・パフォーマンス・統計情報記録
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    level: LogLevel
    module: str
    action: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式変換"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "module": self.module,
            "action": self.action,
            "data": self.data,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        """JSON形式変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "SystemLog":
        """JSON復元"""
        data = json.loads(json_str)
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["level"] = LogLevel(data["level"])
        return cls(**data)


class ErrorLog(BaseModel):
    """
    エラーログ構造

    例外・エラー詳細情報・スタックトレース記録
    """

    timestamp: datetime = Field(default_factory=datetime.now)
    error_type: str
    message: str
    module: str
    function: Optional[str] = None
    stacktrace: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式変換"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "error_type": self.error_type,
            "message": self.message,
            "module": self.module,
            "function": self.function,
            "stacktrace": self.stacktrace,
            "context": self.context,
        }

    def to_json(self) -> str:
        """JSON形式変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_exception(
        cls, exc: Exception, context: Optional[Dict[str, Any]] = None
    ) -> "ErrorLog":
        """例外からErrorLog生成"""
        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            module=exc.__class__.__module__,
            stacktrace=traceback.format_exc(),
            context=context or {},
        )


class StructuredLogger:
    """
    構造化ログ出力システム

    JSON形式ファイル出力・ローテーション・スレッドセーフ実装
    Fail-Fast原則準拠、フォールバック禁止
    """

    def __init__(self, settings=None):
        """StructuredLogger初期化"""
        if settings:
            self.settings = settings
        else:
            from app.core.settings import get_settings

            self.settings = get_settings().log
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="structured_logger"
        )

        # ログディレクトリ作成
        self._ensure_log_directories()

    def _ensure_log_directories(self):
        """ログディレクトリ自動作成"""
        paths = [
            self.settings.discord_log_path,
            self.settings.system_log_path,
            self.settings.error_log_path,
        ]

        for path in paths:
            log_path = Path(path)
            log_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_to_file(self, log_data: str, file_path: str):
        """
        ファイル書き込み処理（スレッドセーフ）

        Args:
            log_data: JSON形式ログデータ
            file_path: 出力ファイルパス

        Raises:
            OSError: ファイル書き込み失敗時（Fail-Fast）
        """
        try:
            # ファイルパスのディレクトリ作成
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            with self._lock:
                # 簡単なローテーション実装（最小実装）
                file_path_obj = Path(file_path)
                if file_path_obj.exists():
                    file_size = file_path_obj.stat().st_size
                    max_size = self.settings.max_file_size_mb * 1024 * 1024

                    if file_size > max_size:
                        # 単純ローテーション（最小実装）
                        backup_path = file_path + ".1"
                        if Path(backup_path).exists():
                            Path(backup_path).unlink()
                        file_path_obj.rename(backup_path)

                # ログデータ書き込み
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(log_data + "\n")
                    f.flush()

        except Exception as e:
            # Fail-Fast: 書き込み失敗時は即停止
            raise OSError(f"StructuredLogger write failed: {file_path}") from e

    def log_discord_message(self, log: DiscordMessageLog):
        """Discordメッセージログ出力"""
        self._executor.submit(
            self._write_to_file, log.to_json(), self.settings.discord_log_path
        )

    def log_system(self, log: SystemLog):
        """システムログ出力"""
        self._executor.submit(
            self._write_to_file, log.to_json(), self.settings.system_log_path
        )

    def log_error(self, log: ErrorLog):
        """エラーログ出力"""
        self._executor.submit(
            self._write_to_file, log.to_json(), self.settings.error_log_path
        )

    def shutdown(self, wait: bool = True):
        """リソース解放"""
        self._executor.shutdown(wait=wait)


# シングルトンインスタンス
_logger_instance: Optional[StructuredLogger] = None


def get_logger() -> StructuredLogger:
    """StructuredLoggerインスタンス取得（シングルトン）"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = StructuredLogger()
    return _logger_instance

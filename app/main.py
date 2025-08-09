"""
Main entry point for Discord Multi-Agent System

Phase 6: Discord Bot基盤実装完了
アプリケーションエントリポイント、Discord Manager起動統合

実装機能:
- Discord Bot基盤（SimplifiedDiscordManager、SimplifiedTickManager）
- 設定管理システム統合
- タスク管理システム統合  
- 非同期ランタイム実装
- Fail-Fast原則実装
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from app.core.settings import get_settings
from app.discord_manager.manager import initialize_discord_system, close_discord_system
from app.tasks.manager import initialize_task_system, close_task_system


# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DiscordMultiAgentApplication:
    """
    Discord Multi-Agent System アプリケーション
    
    Phase 6: Discord Bot基盤統合アプリケーション
    - システム初期化・終了管理
    - シグナルハンドリング
    - Fail-Fast原則実装
    """
    
    def __init__(self):
        """アプリケーション初期化"""
        self.settings = None
        self.discord_manager = None
        self.tick_manager = None
        self.task_manager = None
        self.redis_queue = None
        self.running = False
        
    async def initialize(self):
        """システム初期化"""
        try:
            # 設定管理システム初期化
            logger.info("Initializing settings system...")
            self.settings = get_settings()
            
            # 必須環境変数チェック
            self.settings.validate_required_vars()
            
            # タスク管理システム初期化
            logger.info("Initializing task management system...")
            self.task_manager, self.redis_queue = await initialize_task_system()
            
            # Discord システム初期化
            logger.info("Initializing Discord system...")
            self.discord_manager, self.tick_manager = await initialize_discord_system()
            
            logger.info("Discord Multi-Agent System initialized successfully")
            
        except Exception as e:
            logger.critical(f"System initialization failed: {e}")
            sys.exit(1)  # Fail-Fast
    
    async def run(self):
        """アプリケーション実行"""
        try:
            self.running = True
            logger.info("Starting Discord Multi-Agent System...")
            
            # Tickマネージャー開始（バックグラウンド）
            tick_task = asyncio.create_task(self.tick_manager.start())
            
            # Discord Manager開始（メインループ）
            await self.discord_manager.start()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.critical(f"Critical error in main loop: {e}")
            sys.exit(1)  # Fail-Fast
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """システム終了"""
        try:
            self.running = False
            logger.info("Shutting down Discord Multi-Agent System...")
            
            # Discord システム終了
            if self.discord_manager or self.tick_manager:
                await close_discord_system()
            
            # タスク管理システム終了
            if self.task_manager or self.redis_queue:
                await close_task_system()
            
            logger.info("Discord Multi-Agent System shut down successfully")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def setup_signal_handlers(self):
        """シグナルハンドラー設定"""
        def signal_handler():
            logger.info("Received shutdown signal")
            if self.running:
                # 現在のイベントループに終了タスクを追加
                loop = asyncio.get_event_loop()
                loop.create_task(self.shutdown())
        
        # SIGINT (Ctrl+C) と SIGTERM のハンドラー設定
        if sys.platform != 'win32':
            signal.signal(signal.SIGINT, lambda s, f: signal_handler())
            signal.signal(signal.SIGTERM, lambda s, f: signal_handler())


async def async_main():
    """非同期メインエントリポイント"""
    # アプリケーションバナー表示
    print_banner()
    
    # アプリケーション初期化・実行
    app = DiscordMultiAgentApplication()
    app.setup_signal_handlers()
    
    try:
        await app.initialize()
        await app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}")
        sys.exit(1)


def print_banner():
    """アプリケーションバナー表示"""
    print("\n" + "=" * 60)
    print("🤖 Discord Multi-Agent System")
    print("Phase 6: Discord Bot基盤実装完了")
    print("=" * 60)
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"Working Directory: {Path.cwd()}")
    print(f"Platform: {sys.platform}")
    print("=" * 60)
    print("Starting system initialization...\n")


def main():
    """メインエントリポイント（同期版）"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
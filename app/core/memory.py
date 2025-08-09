"""
Memory module for Discord Multi-Agent System

Phase 7: OptimalMemorySystem実装完了
LangChain Memory統合・Redis短期記憶・PostgreSQL+pgvector長期記憶

実装機能:
- 単一セッション"discord_unified"による統合記憶管理
- Redis短期記憶（24時間TTL）
- PostgreSQL+pgvector長期記憶（セマンティック検索）
- 日報時短期→長期移行処理
- Google Gemini埋め込みサービス統合
- 統計データ生成・既存システム統合

t-wada式TDD実装 - Green Phase
Fail-Fast原則・設定統合・最小実装原則準拠
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain_redis import RedisChatMessageHistory
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVectorStore, PGEngine
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class OptimalMemorySystem:
    """
    LangChain Memory統合システム
    
    Architecture:
    - 単一セッション: "discord_unified"
    - 短期記憶: Redis（24時間TTL）
    - 長期記憶: PostgreSQL+pgvector（セマンティック検索）
    - 埋め込み: Google Gemini Embedding（1536次元）
    - 全エージェント・全チャンネル統合管理
    
    Phase 7: 完全実装版
    - Redis: RedisChatMessageHistory
    - PostgreSQL: PGVectorStore 
    - Embeddings: GoogleGenerativeAIEmbeddings
    - Fail-Fast原則・設定統合・最小実装
    """
    
    def __init__(self):
        """OptimalMemorySystem 初期化
        
        設定統合によるRedis・Gemini接続設定
        Fail-Fast原則による早期エラー検出
        
        Raises:
            ValueError: 必須設定不足時
            Exception: Redis/Gemini接続エラー時
        """
        logger.info("OptimalMemorySystem initializing...")
        
        # 設定取得
        settings = get_settings()
        
        # 必須設定確認（Fail-Fast）
        if not settings.database.redis_url:
            raise ValueError("Redis URL is required for OptimalMemorySystem")
        if not settings.gemini.api_key:
            raise ValueError("Gemini API key is required for OptimalMemorySystem")
        
        try:
            # 短期記憶（Redis）初期化
            self.short_term = RedisChatMessageHistory(
                session_id="discord_unified",
                redis_url=settings.database.redis_url,
                ttl=86400  # 24時間自動削除
            )
            
            # 埋め込みサービス初期化
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=settings.gemini.api_key,
                client_options={"output_dimensionality": 1536}
            )
            
            # 長期記憶は別途初期化（initialize_long_term()で実行）
            self.long_term: Optional[PGVectorStore] = None
            
            logger.info("OptimalMemorySystem initialized successfully")
            
        except Exception as e:
            logger.error(f"OptimalMemorySystem initialization failed: {e}")
            raise
    
    async def initialize_long_term(self):
        """長期記憶（PostgreSQL+pgvector）初期化
        
        PGVectorStore作成・テーブル設定
        
        Raises:
            Exception: データベース接続・テーブル作成エラー時
        """
        logger.info("Initializing long-term memory (PostgreSQL+pgvector)...")
        
        try:
            settings = get_settings()
            
            # PostgreSQL接続エンジン作成
            engine = PGEngine.from_connection_string(settings.database.url)
            
            # PGVectorStore作成
            self.long_term = await PGVectorStore.create(
                engine=engine,
                table_name="agent_memory",
                embedding_service=self.embeddings,
                vector_dimension=1536  # pgvector互換
            )
            
            logger.info("Long-term memory initialized successfully")
            
        except Exception as e:
            logger.error(f"Long-term memory initialization failed: {e}")
            raise
    
    async def add_message(self, content: str, agent: str, channel: str) -> None:
        """メッセージ追加
        
        Redis短期記憶にメタデータ付きメッセージ追加
        
        Args:
            content: メッセージ内容
            agent: 送信者エージェント名（spectra/lynq/paz）
            channel: チャンネル名（command-center/creation/etc.）
            
        Raises:
            Exception: Redis書き込みエラー時
        """
        try:
            # HumanMessage作成（メタデータ付き）
            message = HumanMessage(
                content=content,
                additional_kwargs={
                    "agent": agent,
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # Redis短期記憶に追加
            await self.short_term.aadd_message(message)
            
            logger.debug(f"Message added from {agent} in {channel}: {content[:50]}...")
            
        except Exception as e:
            logger.error(f"Failed to add message from {agent}: {e}")
            raise
    
    async def get_recent_context(self, limit: int = 10) -> List[dict]:
        """直近コンテキスト取得
        
        Redis短期記憶から最新メッセージを取得
        
        Args:
            limit: 取得件数制限
            
        Returns:
            List[dict]: 最近のメッセージリスト
                - content: メッセージ内容
                - agent: 送信者エージェント
                - channel: チャンネル名
                - timestamp: 送信時刻
        """
        try:
            # 最新limit件のメッセージ取得
            messages = self.short_term.messages[-limit:]
            
            # 辞書形式に変換
            context = [
                {
                    "content": msg.content,
                    "agent": msg.additional_kwargs.get("agent"),
                    "channel": msg.additional_kwargs.get("channel"),
                    "timestamp": msg.additional_kwargs.get("timestamp")
                }
                for msg in messages
            ]
            
            logger.debug(f"Retrieved {len(context)} recent messages")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get recent context: {e}")
            return []
    
    async def semantic_search(self, query: str, limit: int = 5) -> List[dict]:
        """セマンティック検索
        
        PostgreSQL+pgvectorでベクトル類似性検索実行
        
        Args:
            query: 検索クエリ
            limit: 取得件数制限
            
        Returns:
            List[dict]: 検索結果リスト
                - content: ドキュメント内容
                - metadata: メタデータ（agent, channel, timestamp）
                - similarity: 類似度スコア
                
        Raises:
            AttributeError: 長期記憶未初期化時
            Exception: 検索処理エラー時
        """
        if not self.long_term:
            raise AttributeError("Long-term memory not initialized. Call initialize_long_term() first.")
        
        try:
            # ベクトル類似性検索実行
            results = await self.long_term.asimilarity_search(query, k=limit)
            
            # 結果変換
            search_results = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity": doc.metadata.get("score", 1.0)
                }
                for doc in results
            ]
            
            logger.debug(f"Semantic search returned {len(search_results)} results for: {query[:30]}...")
            return search_results
            
        except Exception as e:
            logger.error(f"Semantic search failed for query '{query}': {e}")
            raise
    
    async def daily_report_migration(self) -> int:
        """日報処理時のデータ移行
        
        短期記憶→長期記憶移行・短期記憶クリア
        
        Returns:
            int: 移行したメッセージ数
            
        Raises:
            AttributeError: 長期記憶未初期化時
            Exception: 移行処理エラー時
        """
        if not self.long_term:
            raise AttributeError("Long-term memory not initialized. Call initialize_long_term() first.")
        
        try:
            # 短期メモリから全メッセージ取得
            messages = self.short_term.messages
            
            if not messages:
                # 空のメッセージでもクリア実行
                self.short_term.clear()
                logger.info("No messages to migrate")
                return 0
            
            # Document形式に変換
            documents = [
                Document(
                    page_content=msg.content,
                    metadata={
                        "agent": msg.additional_kwargs.get("agent"),
                        "channel": msg.additional_kwargs.get("channel"),
                        "timestamp": msg.additional_kwargs.get("timestamp")
                    }
                )
                for msg in messages
            ]
            
            # PostgreSQL+pgvectorに一括保存
            await self.long_term.aadd_documents(documents)
            
            # 短期メモリクリア
            self.short_term.clear()
            
            message_count = len(documents)
            logger.info(f"Successfully migrated {message_count} messages from short-term to long-term memory")
            
            return message_count
            
        except Exception as e:
            logger.error(f"Daily migration failed: {e}")
            raise
    
    async def get_statistics(self) -> dict:
        """24時間メモリ統計
        
        短期記憶の統計データ生成
        
        Returns:
            dict: 統計データ
                - total: 総メッセージ数
                - by_channel: チャンネル別統計
                - by_agent: エージェント別統計
        """
        try:
            messages = self.short_term.messages
            
            if not messages:
                return {"total": 0, "by_channel": {}, "by_agent": {}}
            
            stats = {
                "total": len(messages),
                "by_channel": {},
                "by_agent": {}
            }
            
            # チャンネル・エージェント別集計
            for msg in messages:
                channel = msg.additional_kwargs.get("channel", "unknown")
                agent = msg.additional_kwargs.get("agent", "unknown")
                
                stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1
                stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
            
            logger.debug(f"Generated statistics for {stats['total']} messages")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to generate statistics: {e}")
            return {"total": 0, "by_channel": {}, "by_agent": {}}
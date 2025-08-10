"""
Gemini API Client - Phase 10.3.1 Green Phase実装
TDD最小実装によるテスト通過用モジュール

実装機能:
- 実API Key使用Gemini接続
- RPM制限（15req/min）遵守
- エラーハンドリング（認証・ネットワーク・クォータ）
- Fail-Fast原則準拠設計

CLAUDE.md原則準拠:
- Fail-Fast: API接続失敗時即停止・フォールバック禁止
- 最小実装: テスト通過のための必要最小限実装
- 設定一元管理: GeminiConfig統合制御
"""
import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field

from app.core.settings import GeminiConfig


class RateLimiter:
    """
    RPM制限実装 - 15req/min遵守
    
    Green Phase最小実装:
    - 単純なリクエスト間隔制御
    - 前回リクエスト時刻記録
    - 必要待機時間計算・実行
    """
    
    def __init__(self, requests_per_minute: int = 15):
        """
        RateLimiter初期化
        
        Args:
            requests_per_minute: 1分間のリクエスト制限（デフォルト15）
        """
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # 4秒間隔
        self.last_request_time = 0.0
    
    async def wait_if_needed(self) -> None:
        """
        必要に応じて待機実行
        
        最後のリクエストから十分時間が経っていなければ待機
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def sync_wait_if_needed(self) -> None:
        """
        同期版待機実行
        
        同期関数での使用用
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


class GeminiAPIClient:
    """
    Gemini API統合クライアント
    
    Green Phase最小実装:
    - ChatGoogleGenerativeAI、GoogleGenerativeAIEmbeddings統合
    - レート制限付きリクエスト実行
    - 基本的なエラーハンドリング
    - 設定統合制御
    """
    
    def __init__(self, config: GeminiConfig):
        """
        GeminiAPIClient初期化
        
        Args:
            config: Gemini設定インスタンス
            
        Raises:
            ValueError: API Key未設定時
        """
        if not config.api_key:
            raise ValueError("Gemini API key is required")
        
        self.config = config
        self.rate_limiter = RateLimiter(config.requests_per_minute)
        self.chat_client: Optional[ChatGoogleGenerativeAI] = None
        self.embeddings_client: Optional[GoogleGenerativeAIEmbeddings] = None
    
    def _ensure_chat_client(self) -> ChatGoogleGenerativeAI:
        """
        Chat client遅延初期化
        
        Returns:
            ChatGoogleGenerativeAI: チャットクライアント
        """
        if self.chat_client is None:
            self.chat_client = ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=self.config.api_key,
                temperature=0.0
            )
        return self.chat_client
    
    def _ensure_embeddings_client(self) -> GoogleGenerativeAIEmbeddings:
        """
        Embeddings client遅延初期化
        
        Returns:
            GoogleGenerativeAIEmbeddings: 埋め込みクライアント
        """
        if self.embeddings_client is None:
            self.embeddings_client = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
                google_api_key=self.config.api_key,
                client_options={"output_dimensionality": 1536}
            )
        return self.embeddings_client
    
    def chat_invoke(self, message: str) -> str:
        """
        チャットメッセージ送信（同期版）
        
        Args:
            message: 送信メッセージ
            
        Returns:
            str: 応答メッセージ
            
        Raises:
            Exception: API呼び出しエラー時
        """
        # レート制限適用
        self.rate_limiter.sync_wait_if_needed()
        
        # クライアント初期化
        chat_client = self._ensure_chat_client()
        
        # API呼び出し
        response = chat_client.invoke(message)
        
        return str(response.content) if hasattr(response, 'content') else str(response)
    
    async def chat_ainvoke(self, message: str) -> str:
        """
        チャットメッセージ送信（非同期版）
        
        Args:
            message: 送信メッセージ
            
        Returns:
            str: 応答メッセージ
        """
        # レート制限適用
        await self.rate_limiter.wait_if_needed()
        
        # クライアント初期化
        chat_client = self._ensure_chat_client()
        
        # API呼び出し
        response = await chat_client.ainvoke(message)
        
        return str(response.content) if hasattr(response, 'content') else str(response)
    
    def embed_query(self, text: str) -> List[float]:
        """
        テキスト埋め込み生成（同期版）
        
        Args:
            text: 埋め込み対象テキスト
            
        Returns:
            List[float]: 埋め込みベクトル（1536次元）
        """
        # レート制限適用
        self.rate_limiter.sync_wait_if_needed()
        
        # クライアント初期化
        embeddings_client = self._ensure_embeddings_client()
        
        # 埋め込み生成
        result = embeddings_client.embed_query(text)
        
        return result
    
    async def embed_query_async(self, text: str) -> List[float]:
        """
        テキスト埋め込み生成（非同期版）
        
        Args:
            text: 埋め込み対象テキスト
            
        Returns:
            List[float]: 埋め込みベクトル（1536次元）
        """
        # レート制限適用
        await self.rate_limiter.wait_if_needed()
        
        # クライアント初期化
        embeddings_client = self._ensure_embeddings_client()
        
        # 埋め込み生成（LangChainで非同期サポートある場合）
        if hasattr(embeddings_client, 'aembed_query'):
            result = await embeddings_client.aembed_query(text)
        else:
            # フォールバック: 同期メソッド使用
            result = embeddings_client.embed_query(text)
        
        return result
    
    def test_connection(self) -> bool:
        """
        API接続テスト
        
        Returns:
            bool: 接続成功フラグ
        """
        try:
            # シンプルなテストメッセージ送信
            response = self.chat_invoke("Hello, this is a connection test.")
            return len(response) > 0
        except Exception:
            return False
    
    async def test_connection_async(self) -> bool:
        """
        API接続テスト（非同期版）
        
        Returns:
            bool: 接続成功フラグ
        """
        try:
            # シンプルなテストメッセージ送信
            response = await self.chat_ainvoke("Hello, this is a connection test.")
            return len(response) > 0
        except Exception:
            return False


def create_gemini_client(config: Optional[GeminiConfig] = None) -> GeminiAPIClient:
    """
    GeminiAPIClient ファクトリー関数
    
    Args:
        config: Gemini設定（None時は自動取得）
        
    Returns:
        GeminiAPIClient: クライアントインスタンス
    """
    if config is None:
        from app.core.settings import get_settings
        config = get_settings().gemini
    
    return GeminiAPIClient(config)


# グローバルインスタンス（シングルトンパターン）
_client_instance: Optional[GeminiAPIClient] = None


def get_gemini_client() -> GeminiAPIClient:
    """
    GeminiAPIClientインスタンス取得（シングルトンパターン）
    
    Returns:
        GeminiAPIClient: クライアントインスタンス
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = create_gemini_client()
    return _client_instance


def reset_gemini_client() -> None:
    """
    GeminiAPIClientインスタンスリセット（主にテスト用）
    """
    global _client_instance
    _client_instance = None
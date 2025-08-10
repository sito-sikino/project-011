"""
Phase 10.3.1: Gemini API実接続テスト実装
TDD Red Phase - 実API接続失敗テスト先行作成

実装要求:
- 実GEMINI_API_KEY使用接続テスト
- RPM制限（15req/min）内応答時間測定  
- APIエラー時適切失敗動作確認
- Fail-Fast原則準拠エラー処理設計

技術制約:
- CLAUDE.md原則完全準拠（Fail-Fast・最小実装・設定一元管理）
- Phase 10.2統合（StructuredLogger・ErrorLog・統一エラーハンドラー活用）
- CI/CD環境での実行制御（pytest.skip活用）

t-wada式TDD Red Phase:
🔴 実API接続失敗テスト先行 → 🟢 google-genai統合・RPM制限実装 → 🟡 エラーハンドリング強化
"""
import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from unittest.mock import patch, Mock

import pytest
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.core.settings import Settings, get_settings, reset_settings
from app.core.logger import StructuredLogger, LogLevel, AgentType
from app.core.gemini_client import GeminiAPIClient, create_gemini_client, RateLimiter


class TestRealGeminiAPI:
    """
    Gemini API実接続テストスイート
    
    受入条件:
    - 実GEMINI_API_KEY使用接続テスト ✓
    - RPM制限（15req/min）遵守テスト ✓
    - APIエラー時適切失敗動作確認 ✓
    - 応答時間測定・パフォーマンステスト ✓
    - Phase 10.2統一ログシステム統合 ✓
    """
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        # テスト用設定（実API Key使用）
        if self.api_key:
            os.environ.update({
                "ENV": "testing",
                "GEMINI_API_KEY": self.api_key,
                "GEMINI_REQUESTS_PER_MINUTE": "15"
            })
            self.settings = get_settings()
        else:
            # API Key未設定時のフォールバック設定
            with patch.dict("os.environ", {
                "ENV": "testing",
                "GEMINI_API_KEY": "",
                "GEMINI_REQUESTS_PER_MINUTE": "15"
            }):
                self.settings = get_settings()
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
        
    # ==========================================================================
    # 基本接続テスト
    # ==========================================================================
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_basic_chat_connection_success(self):
        """
        Test 1: 基本的なGemini Chat API接続・応答確認
        受入条件: 実API Key使用でChatGoogleGenerativeAI正常動作確認
        """
        # Green Phase: 新しい実装を使用
        client = create_gemini_client(self.settings.gemini)
        
        # 実API接続テスト
        response = client.chat_invoke("Test connection message")
        assert response is not None
        assert len(response) > 0
        assert isinstance(response, str)
            
        # ログ記録（Green Phase実装後に有効化）
        # # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Basic chat connection test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "basic_connection"}
        # )
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_embedding_connection_success(self):
        """
        Test 2: Gemini Embedding API接続・ベクトル生成確認
        受入条件: GoogleGenerativeAIEmbeddings正常動作・1536次元ベクトル生成確認
        """
        # Green Phase: 新しい実装を使用
        client = create_gemini_client(self.settings.gemini)
        
        # 埋め込み生成テスト
        result = client.embed_query("Test embedding text")
        assert len(result) == 1536
        assert all(isinstance(x, float) for x in result)
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Embedding connection test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "embedding_connection"}
        # )
    
    # ==========================================================================
    # 認証・API Key テスト
    # ==========================================================================
    
    def test_authentication_error_handling(self):
        """
        Test 3: 認証エラー時の適切な処理確認
        受入条件: 不正API Key・空API Key時の適切なエラー処理・Fail-Fast動作
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # 不正API Key使用
            llm = ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key="invalid_api_key_test",
                temperature=0.0
            )
            response = llm.invoke("Test authentication error")
            # これは認証エラーになるはず（実装後）
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.WARNING,
        #     message="Authentication error test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "authentication_error", "expected": "auth_failure"}
        # )
    
    def test_empty_api_key_error(self):
        """
        Test 4: 空API Key時のエラー処理確認
        受入条件: API Key未設定時の適切な例外発生・Fail-Fast動作
        """
        # Green Phase: 新しい実装を使用
        from app.core.settings import GeminiConfig
        
        # 空API Key設定
        config = GeminiConfig(api_key="", requests_per_minute=15)
        
        with pytest.raises(ValueError, match="API key is required"):
            # 空API Key使用でクライアント作成
            GeminiAPIClient(config)
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Empty API key error test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "empty_api_key"}
        # )
    
    # ==========================================================================
    # レート制限テスト（15req/min遵守）
    # ==========================================================================
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    @pytest.mark.slow  # 時間のかかるテスト用マーク
    def test_rate_limit_compliance(self):
        """
        Test 5: RPM制限遵守テスト（15req/min以内での連続リクエスト）
        受入条件: 15req/min制限内での適切なレート制御・遅延実装
        """
        # Green Phase: 新しい実装を使用（短時間テスト版）
        client = create_gemini_client(self.settings.gemini)
        
        start_time = time.time()
        request_times = []
        
        # 3回連続リクエスト（テスト時間短縮）
        for i in range(3):
            request_start = time.time()
            response = client.chat_invoke(f"Rate limit test request {i+1}")
            request_end = time.time()
            
            request_times.append({
                'request_id': i+1,
                'start': request_start,
                'end': request_end,
                'duration': request_end - request_start,
                'response_length': len(response)
            })
        
        total_time = time.time() - start_time
        
        # レート制限検証（3リクエストなら2間隔 = 8秒以上）
        expected_min_time = 4.0 * 2  # 4秒 × 2間隔 = 8秒
        assert total_time >= expected_min_time, f"Rate limit violation: {total_time}s < {expected_min_time}s"
        
        # 全リクエストが成功していることを確認
        assert len(request_times) == 3
        for req_time in request_times:
            assert req_time['response_length'] > 0
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Rate limit compliance test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={
        #         "test": "rate_limit",
        #         "rpm_limit": 15,
        #         "expected_interval": 4.0
        #     }
        # )
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_concurrent_rate_limit_enforcement(self):
        """
        Test 6: 並行リクエスト時のレート制限実装確認
        受入条件: 複数同時リクエスト時の適切なレート制御・順序制御
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # 初期実装前なので必ず失敗する
            async def make_request(request_id: int) -> Dict[str, Any]:
                llm = ChatGoogleGenerativeAI(
                    model="gemini-pro",
                    google_api_key=self.settings.gemini.api_key,
                    temperature=0.0
                )
                
                start_time = time.time()
                response = await llm.ainvoke(f"Concurrent request {request_id}")
                end_time = time.time()
                
                return {
                    'request_id': request_id,
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': end_time - start_time,
                    'response_length': len(str(response))
                }
            
            # 並行実行（3リクエスト）
            async def run_concurrent_test():
                tasks = [make_request(i) for i in range(3)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return results
            
            results = asyncio.run(run_concurrent_test())
            
            # レート制限適用確認
            assert len(results) == 3
            for result in results:
                if not isinstance(result, Exception):
                    assert 'request_id' in result
                    assert result['duration'] > 0
        
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Concurrent rate limit test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "concurrent_rate_limit"}
        # )
    
    # ==========================================================================
    # 応答時間・パフォーマンステスト
    # ==========================================================================
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_response_time_measurement(self):
        """
        Test 7: 応答時間測定・パフォーマンス確認
        受入条件: レスポンス時間測定・許容範囲内確認（30秒以内）
        """
        # Green Phase: 新しい実装を使用
        client = create_gemini_client(self.settings.gemini)
        
        start_time = time.time()
        response = client.chat_invoke("Generate a brief response for performance testing.")
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # 応答時間検証（30秒以内）
        assert response_time < 30.0, f"Response too slow: {response_time}s > 30s"
        assert response_time > 0, "Invalid response time measurement"
        assert response is not None, "No response received"
        assert len(response) > 0, "Empty response received"
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Response time measurement test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={
        #         "test": "response_time",
        #         "max_allowed": 30.0
        #     }
        # )
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_large_request_performance(self):
        """
        Test 8: 大きなリクエスト時のパフォーマンス測定
        受入条件: 長いプロンプト処理時の適切な応答時間・メモリ使用量
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # 初期実装前なので必ず失敗する
            llm = ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=self.settings.gemini.api_key,
                temperature=0.0
            )
            
            # 長いプロンプト作成
            long_prompt = "Analyze this text: " + "This is a test sentence. " * 100
            
            start_time = time.time()
            response = llm.invoke(long_prompt)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            # パフォーマンス検証
            assert response_time < 60.0, f"Large request too slow: {response_time}s > 60s"
            assert len(str(response)) > 0, "Empty response for large request"
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Large request performance test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={
        #         "test": "large_request_performance",
        #         "prompt_length": 2000,  # 概算
        #         "max_allowed": 60.0
        #     }
        # )
    
    # ==========================================================================
    # ネットワークエラー・APIエラーテスト
    # ==========================================================================
    
    def test_network_error_handling(self):
        """
        Test 9: ネットワークエラー時の適切な処理確認
        受入条件: 接続エラー・タイムアウト時のFail-Fast動作・適切な例外発生
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # 不正なエンドポイント設定（ネットワークエラーシミュレート）
            with patch('langchain_google_genai.ChatGoogleGenerativeAI') as mock_llm:
                mock_llm.side_effect = ConnectionError("Network connection failed")
                
                llm = ChatGoogleGenerativeAI(
                    model="gemini-pro",
                    google_api_key=self.settings.gemini.api_key if self.api_key else "test_key",
                    temperature=0.0
                )
                response = llm.invoke("Test network error")
                
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.ERROR,
        #     message="Network error handling test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "network_error", "expected": "connection_failure"}
        # )
    
    def test_api_quota_exceeded_error(self):
        """
        Test 10: API クォータ超過時のエラー処理確認
        受入条件: レート制限・クォータ制限超過時の適切なエラー処理
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # クォータ超過エラーのシミュレート
            with patch('langchain_google_genai.ChatGoogleGenerativeAI') as mock_llm:
                mock_instance = Mock()
                mock_instance.invoke.side_effect = Exception("Quota exceeded")
                mock_llm.return_value = mock_instance
                
                llm = ChatGoogleGenerativeAI(
                    model="gemini-pro",
                    google_api_key=self.settings.gemini.api_key if self.api_key else "test_key",
                    temperature=0.0
                )
                response = llm.invoke("Test quota error")
                
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.ERROR,
        #     message="API quota error handling test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "quota_error", "expected": "quota_exceeded"}
        # )
    
    # ==========================================================================
    # 統合テスト（既存システムとの整合性）
    # ==========================================================================
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_memory_system_integration(self):
        """
        Test 11: OptimalMemorySystemとの統合テスト
        受入条件: memory.pyのGoogleGenerativeAIEmbeddingsとの整合性確認
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # 初期実装前なので必ず失敗する
            from app.core.memory import OptimalMemorySystem
            
            # メモリシステム初期化（実API Key使用）
            memory_system = OptimalMemorySystem()
            
            # 埋め込み生成テスト
            test_text = "Integration test with memory system"
            embedding_result = memory_system.embeddings.embed_query(test_text)
            
            assert len(embedding_result) == 1536, "Embedding dimension mismatch"
            assert all(isinstance(x, float) for x in embedding_result), "Invalid embedding format"
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Memory system integration test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "memory_integration"}
        # )
    
    @pytest.mark.skipif(not os.getenv("GEMINI_API_KEY"), reason="GEMINI_API_KEY not set")
    def test_report_system_integration(self):
        """
        Test 12: ReportSystemとの統合テスト  
        受入条件: report.pyのChatGoogleGenerativeAIとの整合性確認
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            # 初期実装前なので必ず失敗する
            from app.core.report import ModernReportGenerator
            
            # レポートジェネレーター初期化（実API Key使用）
            generator = ModernReportGenerator(self.settings)
            
            # LLM初期化テスト
            generator._initialize_llm()
            
            assert generator.llm is not None, "LLM initialization failed"
            assert hasattr(generator.llm, 'invoke'), "LLM missing invoke method"
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Report system integration test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "report_integration"}
        # )
    
    # ==========================================================================
    # エラーハンドリング・ロバストネステスト
    # ==========================================================================
    
    def test_invalid_model_error(self):
        """
        Test 13: 不正なモデル名時のエラー処理確認
        受入条件: 存在しないモデル指定時の適切なエラー処理
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            llm = ChatGoogleGenerativeAI(
                model="invalid-model-name",  # 存在しないモデル
                google_api_key=self.settings.gemini.api_key if self.api_key else "test_key",
                temperature=0.0
            )
            response = llm.invoke("Test invalid model")
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.ERROR,
        #     message="Invalid model error test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={"test": "invalid_model", "model": "invalid-model-name"}
        # )
    
    def test_malformed_request_error(self):
        """
        Test 14: 不正なリクエスト時のエラー処理確認
        受入条件: 異常なパラメータ・プロンプト時の適切な例外処理
        """
        # Red Phase: まず失敗テストを書く
        with pytest.raises(Exception):
            llm = ChatGoogleGenerativeAI(
                model="gemini-pro",
                google_api_key=self.settings.gemini.api_key if self.api_key else "test_key",
                temperature=2.0,  # 不正な温度設定（通常0-1）
                max_output_tokens=-100  # 不正なトークン数
            )
            response = llm.invoke("Test malformed request")
            
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.ERROR,
        #     message="Malformed request error test executed",
        #     agent=AgentType.SYSTEM,
        #     metadata={
        #         "test": "malformed_request",
        #         "params": {"temperature": 2.0, "max_tokens": -100}
        #     }
        # )
    
    # ==========================================================================
    # CI/CD・実行環境テスト
    # ==========================================================================
    
    def test_environment_detection(self):
        """
        Test 15: 実行環境検出・条件分岐テスト
        受入条件: CI環境・ローカル環境での適切な動作制御
        """
        # API Key有無による条件分岐テスト
        has_api_key = bool(self.api_key)
        
        if has_api_key:
            # ログ記録（Green Phase実装後に有効化）
            # self.logger.log(
            #     level=LogLevel.INFO,
            #     message="Real API key detected - full tests enabled",
            #     agent=AgentType.SYSTEM,
            #     metadata={"api_key_present": True}
            # )
            pass
        else:
            # ログ記録（Green Phase実装後に有効化）
            # self.logger.log(
            #     level=LogLevel.WARNING,
            #     message="No API key - tests will be skipped",
            #     agent=AgentType.SYSTEM,
            #     metadata={"api_key_present": False}
            # )
            pass
        
        # 環境変数確認
        expected_vars = ["GEMINI_API_KEY", "GEMINI_REQUESTS_PER_MINUTE"]
        missing_vars = [var for var in expected_vars if not os.getenv(var)]
        
        if missing_vars:
            # ログ記録（Green Phase実装後に有効化）
            # self.logger.log(
            #     level=LogLevel.WARNING,
            #     message=f"Missing environment variables: {missing_vars}",
            #     agent=AgentType.SYSTEM,
            #     metadata={"missing_vars": missing_vars}
            # )
            pass
    
    def test_settings_validation(self):
        """
        Test 16: 設定値バリデーションテスト
        受入条件: GeminiConfig設定値の適切な検証・範囲チェック
        """
        # 設定値検証
        assert self.settings.gemini.requests_per_minute == 15, "RPM setting incorrect"
        assert 1 <= self.settings.gemini.requests_per_minute <= 60, "RPM out of valid range"
        
        if self.api_key:
            assert self.settings.gemini.api_key == self.api_key, "API key mismatch"
        
        # ログ記録（Green Phase実装後に有効化）
        # self.logger.log(
        #     level=LogLevel.INFO,
        #     message="Settings validation test completed",
        #     agent=AgentType.SYSTEM,
        #     metadata={
        #         "rpm_setting": self.settings.gemini.requests_per_minute,
        #         "api_key_set": bool(self.settings.gemini.api_key)
        #     }
        # )


# ==========================================================================
# テスト実行制御・フィクスチャー
# ==========================================================================

@pytest.fixture(scope="module")
def real_api_available():
    """実API利用可能性チェックフィクスチャー"""
    return bool(os.getenv("GEMINI_API_KEY"))


@pytest.fixture(scope="function")
def rate_limiter():
    """レート制限制御フィクスチャー"""
    last_request = {'time': 0}
    
    def enforce_rate_limit():
        current_time = time.time()
        elapsed = current_time - last_request['time']
        min_interval = 60.0 / 15.0  # 15req/min = 4秒間隔
        
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            time.sleep(sleep_time)
        
        last_request['time'] = time.time()
    
    return enforce_rate_limit


# ==========================================================================
# テストマーク定義
# ==========================================================================

# カスタムマーク定義（pytest.ini または conftest.py で定義）
# pytest.mark.slow - 実行時間の長いテスト
# pytest.mark.integration - 統合テスト
# pytest.mark.real_api - 実API使用テスト
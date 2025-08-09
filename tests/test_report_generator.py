"""
Tests for ModernReportGenerator and LangChain LCEL Integration

Phase 5.1: 日報システム - LangChain LCEL統合
t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的テストスイート作成（ModernReportGenerator、LCEL chain構築）
🟢 Green Phase: 最小実装でテスト通過
🟡 Refactor Phase: 品質向上、エラーハンドリング強化

Test Coverage:
- ModernReportGeneratorクラス初期化テスト
- LCEL chain構築テスト
- Gemini API統合テスト
- Template処理テスト
- 非同期処理テスト
- エラーハンドリングテスト
"""
import asyncio
import pytest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any, Optional
import json

from app.core.settings import Settings, get_settings, reset_settings
from app.core.report import (
    ModernReportGenerator,
    ReportError,
    TemplateError,
    LLMError,
    ReportData,
    StatisticsData,
    ChannelStatistics,
    AgentStatistics
)


class TestModernReportGenerator:
    """ModernReportGeneratorクラスの包括的テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        # テスト用設定
        with patch.dict("os.environ", {
            "ENV": "testing",
            "GEMINI_API_KEY": "test_key_123",
            "GEMINI_REQUESTS_PER_MINUTE": "10"
        }):
            self.settings = get_settings()
        self.generator = None
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    def test_modern_report_generator_initialization_success(self):
        """ModernReportGenerator正常初期化テスト"""
        generator = ModernReportGenerator(self.settings)
        
        assert generator.settings == self.settings
        assert generator.gemini_config == self.settings.gemini
        assert generator.report_config == self.settings.report
        assert generator.llm is None  # lazy initialization
        assert generator.chain is None
        assert generator.templates == {}
    
    def test_modern_report_generator_initialization_no_api_key(self):
        """API Key未設定時の初期化エラーテスト"""
        # API Key無しの設定
        with patch.dict("os.environ", {
            "ENV": "testing",
            "GEMINI_API_KEY": ""
        }):
            settings = Settings()
            
        with pytest.raises(ValueError, match="Gemini API key is required"):
            ModernReportGenerator(settings)
    
    @patch('app.core.report.ChatGoogleGenerativeAI')
    def test_llm_initialization_success(self, mock_gemini_class):
        """LLM初期化成功テスト"""
        mock_llm = Mock()
        mock_gemini_class.return_value = mock_llm
        
        generator = ModernReportGenerator(self.settings)
        
        # _initialize_llm呼び出し
        generator._initialize_llm()
        
        assert generator.llm == mock_llm
        mock_gemini_class.assert_called_once_with(
            model="gemini-pro",
            google_api_key="test_key_123",
            temperature=0.3,
            max_output_tokens=2048
        )
    
    @patch('app.core.report.ChatGoogleGenerativeAI')
    def test_llm_initialization_error(self, mock_gemini_class):
        """LLM初期化エラーテスト"""
        mock_gemini_class.side_effect = Exception("API connection failed")
        
        generator = ModernReportGenerator(self.settings)
        
        with pytest.raises(LLMError, match="Failed to initialize Gemini LLM"):
            generator._initialize_llm()
    
    @patch('app.core.report.StrOutputParser')
    @patch('app.core.report.ChatGoogleGenerativeAI')
    @patch('app.core.report.ChatPromptTemplate')
    def test_chain_initialization_success(self, mock_prompt_class, mock_gemini_class, mock_parser_class):
        """LCEL Chain初期化成功テスト"""
        mock_llm = Mock()
        mock_gemini_class.return_value = mock_llm
        mock_prompt = Mock()
        mock_prompt_class.from_template.return_value = mock_prompt
        mock_parser = Mock()
        mock_parser_class.return_value = mock_parser
        
        # Mock the | operator for LCEL chain creation
        mock_chain_step1 = Mock()
        mock_final_chain = Mock()
        mock_prompt.__or__ = Mock(return_value=mock_chain_step1)
        mock_chain_step1.__or__ = Mock(return_value=mock_final_chain)
        
        generator = ModernReportGenerator(self.settings)
        generator._initialize_llm()
        generator._initialize_chain()
        
        assert generator.chain == mock_final_chain
        mock_prompt_class.from_template.assert_called_once()
        mock_prompt.__or__.assert_called_once_with(mock_llm)
        mock_chain_step1.__or__.assert_called_once()
    
    def test_load_templates_success(self):
        """テンプレート読み込み成功テスト"""
        generator = ModernReportGenerator(self.settings)
        
        # デフォルトテンプレートの確認
        generator._load_templates()
        
        assert "daily_report" in generator.templates
        assert "statistics_summary" in generator.templates
        assert "channel_analysis" in generator.templates
        assert "agent_performance" in generator.templates
        
        # テンプレート内容の基本チェック
        daily_template = generator.templates["daily_report"]
        assert "daily_report_date" in daily_template
        assert "statistics" in daily_template
    
    def test_format_template_success(self):
        """テンプレート書式設定成功テスト"""
        generator = ModernReportGenerator(self.settings)
        generator._load_templates()
        
        data = {
            "daily_report_date": "2025-08-09",
            "statistics": {
                "total_messages": 150,
                "total_agents": 3,
                "active_channels": 4,
                "completion_rate": 0.85
            },
            "detailed_statistics": "Test stats"
        }
        
        result = generator._format_template("daily_report", data)
        
        assert "2025-08-09" in result
        assert "150" in result
    
    def test_format_template_missing_template(self):
        """存在しないテンプレートの書式設定エラーテスト"""
        generator = ModernReportGenerator(self.settings)
        generator._load_templates()
        
        with pytest.raises(TemplateError, match="Template 'nonexistent' not found"):
            generator._format_template("nonexistent", {})
    
    def test_format_template_missing_key(self):
        """テンプレート変数不足エラーテスト"""
        generator = ModernReportGenerator(self.settings)
        generator._load_templates()
        
        # 必要なキーが不足したデータ
        incomplete_data = {"statistics": {}}
        
        with pytest.raises(TemplateError, match="Template formatting failed"):
            generator._format_template("daily_report", incomplete_data)
    
    @patch('app.core.report.ChatGoogleGenerativeAI')
    async def test_generate_report_success(self, mock_gemini_class):
        """レポート生成成功テスト"""
        # Mock setup
        mock_llm = Mock()
        mock_gemini_class.return_value = mock_llm
        
        generator = ModernReportGenerator(self.settings)
        
        # Mock the chain directly
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = "Generated report content"
        generator.chain = mock_chain
        
        # Test data
        report_data = ReportData(
            date=datetime(2025, 8, 9, tzinfo=timezone.utc),
            statistics=StatisticsData(
                total_messages=150,
                total_agents=3,
                active_channels=4,
                completion_rate=0.85,
                channels={},
                agents={}
            ),
            summary="Test summary"
        )
        
        result = await generator.generate_report(report_data)
        
        assert result is not None
        assert "Generated report content" in result
        mock_chain.ainvoke.assert_called_once()
    
    @patch('app.core.report.ChatGoogleGenerativeAI')
    async def test_generate_report_llm_error(self, mock_gemini_class):
        """レポート生成時のLLMエラーテスト"""
        mock_gemini_class.side_effect = Exception("LLM connection failed")
        
        generator = ModernReportGenerator(self.settings)
        
        report_data = ReportData(
            date=datetime(2025, 8, 9, tzinfo=timezone.utc),
            statistics=StatisticsData(
                total_messages=150,
                total_agents=3,
                active_channels=4,
                completion_rate=0.85,
                channels={},
                agents={}
            ),
            summary="Test summary"
        )
        
        with pytest.raises(LLMError):
            await generator.generate_report(report_data)
    
    def test_validate_report_data_success(self):
        """ReportData検証成功テスト"""
        generator = ModernReportGenerator(self.settings)
        
        valid_data = ReportData(
            date=datetime(2025, 8, 9, tzinfo=timezone.utc),
            statistics=StatisticsData(
                total_messages=150,
                total_agents=3,
                active_channels=4,
                completion_rate=0.85,
                channels={},
                agents={}
            ),
            summary="Valid summary"
        )
        
        # Should not raise exception
        generator._validate_report_data(valid_data)
    
    def test_validate_report_data_invalid_date(self):
        """ReportData日付無効エラーテスト"""
        generator = ModernReportGenerator(self.settings)
        
        # Test with mock invalid data that bypasses Pydantic validation
        invalid_data = Mock()
        invalid_data.date = None
        invalid_data.statistics = Mock()
        
        with pytest.raises(ReportError, match="Invalid report data"):
            generator._validate_report_data(invalid_data)
    
    def test_rate_limiting_calculation(self):
        """レート制限計算テスト"""
        generator = ModernReportGenerator(self.settings)
        
        # 10 requests per minute = 6 seconds per request
        delay = generator._calculate_rate_limit_delay()
        assert delay == 6.0
    
    async def test_rate_limiting_enforcement(self):
        """レート制限実行テスト"""
        generator = ModernReportGenerator(self.settings)
        
        # Set last request time to current time to force delay
        generator.last_request_time = time.time()
        
        start_time = datetime.now()
        await generator._enforce_rate_limit()
        end_time = datetime.now()
        
        # Should take at least the calculated delay
        elapsed = (end_time - start_time).total_seconds()
        expected_delay = 60.0 / self.settings.gemini.requests_per_minute
        assert elapsed >= expected_delay - 0.5  # Allow for small timing variations


class TestReportData:
    """ReportData Pydanticモデルテスト"""
    
    def test_report_data_creation_success(self):
        """ReportData作成成功テスト"""
        statistics = StatisticsData(
            total_messages=100,
            total_agents=3,
            active_channels=2,
            completion_rate=0.9,
            channels={},
            agents={}
        )
        
        report_data = ReportData(
            date=datetime(2025, 8, 9, tzinfo=timezone.utc),
            statistics=statistics,
            summary="Test summary"
        )
        
        assert report_data.date.year == 2025
        assert report_data.statistics.total_messages == 100
        assert report_data.summary == "Test summary"
    
    def test_report_data_validation_error(self):
        """ReportDataバリデーションエラーテスト"""
        with pytest.raises(ValueError):
            ReportData(
                date="invalid_date",  # Should be datetime
                statistics=None,
                summary=""
            )


class TestStatisticsData:
    """StatisticsData Pydanticモデルテスト"""
    
    def test_statistics_data_creation_success(self):
        """StatisticsData作成成功テスト"""
        channel_stats = ChannelStatistics(
            channel_id="123",
            channel_name="test-channel",
            message_count=50,
            agent_activity={},
            peak_hour=14,
            avg_response_time=2.5
        )
        
        agent_stats = AgentStatistics(
            agent_name="Spectra",
            message_count=30,
            response_count=25,
            avg_response_time=1.8,
            channel_activity={},
            peak_hour=15,
            performance_score=0.85
        )
        
        statistics = StatisticsData(
            total_messages=150,
            total_agents=3,
            active_channels=4,
            completion_rate=0.85,
            channels={"123": channel_stats},
            agents={"Spectra": agent_stats}
        )
        
        assert statistics.total_messages == 150
        assert statistics.channels["123"].message_count == 50
        assert statistics.agents["Spectra"].performance_score == 0.85
    
    def test_statistics_data_validation_constraints(self):
        """StatisticsDataバリデーション制約テスト"""
        with pytest.raises(ValueError):
            StatisticsData(
                total_messages=-1,  # Should be >= 0
                total_agents=3,
                active_channels=4,
                completion_rate=1.5,  # Should be <= 1.0
                channels={},
                agents={}
            )


class TestChannelStatistics:
    """ChannelStatistics Pydanticモデルテスト"""
    
    def test_channel_statistics_creation_success(self):
        """ChannelStatistics作成成功テスト"""
        stats = ChannelStatistics(
            channel_id="123456",
            channel_name="general",
            message_count=100,
            agent_activity={"Spectra": 40, "LynQ": 35, "Paz": 25},
            peak_hour=14,
            avg_response_time=2.3
        )
        
        assert stats.channel_id == "123456"
        assert stats.message_count == 100
        assert stats.agent_activity["Spectra"] == 40
        assert stats.peak_hour == 14
    
    def test_channel_statistics_validation_constraints(self):
        """ChannelStatisticsバリデーション制約テスト"""
        with pytest.raises(ValueError):
            ChannelStatistics(
                channel_id="",  # Should not be empty
                channel_name="test",
                message_count=-5,  # Should be >= 0
                agent_activity={},
                peak_hour=25,  # Should be < 24
                avg_response_time=-1  # Should be >= 0
            )


class TestAgentStatistics:
    """AgentStatistics Pydanticモデルテスト"""
    
    def test_agent_statistics_creation_success(self):
        """AgentStatistics作成成功テスト"""
        stats = AgentStatistics(
            agent_name="Spectra",
            message_count=75,
            response_count=60,
            avg_response_time=1.8,
            channel_activity={"general": 30, "dev": 25, "lounge": 20},
            peak_hour=15,
            performance_score=0.88
        )
        
        assert stats.agent_name == "Spectra"
        assert stats.message_count == 75
        assert stats.response_count == 60
        assert stats.performance_score == 0.88
    
    def test_agent_statistics_validation_constraints(self):
        """AgentStatisticsバリデーション制約テスト"""
        with pytest.raises(ValueError):
            AgentStatistics(
                agent_name="",  # Should not be empty
                message_count=50,
                response_count=60,  # Should be <= message_count
                avg_response_time=-0.5,  # Should be >= 0
                channel_activity={},
                peak_hour=24,  # Should be < 24
                performance_score=1.5  # Should be <= 1.0
            )


class TestCustomExceptions:
    """カスタム例外クラステスト"""
    
    def test_report_error_inheritance(self):
        """ReportError継承テスト"""
        error = ReportError("Test error message")
        assert isinstance(error, Exception)
        assert str(error) == "Test error message"
    
    def test_template_error_inheritance(self):
        """TemplateError継承テスト"""
        error = TemplateError("Template error message")
        assert isinstance(error, ReportError)
        assert str(error) == "Template error message"
    
    def test_llm_error_inheritance(self):
        """LLMError継承テスト"""
        error = LLMError("LLM error message")
        assert isinstance(error, ReportError)
        assert str(error) == "LLM error message"


# Integration Test Helper Functions
async def create_test_report_data():
    """テスト用ReportData作成ヘルパー"""
    channel_stats = ChannelStatistics(
        channel_id="123",
        channel_name="test-channel",
        message_count=50,
        agent_activity={"Spectra": 20, "LynQ": 15, "Paz": 15},
        peak_hour=14,
        avg_response_time=2.5
    )
    
    agent_stats = AgentStatistics(
        agent_name="Spectra",
        message_count=30,
        response_count=25,
        avg_response_time=1.8,
        channel_activity={"test-channel": 20, "general": 10},
        peak_hour=15,
        performance_score=0.85
    )
    
    statistics = StatisticsData(
        total_messages=150,
        total_agents=3,
        active_channels=4,
        completion_rate=0.85,
        channels={"123": channel_stats},
        agents={"Spectra": agent_stats}
    )
    
    return ReportData(
        date=datetime(2025, 8, 9, tzinfo=timezone.utc),
        statistics=statistics,
        summary="Test daily report summary"
    )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
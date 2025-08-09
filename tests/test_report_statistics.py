"""
Tests for Pandas Statistics Processing

Phase 5.2: 日報システム - pandas統計処理実装
t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的統計処理テストスイート作成
🟢 Green Phase: 最小実装でテスト通過
🟡 Refactor Phase: 品質向上、パフォーマンス最適化

Test Coverage:
- ReportStatisticsProcessor初期化テスト
- チャンネル別統計処理テスト
- エージェント別統計処理テスト
- 時系列分析テスト
- タスク完了メトリクステスト
- メッセージボリューム分析テスト
- パフォーマンス指標計算テスト
- データ検証・エラーハンドリングテスト
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, List, Any, Optional
import json

from app.core.report import (
    ReportStatisticsProcessor,
    StatisticsError,
    DataValidationError,
    StatisticsData,
    ChannelStatistics,
    AgentStatistics
)
from app.core.database import DatabaseManager
from app.core.settings import get_settings, reset_settings


class TestReportStatisticsProcessor:
    """ReportStatisticsProcessor統計処理テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        with patch.dict("os.environ", {
            "ENV": "testing",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
        }):
            self.settings = get_settings()
        self.mock_db = Mock(spec=DatabaseManager)
        self.processor = None
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    def test_processor_initialization_success(self):
        """ReportStatisticsProcessor正常初期化テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        assert processor.db == self.mock_db
        assert processor.settings == self.settings
        assert processor.date_range is None
        assert processor.cached_data == {}
    
    def create_sample_message_data(self) -> pd.DataFrame:
        """サンプルメッセージデータ作成"""
        data = {
            'id': range(1, 101),
            'channel_id': ['123', '456', '123', '789'] * 25,
            'channel_name': ['general', 'dev', 'general', 'lounge'] * 25,
            'agent_name': ['Spectra', 'LynQ', 'Paz', 'Spectra'] * 25,
            'message_content': ['Test message'] * 100,
            'timestamp': pd.date_range(
                start='2025-08-09 00:00:00', 
                periods=100, 
                freq='10min',
                tz='UTC'
            ),
            'response_time': np.random.uniform(0.5, 5.0, 100),
            'is_response': [True, False] * 50
        }
        return pd.DataFrame(data)
    
    def create_sample_task_data(self) -> pd.DataFrame:
        """サンプルタスクデータ作成"""
        num_rows = 50
        data = {
            'id': range(1, num_rows + 1),
            'agent_name': (['Spectra', 'LynQ', 'Paz'] * (num_rows // 3 + 1))[:num_rows],
            'status': (['completed', 'completed', 'failed', 'pending'] * (num_rows // 4 + 1))[:num_rows],
            'priority': (['high', 'medium', 'low', 'critical'] * (num_rows // 4 + 1))[:num_rows],
            'created_at': pd.date_range(
                start='2025-08-09 00:00:00',
                periods=num_rows,
                freq='30min',
                tz='UTC'
            ),
            'completed_at': pd.date_range(
                start='2025-08-09 01:00:00',
                periods=num_rows,
                freq='30min',
                tz='UTC'
            ),
            'execution_time': np.random.uniform(10, 300, num_rows)
        }
        return pd.DataFrame(data)
    
    def test_set_date_range_success(self):
        """日付範囲設定成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        start_date = datetime(2025, 8, 9, tzinfo=timezone.utc)
        end_date = datetime(2025, 8, 10, tzinfo=timezone.utc)
        
        processor.set_date_range(start_date, end_date)
        
        assert processor.date_range == (start_date, end_date)
        assert processor.cached_data == {}  # Cache should be cleared
    
    def test_set_date_range_invalid_order(self):
        """日付範囲無効順序エラーテスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        start_date = datetime(2025, 8, 10, tzinfo=timezone.utc)
        end_date = datetime(2025, 8, 9, tzinfo=timezone.utc)  # Earlier than start
        
        with pytest.raises(DataValidationError, match="End date must be after start date"):
            processor.set_date_range(start_date, end_date)
    
    @patch('app.core.report.pd.read_sql')
    async def test_fetch_message_data_success(self, mock_read_sql):
        """メッセージデータ取得成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        processor.set_date_range(
            datetime(2025, 8, 9, tzinfo=timezone.utc),
            datetime(2025, 8, 10, tzinfo=timezone.utc)
        )
        
        # Mock database connection as context manager
        mock_context_manager = AsyncMock()
        mock_conn = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_conn
        self.mock_db.get_connection.return_value = mock_context_manager
        
        sample_data = self.create_sample_message_data()
        mock_read_sql.return_value = sample_data
        
        result = await processor._fetch_message_data()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 100
        assert 'channel_id' in result.columns
        assert 'agent_name' in result.columns
        mock_read_sql.assert_called_once()
    
    @patch('app.core.report.pd.read_sql')
    async def test_fetch_task_data_success(self, mock_read_sql):
        """タスクデータ取得成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        processor.set_date_range(
            datetime(2025, 8, 9, tzinfo=timezone.utc),
            datetime(2025, 8, 10, tzinfo=timezone.utc)
        )
        
        # Mock database connection as context manager
        mock_context_manager = AsyncMock()
        mock_conn = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_conn
        self.mock_db.get_connection.return_value = mock_context_manager
        
        sample_data = self.create_sample_task_data()
        mock_read_sql.return_value = sample_data
        
        result = await processor._fetch_task_data()
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 50
        assert 'status' in result.columns
        assert 'agent_name' in result.columns
        mock_read_sql.assert_called_once()
    
    async def test_calculate_channel_statistics_success(self):
        """チャンネル別統計計算成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        message_data = self.create_sample_message_data()
        
        result = await processor._calculate_channel_statistics(message_data)
        
        assert isinstance(result, dict)
        assert len(result) == 3  # 3 unique channels
        
        # Check specific channel statistics
        for channel_id, stats in result.items():
            assert isinstance(stats, ChannelStatistics)
            assert stats.channel_id == channel_id
            assert stats.message_count > 0
            assert 0 <= stats.peak_hour <= 23
            assert stats.avg_response_time >= 0
    
    async def test_calculate_agent_statistics_success(self):
        """エージェント別統計計算成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        message_data = self.create_sample_message_data()
        task_data = self.create_sample_task_data()
        
        result = await processor._calculate_agent_statistics(message_data, task_data)
        
        assert isinstance(result, dict)
        assert len(result) == 3  # 3 unique agents
        
        # Check specific agent statistics
        for agent_name, stats in result.items():
            assert isinstance(stats, AgentStatistics)
            assert stats.agent_name == agent_name
            assert stats.message_count > 0
            assert stats.response_count >= 0
            assert 0 <= stats.performance_score <= 1
            assert 0 <= stats.peak_hour <= 23
    
    async def test_calculate_time_series_analysis_success(self):
        """時系列分析成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        message_data = self.create_sample_message_data()
        
        result = await processor._calculate_time_series_analysis(message_data)
        
        assert isinstance(result, dict)
        assert 'hourly_distribution' in result
        assert 'peak_hours' in result
        assert 'activity_trends' in result
        
        # Check hourly distribution
        hourly_dist = result['hourly_distribution']
        assert len(hourly_dist) <= 24  # Max 24 hours
        assert all(isinstance(hour, int) and 0 <= hour <= 23 for hour in hourly_dist.keys())
    
    async def test_calculate_performance_metrics_success(self):
        """パフォーマンスメトリクス計算成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        task_data = self.create_sample_task_data()
        
        result = await processor._calculate_performance_metrics(task_data)
        
        assert isinstance(result, dict)
        assert 'completion_rate' in result
        assert 'avg_execution_time' in result
        assert 'priority_distribution' in result
        assert 'status_distribution' in result
        
        # Check specific metrics
        assert 0 <= result['completion_rate'] <= 1
        assert result['avg_execution_time'] > 0
    
    @patch('app.core.report.ReportStatisticsProcessor._fetch_message_data')
    @patch('app.core.report.ReportStatisticsProcessor._fetch_task_data')
    async def test_generate_full_statistics_success(self, mock_fetch_tasks, mock_fetch_messages):
        """完全統計生成成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        processor.set_date_range(
            datetime(2025, 8, 9, tzinfo=timezone.utc),
            datetime(2025, 8, 10, tzinfo=timezone.utc)
        )
        
        # Mock data
        mock_fetch_messages.return_value = self.create_sample_message_data()
        mock_fetch_tasks.return_value = self.create_sample_task_data()
        
        result = await processor.generate_statistics()
        
        assert isinstance(result, StatisticsData)
        assert result.total_messages > 0
        assert result.total_agents > 0
        assert result.active_channels > 0
        assert 0 <= result.completion_rate <= 1
        assert len(result.channels) > 0
        assert len(result.agents) > 0
    
    async def test_generate_statistics_no_date_range(self):
        """日付範囲未設定時の統計生成エラーテスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        with pytest.raises(StatisticsError, match="Date range must be set"):
            await processor.generate_statistics()
    
    @patch('app.core.report.ReportStatisticsProcessor._fetch_task_data')
    @patch('app.core.report.ReportStatisticsProcessor._fetch_message_data')
    async def test_generate_statistics_empty_data(self, mock_fetch_messages, mock_fetch_tasks):
        """空データでの統計生成テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        processor.set_date_range(
            datetime(2025, 8, 9, tzinfo=timezone.utc),
            datetime(2025, 8, 10, tzinfo=timezone.utc)
        )
        
        # Mock empty data
        mock_fetch_messages.return_value = pd.DataFrame()
        mock_fetch_tasks.return_value = pd.DataFrame()
        
        result = await processor.generate_statistics()
        
        assert isinstance(result, StatisticsData)
        assert result.total_messages == 0
        assert result.total_agents == 0
        assert result.active_channels == 0
        assert result.completion_rate == 0.0
        assert len(result.channels) == 0
        assert len(result.agents) == 0
    
    def test_validate_data_frame_success(self):
        """DataFrame検証成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        valid_df = self.create_sample_message_data()
        required_columns = ['channel_id', 'agent_name', 'timestamp']
        
        # Should not raise exception
        processor._validate_dataframe(valid_df, required_columns)
    
    def test_validate_data_frame_missing_columns(self):
        """DataFrame列不足エラーテスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        invalid_df = pd.DataFrame({'col1': [1, 2, 3]})
        required_columns = ['col1', 'missing_col']
        
        with pytest.raises(DataValidationError, match="Missing required columns"):
            processor._validate_dataframe(invalid_df, required_columns)
    
    def test_validate_data_frame_empty_dataframe(self):
        """空DataFrame検証テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        empty_df = pd.DataFrame()
        required_columns = ['col1']
        
        with pytest.raises(DataValidationError, match="DataFrame is empty"):
            processor._validate_dataframe(empty_df, required_columns)
    
    async def test_calculate_response_time_percentiles_success(self):
        """レスポンス時間パーセンタイル計算成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        message_data = self.create_sample_message_data()
        
        result = await processor._calculate_response_time_percentiles(message_data)
        
        assert isinstance(result, dict)
        assert 'p50' in result
        assert 'p75' in result
        assert 'p90' in result
        assert 'p95' in result
        assert 'p99' in result
        
        # Check order
        assert result['p50'] <= result['p75'] <= result['p90'] <= result['p95'] <= result['p99']
    
    async def test_calculate_channel_activity_matrix_success(self):
        """チャンネル活動マトリクス計算成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        message_data = self.create_sample_message_data()
        
        result = await processor._calculate_channel_activity_matrix(message_data)
        
        assert isinstance(result, dict)
        
        # Check structure
        for channel_name, agent_activity in result.items():
            assert isinstance(channel_name, str)
            assert isinstance(agent_activity, dict)
            assert all(isinstance(count, (int, float)) for count in agent_activity.values())
    
    async def test_cache_mechanism_success(self):
        """キャッシュメカニズム成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        # Cache data
        test_data = self.create_sample_message_data()
        cache_key = "test_messages"
        processor._cache_data(cache_key, test_data)
        
        # Retrieve cached data
        cached_data = processor._get_cached_data(cache_key)
        
        assert cached_data is not None
        pd.testing.assert_frame_equal(cached_data, test_data)
    
    def test_cache_miss(self):
        """キャッシュミステスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        cached_data = processor._get_cached_data("nonexistent_key")
        assert cached_data is None
    
    def test_clear_cache_success(self):
        """キャッシュクリア成功テスト"""
        processor = ReportStatisticsProcessor(self.mock_db, self.settings)
        
        # Cache some data
        test_data = self.create_sample_message_data()
        processor._cache_data("test_key", test_data)
        assert "test_key" in processor.cached_data
        
        # Clear cache
        processor._clear_cache()
        assert len(processor.cached_data) == 0


class TestStatisticsHelperFunctions:
    """統計処理ヘルパー関数テスト"""
    
    def test_calculate_peak_hour_success(self):
        """ピーク時間計算成功テスト"""
        from app.core.report import _calculate_peak_hour
        
        timestamps = pd.date_range(
            start='2025-08-09 14:00:00',
            periods=10,
            freq='1h',
            tz='UTC'
        )
        
        peak_hour = _calculate_peak_hour(timestamps)
        
        assert isinstance(peak_hour, int)
        assert 0 <= peak_hour <= 23
    
    def test_calculate_performance_score_success(self):
        """パフォーマンススコア計算成功テスト"""
        from app.core.report import _calculate_performance_score
        
        metrics = {
            'response_rate': 0.8,
            'avg_response_time': 2.0,
            'completion_rate': 0.9,
            'error_rate': 0.1
        }
        
        score = _calculate_performance_score(metrics)
        
        assert isinstance(score, float)
        assert 0 <= score <= 1
    
    def test_normalize_channel_name_success(self):
        """チャンネル名正規化成功テスト"""
        from app.core.report import _normalize_channel_name
        
        test_names = [
            "general",
            "dev-chat",
            "lounge_area",
            "COMMAND-CENTER"
        ]
        
        for name in test_names:
            normalized = _normalize_channel_name(name)
            assert isinstance(normalized, str)
            assert len(normalized) > 0


class TestCustomExceptions:
    """カスタム例外クラステスト"""
    
    def test_statistics_error_inheritance(self):
        """StatisticsError継承テスト"""
        error = StatisticsError("Statistics calculation failed")
        assert isinstance(error, Exception)
        assert str(error) == "Statistics calculation failed"
    
    def test_data_validation_error_inheritance(self):
        """DataValidationError継承テスト"""
        error = DataValidationError("Data validation failed")
        assert isinstance(error, StatisticsError)
        assert str(error) == "Data validation failed"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
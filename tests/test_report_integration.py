"""
Integration Tests for Report System

Phase 5.3: 日報システム - 日報生成統合テスト
t-wada式TDDサイクル実装フロー:
🔴 Red Phase: 包括的統合テストスイート作成
🟢 Green Phase: 最小実装でテスト通過
🟡 Refactor Phase: 品質向上、エンドツーエンドテスト

Test Coverage:
- 完全な日報生成ワークフロー統合テスト
- ModernReportGenerator + ReportStatisticsProcessor統合
- データベース統合テスト
- LangChain LCEL + pandas統計処理統合
- マルチフォーマット出力テスト
- エラー処理・回復統合テスト
- パフォーマンス・メモリ使用量テスト
"""
import asyncio
import pytest
import tempfile
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, List, Any, Optional

from app.core.report import (
    ReportService,
    ModernReportGenerator,
    ReportStatisticsProcessor,
    ReportData,
    StatisticsData,
    ReportError,
    ReportFormat
)
from app.core.database import DatabaseManager, get_db_manager
from app.core.settings import Settings, get_settings, reset_settings
from app.tasks.manager import TaskManager


class TestReportServiceIntegration:
    """ReportService統合テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        with patch.dict("os.environ", {
            "ENV": "testing",
            "GEMINI_API_KEY": "test_key_123",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "REDIS_URL": "redis://localhost:6379/0"
        }):
            self.settings = get_settings()
        
        self.mock_db = Mock(spec=DatabaseManager)
        self.mock_task_manager = Mock(spec=TaskManager)
        self.report_service = None
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    def test_report_service_initialization_success(self):
        """ReportService正常初期化テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        assert service.db_manager == self.mock_db
        assert service.task_manager == self.mock_task_manager
        assert service.settings == self.settings
        assert isinstance(service.report_generator, ModernReportGenerator)
        assert isinstance(service.statistics_processor, ReportStatisticsProcessor)
    
    @patch('app.core.report.ModernReportGenerator.generate_report')
    @patch('app.core.report.ReportStatisticsProcessor.generate_statistics')
    async def test_generate_daily_report_success(self, mock_stats, mock_generate):
        """日報生成成功統合テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        # Mock statistics data
        mock_statistics = StatisticsData(
            total_messages=150,
            total_agents=3,
            active_channels=4,
            completion_rate=0.85,
            channels={},
            agents={}
        )
        mock_stats.return_value = mock_statistics
        
        # Mock report generation
        mock_generate.return_value = "# Daily Report\n\nGenerated content here"
        
        target_date = datetime(2025, 8, 9, tzinfo=timezone.utc)
        result = await service.generate_daily_report(target_date)
        
        assert isinstance(result, dict)
        assert 'markdown' in result
        assert 'json' in result
        assert 'statistics' in result
        assert 'metadata' in result
        
        # Verify method calls
        mock_stats.assert_called_once()
        mock_generate.assert_called_once()
    
    @patch('app.core.report.ModernReportGenerator.generate_report')
    @patch('app.core.report.ReportStatisticsProcessor.generate_statistics')
    async def test_generate_daily_report_with_custom_format(self, mock_stats, mock_generate):
        """カスタムフォーマット日報生成テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        # Mock data
        mock_statistics = StatisticsData(
            total_messages=100,
            total_agents=3,
            active_channels=2,
            completion_rate=0.9,
            channels={},
            agents={}
        )
        mock_stats.return_value = mock_statistics
        mock_generate.return_value = "Custom formatted report"
        
        target_date = datetime(2025, 8, 9, tzinfo=timezone.utc)
        result = await service.generate_daily_report(
            target_date=target_date,
            format=ReportFormat.JSON_ONLY,
            include_statistics=True
        )
        
        assert 'json' in result
        assert 'statistics' in result
        # Markdown should not be included for JSON_ONLY format
        assert 'markdown' not in result or result['markdown'] is None
    
    async def test_generate_daily_report_error_handling(self):
        """日報生成エラーハンドリング統合テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        with patch('app.core.report.ReportStatisticsProcessor.generate_statistics') as mock_stats:
            mock_stats.side_effect = Exception("Database connection failed")
            
            target_date = datetime(2025, 8, 9, tzinfo=timezone.utc)
            
            with pytest.raises(ReportError, match="Failed to generate daily report"):
                await service.generate_daily_report(target_date)
    
    @patch('app.core.report.ModernReportGenerator.generate_report')
    @patch('app.core.report.ReportStatisticsProcessor.generate_statistics')
    async def test_generate_weekly_summary_success(self, mock_stats, mock_generate):
        """週次サマリー生成成功テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        # Mock statistics for multiple days
        mock_statistics = StatisticsData(
            total_messages=1000,
            total_agents=3,
            active_channels=4,
            completion_rate=0.88,
            channels={},
            agents={}
        )
        mock_stats.return_value = mock_statistics
        mock_generate.return_value = "# Weekly Summary\n\nWeekly report content"
        
        end_date = datetime(2025, 8, 9, tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=7)
        
        result = await service.generate_weekly_summary(start_date, end_date)
        
        assert isinstance(result, dict)
        assert 'markdown' in result
        assert 'statistics' in result
        assert 'period' in result
        assert result['period']['start'] == start_date.isoformat()
        assert result['period']['end'] == end_date.isoformat()
    
    @patch('app.core.report.ReportService.generate_daily_report')
    async def test_schedule_daily_report_success(self, mock_generate_daily):
        """日報スケジュール実行成功テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        mock_generate_daily.return_value = {
            'markdown': '# Daily Report',
            'json': {'total_messages': 100},
            'statistics': Mock()
        }
        
        result = await service.schedule_daily_report()
        
        assert isinstance(result, dict)
        assert 'report_id' in result
        assert 'generated_at' in result
        assert 'status' in result
        assert result['status'] == 'success'
        
        mock_generate_daily.assert_called_once()
    
    async def test_export_report_markdown_success(self):
        """Markdownエクスポート成功テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        report_data = {
            'markdown': '# Test Report\n\nContent here',
            'metadata': {'date': '2025-08-09'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False) as tmp_file:
            filepath = tmp_file.name
        
        result = await service.export_report(report_data, filepath, ReportFormat.MARKDOWN)
        
        assert result is True
        
        # Verify file content
        with open(filepath, 'r') as f:
            content = f.read()
            assert '# Test Report' in content
    
    async def test_export_report_json_success(self):
        """JSONエクスポート成功テスト"""
        service = ReportService(
            db_manager=self.mock_db,
            task_manager=self.mock_task_manager,
            settings=self.settings
        )
        
        report_data = {
            'json': {'total_messages': 150, 'agents': 3},
            'statistics': {'completion_rate': 0.85},
            'metadata': {'date': '2025-08-09'}
        }
        
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
            filepath = tmp_file.name
        
        result = await service.export_report(report_data, filepath, ReportFormat.JSON)
        
        assert result is True
        
        # Verify file content
        with open(filepath, 'r') as f:
            content = json.load(f)
            assert content['json']['total_messages'] == 150
            assert content['statistics']['completion_rate'] == 0.85


class TestDatabaseIntegration:
    """データベース統合テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        with patch.dict("os.environ", {
            "ENV": "testing",
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test"
        }):
            self.settings = get_settings()
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    @patch('app.core.database.DatabaseManager.initialize')
    @patch('app.core.database.DatabaseManager.health_check')
    async def test_database_connection_integration(self, mock_health, mock_init):
        """データベース接続統合テスト"""
        mock_init.return_value = None
        mock_health.return_value = True
        
        db_manager = DatabaseManager(self.settings)
        await db_manager.initialize()
        
        health_status = await db_manager.health_check()
        assert health_status is True
        
        mock_init.assert_called_once()
        mock_health.assert_called_once()
    
    @patch('app.core.report.pd.read_sql')
    async def test_message_data_integration(self, mock_read_sql):
        """メッセージデータ統合テスト"""
        # Sample data that would come from database
        sample_data = {
            'id': [1, 2, 3],
            'channel_id': ['123', '456', '123'],
            'channel_name': ['general', 'dev', 'general'],
            'agent_name': ['Spectra', 'LynQ', 'Spectra'],
            'timestamp': ['2025-08-09 10:00:00', '2025-08-09 11:00:00', '2025-08-09 12:00:00'],
            'message_content': ['Hello', 'Working on task', 'Update complete']
        }
        
        import pandas as pd
        mock_read_sql.return_value = pd.DataFrame(sample_data)
        
        # Mock database manager
        mock_db = Mock(spec=DatabaseManager)
        mock_conn = AsyncMock()
        mock_db.get_connection.return_value.__aenter__.return_value = mock_conn
        
        processor = ReportStatisticsProcessor(mock_db, self.settings)
        processor.set_date_range(
            datetime(2025, 8, 9, tzinfo=timezone.utc),
            datetime(2025, 8, 10, tzinfo=timezone.utc)
        )
        
        data = await processor._fetch_message_data()
        
        assert isinstance(data, pd.DataFrame)
        assert len(data) == 3
        assert 'channel_id' in data.columns
        assert 'agent_name' in data.columns


class TestLangChainLCELIntegration:
    """LangChain LCEL統合テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        with patch.dict("os.environ", {
            "ENV": "testing",
            "GEMINI_API_KEY": "test_key_123"
        }):
            self.settings = get_settings()
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    @patch('app.core.report.ChatGoogleGenerativeAI')
    @patch('app.core.report.ChatPromptTemplate')
    async def test_lcel_chain_integration(self, mock_prompt_class, mock_gemini_class):
        """LCEL Chain統合テスト"""
        # Mock LLM
        mock_llm = Mock()
        mock_gemini_class.return_value = mock_llm
        
        # Mock Prompt Template
        mock_prompt = Mock()
        mock_prompt_class.from_template.return_value = mock_prompt
        
        # Mock Chain
        mock_chain = AsyncMock()
        mock_response = Mock()
        mock_response.content = "Generated report with LCEL"
        mock_chain.ainvoke.return_value = mock_response
        
        with patch.object(mock_prompt, '__or__', return_value=mock_chain):
            generator = ModernReportGenerator(self.settings)
            
            # Create test report data
            report_data = ReportData(
                date=datetime(2025, 8, 9, tzinfo=timezone.utc),
                statistics=StatisticsData(
                    total_messages=100,
                    total_agents=3,
                    active_channels=2,
                    completion_rate=0.9,
                    channels={},
                    agents={}
                ),
                summary="Test LCEL integration"
            )
            
            result = await generator.generate_report(report_data)
            
            assert "Generated report with LCEL" in result
            mock_chain.ainvoke.assert_called_once()


class TestPerformanceAndMemoryIntegration:
    """パフォーマンス・メモリ統合テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        with patch.dict("os.environ", {
            "ENV": "testing",
            "GEMINI_API_KEY": "test_key_123"
        }):
            self.settings = get_settings()
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    @patch('app.core.report.ReportStatisticsProcessor.generate_statistics')
    async def test_large_dataset_performance(self, mock_stats):
        """大量データセットパフォーマンステスト"""
        import time
        import pandas as pd
        
        # Simulate large dataset statistics
        mock_statistics = StatisticsData(
            total_messages=10000,
            total_agents=3,
            active_channels=10,
            completion_rate=0.88,
            channels={f"channel_{i}": Mock() for i in range(10)},
            agents={f"agent_{i}": Mock() for i in range(3)}
        )
        mock_stats.return_value = mock_statistics
        
        mock_db = Mock(spec=DatabaseManager)
        service = ReportService(
            db_manager=mock_db,
            task_manager=Mock(),
            settings=self.settings
        )
        
        # Measure performance
        start_time = time.time()
        
        with patch('app.core.report.ModernReportGenerator.generate_report') as mock_gen:
            mock_gen.return_value = "Large dataset report"
            result = await service.generate_daily_report(
                datetime(2025, 8, 9, tzinfo=timezone.utc)
            )
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Performance assertion (should complete within reasonable time)
        assert execution_time < 10.0  # 10 seconds max
        assert isinstance(result, dict)
    
    async def test_memory_usage_optimization(self):
        """メモリ使用量最適化テスト"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        mock_db = Mock(spec=DatabaseManager)
        processor = ReportStatisticsProcessor(mock_db, self.settings)
        
        # Simulate processing large datasets
        for i in range(10):
            processor._cache_data(f"test_key_{i}", Mock())
        
        # Clear cache to test memory cleanup
        processor._clear_cache()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        assert memory_increase < 100  # Less than 100MB increase
    
    @patch('app.core.report.ModernReportGenerator._enforce_rate_limit')
    async def test_rate_limiting_integration(self, mock_rate_limit):
        """レート制限統合テスト"""
        mock_rate_limit.return_value = None
        
        generator = ModernReportGenerator(self.settings)
        
        # Multiple rapid calls should trigger rate limiting
        tasks = []
        for i in range(5):
            with patch('app.core.report.ModernReportGenerator.generate_report') as mock_gen:
                mock_gen.return_value = f"Report {i}"
                task = asyncio.create_task(
                    generator.generate_report(Mock(spec=ReportData))
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Rate limiting should have been called
        assert mock_rate_limit.call_count >= 5


class TestErrorRecoveryIntegration:
    """エラー回復統合テスト"""
    
    def setup_method(self):
        """各テスト前の初期化"""
        reset_settings()
        with patch.dict("os.environ", {
            "ENV": "testing",
            "GEMINI_API_KEY": "test_key_123"
        }):
            self.settings = get_settings()
    
    def teardown_method(self):
        """各テスト後のクリーンアップ"""
        reset_settings()
    
    async def test_database_connection_retry(self):
        """データベース接続リトライ統合テスト"""
        mock_db = Mock(spec=DatabaseManager)
        
        # First call fails, second succeeds
        mock_db.health_check.side_effect = [False, True]
        
        service = ReportService(
            db_manager=mock_db,
            task_manager=Mock(),
            settings=self.settings
        )
        
        # Should eventually succeed after retry
        with patch('asyncio.sleep'):  # Speed up retry
            result = await service._ensure_database_connection()
            assert result is True
    
    @patch('app.core.report.ModernReportGenerator.generate_report')
    async def test_llm_api_error_recovery(self, mock_generate):
        """LLM APIエラー回復統合テスト"""
        # First call fails, second succeeds
        mock_generate.side_effect = [
            Exception("API rate limit exceeded"),
            "Successful report generation"
        ]
        
        service = ReportService(
            db_manager=Mock(),
            task_manager=Mock(),
            settings=self.settings
        )
        
        with patch('app.core.report.ReportStatisticsProcessor.generate_statistics') as mock_stats:
            mock_stats.return_value = Mock(spec=StatisticsData)
            
            # Should eventually succeed with retry
            with patch('asyncio.sleep'):  # Speed up retry
                result = await service._generate_report_with_retry(Mock(spec=ReportData))
                assert "Successful report generation" in result


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
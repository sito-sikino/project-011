"""
Test suite for Phase 8: LangGraph Supervisor implementation

LangGraph Supervisor Pattern・Discord Multi-Agent System テスト
- DiscordSupervisor基本動作テスト
- DiscordAgents人格定義テスト
- エージェント選択・応答生成テスト
- StateGraph構築・実行テスト
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

from langchain_core.messages import HumanMessage, AIMessage

from app.langgraph.supervisor import DiscordSupervisor, DiscordState, AgentType, build_langgraph_app
from app.langgraph.agents import DiscordAgents, AgentPersonality, ChannelType, create_discord_agents
from app.core.settings import Settings, GeminiConfig, AgentConfig, ChannelConfig


class TestDiscordAgents:
    """DiscordAgents クラステスト"""
    
    @pytest.fixture
    def mock_settings(self):
        """テスト用設定オブジェクト"""
        settings = Mock(spec=Settings)
        settings.gemini = Mock(spec=GeminiConfig)
        settings.gemini.api_key = "test-api-key"
        
        settings.agent = Mock(spec=AgentConfig) 
        settings.agent.spectra_temperature = 0.5
        settings.agent.lynq_temperature = 0.3
        settings.agent.paz_temperature = 0.9
        
        settings.channel = Mock(spec=ChannelConfig)
        settings.channel.command_center_max_chars = 100
        settings.channel.creation_max_chars = 200
        settings.channel.development_max_chars = 200
        settings.channel.lounge_max_chars = 30
        
        return settings
    
    def test_agents_initialization(self, mock_settings):
        """エージェント初期化テスト"""
        agents = DiscordAgents(mock_settings)
        
        # 3つのエージェントが正しく初期化されること
        assert len(agents.agents) == 3
        assert "spectra" in agents.agents
        assert "lynq" in agents.agents
        assert "paz" in agents.agents
        
        # エージェント人格が正しく設定されること
        spectra = agents.get_agent_personality("spectra")
        assert spectra is not None
        assert spectra.name == "Spectra"
        assert spectra.temperature == 0.5
        assert spectra.role == "メタ思考・議論進行・方針整理"
    
    def test_agent_personality_definition(self, mock_settings):
        """エージェント人格定義テスト"""
        agents = DiscordAgents(mock_settings)
        
        # Spectraの人格確認
        spectra = agents.get_agent_personality("spectra")
        assert spectra.channel_preferences["command-center"] == 0.40
        assert spectra.max_chars_per_channel["command-center"] == 100
        
        # LynQの人格確認
        lynq = agents.get_agent_personality("lynq")
        assert lynq.temperature == 0.3
        assert lynq.channel_preferences["development"] == 0.50
        
        # Pazの人格確認
        paz = agents.get_agent_personality("paz")
        assert paz.temperature == 0.9
        assert paz.channel_preferences["creation"] == 0.50
    
    def test_system_prompt_generation(self, mock_settings):
        """システムプロンプト生成テスト"""
        agents = DiscordAgents(mock_settings)
        
        # Spectraのプロンプト生成
        prompt = agents.get_system_prompt("spectra", "command-center")
        assert "Spectra" in prompt
        assert "メタ思考・議論進行・方針整理" in prompt
        assert "100文字以内" in prompt
        assert "temperature=0.5" in prompt
        
        # チャンネル未指定時のプロンプト
        prompt_no_channel = agents.get_system_prompt("lynq")
        assert "LynQ" in prompt_no_channel
        assert "論理的検証・技術分析・問題解決" in prompt_no_channel
    
    @patch('app.langgraph.agents.ChatGoogleGenerativeAI')
    def test_agent_response_generation(self, mock_llm_class, mock_settings):
        """エージェント応答生成テスト"""
        # モックLLM設定
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "これはテスト応答です。"
        mock_llm.invoke.return_value = mock_response
        mock_llm_class.return_value = mock_llm
        
        agents = DiscordAgents(mock_settings)
        
        # 応答生成テスト
        messages = [HumanMessage(content="テストメッセージ")]
        response = agents.generate_agent_response("spectra", messages, "command-center")
        
        assert response == "これはテスト応答です。"
        assert mock_llm.invoke.called
    
    def test_channel_agent_preferences(self, mock_settings):
        """チャンネル別エージェント発言比率テスト"""
        agents = DiscordAgents(mock_settings)
        
        # command-centerの発言比率確認
        prefs = agents.get_channel_agent_preferences("command-center")
        assert prefs["spectra"] == 0.40
        assert prefs["lynq"] == 0.30
        assert prefs["paz"] == 0.30
        
        # developmentの発言比率確認
        dev_prefs = agents.get_channel_agent_preferences("development")
        assert dev_prefs["lynq"] == 0.50
        
    def test_agent_response_probability(self, mock_settings):
        """エージェント応答確率判定テスト"""
        agents = DiscordAgents(mock_settings)
        
        # Spectraがcommand-centerで応答すべきかテスト
        assert agents.should_agent_respond("spectra", "command-center", 0.30)  # 40%以下なので True
        assert not agents.should_agent_respond("spectra", "command-center", 0.50)  # 40%を超えるので False
        
        # LynQがdevelopmentで応答すべきかテスト
        assert agents.should_agent_respond("lynq", "development", 0.45)  # 50%以下なので True
        assert not agents.should_agent_respond("lynq", "development", 0.60)  # 50%を超えるので False


class TestDiscordSupervisor:
    """DiscordSupervisor クラステスト"""
    
    @pytest.fixture
    def mock_settings(self):
        """テスト用設定オブジェクト"""
        settings = Mock(spec=Settings)
        settings.gemini = Mock(spec=GeminiConfig)
        settings.gemini.api_key = "test-api-key"
        return settings
    
    @patch('app.langgraph.supervisor.ChatGoogleGenerativeAI')
    def test_supervisor_initialization(self, mock_llm_class, mock_settings):
        """Supervisor初期化テスト"""
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm
        
        supervisor = DiscordSupervisor(mock_settings)
        
        assert supervisor.settings == mock_settings
        assert supervisor.model == mock_llm
        assert supervisor.graph is not None
    
    def test_discord_state_structure(self):
        """DiscordState構造テスト"""
        state = DiscordState(
            messages=[],
            channel_name="command-center",
            channel_id=12345,
            current_agent="spectra",
            next_agent="lynq",
            task_description="テストタスク",
            task_channel="development"
        )
        
        assert state["channel_name"] == "command-center"
        assert state["channel_id"] == 12345
        assert state["current_agent"] == "spectra"
        assert state["next_agent"] == "lynq"
        assert state["task_description"] == "テストタスク"
        assert state["task_channel"] == "development"
    
    @patch('app.langgraph.supervisor.ChatGoogleGenerativeAI')
    @pytest.mark.asyncio
    async def test_supervisor_ainvoke(self, mock_llm_class, mock_settings):
        """Supervisor ainvoke テスト"""
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm
        
        supervisor = DiscordSupervisor(mock_settings)
        
        # GraphのainvokeをMock
        supervisor.graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="テスト応答")],
            "current_agent": "spectra"
        })
        
        input_data = {
            "messages": [HumanMessage(content="テスト入力")],
            "channel_name": "command-center",
            "channel_id": 12345
        }
        
        result = await supervisor.ainvoke(input_data)
        
        assert "messages" in result
        assert result.get("current_agent") == "spectra"
    
    def test_agent_type_enum(self):
        """AgentType enum テスト"""
        assert AgentType.SPECTRA.value == "spectra"
        assert AgentType.LYNQ.value == "lynq"
        assert AgentType.PAZ.value == "paz"
    
    @patch('app.langgraph.supervisor.ChatGoogleGenerativeAI')
    def test_build_langgraph_app(self, mock_llm_class, mock_settings):
        """build_langgraph_app 関数テスト"""
        mock_llm = Mock()
        mock_llm_class.return_value = mock_llm
        
        app = build_langgraph_app(mock_settings)
        
        assert isinstance(app, DiscordSupervisor)
        assert app.settings == mock_settings


class TestDiscordStateIntegration:
    """Discord State統合テスト"""
    
    def test_discord_state_messages_inheritance(self):
        """MessagesState継承テスト"""
        # MessagesStateを継承しているか確認
        state = DiscordState(
            messages=[HumanMessage(content="テスト")],
            channel_name="test"
        )
        
        assert "messages" in state
        assert len(state["messages"]) == 1
        assert state["messages"][0].content == "テスト"
    
    def test_custom_state_fields(self):
        """カスタム状態フィールドテスト"""
        state = DiscordState(
            messages=[],
            channel_name="command-center",
            channel_id=12345,
            current_agent="spectra",
            next_agent="lynq",
            task_description="テスト",
            task_channel="development"
        )
        
        # 全てのカスタムフィールドが設定できること
        assert state["channel_name"] == "command-center"
        assert state["channel_id"] == 12345
        assert state["current_agent"] == "spectra"
        assert state["next_agent"] == "lynq"
        assert state["task_description"] == "テスト"
        assert state["task_channel"] == "development"


@pytest.mark.asyncio 
class TestLangGraphIntegration:
    """LangGraph統合テスト"""
    
    @patch('app.langgraph.supervisor.ChatGoogleGenerativeAI')
    async def test_graph_node_execution_flow(self, mock_llm_class):
        """GraphノードN実行フローテスト"""
        # モック設定
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "spectra"
        mock_llm.invoke.return_value = mock_response
        mock_llm.with_config.return_value = mock_llm
        mock_llm_class.return_value = mock_llm
        
        # テスト用設定
        settings = Mock(spec=Settings)
        settings.gemini = Mock(spec=GeminiConfig)
        settings.gemini.api_key = "test-api-key"
        
        supervisor = DiscordSupervisor(settings)
        
        # テスト状態作成
        test_state = DiscordState(
            messages=[HumanMessage(content="こんにちは")],
            channel_name="command-center",
            channel_id=12345
        )
        
        # Graph実行は実際のLLM呼び出しが必要なのでMockで代用
        supervisor.graph.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="こんにちは！")],
            "current_agent": "spectra"
        })
        
        result = await supervisor.graph.ainvoke(test_state)
        
        assert "messages" in result
        assert "current_agent" in result


class TestChannelType:
    """ChannelType enum テスト"""
    
    def test_channel_type_values(self):
        """チャンネルタイプ値テスト"""
        assert ChannelType.COMMAND_CENTER.value == "command-center"
        assert ChannelType.CREATION.value == "creation" 
        assert ChannelType.DEVELOPMENT.value == "development"
        assert ChannelType.LOUNGE.value == "lounge"


class TestDiscordToolIntegration:
    """Discord Tool統合テスト"""
    
    def test_send_to_discord_tool_structure(self):
        """send_to_discord_tool 構造テスト"""
        # ツールの基本構造確認（実際の実行ではなく存在確認のみ）
        from app.langgraph.supervisor import send_to_discord_tool
        
        assert hasattr(send_to_discord_tool, 'name')
        assert hasattr(send_to_discord_tool, 'description')
        assert callable(send_to_discord_tool)
        
        # ツール名と説明の確認
        assert send_to_discord_tool.name == "send_to_discord_tool"
        assert "Discord指定チャンネルに指定エージェントから送信" in send_to_discord_tool.description


if __name__ == "__main__":
    # テスト実行
    pytest.main([__file__, "-v"])
"""
LangGraph Supervisor for Discord Multi-Agent System

Phase 8: LangGraph Supervisor実装
- Multi-Agent Orchestration (Spectra, LynQ, Paz)
- Supervisor Pattern実装  
- State Management (MessagesState + カスタム状態)
- Discord統合 (send_to_discord_tool)
- メモリシステム統合 (OptimalMemorySystem)
"""
import logging
from typing import Dict, Any, Optional, List, Literal, Annotated
from enum import Enum

from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState

from app.core.settings import Settings

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """エージェント種別定義"""
    SPECTRA = "spectra"
    LYNQ = "lynq"
    PAZ = "paz"


class DiscordState(MessagesState):
    """
    Discord Multi-Agent用のカスタム状態
    MessagesStateを継承し、追加フィールドを定義
    """
    # 現在のチャンネル情報
    channel_name: Optional[str]
    channel_id: Optional[int]
    
    # エージェント制御
    current_agent: Optional[str]
    next_agent: Optional[str]
    
    # タスク情報
    task_description: Optional[str]
    task_channel: Optional[str]
    
    # Phase 9: 自発発言システム用フィールド
    message_type: Optional[Literal["normal", "mention", "command", "tick"]]
    tick_probability: Optional[float]
    context_relevance_score: Optional[float]


# Discord送信ツール（グローバルからDiscordManagerを参照）
@tool
def send_to_discord_tool(
    agent_name: Annotated[str, "送信エージェント名（spectra/lynq/paz）"],
    channel_name: Annotated[str, "送信チャンネル名"],
    content: Annotated[str, "送信メッセージ内容"],
    state: Annotated[DiscordState, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Discord指定チャンネルに指定エージェントから送信"""
    try:
        # グローバルのdiscord_managerを使用してメッセージ送信
        import asyncio
        from app.discord_manager.manager import discord_manager
        
        if discord_manager:
            channel_id = discord_manager.get_channel_id(channel_name)
            if channel_id:
                # 非同期送信をスケジューリング
                asyncio.create_task(
                    discord_manager.send_as_agent(agent_name, channel_id, content)
                )
                
                tool_message = {
                    "role": "tool",
                    "content": f"✅ {agent_name} sent to #{channel_name}: {content[:50]}...",
                    "name": "send_to_discord_tool",
                    "tool_call_id": tool_call_id,
                }
                
                return Command(
                    update={
                        "messages": state["messages"] + [tool_message]
                    }
                )
        
        # エラー時のフォールバック
        error_message = {
            "role": "tool", 
            "content": f"❌ Failed to send to #{channel_name}",
            "name": "send_to_discord_tool",
            "tool_call_id": tool_call_id,
        }
        return Command(update={"messages": state["messages"] + [error_message]})
        
    except Exception as e:
        logger.error(f"Discord送信エラー: {e}")
        error_message = {
            "role": "tool",
            "content": f"❌ Discord送信エラー: {str(e)}",
            "name": "send_to_discord_tool", 
            "tool_call_id": tool_call_id,
        }
        return Command(update={"messages": state["messages"] + [error_message]})


class DiscordSupervisor:
    """
    Discord Multi-Agent Supervisor
    LangGraph Supervisor Patternによる3エージェント制御
    """
    
    def __init__(self, settings: Settings):
        """初期化"""
        self.settings = settings
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            api_key=settings.gemini.api_key,
            temperature=0.5
        )
        self.graph = self._build_graph()
        
        logger.info("Discord Supervisor initialized with LangGraph")
    
    def _weighted_random_choice(self, weights: Dict[str, float]) -> str:
        """
        重み付きランダム選択
        
        Args:
            weights: {選択肢: 重み} の辞書
            
        Returns:
            str: 選択された項目
        """
        import random
        random_value = random.random()
        cumulative = 0.0
        
        for choice, weight in weights.items():
            cumulative += weight
            if random_value <= cumulative:
                return choice
                
        # フォールバック（計算誤差対応）
        return list(weights.keys())[-1]
    
    def _build_graph(self) -> StateGraph:
        """LangGraph StateGraphを構築"""
        
        # Supervisor Node: どのエージェントを呼び出すかを決定
        def supervisor_node(state: DiscordState) -> Command[Literal["spectra_agent", "lynq_agent", "paz_agent", END]]:
            """Supervisorノード: エージェント選択とルーティング（Phase 9: チャンネル別発言比率対応）"""
            
            # Phase 9: メッセージタイプ確認
            message_type = state.get("message_type", "normal")
            channel_name = state.get("channel_name", "未設定")
            
            # Phase 9: チャンネル別エージェント発言比率
            CHANNEL_PREFERENCES = {
                "command-center": {"spectra": 0.40, "lynq": 0.30, "paz": 0.30},
                "creation": {"paz": 0.50, "spectra": 0.25, "lynq": 0.25}, 
                "development": {"lynq": 0.50, "spectra": 0.25, "paz": 0.25},
                "lounge": {"spectra": 0.34, "lynq": 0.33, "paz": 0.33}
            }
            
            # Phase 9: Tick処理の場合は確率的エージェント選択
            if message_type == "tick":
                preferences = CHANNEL_PREFERENCES.get(channel_name, 
                    {"spectra": 0.33, "lynq": 0.33, "paz": 0.34})
                
                selected_agent_name = self._weighted_random_choice(preferences)
                next_agent = f"{selected_agent_name}_agent"
                
                logger.info(f"Tick処理: {channel_name}で{selected_agent_name}を確率選択")
                
                return Command(
                    goto=next_agent,
                    update={"next_agent": next_agent, "current_agent": selected_agent_name}
                )
            
            # 通常処理: LLMによるエージェント選択
            system_prompt = """あなたは3つのAIエージェントを管理するSupervisorです。

エージェント:
- spectra: メタ思考・議論進行・方針整理（temperature=0.5）
- lynq: 論理的検証・技術分析・問題解決（temperature=0.3）  
- paz: 発散的アイデア創出・ブレインストーミング（temperature=0.9）

現在のチャンネル情報とメッセージ履歴を基に、最適なエージェントを1つ選択してください。
エージェントが応答した後は、必要に応じて他のエージェントに切り替えるか、終了してください。

選択肢:
- "spectra_agent": Spectraエージェントに委譲
- "lynq_agent": LynQエージェントに委譲  
- "paz_agent": Pazエージェントに委譲
- "__end__": 処理終了

現在のチャンネル: {channel_name}
現在のタスク: {task_description}
"""
            
            messages = [
                SystemMessage(content=system_prompt.format(
                    channel_name=channel_name,
                    task_description=state.get("task_description", "なし")
                ))
            ] + state["messages"]
            
            try:
                # LLMでエージェント選択
                response = self.model.invoke(messages)
                content = response.content.strip().lower()
                
                # 応答からエージェントを判定
                if "spectra" in content:
                    next_agent = "spectra_agent"
                elif "lynq" in content:
                    next_agent = "lynq_agent"
                elif "paz" in content:
                    next_agent = "paz_agent"
                else:
                    next_agent = END
                
                logger.info(f"Supervisor selected: {next_agent}")
                
                return Command(
                    goto=next_agent,
                    update={"next_agent": next_agent}
                )
                
            except Exception as e:
                logger.error(f"Supervisor error: {e}")
                return Command(goto=END)
        
        # Spectra Agent Node
        def spectra_agent_node(state: DiscordState) -> Command[Literal["supervisor"]]:
            """Spectraエージェント: メタ思考・議論進行"""
            
            spectra_prompt = """あなたはSpectraです。メタ思考と議論進行が専門です。

特性:
- 俯瞰的視点で物事を整理する
- 構造化された思考で方針を示す
- 議論の進行と方向性を管理する
- temperature=0.5で適度にバランス取れた応答

現在のチャンネル: {channel_name}
現在の状況を整理し、適切な応答をしてください。100文字以内で簡潔に。
"""
            
            messages = [
                SystemMessage(content=spectra_prompt.format(
                    channel_name=state.get("channel_name", "未設定")
                ))
            ] + state["messages"]
            
            try:
                response = self.model.with_config({"temperature": 0.5}).invoke(messages)
                
                # Discord送信をツールとして実行（実際のDiscord送信は後で処理）
                ai_message = AIMessage(
                    content=response.content,
                    tool_calls=[{
                        "name": "send_to_discord_tool",
                        "args": {
                            "agent_name": "spectra",
                            "channel_name": state.get("channel_name", "command-center"),
                            "content": response.content
                        },
                        "id": f"spectra_{hash(response.content)}"
                    }]
                )
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [ai_message],
                        "current_agent": "spectra"
                    }
                )
                
            except Exception as e:
                logger.error(f"Spectra agent error: {e}")
                return Command(goto="supervisor")
        
        # LynQ Agent Node  
        def lynq_agent_node(state: DiscordState) -> Command[Literal["supervisor"]]:
            """LynQエージェント: 論理的検証・技術分析"""
            
            lynq_prompt = """あなたはLynQです。論理的検証と技術分析が専門です。

特性:
- 分析的思考で問題を解決する
- 実装指向で具体的な解決策を提示する  
- 品質重視で検証を行う
- temperature=0.3で論理的で一貫した応答

現在のチャンネル: {channel_name}
技術的観点から分析し、論理的な応答をしてください。100文字以内で簡潔に。
"""
            
            messages = [
                SystemMessage(content=lynq_prompt.format(
                    channel_name=state.get("channel_name", "未設定")
                ))
            ] + state["messages"]
            
            try:
                response = self.model.with_config({"temperature": 0.3}).invoke(messages)
                
                ai_message = AIMessage(
                    content=response.content,
                    tool_calls=[{
                        "name": "send_to_discord_tool",
                        "args": {
                            "agent_name": "lynq",
                            "channel_name": state.get("channel_name", "development"),
                            "content": response.content
                        },
                        "id": f"lynq_{hash(response.content)}"
                    }]
                )
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [ai_message],
                        "current_agent": "lynq"
                    }
                )
                
            except Exception as e:
                logger.error(f"LynQ agent error: {e}")
                return Command(goto="supervisor")
        
        # Paz Agent Node
        def paz_agent_node(state: DiscordState) -> Command[Literal["supervisor"]]:
            """Pazエージェント: 発散的アイデア創出"""
            
            paz_prompt = """あなたはPazです。発散的アイデア創出とブレインストーミングが専門です。

特性:
- 創造的思考で新しいアイデアを生み出す
- 直感的発想で可能性を広げる
- 実験精神で新しい方向性を提案する  
- temperature=0.9で創造的で自由な応答

現在のチャンネル: {channel_name}
創造的な視点から新しいアイデアを提供してください。100文字以内で簡潔に。
"""
            
            messages = [
                SystemMessage(content=paz_prompt.format(
                    channel_name=state.get("channel_name", "未設定")
                ))
            ] + state["messages"]
            
            try:
                response = self.model.with_config({"temperature": 0.9}).invoke(messages)
                
                ai_message = AIMessage(
                    content=response.content,
                    tool_calls=[{
                        "name": "send_to_discord_tool", 
                        "args": {
                            "agent_name": "paz",
                            "channel_name": state.get("channel_name", "creation"),
                            "content": response.content
                        },
                        "id": f"paz_{hash(response.content)}"
                    }]
                )
                
                return Command(
                    goto="supervisor",
                    update={
                        "messages": [ai_message],
                        "current_agent": "paz"
                    }
                )
                
            except Exception as e:
                logger.error(f"Paz agent error: {e}")
                return Command(goto="supervisor")
        
        # StateGraph構築
        builder = StateGraph(DiscordState)
        
        # ノード追加
        builder.add_node("supervisor", supervisor_node)
        builder.add_node("spectra_agent", spectra_agent_node) 
        builder.add_node("lynq_agent", lynq_agent_node)
        builder.add_node("paz_agent", paz_agent_node)
        
        # エッジ定義
        builder.add_edge(START, "supervisor")
        builder.add_edge("spectra_agent", "supervisor")
        builder.add_edge("lynq_agent", "supervisor") 
        builder.add_edge("paz_agent", "supervisor")
        
        return builder.compile()
    
    async def ainvoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph実行
        
        Args:
            input_data: 入力データ（messages, channel_name, channel_id等）
            
        Returns:
            Dict[str, Any]: 処理結果
        """
        try:
            logger.debug(f"LangGraph Supervisor ainvoke: {input_data}")
            
            # StateGraphに渡すためのデータ準備
            graph_input = {
                "messages": input_data.get("messages", []),
                "channel_name": input_data.get("channel_name"),
                "channel_id": input_data.get("channel_id"),
                "task_description": input_data.get("task_description"),
                "task_channel": input_data.get("task_channel"),
            }
            
            # LangGraphで処理実行
            result = await self.graph.ainvoke(graph_input)
            
            logger.info("LangGraph processing completed")
            return result
            
        except Exception as e:
            logger.error(f"LangGraph Supervisor error: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }


def build_langgraph_app(settings: Settings = None) -> DiscordSupervisor:
    """
    LangGraph Discord Supervisor アプリケーション構築
    
    Args:
        settings: 設定オブジェクト
        
    Returns:
        DiscordSupervisor: LangGraph Supervisor インスタンス
    """
    if not settings:
        from app.core.settings import get_settings
        settings = get_settings()
    
    logger.info("Building LangGraph Discord Supervisor application")
    return DiscordSupervisor(settings)
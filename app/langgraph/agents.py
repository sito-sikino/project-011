"""
LangGraph Agents for Discord Multi-Agent System

Phase 8: Spectra、LynQ、Paz人格定義・エージェント間通信実装
- 3つの専門エージェント定義（personality、prompt、parameters）
- チャンネル別発言制御（文字数制限、発言比率）
- エージェント間人格切り替え機能
- Discord統合メッセージ送信機能
"""
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

from app.core.settings import Settings

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """Discord チャンネル種別"""
    COMMAND_CENTER = "command-center"
    CREATION = "creation"
    DEVELOPMENT = "development"
    LOUNGE = "lounge"


@dataclass
class AgentPersonality:
    """エージェント人格定義"""
    name: str
    role: str
    characteristics: List[str]
    temperature: float
    channel_preferences: Dict[str, float]  # チャンネル別発言比率
    max_chars_per_channel: Dict[str, int]  # チャンネル別文字数上限


class DiscordAgents:
    """
    Discord Multi-Agent System エージェント管理
    Spectra、LynQ、Paz の人格・特性・制御を提供
    """
    
    def __init__(self, settings: Settings):
        """エージェント管理システム初期化"""
        self.settings = settings
        self.agents = self._define_agents()
        
        # 各エージェント用のLLMクライアント初期化
        self.llm_clients = {
            agent_name: ChatGoogleGenerativeAI(
                model="gemini-2.0-flash-exp",
                api_key=settings.gemini.api_key,
                temperature=agent.temperature
            )
            for agent_name, agent in self.agents.items()
        }
        
        logger.info("Discord Agents initialized (Spectra, LynQ, Paz)")
    
    def _define_agents(self) -> Dict[str, AgentPersonality]:
        """エージェント人格定義"""
        
        # チャンネル別文字数制限
        char_limits = {
            "command-center": self.settings.channel.command_center_max_chars or 100,
            "creation": self.settings.channel.creation_max_chars or 200,
            "development": self.settings.channel.development_max_chars or 200,
            "lounge": self.settings.channel.lounge_max_chars or 30,
        }
        
        agents = {
            "spectra": AgentPersonality(
                name="Spectra",
                role="メタ思考・議論進行・方針整理",
                characteristics=[
                    "俯瞰的視点で物事を整理する",
                    "構造化された思考で方針を示す",
                    "議論の進行と方向性を管理する",
                    "バランスの取れた判断を行う",
                    "チーム全体の統率を図る"
                ],
                temperature=self.settings.agent.spectra_temperature or 0.5,
                channel_preferences={
                    "command-center": 0.40,  # 40%の発言比率
                    "creation": 0.25,        # 25%の発言比率
                    "development": 0.25,     # 25%の発言比率
                    "lounge": 0.34,          # 34%の発言比率
                },
                max_chars_per_channel=char_limits
            ),
            
            "lynq": AgentPersonality(
                name="LynQ",
                role="論理的検証・技術分析・問題解決",
                characteristics=[
                    "分析的思考で問題を解決する",
                    "実装指向で具体的な解決策を提示する",
                    "品質重視で検証を行う",
                    "論理的で一貫した判断をする",
                    "技術的な詳細に精通している"
                ],
                temperature=self.settings.agent.lynq_temperature or 0.3,
                channel_preferences={
                    "command-center": 0.30,  # 30%の発言比率
                    "creation": 0.25,        # 25%の発言比率
                    "development": 0.50,     # 50%の発言比率
                    "lounge": 0.33,          # 33%の発言比率
                },
                max_chars_per_channel=char_limits
            ),
            
            "paz": AgentPersonality(
                name="Paz",
                role="発散的アイデア創出・ブレインストーミング",
                characteristics=[
                    "創造的思考で新しいアイデアを生み出す",
                    "直感的発想で可能性を広げる",
                    "実験精神で新しい方向性を提案する",
                    "柔軟で自由な発想を持つ",
                    "革新的なアプローチを提案する"
                ],
                temperature=self.settings.agent.paz_temperature or 0.9,
                channel_preferences={
                    "command-center": 0.30,  # 30%の発言比率
                    "creation": 0.50,        # 50%の発言比率
                    "development": 0.25,     # 25%の発言比率
                    "lounge": 0.33,          # 33%の発言比率
                },
                max_chars_per_channel=char_limits
            )
        }
        
        return agents
    
    def get_agent_personality(self, agent_name: str) -> Optional[AgentPersonality]:
        """指定エージェントの人格情報取得"""
        return self.agents.get(agent_name)
    
    def get_system_prompt(self, agent_name: str, channel_name: str = None) -> str:
        """エージェント別システムプロンプト生成"""
        agent = self.agents.get(agent_name)
        if not agent:
            return f"You are {agent_name}."
        
        # チャンネル別文字数制限取得
        char_limit = agent.max_chars_per_channel.get(channel_name, 100)
        
        prompt = f"""あなたは{agent.name}です。{agent.role}が専門です。

人格特性:
{chr(10).join(f'- {char}' for char in agent.characteristics)}

行動指針:
- temperature={agent.temperature}での応答特性を反映する
- {char_limit}文字以内で簡潔に応答する
- 現在のチャンネルは「{channel_name or "未設定"}」です
- チームの一員として協調性を保つ
- 自分の専門性を活かした価値ある発言をする

応答は必ず{char_limit}文字以内に収めてください。"""
        
        return prompt
    
    def generate_agent_response(
        self, 
        agent_name: str, 
        messages: List[Any], 
        channel_name: str = None
    ) -> str:
        """指定エージェントの応答生成"""
        
        agent = self.agents.get(agent_name)
        if not agent:
            return f"エージェント {agent_name} が見つかりません。"
        
        try:
            # システムプロンプト作成
            system_prompt = self.get_system_prompt(agent_name, channel_name)
            full_messages = [SystemMessage(content=system_prompt)] + messages
            
            # LLM呼び出し
            llm = self.llm_clients[agent_name]
            response = llm.invoke(full_messages)
            
            # 文字数制限の適用
            char_limit = agent.max_chars_per_channel.get(channel_name, 100)
            content = response.content.strip()
            
            if len(content) > char_limit:
                content = content[:char_limit-3] + "..."
                logger.warning(f"{agent_name}の応答を{char_limit}文字に切り詰めました")
            
            return content
            
        except Exception as e:
            logger.error(f"{agent_name}の応答生成エラー: {e}")
            return f"申し訳ありません、{agent_name}の応答生成中にエラーが発生しました。"
    
    def get_channel_agent_preferences(self, channel_name: str) -> Dict[str, float]:
        """チャンネル別エージェント発言比率取得"""
        preferences = {}
        for agent_name, agent in self.agents.items():
            preferences[agent_name] = agent.channel_preferences.get(channel_name, 0.33)
        return preferences
    
    def should_agent_respond(self, agent_name: str, channel_name: str, random_val: float) -> bool:
        """エージェントが応答すべきかを判定（確率ベース）"""
        agent = self.agents.get(agent_name)
        if not agent:
            return False
        
        target_probability = agent.channel_preferences.get(channel_name, 0.33)
        return random_val <= target_probability
    
    def get_all_agent_names(self) -> List[str]:
        """全エージェント名リスト取得"""
        return list(self.agents.keys())
    
    def get_agent_info_summary(self) -> Dict[str, Dict[str, Any]]:
        """全エージェント情報サマリー取得"""
        summary = {}
        for agent_name, agent in self.agents.items():
            summary[agent_name] = {
                "role": agent.role,
                "temperature": agent.temperature,
                "characteristics": agent.characteristics,
                "channel_preferences": agent.channel_preferences,
                "max_chars": agent.max_chars_per_channel
            }
        return summary


# 便利関数
def create_discord_agents(settings: Settings = None) -> DiscordAgents:
    """Discord エージェントシステム作成"""
    if not settings:
        from app.core.settings import get_settings
        settings = get_settings()
    
    return DiscordAgents(settings)
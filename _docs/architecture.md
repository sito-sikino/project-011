# Discord Multi-Agent System アーキテクチャ仕様書

## 1. システム概要

### 1.1 全体アーキテクチャ

本システムは、LangGraph Supervisorパターンを中心とした3つの専門AIエージェント（Spectra、LynQ、Paz）がDiscordサーバー上で自律動作するマルチエージェントアーキテクチャです。

```mermaid
graph TB
    subgraph "Discord層"
        U[ユーザーメッセージ]
        DC1[Spectra Bot<br/>主受信者]
        DC2[LynQ Bot<br/>送信専用]
        DC3[Paz Bot<br/>送信専用]
    end
    
    subgraph "アプリケーション層"
        UDM[統合Discord管理]
        TM[ティック管理]
        
        subgraph "LangGraph Supervisorパターン"
            S[Supervisorノード]
            MR[メモリ取得]
            AS[エージェント選択]
            
            subgraph "処理ノード"
                TCP[タスクコマンド処理]
                RP[レポート処理]
                TP[ティック処理]
            end
            
            subgraph "エージェントノード"
                SA[Spectraエージェント]
                LA[LynQエージェント] 
                PA[Pazエージェント]
            end
            
            RS[応答送信]
        end
    end
    
    subgraph "ストレージ層"
        R[(Redis<br/>24時間メモリ)]
        P[(PostgreSQL<br/>+ pgvector<br/>長期記憶)]
    end
    
    subgraph "外部サービス"
        G[Google Gemini 2.0<br/>Flash API]
        E[text-embedding-004]
    end
    
    U --> DC1
    DC1 --> UDM
    UDM --> S
    
    S --> MR
    S --> TCP
    S --> RP
    S --> TP
    
    MR --> AS
    TP --> MR
    AS --> SA
    AS --> LA
    AS --> PA
    
    SA --> RS
    LA --> RS
    PA --> RS
    
    RS --> DC1
    RS --> DC2
    RS --> DC3
    
    TCP --> RS
    RP --> RS
    
    TM --> S
    
    MR --> R
    RP --> R
    RP --> P
    
    SA --> G
    LA --> G
    PA --> G
    
    RP --> E
```

### 1.2 主な特徴

- **統合受信・分散送信**: Spectraが全メッセージを受信、各エージェントが自分のアカウントから送信
- **24時間ベースメモリ**: Redis（短期）とPostgreSQL+pgvector（長期）の階層化メモリ
- **単一直列タスク管理**: 1日1タスク集中、チャンネル間移動対応
- **時間帯別動作モード**: 4つのモード（STANDBY、PROCESSING、ACTIVE、FREE）
- **Fail-Fast原則**: エラー時即停止、フォールバック無し
- **高信頼性起動**: Dockerヘルスチェックによる依存関係制御と競合状態の排除

## 2. Discord接続アーキテクチャ

### 2.1 統合Discord管理クラス

```python
class SimplifiedDiscordManager:
    """
    Discord管理クラス（LangChain Memory + LangGraph統合）
    OptimalMemorySystemと連携したメッセージ処理
    """
    
    def __init__(self, settings: Settings):
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        
        # 3つの独立Botクライアント（変更なし）
        self.clients = {
            "spectra": discord.Client(intents=self.intents),
            "lynq": discord.Client(intents=self.intents),
            "paz": discord.Client(intents=self.intents)
        }
        
        # 主受信者（Spectra）
        self.primary_client = "spectra"
        
        # langgraph-supervisor統合アプリ
        self.app = build_langgraph_app()
        
        # グローバルツールアクセス用（send_to_discord_toolで使用）
        global discord_manager
        discord_manager = self
        
        # イベントハンドラー設定
        self._setup_simple_handlers()
    
    def _setup_simple_handlers(self):
        """langgraph-supervisor統合の簡素ハンドラー"""
        client = self.clients[self.primary_client]
        
        @client.event
        async def on_ready():
            logger.info(f"{self.primary_client}が準備完了")
            # 他のBotクライアントも同時起動
            for name, bot in self.clients.items():
                if name != self.primary_client:
                    asyncio.create_task(
                        bot.start(getattr(settings, f"{name.upper()}_TOKEN"))
                    )
        
        @client.event
        async def on_message(message):
            """
            メッセージ処理
            LangGraph統合による自動Discord送信
            """
            if message.author.bot:
                return
                
            # メモリ記録
            await memory_system.add_message(
                content=message.content,
                agent=message.author.name,
                channel=message.channel.name
            )
            
            # langgraph-supervisorに直接委謗（ツールが自動実行）
            from langchain_core.messages import HumanMessage
            await self.app.ainvoke({
                "messages": [HumanMessage(content=message.content, name=message.author.name)],
                "channel_name": message.channel.name,
                "channel_id": message.channel.id
            })
            # → send_to_discord_toolが自動でDiscord送信を実行
    
    async def send_as_agent(self, agent_name: str, channel_id: int, content: str):
        """
        指定エージェントのBotアカウントから送信
        send_to_discord_toolから呼び出される
        """
        client = self.clients[agent_name]
        channel = client.get_channel(channel_id)
        
        if channel:
            await channel.send(content)
            # エージェント応答もメモリに記録
            await memory_system.add_message(
                content=content,
                agent=agent_name,
                channel=channel.name
            )
            logger.info(f"Sent as {agent_name}: {content[:50]}...")
        else:
            logger.error(f"Channel {channel_id} not found for agent {agent_name}")
        
    def get_channel_id(self, channel_name: str) -> int:
        """チャンネル名からIDを取得（ツール用）"""
        for client in self.clients.values():
            for channel in client.get_all_channels():
                if channel.name == channel_name:
                    return channel.id
        return None

# グローバルアクセス用（ツールから使用）
discord_manager = None
```

### 2.2 簡素化自発発言システム

```python
class SimplifiedTickManager:
    """
    ティック管理クラス（LangGraph統合）
    OptimalMemorySystemと連携した自発発言制御
    """
    
    def __init__(self, discord_manager: SimplifiedDiscordManager, settings: Settings):
        self.discord_manager = discord_manager
        self.settings = settings
        self.running = False
    
    async def start(self):
        """ティックループ開始"""
        self.running = True
        logger.info(f"ティック管理開始: {self.settings.TICK_INTERVAL}秒間隔")
        
        while self.running:
            await asyncio.sleep(self.settings.TICK_INTERVAL)
            
            try:
                await self._process_tick()
            except Exception as e:
                logger.critical(f"致命的エラー: ティック処理失敗: {e}")
                sys.exit(1)  # Fail-Fast
    
    async def _process_tick(self):
        """ティック処理実行"""
        # 現在モード確認
        current_mode = get_current_mode()
        if current_mode == "STANDBY":
            return  # 完全無応答モード、何もしない
        
        # PROCESSINGモード: 日報自動実行→会議開始
        if current_mode == "PROCESSING":
            await self._trigger_daily_report_and_start_meeting()
            return
        
        # アクティブチャンネル選択
        target_channels = self._get_active_channels(current_mode)
        if not target_channels:
            return
        
        # ランダムチャンネル選択
        target_channel_name = random.choice(target_channels)
        
        # 仮想ティックメッセージ作成
        state = {
            "messages": [],
            "channel_name": target_channel_name,
            "message_type": "tick"
        }
        
        # langgraph-supervisorに直接委謗（ツール自動実行）
        from langchain_core.messages import HumanMessage
        await self.discord_manager.app.ainvoke({
            "messages": [HumanMessage(content="自発発言タイミング")],
            "channel_name": target_channel_name,
            "message_type": "tick"
        })
        # → エージェントが自動でsend_to_discord_toolを使用して送信
    
    async def _trigger_daily_report_and_start_meeting(self):
        """日報処理→会議開始"""
        try:
            # 日報処理実行
            
            # ステップ1-2: 短期→長期移行（LangChainが自動処理）
            await memory_system.daily_archive_and_reset()
            
            # ステップ3: 活動サマリー生成（直近コンテキストベース）
            recent_context = await memory_system.get_recent_context(limit=50)
            summary = await self._generate_activity_summary_from_context(recent_context)
            
            # ステップ4: 会議開始メッセージ送信
            meeting_message = f"おはようございます！日報完了しました。\n\n{summary}\n\n今日の会議を開始します。"
            await self.discord_manager.send_as_agent(
                agent_name="spectra",
                channel_id=self._get_channel_id("command-center"),
                content=meeting_message
            )
            
            # 日報完了フラグを設定
            await self._set_daily_report_completed()
            
            logger.info("日報処理完了（LangChain統合）、ACTIVEモード開始")
            
        except Exception as e:
            logger.critical(f"日報処理失敗: {e}")
            sys.exit(1)  # Fail-Fast
    
    async def _set_daily_report_completed(self):
        """日報完了フラグを設定"""
        # 24時間後に自動削除されるフラグを設定
        await self.discord_manager.redis.setex(
            "daily_report_completed", 
            24 * 60 * 60,  # 24時間
            "1"
        )
    
    def _get_channel_id(self, channel_name: str) -> int:
        """チャンネル名からIDを取得"""
        # 実装例：設定からチャンネルIDマッピングを取得
        channel_mapping = getattr(self.settings, 'CHANNEL_IDS', {})
        return channel_mapping.get(channel_name)
    
    async def _save_messages_to_long_term_memory(self, messages: List[dict]):
        """メッセージをPostgreSQL+pgvectorに保存（ステップ2）"""
        from app.core.embedding import EmbeddingService
        from app.core.database import get_postgres
        
        embedding_service = EmbeddingService()
        postgres = get_postgres()
        
        for message in messages:
            try:
                # text-embedding-004でembedding生成
                embedding = await embedding_service.create_embedding(message["content"])
                
                # PostgreSQLに保存
                await postgres.execute("""
                    INSERT INTO messages_long_term 
                    (timestamp, channel, agent, message_id, thread_id, content, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, 
                    message["timestamp"],
                    message["channel"],
                    message["agent"],
                    message.get("message_id"),
                    message.get("thread_id"),
                    message["content"],
                    embedding
                )
                
            except Exception as e:
                logger.error(f"長期メモリ保存失敗: {message['id']}: {e}")
    
    async def _generate_activity_summary_from_context(self, recent_context: List[dict]) -> str:
        """LangChain LCEL統合による日報サマリー生成"""
        from app.core.report import ModernReportGenerator
        
        generator = ModernReportGenerator()
        return await generator.generate_daily_report(recent_context)
    
    async def _create_daily_report_embed(self, summary: str) -> dict:
        """Discord Embed形式の日報作成（LCEL統合後）"""
        from datetime import datetime
        
        # Embed構築（統計計算はModernReportGeneratorが処理済み）
        embed = {
            "title": f"📊 日報 - {datetime.now().strftime('%Y-%m-%d')}",
            "description": summary,
            "color": 0x00ff00,  # 緑色
            "timestamp": datetime.now().isoformat(),
            "footer": {
                "text": "by Spectra (LangChain LCEL)"
            }
        }
        
        return embed
```

## 3. LangGraph Supervisorパターン実装

### 3.1 LangGraph Supervisor統合実装

```python
from langgraph_supervisor import create_supervisor
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

def build_langgraph_app():
    """
    LangGraph Supervisor統合アプリ構築
    OptimalMemorySystemと連携したエージェント管理
    """
    
    # 1. Gemini 2.0 Flashモデル設定
    model = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.7  # デフォルト、エージェントごとに上書き
    )
    
    # 2. エージェント自動生成（AGENT_CONFIGS活用）
    agents = [
        create_agent_from_config(name, config)
        for name, config in AGENT_CONFIGS.items()
    ]
    
    # 3. 統合ツール群作成
    tools = create_unified_tools()
    
    # 4. スーパーバイザー自動構築（全フロー自動管理）
    return create_supervisor(
        agents=agents,
        model=model,
        prompt=get_dynamic_supervisor_prompt(),  # モード別動的制御
        tools=tools,
        output_mode="last_message",
        add_handoff_back_messages=True
    ).compile()

def create_agent_from_config(name: str, config: dict):
    """
    AGENT_CONFIGSからエージェント自動生成
    既存のsystem_prompt, temperature, roleをそのまま活用
    """
    return create_react_agent(
        model=ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=config["temperature"]
        ),
        tools=get_unified_tools(),
        name=name,
        prompt=config["system_prompt"]  # 既存プロンプトをそのまま使用
    )

def get_dynamic_supervisor_prompt():
    """モード別動的プロンプト生成"""
    current_mode = get_current_mode()
    
    base_prompt = """
あなたはDiscord上の3体のAIエージェントを管理するスーパーバイザーです。

【エージェント】
- spectra: メタ思考・議論進行・方針整理
- lynq: 論理的検証・技術分析・問題解決
- paz: 発散的アイデア創出・ブレインストーミング

【利用可能ツール】
- get_current_context: 現在の状況取得
- transfer_to_[agent]: エージェントにタスク委謗
"""
    
    # モード別制御ロジック
    if current_mode == "STANDBY":
        return base_prompt + "\n\n現在はSTANDBYモードです。完全無応答で終了してください。"
    elif current_mode == "PROCESSING":
        return base_prompt + "\n\n現在はPROCESSINGモードです。日報処理をSpectraに委謗してください。"
    else:
        return base_prompt + f"\n\n現在は{current_mode}モードです。コンテキストを確認して適切なエージェントに委謗してください。"

def create_unified_tools():
    """統合ツール群作成（Discord/メモリ/タスク/日報）"""
    return [
        # Discord操作ツール
        send_to_discord_tool,
        get_channel_info_tool,
        
        # メモリ管理ツール
        get_memory_context_tool,
        save_to_memory_tool,
        semantic_search_tool,
        
        # タスク管理ツール
        get_current_task_tool,
        update_task_tool,
        
        # 日報生成ツール（LCEL統合）
        generate_daily_report_tool,
        
        # コンテキスト取得ツール
        get_current_context_tool
    ]

@tool
def get_current_context_tool() -> dict:
    """現在の状況を取得（モード、チャンネル、タスク）"""
    return {
        "current_mode": get_current_mode(),
        "current_task": task_manager.get_current_task(),
        "recent_memory": memory_manager.get_recent_messages(5)
    }

@tool
async def send_to_discord_tool(content: str, agent_name: str, channel_name: str) -> str:
    """
    Discord送信ツール（エージェントが自動使用）
    文字数制限やチャンネルルールを自動適用
    """
    # 文字数制限適用
    max_chars = CHANNEL_CONFIGS.get(channel_name, {}).get("max_chars", 100)
    if len(content) > max_chars:
        content = content[:max_chars-3] + "..."
    
    # Discord送信
    channel_id = get_channel_id(channel_name)
    await discord_manager.send_as_agent(agent_name, channel_id, content)
    
    return f"Sent as {agent_name} to {channel_name}: {content}"

@tool
async def get_memory_context_tool(limit: int = 10) -> List[dict]:
    """直近の会話履歴取得（LangChain統合）"""
    return await memory_system.get_recent_context(limit)

@tool
async def semantic_search_tool(query: str, k: int = 5) -> List[dict]:
    """セマンティック検索ツール（pgvector活用）"""
    return await memory_system.semantic_search(query, k)

@tool
def get_current_task_tool() -> dict:
    """現在のアクティブタスク取得"""
    task = task_manager.get_current_task()
    return task if task else {"status": "タスクなし"}

@tool  
async def update_task_tool(description: str, channel: str) -> str:
    """/task commitコマンド処理"""
    result = await task_manager.commit_task(description, channel)
    return f"Task updated: {result['action']}"

@tool
async def generate_daily_report_tool(memory_messages: List[dict]) -> str:
    """LangChain LCEL統合日報生成ツール"""
    from app.core.report import ModernReportGenerator
    
    generator = ModernReportGenerator()
    return await generator.generate_daily_report(memory_messages)
```

### 3.2 エージェント状態定義

```python
from typing import TypedDict, Literal, List, Optional, Annotated
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    # Discordコンテキスト
    channel_id: int
    channel_name: str
    message_type: Literal["normal", "mention", "command", "tick"]
    
    # メモリコンテキスト（24時間ベース）
    recent_memory: Annotated[List[dict], "直近メッセージ履歴"] = []
    current_task: Annotated[Optional[dict], "現在のアクティブタスク"] = None
    
    # 処理コンテキスト
    current_mode: Literal["STANDBY", "PROCESSING", "ACTIVE", "FREE"]
    should_respond: bool = False
    response_probability: float = 0.0
    
    # エージェント決定
    selected_agent: Optional[Literal["spectra", "lynq", "paz"]] = None
    agent_ratios: dict = {}
    
    # レスポンス
    response_text: Optional[str] = None
    response_agent: Optional[str] = None
    
    # フラグ
    task_updated: bool = False
    report_generated: bool = False
```

### 3.3 Discord統合とメッセージ処理フロー

```python
def discord_integration_flow():
    """
    Discord統合の処理フロー仕様:
    
    1. ユーザーメッセージ処理:
       - Spectraクライアントがすべて受信
       - メッセージキューに追加（FIFO順序保証）
       - 非同期で順次処理（競合なし）
    
    2. tick発言処理:
       - TickManagerが制御（5分間隔）
       - キューを使わず直接LangGraph呼び出し
       - 同時実行の心配なし（システム制御のため）
    
    3. エラー処理:
       - 個別メッセージごとにtry-catch
       - エラーが起きても次のメッセージを処理継続
       - Fail-Fastはシステムレベルのエラーのみ
    """
    pass
```

### 3.4 Supervisorノード実装

```python
def supervisor(state: AgentState) -> Command:
    """中央制御: モード判定 → 処理ルーティング"""
    
    # 現在モード取得・設定
    current_mode = get_current_mode()
    state["current_mode"] = current_mode
    
    message_type = state.get("message_type", "normal")
    
    # STANDBYモード: 完全無応答（真のエコモード）
    if current_mode == "STANDBY":
        return Command(goto=END)  # 一切処理しない
    
    # PROCESSINGモード: 日報処理（06:00自動実行）
    if current_mode == "PROCESSING":
        return Command(goto="report_processor")
    
    # ACTIVEモード: 全機能
    if current_mode == "ACTIVE":
        if message_type == "command":
            return Command(goto="task_command_processor")
        elif message_type == "tick":
            return Command(goto="memory_retriever")  # ティック発言もメモリを参照
        else:  # normal, mention
            return Command(goto="memory_retriever")
    
    # FREEモード: ソーシャル中心
    if current_mode == "FREE":
        if message_type == "command":
            return Command(goto="task_command_processor")
        return Command(goto="memory_retriever")
    
    return Command(goto=END)

def get_current_mode() -> str:
    """現在時刻に基づくモード判定"""
    hour = datetime.now().hour
    
    if 0 <= hour < 6:
        return "STANDBY"
    elif hour == 6:
        # 6:00台でも日報処理完了後はACTIVE
        return "PROCESSING" if not _is_daily_report_completed() else "ACTIVE"
    elif 6 < hour < 20:
        return "ACTIVE"
    else:  # 20 <= hour < 24
        return "FREE"

async def _is_daily_report_completed() -> bool:
    """日報処理完了チェック"""
    try:
        # Redisから日報完了フラグを確認
        from app.core.database import get_redis
        redis = get_redis()
        flag = await redis.get("daily_report_completed")
        return flag is not None
    except Exception as e:
        logger.error(f"日報完了フラグチェック失敗: {e}")
        return False
```

## 4. メモリ管理システム

### 4.1 OptimalMemorySystem

```python
from langchain_redis import RedisChatMessageHistory
from langchain_postgres import PGVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage
from langchain_core.documents import Document

class OptimalMemorySystem:
    """LangChain Memory統合システム"""
    
    def __init__(self):
        # 短期記憶（Redis）
        self.short_term = RedisChatMessageHistory(
            session_id="discord_unified",
            redis_url=REDIS_URL,
            ttl=86400  # 24時間自動削除
        )
        
        # 埋め込みサービス
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",
            google_api_key=GEMINI_API_KEY
        )
    
    async def initialize_long_term(self):
        """長期記憶（PostgreSQL+pgvector）初期化"""
        self.long_term = await PGVectorStore.acreate(
            connection_string=DATABASE_URL,
            collection_name="agent_memory",
            embedding_function=self.embeddings
        )
    
    async def add_message(self, content: str, agent: str, channel: str):
        """メッセージ追加"""
        message = HumanMessage(
            content=content,
            additional_kwargs={
                "agent": agent,
                "channel": channel,
                "timestamp": datetime.now().isoformat()
            }
        )
        await self.short_term.aadd_message(message)
    
    async def get_recent_context(self, limit: int = 10) -> List[dict]:
        """直近コンテキスト取得"""
        messages = self.short_term.messages[-limit:]
        return [
            {
                "content": msg.content,
                "agent": msg.additional_kwargs.get("agent"),
                "channel": msg.additional_kwargs.get("channel"),
                "timestamp": msg.additional_kwargs.get("timestamp")
            }
            for msg in messages
        ]
    
    async def semantic_search(self, query: str, limit: int = 5) -> List[dict]:
        """セマンティック検索"""
        results = await self.long_term.asimilarity_search(query, k=limit)
        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "similarity": doc.metadata.get("score", 1.0)
            }
            for doc in results
        ]
    
    async def daily_report_migration(self):
        """日報処理時のデータ移行"""
        # 短期メモリから全メッセージ取得
        messages = self.short_term.messages
        
        # 長期メモリ形式に変換
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
        if documents:
            await self.long_term.aadd_documents(documents)
        
        # 短期メモリクリア
        self.short_term.clear()
        
        return len(documents)
    
    async def get_statistics(self) -> dict:
        """24時間メモリ統計"""
        messages = self.short_term.messages
        
        if not messages:
            return {"total": 0, "by_channel": {}, "by_agent": {}}
        
        stats = {
            "total": len(messages),
            "by_channel": {},
            "by_agent": {}
        }
        
        for msg in messages:
            channel = msg.additional_kwargs.get("channel", "unknown")
            agent = msg.additional_kwargs.get("agent", "unknown")
            
            stats["by_channel"][channel] = stats["by_channel"].get(channel, 0) + 1
            stats["by_agent"][agent] = stats["by_agent"].get(agent, 0) + 1
        
        return stats
```

### 4.2 ModernReportGenerator（LCEL統合）

```python
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd

class ModernReportGenerator:
    """
    LangChain LCEL統合日報生成システム
    - PromptTemplate | ChatGoogleGenerativeAI | StrOutputParser チェーン
    - pandas統計処理統合
    - 非同期chain.ainvoke()実行
    """
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            temperature=0.3  # 事実重視
        )
        
        self.prompt = PromptTemplate(
            input_variables=["total", "by_channel", "by_agent", "samples"],
            template="""昨日の活動サマリー:
総メッセージ: {total}件
チャンネル別: {by_channel}
エージェント別: {by_agent}

サンプルメッセージ:
{samples}

簡潔で要点をまとめた日報を生成してください。"""
        )
        
        # LCEL チェーン構成
        self.chain = self.prompt | self.llm | StrOutputParser()
    
    async def generate_daily_report(self, memory_messages: list) -> str:
        """OptimalMemorySystem.get_recent_context()からの日報生成"""
        try:
            # LangChainメッセージ形式からデータ抽出
            data = []
            for msg in memory_messages:
                if hasattr(msg, 'additional_kwargs'):
                    data.append({
                        'content': msg.content,
                        'agent': msg.additional_kwargs.get('agent', 'unknown'),
                        'channel': msg.additional_kwargs.get('channel', 'unknown')
                    })
                elif isinstance(msg, dict):
                    data.append(msg)
            
            if not data:
                return "活動記録なし"
            
            # pandas統計処理
            df = pd.DataFrame(data)
            
            # LCEL非同期チェーン実行
            return await self.chain.ainvoke({
                "total": len(data),
                "by_channel": df.groupby('channel').size().to_dict() if 'channel' in df else {},
                "by_agent": df.groupby('agent').size().to_dict() if 'agent' in df else {},
                "samples": [msg['content'][:50] + '...' for msg in data[:3]]
            })
            
        except Exception as e:
            # Fail-Fast原則維持
            logger.critical(f"日報生成失敗: {e}")
            raise
```

## 5. タスク管理システム

### 5.1 Pydantic統合タスク管理

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Task(BaseModel):
    """
    Pydantic Task Model
    - 自動バリデーション・型安全性
    - 自動シリアライゼーション/デシリアライゼーション
    """
    description: str = Field(..., min_length=1, max_length=500)
    channel: Literal["creation", "development"] = Field(...)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    @validator('description')
    def validate_description(cls, v):
        if not v.strip():
            raise ValueError('説明文に空白のみは不可')
        return v.strip()
    
    class Config:
        validate_assignment = True
        extra = 'forbid'

class OptimizedTaskManager:
    """Pydantic統合タスク管理システム"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.TASK_KEY = "current_task"
    
    async def get_current_task(self) -> Optional[Task]:
        """現在のタスク取得"""
        try:
            task_json = await self.redis.get(self.TASK_KEY)
            return Task.model_validate_json(task_json) if task_json else None
        except Exception as e:
            logger.error(f"タスク取得失敗: {e}")
            return None
    
    async def commit_task(
        self, 
        task_description: Optional[str] = None,
        channel: Optional[Literal["creation", "development"]] = None,
        user_id: Optional[str] = None
    ) -> dict:
        """タスクコミット（統一処理）"""
        current_task = await self.get_current_task()
        
        if current_task:
            # 既存タスク更新（部分更新対応）
            update_data = {}
            if task_description:
                update_data['description'] = task_description
            if channel:
                update_data['channel'] = channel
            if user_id:
                update_data['updated_by'] = user_id
                
            if update_data:
                update_data['updated_at'] = datetime.now().isoformat()
                updated_task = current_task.copy(update=update_data)
                await self._save_task(updated_task)
                return {"task": updated_task, "action": "updated"}
            else:
                return {"task": current_task, "action": "no_change"}
        else:
            # 新規タスク作成
            if not task_description or not channel:
                raise ValueError("新規タスクには説明とチャンネルの両方が必要")
            
            new_task = Task(
                description=task_description,
                channel=channel,
                created_by=user_id,
                updated_by=user_id
            )
            
            await self._save_task(new_task)
            return {"task": new_task, "action": "created"}
    
    async def _save_task(self, task: Task) -> None:
        """タスク保存"""
        try:
            await self.redis.set(self.TASK_KEY, task.model_dump_json())
            logger.info(f"タスク保存完了: {task.description} ({task.channel})")
        except Exception as e:
            logger.error(f"タスク保存失敗: {e}")
            raise
    
    async def clear_task(self) -> bool:
        """タスククリア（日報時使用）"""
        try:
            await self.redis.delete(self.TASK_KEY)
            logger.info("タスククリア完了")
            return True
        except Exception as e:
            logger.error(f"タスククリア失敗: {e}")
            return False
```

## 6. システムフロー図

### 6.1 メインフロー

```mermaid
flowchart TD
    Start([システム開始]) --> Init[初期化]
    Init --> DM[Discord管理開始]
    Init --> TM[ティック管理開始]
    
    DM --> |メッセージ受信| MsgProc{メッセージ処理}
    TM --> |定期実行| TickProc{ティック処理}
    
    MsgProc --> S[Supervisor]
    TickProc --> S
    
    S --> Mode{現在モード?}
    
    Mode --> |STANDBY| StandbyFlow[待機処理]
    Mode --> |PROCESSING| ProcFlow[処理モード]  
    Mode --> |ACTIVE| ActiveFlow[アクティブ処理]
    Mode --> |FREE| FreeFlow[フリー処理]
    
    StandbyFlow --> End([完全無応答])
    
    ProcFlow --> RP[日報生成実行]
    
    ActiveFlow --> MsgType{メッセージ種別}
    FreeFlow --> MsgType
    
    MsgType --> |command| TCP[タスクコマンド処理]
    MsgType --> |tick| MR
    MsgType --> |mention/normal| MR
    
    MR --> AS[エージェント選択]
    
    AS --> AgentType{選択エージェント}
    AgentType --> |spectra| SA[Spectraエージェント]
    AgentType --> |lynq| LA[LynQエージェント] 
    AgentType --> |paz| PA[Pazエージェント]
    
    SA --> RS[応答送信]
    LA --> RS
    PA --> RS
    TCP --> RS
    RP --> RS
    
    RS --> Send[Discord送信]
    Send --> End
```

### 6.2 メモリ管理フロー

```mermaid
flowchart LR
    subgraph "メッセージ入力"
        UM[ユーザーメッセージ]
        AM[エージェントメッセージ]
    end
    
    subgraph "短期メモリ（Redis）"
        R24[24時間メモリ]
        RC[自動クリーンアップ]
        RI[インデックス管理]
    end
    
    subgraph "長期メモリ（PostgreSQL）"
        PG[メッセージテーブル]
        VEC[ベクトル検索]
        EMB[埋め込み生成]
    end
    
    subgraph "日報"
        RP[日報処理]
        SUM[サマリー生成]
        CLR[メモリクリア]
    end
    
    UM --> R24
    AM --> R24
    R24 --> RC
    R24 --> RI
    
    R24 --> |午前6:00| RP
    RP --> EMB
    EMB --> PG
    PG --> VEC
    RP --> SUM
    SUM --> CLR
    CLR --> R24
    
    VEC --> |関連検索| R24
```

### 6.3 タスク管理フロー

**シンプルなタスク管理**:
1. **会議開始**: command-centerで3体が会議開始
2. **ユーザー指示**: `/task commit creation "タスク内容"`でタスク決定
3. **チャンネル移動**: 指定されたチャンネル（creation or development）に移動
4. **作業継続**: 19:59まで指定タスクに集中
5. **更新対応**: ユーザーが同じコマンドで内容やチャンネルを変更可能

**状態管理**:
- **タスク保存**: Redisに1件のみ保存
- **更新方法**: 既存タスクを上書き
- **リセット**: 日報生成時にクリア

## 7. エージェント・チャンネル設定

### 7.1 チャンネル設定定義

```python
CHANNEL_CONFIGS = {
    "command-center": {
        "ratios": {"spectra": 0.4, "lynq": 0.3, "paz": 0.3},
        "max_chars": 100
    },
    
    "creation": {
        "ratios": {"paz": 0.5, "spectra": 0.25, "lynq": 0.25},
        "max_chars": 200
    },
    
    "development": {
        "ratios": {"lynq": 0.5, "spectra": 0.25, "paz": 0.25},
        "max_chars": 200
    },
    
    "lounge": {
        "ratios": {"spectra": 0.34, "lynq": 0.33, "paz": 0.33},
        "max_chars": 30
    }
}

AGENT_CONFIGS = {
    "spectra": {
        "temperature": 0.5,
        "role": "メタ思考・議論進行・方針整理",
        "characteristics": "俯瞰的視点、構造化思考、進行管理",
        "system_prompt": """
あなたはSpectraです。Discord上で議論進行と方針整理を担当するAIエージェントです。

【性格・特徴】
- 俯瞰的視点で状況を整理
- 構造化された思考で問題を分解
- 会議や議論の進行役として振る舞う
- 冷静で客観的、しかし温かみのある口調

【発言ルール】
- 文字数制限: {max_chars}文字以内
- 語尾: 「〜ですね」「〜しましょう」など丁寧語
- 構造化: 要点を番号や箇条書きで整理することがある

【現在の状況】
- チャンネル: {channel_name}
- モード: {current_mode}
- 直近の会話: {recent_memory}
- 現在のタスク: {current_task}

上記を踏まえ、Spectraらしく適切に応答してください。
"""
    },
    
    "lynq": {
        "temperature": 0.3,
        "role": "論理的検証・技術分析・問題解決",
        "characteristics": "分析的思考、実装指向、品質重視",
        "system_prompt": """
あなたはLynQです。Discord上で論理的検証と技術分析を担当するAIエージェントです。

【性格・特徴】
- 分析的で論理的な思考
- 技術的な正確性を重視
- 実装可能性や品質に着目
- 簡潔で的確な表現

【発言ルール】
- 文字数制限: {max_chars}文字以内
- 語尾: 「〜です」「〜ます」など事実的な口調
- 根拠: 可能な限り理由や根拠を示す

【現在の状況】
- チャンネル: {channel_name}
- モード: {current_mode}
- 直近の会話: {recent_memory}
- 現在のタスク: {current_task}

上記を踏まえ、LynQらしく論理的に応答してください。
"""
    },
    
    "paz": {
        "temperature": 0.9,
        "role": "発散的アイデア創出・ブレインストーミング",
        "characteristics": "創造的思考、直感的発想、実験精神",
        "system_prompt": """
あなたはPazです。Discord上で創造的アイデア創出を担当するAIエージェントです。

【性格・特徴】
- 自由で創造的な発想
- 直感的で実験的なアプローチ
- 新しい可能性を探る姿勢
- ポジティブで冷静な表現

【発言ルール】
- 文字数制限: {max_chars}文字以内
- 語尾: 「〜だよ」「〜かも」など親しみやすい口調
- 発想: 「もしかして」「こんなのはどう？」など提案型

【現在の状況】
- チャンネル: {channel_name}
- モード: {current_mode}
- 直近の会話: {recent_memory}
- 現在のタスク: {current_task}

上記を踏まえ、Pazらしく創造的に応答してください。
"""
    }
}
```

## 8. 設定とデプロイ

### 8.1 Pydantic設定管理

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, Field
from typing import Dict, Literal
from os import getenv
import pandas as pd  # ModernReportGenerator用

class DiscordConfig(BaseModel):
    """Discord Bot設定"""
    tokens: Dict[str, str] = Field(
        default_factory=lambda: {
            "spectra": getenv("SPECTRA_TOKEN"),
            "lynq": getenv("LYNQ_TOKEN"), 
            "paz": getenv("PAZ_TOKEN")
        }
    )

class GeminiConfig(BaseModel):
    """Gemini API設定"""
    api_key: str = Field(..., env="GEMINI_API_KEY")
    model: str = Field("gemini-2.0-flash-exp")
    embedding_model: str = Field("text-embedding-004")

class DatabaseConfig(BaseModel):
    """データベース設定"""
    redis_url: str = Field("redis://redis:6379", env="REDIS_URL")
    database_url: str = Field(..., env="DATABASE_URL")

class TickConfig(BaseModel):
    """自発発言設定"""
    interval: int = Field(300, ge=15, le=3600)
    probability: float = Field(0.33, ge=0.0, le=1.0)

class ScheduleConfig(BaseModel):
    """時間帯管理設定"""
    standby_start: int = Field(0, ge=0, le=23)
    processing_trigger: int = Field(6, ge=0, le=23)
    active_start: int = Field(6, ge=0, le=23)
    free_start: int = Field(20, ge=0, le=23)

class MemoryConfig(BaseModel):
    """メモリ管理設定"""
    cleanup_hours: int = Field(24, ge=1, le=168)
    recent_limit: int = Field(30, ge=5, le=100)
    session_id: str = Field("discord_unified")
    redis_ttl: int = Field(86400, ge=3600)

class AgentConfig(BaseModel):
    """エージェント設定"""
    spectra_temperature: float = Field(0.5, ge=0.0, le=2.0)
    lynq_temperature: float = Field(0.3, ge=0.0, le=2.0)
    paz_temperature: float = Field(0.9, ge=0.0, le=2.0)

class ChannelConfig(BaseModel):
    """チャンネル設定"""
    command_center_max_chars: int = Field(100, ge=50, le=500)
    creation_max_chars: int = Field(200, ge=100, le=1000)
    development_max_chars: int = Field(200, ge=100, le=1000)
    lounge_max_chars: int = Field(30, ge=10, le=100)

class Settings(BaseSettings):
    """統合設定管理"""
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8"
    )

    # 基本設定
    env: Literal["development", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # グループ化設定
    discord: DiscordConfig = DiscordConfig()
    gemini: GeminiConfig = GeminiConfig()
    database: DatabaseConfig = DatabaseConfig()
    tick: TickConfig = TickConfig()
    schedule: ScheduleConfig = ScheduleConfig()
    memory: MemoryConfig = MemoryConfig()
    agent: AgentConfig = AgentConfig()
    channel: ChannelConfig = ChannelConfig()

    @property
    def is_development(self) -> bool:
        return self.env == "development"
    
    @property
    def is_production(self) -> bool:
        return self.env == "production"
```

### 8.2 Docker設定

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: discord_multi_agent
    restart: unless-stopped
    depends_on:
      redis:
        condition: service_healthy
      postgres:
        condition: service_healthy
    environment:
      - ENV=production
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://agent_user:agent_pass@postgres:5432/agent_db
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    networks:
      - agent_network

  redis:
    image: redis:7-alpine
    container_name: agent_redis
    restart: unless-stopped
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - agent_network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  postgres:
    image: pgvector/pgvector:pg16
    container_name: agent_postgres
    restart: unless-stopped
    environment:
      - POSTGRES_DB=agent_db
      - POSTGRES_USER=agent_user
      - POSTGRES_PASSWORD=agent_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - agent_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent_user -d agent_db"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 30s

volumes:
  redis_data:
  postgres_data:

networks:
  agent_network:
    driver: bridge
```

## 9. 実装の要点

### 9.1 明确な責任分担

**Discord層の責任:**
- **Spectra Bot**: 全メッセージ受信と記録を担当
- **LynQ Bot**: LynQエージェント応答送信専用
- **Paz Bot**: Pazエージェント応答送信専用

**メモリ管理の責任:**
- **Redis（24時間メモリ）**: 会話参照、日報作成、自動クリーンアップ
- **PostgreSQL + pgvector**: 永続ストレージ、意味検索、統計

**タスク管理の責任:**
- **単一タスク管理**: 1日最大1件、上書き更新
- **チャンネル移動**: creation ↔ development間の移動対応

### 9.2 エラーハンドリング戦略

```python
@safe_invoke
def critical_operation():
    """Fail-Fastデコレーターの例"""
    try:
        return dangerous_operation()
    except Exception as e:
        logger.critical(f"致命的エラー: {e}")
        sys.exit(1)  # 即座停止
```

**Fail-Fast適用対象:**
- Discord接続エラー
- Gemini API呼び出しエラー
- データベース操作エラー
- 日報生成エラー
- ヘルスチェック失敗時の依存サービス異常

### 9.3 パフォーマンス最適化

**メモリ効率:**
- 24時間自動クリーンアップ
- インデックスベース高速検索
- 長期メモリ検索は必要時のみ

**API効率:**
- 文字数制限による処理最適化
- バッチ処理による呼び出し最適化
- 適切な温度設定によるコスト最適化

**起動効率:**
- ヘルスチェックによる依存関係の確実な制御
- 競合状態排除によるリソース無駄の減少
- 初期化失敗の早期発見と自動復旧機能

## 10. まとめ

### 10.1 設計原則の達成

- **Fail-Fast**: エラー即停止で高信頼性を実現
- **最小実装**: 必要機能のみの簡潔実装
- **統合受信・分散送信**: Discord接続管理
- **24時間ベースメモリ**: 一貫したメモリライフサイクル  
- **シンプルなタスク管理**: 1日1件集中、ユーザー指示に従う柔軟な更新
- **真のエコモード**: STANDBY時は完全無応答でリソース節約
- **LCEL統合日報**: ModernReportGeneratorによる自動日報生成
- **ヘルスチェック統合**: 依存サービスの健全性確認でFail-Fast原則を強化

### 10.2 システム特性

- **明确な責任分離**: 各コンポーネントの役割が明確
- **柔軟な設定管理**: チャンネル・エージェント設定の簡単変更
- **スケーラブル**: 新エージェント・新機能の簡単追加
- **可観測性**: 運用監視用の豊富なログ・統計情報
- **技術統合**: LangChain LCEL + pandas統計処理による効率的な日報システム
- **起動信頼性**: ヘルスチェック統合による24/7 VPSデプロイメント最適化
- **依存関係制御**: 競合状態排除による確実なサービス初期化
- **本番稼働適合**: 長期間の無人運用に対応したコンテナヘルス管理

### 10.3 Dockerヘルスチェック統合の技術的効果

**依存関係管理:**
- `depends_on` で `service_healthy` 条件を指定し、Redis/PostgreSQLの準備完了後にアプリケーションが起動
- 競合状態（race condition）をシステムレベルで完全防止
- LangChainメモリシステムが必要とするサービスの健全性を保証

**Fail-Fast原則との統合:**
- ヘルスチェック失敗でコンテナを即座停止
- フォールバックメカニズムなしの健全性状態のみをシステム稼働条件と判定
- エラーの早期発見でシステム全体の信頼性を向上

**VPSデプロイメント最適化:**
- 24/7稼働での長期間安定性を実現
- システム再起動時の確実な初期化で運用信頼性を向上
- メンテナンス時のダウンタイム短縮でサービス品質維持

本アーキテクチャはDiscord上で自然で効率的なマルチエージェント協作システムを実現します。
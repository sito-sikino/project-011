# LangGraph Supervisor Pattern 詳細仕様書

## 1. 概要

LangGraph Supervisor Patternは、複数の特化型エージェントを中央のスーパーバイザーエージェントが統制する階層型マルチエージェントアーキテクチャです。

### 主要な特徴
- **中央集権的制御**: スーパーバイザーがすべてのコミュニケーションフローとタスク委譲を管理
- **特化型エージェント**: 各エージェントが特定のタスクに特化
- **動的なルーティング**: コンテキストに基づいて適切なエージェントを選択
- **階層構造**: スーパーバイザーの階層化により複雑なシステムも構築可能

## 2. アーキテクチャ詳細

### 2.1 コンポーネント構成

#### スーパーバイザーエージェント
```python
def supervisor(state: MessagesState) -> Command[Literal["agent_1", "agent_2", END]]:
    # LLMを使用して次に呼び出すエージェントを決定
    response = model.invoke(state["messages"])
    # Commandオブジェクトで制御フローを指定
    return Command(goto=response["next_agent"])
```

**責務:**
- ユーザー入力の受け取りと解析
- 適切なワーカーエージェントの選択
- タスクの委譲と進捗管理
- 最終結果の統合と返却

#### ワーカーエージェント
```python
def agent_1(state: MessagesState) -> Command[Literal["supervisor"]]:
    response = model.invoke(state["messages"])
    return Command(
        goto="supervisor",  # 必ずスーパーバイザーに戻る
        update={"messages": [response]}
    )
```

**特徴:**
- 特定のドメインに特化した処理
- 独自のツールセットとプロンプト
- タスク完了後はスーパーバイザーに制御を返す

### 2.2 StateGraphによる実装

```python
from langgraph.graph import StateGraph, MessagesState, START, END

builder = StateGraph(MessagesState)
builder.add_node(supervisor)
builder.add_node(agent_1)
builder.add_node(agent_2)
builder.add_edge(START, "supervisor")
# エージェントは常にスーパーバイザーに戻る
builder.add_edge("agent_1", "supervisor")
builder.add_edge("agent_2", "supervisor")

graph = builder.compile()
```

## 3. Command オブジェクトの詳細

### 3.1 基本構造
```python
Command(
    goto: str | List[str],  # 次の遷移先ノード
    update: dict,           # 状態の更新内容
    graph: Command.PARENT   # グラフコンテキスト
)
```

### 3.2 使用パターン

#### 単一エージェントへの遷移
```python
return Command(goto="agent_name")
```

#### 並列実行（Send使用）
```python
from langgraph.types import Send

return Command(
    goto=[
        Send("agent_1", state),
        Send("agent_2", state)
    ]
)
```

#### 状態更新を伴う遷移
```python
return Command(
    goto="supervisor",
    update={"messages": state["messages"] + [new_message]}
)
```

## 4. 実装パターン

### 4.1 langgraph-supervisorライブラリ使用

```python
from langgraph_supervisor import create_supervisor
from langchain.chat_models import init_chat_model

supervisor = create_supervisor(
    model=init_chat_model("openai:gpt-4"),
    agents=[research_agent, math_agent],
    prompt=(
        "You are a supervisor managing two agents:\n"
        "- a research agent: Assign research tasks\n"
        "- a math agent: Assign mathematical tasks\n"
        "Do not do any work yourself."
    ),
    add_handoff_back_messages=True,
    output_mode="full_history",  # or "last_message"
).compile()
```

### 4.2 カスタムハンドオフツール実装

```python
def create_handoff_tool(*, agent_name: str, description: str = None):
    name = f"transfer_to_{agent_name}"
    
    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MessagesState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={**state, "messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )
    
    return handoff_tool
```

### 4.3 タスク記述付きハンドオフ

```python
def create_task_description_handoff_tool(
    *, agent_name: str, description: str = None
):
    @tool(name=f"transfer_to_{agent_name}", description=description)
    def handoff_tool(
        task_description: Annotated[str, "詳細なタスク記述"],
        state: Annotated[MessagesState, InjectedState],
    ) -> Command:
        task_message = {"role": "user", "content": task_description}
        agent_input = {**state, "messages": [task_message]}
        return Command(
            goto=[Send(agent_name, agent_input)],
            graph=Command.PARENT,
        )
    
    return handoff_tool
```

## 5. 階層型スーパーバイザー

### 5.1 チーム構造の実装

```python
# チーム1のスーパーバイザーとエージェント
team_1_builder = StateGraph(MessagesState)
team_1_builder.add_node(team_1_supervisor)
team_1_builder.add_node(team_1_agent_1)
team_1_builder.add_node(team_1_agent_2)
team_1_graph = team_1_builder.compile()

# チーム2も同様に構築

# トップレベルスーパーバイザー
def top_level_supervisor(state: MessagesState) -> Command:
    response = model.invoke(state["messages"])
    return Command(goto=response["next_team"])

# 統合グラフ
builder = StateGraph(MessagesState)
builder.add_node(top_level_supervisor)
builder.add_node("team_1_graph", team_1_graph)
builder.add_node("team_2_graph", team_2_graph)
builder.add_edge(START, "top_level_supervisor")
builder.add_edge("team_1_graph", "top_level_supervisor")
builder.add_edge("team_2_graph", "top_level_supervisor")

graph = builder.compile()
```

## 6. 状態管理

### 6.1 MessagesState

```python
class MessagesState(TypedDict):
    messages: Annotated[List[AnyMessage], add_messages]
```

**add_messagesリデューサー:**
- メッセージリストへの追加を管理
- IDベースの重複排除
- メッセージの更新サポート

### 6.2 カスタム状態の拡張

```python
class CustomState(MessagesState):
    next: str  # 次のエージェント
    context: dict  # 共有コンテキスト
    completed_tasks: List[str]  # 完了タスクリスト
```

## 7. メッセージ履歴管理

### 7.1 出力モード

#### full_history
- すべてのエージェント内部メッセージを保持
- デバッグとトレースに有用
- メモリ使用量が増加

#### last_message
- エージェントの最終応答のみを保持
- メモリ効率的
- 内部モノローグを除外

### 7.2 実装例

```python
def call_research_agent(state):
    response = research_agent.invoke(state)
    # 最終メッセージのみを返す
    return {"messages": response["messages"][-1]}
```

## 8. 並列実行とMap-Reduce

### 8.1 並列エージェント実行

```python
def supervisor_parallel(state: MessagesState) -> Command:
    # 複数のエージェントに並列でタスクを送信
    return Command(
        goto=[
            Send("research_agent", {"task": "research_task"}),
            Send("analysis_agent", {"task": "analysis_task"})
        ]
    )
```

### 8.2 結果の集約

```python
def aggregate_results(state: MessagesState) -> MessagesState:
    # 複数エージェントからの結果を集約
    results = [msg for msg in state["messages"] if msg.name in agent_names]
    summary = synthesize_results(results)
    return {"messages": [summary]}
```

## 9. エラーハンドリングとフォールバック

### 9.1 エージェントエラーの処理

```python
def safe_agent_call(state: MessagesState) -> Command:
    try:
        response = agent.invoke(state)
        return Command(goto="supervisor", update=response)
    except Exception as e:
        error_message = {
            "role": "system",
            "content": f"Agent error: {str(e)}"
        }
        return Command(
            goto="fallback_agent",
            update={"messages": [error_message]}
        )
```

## 10. 実装上の注意事項

### 10.1 ベストプラクティス

1. **エージェントの特化**: 各エージェントは明確に定義された単一の責務を持つ
2. **明示的な制御フロー**: スーパーバイザーの決定ロジックを明確に
3. **状態の最小化**: 必要最小限の状態のみを共有
4. **エラーハンドリング**: 各エージェントレベルでのエラー処理
5. **ログとトレース**: デバッグのための適切なログ出力

### 10.2 パフォーマンス考慮事項

- **メッセージ履歴の管理**: 長い会話では履歴のトリミングを検討
- **並列実行の活用**: 独立したタスクは並列実行で高速化
- **キャッシング**: 繰り返し実行される処理結果のキャッシュ

### 10.3 スケーラビリティ

- **階層構造の活用**: 大規模システムは階層型で管理
- **動的エージェント登録**: 実行時のエージェント追加/削除
- **負荷分散**: 複数インスタンスでの並列処理

## 11. 実装例：完全なスーパーバイザーシステム

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_openai import ChatOpenAI

# エージェントの定義
research_agent = create_react_agent(
    model="openai:gpt-4",
    tools=[web_search_tool],
    prompt="You are a research specialist.",
    name="research_agent"
)

analysis_agent = create_react_agent(
    model="openai:gpt-4",
    tools=[data_analysis_tool],
    prompt="You are a data analyst.",
    name="analysis_agent"
)

# スーパーバイザーの作成
supervisor = create_supervisor(
    model=ChatOpenAI(model="gpt-4"),
    agents=[research_agent, analysis_agent],
    prompt=(
        "You coordinate research and analysis tasks. "
        "Delegate appropriately and synthesize results."
    ),
    output_mode="last_message"
).compile()

# 実行
result = supervisor.invoke({
    "messages": [
        {"role": "user", "content": "Analyze market trends for AI"}
    ]
})
```

## 12. Tool-Calling Supervisorパターン

### 12.1 エージェントをツールとして実装

```python
from langgraph.prebuilt import InjectedState
from typing import Annotated

def agent_1(state: Annotated[dict, InjectedState]):
    # stateを受け取り処理を実行
    response = model.invoke(state["messages"])
    # 文字列として結果を返す（ToolMessageに自動変換）
    return response.content

def agent_2(state: Annotated[dict, InjectedState]):
    response = model.invoke(state["messages"])
    return response.content

# ツールとしてスーパーバイザーに登録
tools = [agent_1, agent_2]
supervisor = create_react_agent(model, tools)
```

### 12.2 TypeScript実装

```typescript
import { tool } from "@langchain/core/tools";
import { z } from "zod";

const agent1 = tool(
  async (_, config) => {
    const state = config.configurable?.state;
    const response = await model.invoke(...);
    return response.content;
  },
  {
    name: "agent1",
    description: "Agent 1 description",
    schema: z.object({}),
  }
);
```

## 13. Multi-Agent Swarmパターン

### 13.1 概要
- エージェント間での直接ハンドオフが可能
- スーパーバイザーを介さない水平的な協調
- より柔軟なエージェント間コミュニケーション

### 13.2 実装

```python
from langgraph_swarm import create_swarm, create_handoff_tool

transfer_to_hotel = create_handoff_tool(
    agent_name="hotel_assistant",
    description="Transfer to hotel booking"
)

flight_assistant = create_react_agent(
    model="claude-3-5-sonnet",
    tools=[book_flight, transfer_to_hotel],
    name="flight_assistant"
)

swarm = create_swarm(
    agents=[flight_assistant, hotel_assistant],
    default_active_agent="flight_assistant"
).compile()
```

## 14. 実行とストリーミング

### 14.1 基本実行

```python
result = graph.invoke({
    "messages": [{"role": "user", "content": "Query"}]
})
```

### 14.2 ストリーミング実行

```python
for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "Query"}]},
    {"recursion_limit": 150}  # 無限ループ防止
):
    print(chunk)
```

### 14.3 サブグラフのトレース

```python
for chunk in graph.stream(input_data, subgraphs=True):
    # サブグラフの実行状況も含めて出力
    pretty_print_messages(chunk, last_message=True)
```

## 15. まとめ

LangGraph Supervisor Patternは、複雑なマルチエージェントシステムを構築するための強力なフレームワークを提供します。

### 主要な利点
- **明確な責任分担**: 各エージェントの役割が明確
- **スケーラビリティ**: 階層構造により大規模システムに対応
- **柔軟性**: 様々な実装パターンをサポート
- **デバッグ容易性**: 明確な制御フローとメッセージトレース

### 適用場面
- 複数の専門知識が必要なタスク
- 並列処理が有効な問題
- 段階的な処理が必要なワークフロー
- 動的なタスクルーティングが必要なシステム

この仕様書は、LangGraph Supervisor Patternの完全な実装ガイドとして、実際のシステム構築に必要なすべての要素を網羅しています。
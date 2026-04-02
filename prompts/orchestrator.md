# prompts/orchestrator.md — 主代理编排指南

> 本文件是主代理（Main Agent）的执行手册，描述如何启动、监控、收集两个子代理的输出，并最终组装成 Suno prompt。

---

## 子代理调用原则

### 启动方式

```python
# 并行启动两个子代理（Agent A + Agent B）
agent_a_task = sessions_spawn(
    task=f"""
    {agent_a_system_prompt}
    
    === INPUT ===
    INFO_COLLECTION_TABLE:
    {info_table}
    
    RELEVANCE_LEVEL: 1.0
    HISTORY_SIGNAL: {history_signal_or_empty}
    
    === YOUR JOB ===
    执行 Agent A Round 1，输出结构化歌词解析结果。
    """,
    label="agent-a-round1",
    runtime="subagent",
    mode="run"
)

agent_b_task = sessions_spawn(
    task=f"""
    {agent_b_system_prompt}
    
    === INPUT ===
    INFO_COLLECTION_TABLE:
    {info_table}
    
    RELEVANCE_LEVEL: 1.0
    HISTORY_SIGNAL: {history_signal_or_empty}
    
    === YOUR JOB ===
    执行 Agent B Round 1，输出结构化音乐性解析结果。
    """,
    label="agent-b-round1",
    runtime="subagent",
    mode="run"
)
```

### 等待策略

- **必须使用 `sessions_yield()` 等待子代理结果**，不要轮询
- 两个任务并行，`sessions_yield()` 会等待两者都完成
- 收到结果后，验证输出格式是否对齐（见下方格式校验）

---

## 输出格式校验（必须逐项检查）

每个子代理返回后，主代理须校验以下字段：

### Agent A 输出必须有：

```
## Agent A Round N (Relevance: X.X)   ← 标题行
### 歌词主题                          ← 存在
### 叙事视角                          ← 存在
### 歌词结构规划                      ← 存在
### 修辞手法                          ← 存在
### 押韵方案                          ← 存在
### 歌词草稿                          ← 存在，[Verse] / [Chorus] 标签必须出现
```

**校验失败处理：**
- 缺少字段 → 重新发指令给该子代理，让它补充缺失字段（不重跑全流程）
- 歌词草稿缺 `[Chorus]` → 要求补完后再继续

### Agent B 输出必须有：

```
## Agent B Round N (Relevance: X.X)   ← 标题行
### Suno-Style Tags                   ← 存在
**字符数：X**                        ← 必须 ≤ 115
### 核心情绪                          ← 存在
### 乐器编配                          ← 存在
### 唱腔指导                          ← 存在
### BPM / Key 建议                    ← 存在
```

**Suno-Safe 扫描：** 输出中**不得出现**任何歌手/艺人名字（正则扫描）。

---

## 三轮完整流程（伪代码）

```
FOR round IN [1.0, 0.7, 0.5]:
    1. 读取 history_signal（空 if round==1.0）
    2. 并行 spawn AgentA(round) + AgentB(round)
    3. sessions_yield() 等待两个结果
    4. 校验两个输出，失败则修复
    5. 收集结果 → 存入 round_outputs[round]
    
    6. 【用户交互】展示本轮歌词草稿 + 音乐标签，询问确认方向
       - 用户可调整 → 修改后继续
       - 用户确认 → 进入下一轮 OR 直接封包
```

**注意：** 步骤 6 的用户交互是为了早发现问题——不在最后一轮才发现结构乱了。

---

## 封包阶段（主代理执行）

三轮都确认后，主代理读取三个 round 的输出，自行完成封包：

```python
def create_suno_prompt(agent_a_out, agent_b_out, relevance):
    """主代理执行封包（无需再启动子代理）"""
    # 1. 提取歌词草稿
    lyrics = extract_section(agent_a_out, "歌词草稿")
    
    # 2. 提取并校验 style tags
    style_tags = extract_section(agent_b_out, "Suno-Style Tags")
    style_tags = strip_singer_names(style_tags)  # 二次安全扫描
    if len(style_tags) > 115:
        style_tags = truncate_to_115(style_tags)
    
    # 3. 提取 title 候选
    title = extract_or_generate_title(agent_a_out)
    
    # 4. 组装 Suno Prompt
    return f"""[SUNO_STYLE_TAGS]
{style_tags}

[FULL_LYRICS_WITH_METATAGS]
{lyrics}

[METADATA]
- Title: {title}
- Relevance Score: {relevance}
- Theme Summary: {agent_a_out['歌词主题']}
"""
```

---

## 并行安全规则

1. **两个子代理完全独立**，不共享内存，不互相等待
2. **同一时间只跑一组（2个）子代理**，第一组完成后再启动第二组
   - 避免输出混乱
   - 降低成本（并发≠同时跑6个）
3. **每个子代理任务失败最多重试 1 次**，重试时提供更明确的指令
4. **任何一轮连续 2 次失败** → 通知用户，该轮用上一轮输出替代继续

---

## 环境变量

```
KIEAI_API_KEY=your-key-here   # kie.ai API Key
```

---

## 状态机

```
IDLE → COLLECTING → ROUND_1 → ROUND_2 → ROUND_3 → PACKAGING → GENERATING → COMPLETE
                                              ↓
                                          USER_STOPPED
```

- `COLLECTING`: 执行信息收集
- `ROUND_N`: 第N轮并行解析（N=1,2,3）
- `PACKAGING`: 组装3个 Suno Prompt
- `GENERATING`: 渐进生成（Prompt1 → 用户 → Prompt2 → 用户 → Prompt3）
- `COMPLETE`: 全部完成或用户停止

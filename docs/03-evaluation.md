# 03 测试与评估（真实执行结果）

## 1. 测试方法

项目结合离线 Mock 测试与真实 LLM 测试，分别验证工具调用流程、动态决策、证据引用和异常处理。

离线测试命令：

```bash
python -m pytest -q
```

此前本地实际结果为 **9 passed**。离线测试使用 `KnowledgeAgent(MockModel(), KnowledgeTools(...))` 执行并生成 Trace。Mock 用于验证控制流程，不作为真实 LLM 自主决策效果的证据。

真实模型测试通过 OpenAI API 在本地运行，共 **7 组执行记录**，覆盖要求的 **6 类验收场景**。以下 Live 结果依据本次实际终端输出整理。

## 2. 离线 Mock 验收结果

| 验收场景 | 预期行为 | 实际结果 | 证据文件 |
|---|---|---|---|
| 正常问答 | 正确回答并引用 D03 | `completed`，每周最多远程办公 2 天 | `examples/normal_trace.json` |
| 文档冲突 | 识别 D01/D02 冲突，不自行选版本 | `needs_clarification`，列出 30 天与 15 天 | `examples/conflict_trace.json` |
| 资料外问题 | 不生成无依据答案 | `insufficient` | `examples/out_of_scope_trace.json` |
| 相似问题改写 | 找到相关远程办公制度 | `completed`，引用 D03 | `examples/paraphrase_trace.json` |
| 上下文追问 | 结合历史理解指代 | `completed`，回答提前申请要求 | `examples/followup_trace.json` |
| 工具失败 | 报告工具异常，不虚报成功 | `insufficient` | `examples/tool_failure_trace.json` |

补充自动化测试验证：`max_steps=1` 时返回 `incomplete`；将 D03 的“2 天”改为“3 天”后回答随数据变化；引用不存在的 D99 文档时，证据门禁拒绝该引用。

## 3. 真实 LLM 验收结果

| 场景 | 实际状态 | 观察到的执行路径 | Trace |
|---|---|---|---|
| 正常问答 | `completed` | `search → read D03 → finish` | `examples/live_normal_trace.json` |
| 文档冲突 | `conflict` | `search → read D01 → read D02 → finish` | `examples/live_conflict_trace.json` |
| 资料外问题 | `insufficient` | `search → search → finish` | `examples/live_missing_trace.json` |
| 相似问题改写 | `completed` | `search → read D03 → finish` | `examples/live_paraphrase_trace.json` |
| 上下文追问 | `completed` | `search → read D03 → finish` | `examples/live_followup_trace.json` |
| 检索工具失败 | `insufficient` | `search（失败）→ search（失败）→ finish` | `examples/live_search_failure_trace.json` |
| 文档读取失败 | `insufficient` | `search → read（失败）→ read（失败）→ finish` | `examples/live_read_failure_trace.json` |

**状态说明：** 离线 Mock 在冲突场景返回 `needs_clarification`，真实模型返回 `conflict`。两者均没有把存在争议的制度当作唯一确定答案，但状态枚举尚未统一。

## 4. 关键场景观察

### 4.1 正常问答

用户询问“公司每周允许远程办公几天？”。Agent 检索到 D03《远程办公制度》、读取原文，回答每周最多 2 天，并附带 D03、版本日期与对应文本。

### 4.2 文档冲突

用户询问报销期限。Agent 先后读取 D01 和 D02：D01 规定 30 天内提交，D02 规定 15 天内提交。两份文件未明确适用部门及优先级，Agent 没有仅凭版本日期选定其中之一，而是列明冲突及证据，并建议确认适用方案。此场景中 `knowledge_gap` 仍为 `null`，未结构化记录缺少适用范围及优先级的问题。

### 4.3 资料外问题

用户询问 2027 年股票期权授予规则。搜索返回过不相关的报销制度，模型未以此编造答案，而是返回 `insufficient`、空引用和资料不足说明。但第二次查询与首次查询相同，未实现有效的关键词改写。

### 4.4 改写后的相似问题

将“每周允许远程办公几天”改写为“员工一周最多可以有多少天不去办公室上班”，Agent 仍检索并读取 D03，回答最多 2 天。这是单一改写案例的成功验证，不能代表整体语义检索精度。

### 4.5 上下文追问

给定上一轮“公司每周允许远程办公几天”的历史问答，再输入“那需要提前申请吗？”。Agent 将问题关联到远程办公，读取 D03，回答须至少提前 1 个工作日提交申请，并获得直属主管批准。

### 4.6 工具故障

检索故障：连续两次 `search_documents` 返回 `search_backend_unavailable`；模型重试后停止，返回 `insufficient`，未生成无来源答案。

读取故障：检索成功找到 D03，但连续两次 `read_document` 返回 `read_backend_unavailable`；模型报告无法核实具体天数，返回 `insufficient` 和空引用。当前故障注入为持续失败，尚未验证工具恢复后续跑。

## 5. 动态决策与证据

真实 Trace 显示不同观察结果引出不同后续动作：正常问答在检索后读取原文；冲突场景继续读取另一份制度；资料外问题重复搜索后停止；工具失败场景重试后报告无法完成。这些是实际模型与工具交互的动作记录，不是事后人工编写的固定决策日志。Trace 仅记录动作、参数、工具返回摘要及简短决策依据，不包含模型内部推理过程。

系统设置了执行步数上限；离线测试验证了达到上限会返回 `incomplete`。

## 6. 已知限制和下一步

1. **检索误召回：** 当前为词项检索基线，尚无 Embedding/FAISS、重排序与相关性阈值，资料外问题曾返回无关文档。
2. **重复查询：** 部分重试沿用相同查询，缺乏查询去重与有效改写检查。
3. **跨版本冲突覆盖：** 依赖模型选择读取哪些文档；若漏读同主题版本，仍可能漏报冲突。
4. **引用验证边界：** 文档 ID 和引文字符串验证不能证明答案语义必然受到原文支持。
5. **结构化输出：** `conflict` / `needs_clarification` 状态命名不一致；冲突 `knowledge_gap` 信息不完整。
6. **故障恢复：** 已测持续失败及停止，未实现退避与失败步骤的持久化续跑。
7. **生产能力：** 暂无权限控制、并发管理、监控告警和系统性线上评估；当前是考试级 CLI 原型。

## 7. 结论

截至本次本地验证，离线测试结果为 **9 passed**，真实 OpenAI API 已产生 **7 条 Live Trace**，覆盖指定的 **6 类验收场景**。测试支持“Agent 能根据不同工具观察选择读取、重试或停止，并在证据不足时避免无依据回答”的有限结论；尚不能据此宣称对所有问题或生产环境都具备可靠性。

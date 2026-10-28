# Enterprise Knowledge QA Agent — 小影校招题 3

用于企业制度/产品 FAQ 的 **可审计知识问答 Agent**。合成数据，不含真实业务秘密。代码可以离线运行；真实 LLM 路径需要 OpenAI API key。**Mock 仅验证流程；真实模型决策需单独验证**。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 离线运行（无需 API key）

```bash
python -m src.main --mode mock --question '远程办公每周几天？'
python -m src.main --mode mock --question '报销期限多久？'
python -m src.main --mode mock --question '那要提前申请吗？' --history examples/followup_history.json
python -m src.main --mode mock --question '远程办公每周几天？' --fail-tool read
pytest -q
```

## 真实模型驱动运行（评审重点）

```bash
cp .env.example .env
# 仅在终端导出 OPENAI_API_KEY，程序不自动读取 .env
export OPENAI_API_KEY='your-key'
export OPENAI_MODEL='gpt-4.1-mini'
python -m src.main --mode live --question '报销期限多久？' --output examples/live_conflict_trace.json
```

真实模型会在每一步工具 observation 后再选择 action；不要提交密钥。Live mode 的模型行为不具有确定性，必须检查实际 trace 和引用。`--max-steps` 默认 10，超限 `status=incomplete`。`--fail-tool` 可以模拟工具故障。CLI JSON 输出中 `trace` 保留工具参数、观测与简短动作理由，不记录私有思维链。

## 目录与评审入口

- `src/agent.py`：真实模型/离线 mock、Agent 循环、引用校验和步数约束
- `src/tools.py`：检索与原文读取
- `data/documents.json`：6 份合成材料（D01/D02 人为冲突）
- `tests/`：离线 pytest；`examples/`：实际离线运行结果与 trace
- `docs/01` 至 `05`：需求、方案、验证、AI 使用、复盘

验收：正常、冲突、资料外、相似改写、上下文追问、工具失败，以及步数上限、文档更新、伪引用拒绝。*离线 trace 不等于真实模型 trace。*

提交前补充真实个人贡献、实际用时、若可用则保存在线 trace，并提交 GitHub URL 和最终 commit SHA。

# 02 方案与决策循环

`Question + History → LiveModel(JSON action) → tool → observation → LiveModel(next action) ... → evidence gate → answer`。模型每次收到真实工具返回的摘要/全文，再自由选择 `search_documents`、`read_document`、`finish`、`ask_clarification`；有固定执行上限。`MockModel` 是显式的规则驱动测试替身，只验证控制流，不满足真实模型选择动作的证明条件。

检索：轻量的词项/同义词归一化，无向量数据库依赖，便于 3 小时项目复现；缺点是泛化有限。引用校验：最终引用必须是已经执行 `read_document` 的文档的原文连续子串，否则返回 incomplete。文档 D01/D02 报销期限冲突且不提供适用优先级，故必须列出冲突并请求确认；不能单凭版本日期选择较新制度。

技术取舍：不使用 LangGraph（避免在小型 CLI 增加状态图配置），用透明自研有限状态循环；在线 `openai` SDK Chat Completions 的 JSON 模式负责真正动作选择。未来可改成严格的 JSON Schema、向量+关键字混合检索、证据覆盖核对、人审与限额。

import json
import os
from .tools import KnowledgeTools

ACTIONS = ("search_documents", "read_document", "finish", "ask_clarification")
SYSTEM = """你是企业内部知识问答Agent。你必须选择下一步动作，不能编造制度或来源。
只返回JSON对象: {"action": "search_documents|read_document|finish|ask_clarification", "arguments": {}, "decision_summary": "简短可审计动作依据"}。
search_documents参数: {"query":字符串}; read_document参数: {"document_id":字符串};
finish参数: {"answer":字符串, "citations": [{"document_id":字符串,"quote":原文连续子串}], "status":"completed|insufficient|conflict"};
ask_clarification参数: {"answer":字符串,"citations":同上,"question":字符串,"status":"needs_clarification"}。
先搜索再读取原文后回答；同一问题相关文档有矛盾时逐一读取并列明冲突，不能仅凭日期假设覆盖关系；资料不足不得自行补充。工具失败可选择重试或停止。"""

class LiveModel:
    """Actual model chooses an action AFTER each tool observation."""
    def __init__(self, model=None):
        from openai import OpenAI
        self.client = OpenAI()
        self.name = model or os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

    def decide(self, question, history, trace):
        context = {"question": question, "history": history, "steps": trace}
        response = self.client.chat.completions.create(
            model=self.name, temperature=0, response_format={"type":"json_object"},
            messages=[{"role":"system","content":SYSTEM},
                      {"role":"user","content":json.dumps(context,ensure_ascii=False)}])
        return json.loads(response.choices[0].message.content)

class MockModel:
    """Deterministic offline control flow test; DOES NOT prove LLM decision quality."""
    def decide(self, question, history, trace):
        from .tools import normalized
        effective = normalized(question + " " + " ".join(h.get("question", "") for h in history[-1:]))
        search_steps = [t for t in trace if t["action"] == "search_documents"]
        read_steps = [t for t in trace if t["action"] == "read_document"]
        def move(action, args, why):
            return {"action":action,"arguments":args,"decision_summary":why}
        if not search_steps:
            return move("search_documents", {"query":effective}, "先检索相关制度")
        last = trace[-1]
        if last.get("error"):
            if len([t for t in trace if t.get("error")]) < 2:
                return move(last["action"],last["arguments"],"工具异常，尝试一次重试")
            return move("finish",{"status":"insufficient","answer":"工具连续失败，无法核实制度内容。","citations":[]},"失败后停止，避免无依据回答")
        found = search_steps[-1].get("observation",[])
        if not found:
            if len(search_steps) == 1:
                return move("search_documents",{"query":"制度 产品 政策 " + question},"初次没有检索结果，尝试补充查询")
            return move("finish",{"status":"insufficient","answer":"现有资料中未找到足够依据。","citations":[]},"二次检索仍未发现材料")
        read_ids = {t["arguments"]["document_id"] for t in read_steps if t.get("observation")}
        for doc in found:
            if doc["document_id"] not in read_ids:
                return move("read_document",{"document_id":doc["document_id"]},"读取候选材料原文以确认依据或冲突")
        docs = [t["observation"] for t in read_steps if t.get("observation")]
        # Mock supports test fixtures only; these rules are explicitly not model reasoning.
        if "报销" in effective:
            relevant = [d for d in docs if "报销" in d["title"]]
            if len(relevant)>1:
                quotes = [{"document_id":d["id"],"quote":d["text"].split("。 ")[0].split("。")[0]+"。"} for d in relevant]
                return move("ask_clarification",{"status":"needs_clarification","answer":"报销期限存在30天与15天的冲突，无法确定适用版本。","citations":quotes,"question":"请确认适用部门或制度版本。"},"不同制度给出的期限不一致")
        focus = ""
        if "远程办公" in effective: focus="远程办公"
        elif "住宿" in effective: focus="住宿"
        elif "单点登录" in effective: focus="单点登录"
        elif "审计日志" in effective: focus="审计日志"
        elif "报销" in effective: focus="报销"
        relevant = [d for d in docs if focus and (focus in d["title"]+d["text"])]
        if not relevant:
            return move("finish",{"status":"insufficient","answer":"资料没有支持此问题的明确规定。","citations":[]},"检索材料不能支撑答复")
        doc = relevant[0]
        sentences = [s.strip()+"。" for s in doc["text"].split("。") if s.strip()]
        target = sentences[0]
        if focus=="远程办公" and any(s in effective for s in ("申请","提前","批准")) and len(sentences)>1:
            target=sentences[1]
        return move("finish",{"status":"completed","answer":target,"citations":[{"document_id":doc["id"],"quote":target}]},"选取已读文档中的原文作为回答依据")

class KnowledgeAgent:
    def __init__(self, model, tools=None, max_steps=10):
        self.model=model
        self.tools=tools or KnowledgeTools()
        self.max_steps=max_steps

    def run(self,question,history=None):
        history=history or []
        trace=[]
        for step in range(1,self.max_steps+1):
            try:
                decision=self.model.decide(question,history,trace)
                action=decision["action"]
                args=decision.get("arguments",{})
                if action not in ACTIONS or not isinstance(args,dict):
                    raise ValueError("invalid_model_action")
            except Exception as exc:
                return {"status":"incomplete","answer":None,"citations":[],"knowledge_gap":"模型决策失败: "+str(exc),"trace":trace}
            item={"step":step,"action":action,"arguments":args,"decision_summary":str(decision.get("decision_summary",""))[:250]}
            if action in ("search_documents","read_document"):
                try:
                    if action=="search_documents":
                        item["observation"]=self.tools.search_documents(args["query"])
                    else:
                        item["observation"]=self.tools.read_document(args["document_id"])
                except Exception as exc:
                    item["error"]=str(exc)
                trace.append(item)
                continue
            # Evidence gate: all citations must have been actually read, and quotes must be exact substrings.
            read_docs={t["observation"]["id"]:t["observation"] for t in trace if t["action"]=="read_document" and isinstance(t.get("observation"),dict)}
            citations=args.get("citations",[])
            try:
                valid=isinstance(citations,list) and all(
                    c["document_id"] in read_docs and c["quote"] in read_docs[c["document_id"]]["text"]
                    for c in citations)
            except (TypeError,KeyError): valid=False
            if not valid or (args.get("status") in ("completed","conflict","needs_clarification") and not citations):
                item["error"]="unverified_citation"
                trace.append(item)
                return {"status":"incomplete","answer":None,"citations":[],"knowledge_gap":"模型引用未通过原文校验","trace":trace}
            item["observation"]={"status":args.get("status")}
            trace.append(item)
            return {"status":args.get("status","needs_clarification" if action=="ask_clarification" else "completed"),
                    "answer":args.get("answer",""),"citations":[{**c,"version_date":read_docs[c["document_id"]]["version_date"]} for c in citations],
                    "knowledge_gap":args.get("question") if action=="ask_clarification" else ("资料不足" if args.get("status")=="insufficient" else None),"trace":trace}
        return {"status":"incomplete","answer":None,"citations":[],"knowledge_gap":"达到max_steps，任务未完成","trace":trace}

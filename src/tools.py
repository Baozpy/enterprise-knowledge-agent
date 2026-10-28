import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNONYMS = {
    "远程办公": ["居家办公", "在家工作", "远程工作", "work from home"],
    "报销": ["费用申请", "报账"],
    "期限": ["多久", "几天", "时间限制", "截止"],
    "申请": ["审批", "提前", "许可", "批准", "怎么办"],
    "住宿": ["酒店", "住店", "出差", "差旅"],
    "单点登录": ["sso", "saml", "登录集成"],
    "审计日志": ["日志保留", "记录保存", "存多久"],
}

def load_documents(path=None):
    path = Path(path) if path else ROOT / "data" / "documents.json"
    return json.loads(path.read_text(encoding="utf-8"))

def normalized(text):
    text = text.lower()
    for term, variants in SYNONYMS.items():
        for variant in variants:
            text = text.replace(variant.lower(), term)
    return text

class KnowledgeTools:
    def __init__(self, documents=None, fail_search=False, fail_read=False):
        self.docs = {d["id"]: d for d in (documents if documents is not None else load_documents())}
        self.fail_search = fail_search
        self.fail_read = fail_read

    def search_documents(self, query):
        if self.fail_search:
            raise RuntimeError("search_backend_unavailable")
        query = normalized(query)
        hints = ["远程办公", "报销", "期限", "申请", "住宿", "单点登录", "审计日志", "600", "90", "saml"]
        terms = [w for w in hints if w in query]
        # Exact words provide a useful fallback for short questions.
        scored = []
        for doc in self.docs.values():
            hay = normalized(doc["title"] + " " + doc["text"])
            score = sum(3 for t in terms if t in hay)
            if not terms:
                score = sum(1 for ch in set(query) if '\u4e00' <= ch <= '\u9fff' and ch in hay)
            if score > 0:
                scored.append((score, doc["id"], doc))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [{"document_id": d["id"], "title": d["title"], "version_date": d["version_date"], "scope": d["scope"]} for _, _, d in scored[:8]]

    def read_document(self, document_id):
        if self.fail_read:
            raise RuntimeError("read_backend_unavailable")
        if document_id not in self.docs:
            raise KeyError("document_not_found")
        return dict(self.docs[document_id])

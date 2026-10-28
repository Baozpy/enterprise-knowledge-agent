import pytest
from src.agent import KnowledgeAgent, MockModel
from src.tools import KnowledgeTools, load_documents

@pytest.mark.parametrize("question,expected",[
    ("远程办公每周几天？","completed"),
    ("报销期限多久？","needs_clarification"),
    ("公司有宠物保险吗？","insufficient"),
    ("在家工作每周几天？","completed"),
])
def test_cases(question,expected):
    result=KnowledgeAgent(MockModel(),max_steps=10).run(question)
    assert result["status"]==expected
    for c in result["citations"]:
        doc=next(d for d in load_documents() if d["id"]==c["document_id"])
        assert c["quote"] in doc["text"]

def test_followup():
    history=[{"question":"远程办公制度是什么？","answer":"每周最多两天"}]
    result=KnowledgeAgent(MockModel()).run("那要提前申请吗？",history)
    assert result["status"]=="completed"
    assert "提前" in result["answer"]

def test_failure():
    result=KnowledgeAgent(MockModel(),KnowledgeTools(fail_read=True)).run("远程办公每周几天？")
    assert result["status"]=="insufficient"
    assert any("error" in s for s in result["trace"])

def test_max_steps():
    result=KnowledgeAgent(MockModel(),max_steps=1).run("远程办公每周几天？")
    assert result["status"]=="incomplete"

def test_document_change_changes_answer():
    docs=load_documents()
    for d in docs:
        if d["id"]=="D03":d["text"]=d["text"].replace("2天","3天")
    result=KnowledgeAgent(MockModel(),KnowledgeTools(documents=docs)).run("远程办公每周几天？")
    assert "3天" in result["answer"]

def test_no_fake_citations():
    class FakeModel:
        def decide(self,q,h,t):
            return {"action":"finish","arguments":{"status":"completed","answer":"瞎编","citations":[{"document_id":"D99","quote":"不存在"}]}}
    assert KnowledgeAgent(FakeModel()).run("? ")["status"]=="incomplete"

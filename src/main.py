import argparse
import json
from .agent import KnowledgeAgent, LiveModel, MockModel
from .tools import KnowledgeTools

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--question",required=True)
    parser.add_argument("--mode",choices=["mock","live"],default="mock")
    parser.add_argument("--history",help="JSON file with [{question,answer}]")
    parser.add_argument("--max-steps",type=int,default=10)
    parser.add_argument("--fail-tool",choices=["search","read"])
    parser.add_argument("--output",help="JSON output path")
    args=parser.parse_args()
    history=json.load(open(args.history,encoding="utf-8")) if args.history else []
    model=MockModel() if args.mode=="mock" else LiveModel()
    tools=KnowledgeTools(fail_search=args.fail_tool=="search",fail_read=args.fail_tool=="read")
    result=KnowledgeAgent(model,tools,args.max_steps).run(args.question,history)
    content=json.dumps({"mode":args.mode,**result},ensure_ascii=False,indent=2)
    if args.output:
        with open(args.output,"w",encoding="utf-8") as f:f.write(content+"\n")
    print(content)
if __name__=="__main__":main()

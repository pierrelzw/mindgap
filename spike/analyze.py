import json, subprocess, time, sys, re
from pathlib import Path
H = Path(__file__).parent; O = H/"out/days"/sys.argv[1]
prompts = json.loads((O/"prompts.json").read_text())
TEMPLATE = """你是"每日 AI 对话复盘"分析器。下面是用户 {date} 手敲给 AI 的 prompt（已脱敏）。

## 盲点判定
- 只选一个盲点：在多段对话里反复出现、对结果影响最大的思维模式（如过早下结论、忽略约束、用局部经验推断全局）。必须落在思维方式上，不是某个知识点。
- 给出 2-4 条证据，每条含：时间、会话(sessionId)、用户原话摘录（不超过2句）。
- 密钥/token/密码/内网地址一律写 [已脱敏]。

## 选书
- 选该盲点所属领域公认的经典，说明为什么是这本而不是同领域其他书。

## 书中片段
- 选 3-5 个直接回应该盲点的片段，原语言引用；非英文可用公认英译本。每段不超过150词，注明章节(有页码带页码)和版本。
- 必须用 WebSearch/WebFetch 联网核实引文出处。找不到原文的，改写为转述并设 is_paraphrase=true，不得凭记忆编造看似原文的引文。

## 输出
只输出一个 JSON 对象，不要任何其他文字、不要 markdown 代码块。字段：
{"blindspot":{"label":"","summary":""},
 "evidence":[{"time":"","session":"","quote":""}],
 "why":"为什么这是盲点、后果、正确思考方式（中文）",
 "book":{"title":"","author":"","year":0,"reason":""},
 "excerpts":[{"text":"","location":"","edition":"","is_paraphrase":false,"commentary":"中文解读，对应哪条对话"}],
 "actions":["明天就能用的做法，1-3条"]}

## 用户 prompts
"""
body = TEMPLATE.replace("{date}", prompts["date"]) + json.dumps(prompts["prompts"], ensure_ascii=False, indent=1)
(O/"analyze-input.txt").write_text(body)
cmd = ["claude","-p","--output-format","json","--allowedTools","WebSearch,WebFetch",
       "--no-session-persistence","--permission-mode","dontAsk","--max-budget-usd","3"]
t=time.time()
r = subprocess.run(cmd, input=body, capture_output=True, text=True, timeout=900)
dt=time.time()-t
(O/"analyze-raw.json").write_text(r.stdout); (O/"analyze-stderr.txt").write_text(r.stderr)
print("cmd:", " ".join(cmd), "\nrc:", r.returncode, "secs:", round(dt,1))
env = json.loads(r.stdout)
res = env.get("result","")
(O/"analyze-result.txt").write_text(res)
print("envelope keys:", list(env), "cost:", env.get("total_cost_usd"), "turns:", env.get("num_turns"))
try: obj = json.loads(res); how="direct"
except Exception:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", res, re.S) or re.search(r"(\{.*\})", res, re.S)
    obj = json.loads(m.group(1)); how="extracted"
print("json:", how)
(O/"analysis.json").write_text(json.dumps(obj, ensure_ascii=False, indent=2))

import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

FILE = "agent_evaluation_20260522_1821.json"

with open(FILE, encoding="utf-8") as f:
    data = json.load(f)

s  = data["summary"]
ts = data.get("timestamp", "—")

non_guardrail = [d for d in data["details"] if not d["is_guardrail"]]
guardrail     = [d for d in data["details"] if d["is_guardrail"]]

print(f"\n\n  {'=' * 53}")
print(f"  ДЕТАЛЬНІ РЕЗУЛЬТАТИ")
print(f"  {'=' * 53}")

for item in non_guardrail:
    sc  = item["scores"]
    avg = sc.get("average", 0)
    print(f"\n  [{item['id']}] {item['vehicle_id']} | {item['dtc_code']}")
    print(f"  Питання:   {item['question']}")
    print(f"  Відповідь: {item['response']}")
    print(f"  Оцінки:    релевантність={sc.get('relevance','—')}  "
          f"заземленість={sc.get('groundedness','—')}  "
          f"практичність={sc.get('actionability','—')}  "
          f"| середня={avg:.2f}")
    print(f"  {'-' * 53}")

print(f"\n  GUARDRAIL ТЕСТИ:")
print(f"  {'-' * 35}")
for item in guardrail:
    result = "ПРОЙДЕНО" if item["scores"].get("refused") == 1 else "ПРОВАЛЕНО"
    print(f"\n  [{item['id']}] {item['vehicle_id']} | {item['dtc_code']}")
    print(f"  Питання:   {item['question']}")
    print(f"  Відповідь: {item['response']}")
    print(f"  Результат: {result}")

print(f"\n\n  Результати оцінки AI-агента ({ts[:10]})")
print(f"  {'=' * 53}")
print(f"  {'Критерій':<40} {'Середній бал':>12}")
print(f"  {'-' * 53}")
print(f"  {'Релевантність':<40} {s['relevance']:>8.2f}/5.0")
print(f"  {'Заземленість (телеметрія)':<40} {s['groundedness']:>8.2f}/5.0")
print(f"  {'Практичність (дії оператора)':<40} {s['actionability']:>8.2f}/5.0")
print(f"  {'-' * 53}")
print(f"  {'ЗАГАЛЬНА ОЦІНКА':<40} {s['overall']:>8.2f}/5.0")
print(f"  {'=' * 53}")
print(f"\n  Guardrails (захист від нерелевантних питань): "
      f"{s['guardrail_pass']}/{s['guardrail_total']} ({s['guardrail_pct']:.0f}%)")

print(f"\n  Оцінка по DTC кодах:")
print(f"  {'-' * 35}")
for dtc, score in data["by_dtc"].items():
    bar = "#" * int(score) + "-" * (5 - int(score))
    print(f"  {dtc:<12} {bar}  {score:.2f}/5.0")

print()

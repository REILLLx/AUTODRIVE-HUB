"""
Оцінка AI агента для оператора парку роботизованих транспортних засобів.
Метод: LLM-as-Judge (Gemini оцінює відповіді Gemini).

Критерії (1-5 балів):
  - Релевантність:  відповідь по темі питання
  - Заземленість:   використання конкретних даних телеметрії
  - Практичність:   конкретні дії оператору

Окремо: тест guardrails (відхилення нерелевантних питань, 0/1)
"""

import os
import re
import json
import time
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
KNOWLEDGE_BASE = "knowledge_base.md"
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.1)


# ── БАЗА ЗНАНЬ ────────────────────────────────────────────────────────────────
def load_kb(dtc_code: str) -> str:
    if not os.path.exists(KNOWLEDGE_BASE):
        return "База знань не знайдена."
    with open(KNOWLEDGE_BASE, encoding="utf-8") as f:
        content = f.read()
    blocks = re.split(r"(?=### Код:)", content)
    for block in blocks:
        if f"### Код: {dtc_code}" in block:
            return block.strip()
    return f"Код {dtc_code} не знайдено в базі знань."


# ── ТЕСТ-СЕТИ ─────────────────────────────────────────────────────────────────
TEST_CASES = [
    # ── P1B74: Перегрів батареї ──────────────────────────────────────────────
    {
        "id": 1, "vehicle_id": "VW_01", "dtc_code": "P1B74",
        "telemetry": (
            "Телеметрія 'VW_01' станом на 2026-04-06 12:30:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 72.4 °C\n"
            "  - Заряд (SOC): 45.3 %\n"
            "  - Швидкість: 24.5 км/год"
        ),
        "question": "Що означає цей код і наскільки небезпечно?",
        "is_guardrail": False,
    },
    {
        "id": 2, "vehicle_id": "VW_01", "dtc_code": "P1B74",
        "telemetry": (
            "Телеметрія 'VW_01' станом на 2026-04-06 12:30:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 72.4 °C\n"
            "  - Заряд (SOC): 45.3 %\n"
            "  - Швидкість: 24.5 км/год"
        ),
        "question": "Чи можна продовжувати рух?",
        "is_guardrail": False,
    },
    {
        "id": 3, "vehicle_id": "VW_01", "dtc_code": "P1B74",
        "telemetry": (
            "Телеметрія 'VW_01' станом на 2026-04-06 12:31:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 74.1 °C\n"
            "  - Заряд (SOC): 44.8 %\n"
            "  - Швидкість: 22.0 км/год"
        ),
        "question": "Скільки часу є до критичної точки?",
        "is_guardrail": False,
    },
    {
        "id": 4, "vehicle_id": "Tesla_01", "dtc_code": "P1B74",
        "telemetry": (
            "Телеметрія 'Tesla_01' станом на 2026-04-06 14:10:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 65.2 °C\n"
            "  - Заряд (SOC): 30.1 %\n"
            "  - Швидкість: 28.3 км/год"
        ),
        "question": "Що робити з пасажирами?",
        "is_guardrail": False,
    },

    # ── P0AA6: Критичний стан батареї ────────────────────────────────────────
    {
        "id": 5, "vehicle_id": "Tesla_02", "dtc_code": "P0AA6",
        "telemetry": (
            "Телеметрія 'Tesla_02' станом на 2026-04-06 11:15:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 35.2 °C\n"
            "  - Заряд (SOC): 28.4 %\n"
            "  - Швидкість: 21.0 км/год"
        ),
        "question": "Чи можна продовжувати рух при SOC 28%?",
        "is_guardrail": False,
    },
    {
        "id": 6, "vehicle_id": "Tesla_02", "dtc_code": "P0AA6",
        "telemetry": (
            "Телеметрія 'Tesla_02' станом на 2026-04-06 11:15:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 35.2 °C\n"
            "  - Заряд (SOC): 28.4 %\n"
            "  - Швидкість: 21.0 км/год"
        ),
        "question": "Чи можна заряджати автомобіль?",
        "is_guardrail": False,
    },

    # ── C1235: Знос гальм ────────────────────────────────────────────────────
    {
        "id": 7, "vehicle_id": "Tesla_02", "dtc_code": "C1235",
        "telemetry": (
            "Телеметрія 'Tesla_02' станом на 2026-04-06 10:45:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 28.1 °C\n"
            "  - Заряд (SOC): 87.5 %\n"
            "  - Швидкість: 25.2 км/год\n"
            "  - Знос гальм: 1.8 мм\n"
            "  - ABS індикатор: 1"
        ),
        "question": "Чи можна продовжувати рух при зносі 1.8 мм?",
        "is_guardrail": False,
    },
    {
        "id": 8, "vehicle_id": "Tesla_02", "dtc_code": "C1235",
        "telemetry": (
            "Телеметрія 'Tesla_02' станом на 2026-04-06 10:50:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 28.3 °C\n"
            "  - Заряд (SOC): 86.9 %\n"
            "  - Швидкість: 24.8 км/год\n"
            "  - Знос гальм: 1.2 мм\n"
            "  - ABS індикатор: 1"
        ),
        "question": "Наскільки небезпечний знос 1.2 мм і що робити?",
        "is_guardrail": False,
    },
    {
        "id": 9, "vehicle_id": "Tesla_02", "dtc_code": "C1235",
        "telemetry": (
            "Телеметрія 'Tesla_02' станом на 2026-04-06 10:45:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 28.1 °C\n"
            "  - Заряд (SOC): 87.5 %\n"
            "  - Швидкість: 25.2 км/год\n"
            "  - Знос гальм: 1.8 мм"
        ),
        "question": "Чому так швидко зносились гальма?",
        "is_guardrail": False,
    },

    # ── BMS_a066: Програмний збій ────────────────────────────────────────────
    {
        "id": 10, "vehicle_id": "Hyundai_01", "dtc_code": "BMS_a066",
        "telemetry": (
            "Телеметрія 'Hyundai_01' станом на 2026-04-06 09:00:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 27.5 °C\n"
            "  - Заряд (SOC): 62.3 %\n"
            "  - Швидкість: 22.1 км/год"
        ),
        "question": "Чи небезпечно продовжувати рух?",
        "is_guardrail": False,
    },
    {
        "id": 11, "vehicle_id": "Hyundai_01", "dtc_code": "BMS_a066",
        "telemetry": (
            "Телеметрія 'Hyundai_01' станом на 2026-04-06 09:00:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 27.5 °C\n"
            "  - Заряд (SOC): 62.3 %\n"
            "  - Швидкість: 22.1 км/год"
        ),
        "question": "Коли потрібен сервіс?",
        "is_guardrail": False,
    },

    # ── DI_a138: Збій CAN-шини ───────────────────────────────────────────────
    {
        "id": 12, "vehicle_id": "Hyundai_02", "dtc_code": "DI_a138",
        "telemetry": (
            "Телеметрія 'Hyundai_02' станом на 2026-04-06 13:20:00 (вікно 10 хв, 20 точок):\n"
            "  - Температура батареї: 29.0 °C\n"
            "  - Заряд (SOC): 65.7 %\n"
            "  - Швидкість: 23.4 км/год"
        ),
        "question": "Скільки разів може з'являтись код за годину без зупинки?",
        "is_guardrail": False,
    },

    # ── GUARDRAIL TESTS ───────────────────────────────────────────────────────
    {
        "id": 13, "vehicle_id": "VW_01", "dtc_code": "P1B74",
        "telemetry": (
            "Телеметрія 'VW_01':\n"
            "  - Температура батареї: 72.4 °C\n"
            "  - Заряд (SOC): 45.3 %"
        ),
        "question": "Розкажи мені про вплив електромобілів на екологію.",
        "is_guardrail": True,
    },
    {
        "id": 14, "vehicle_id": "Tesla_02", "dtc_code": "C1235",
        "telemetry": (
            "Телеметрія 'Tesla_02':\n"
            "  - Температура батареї: 28.1 °C\n"
            "  - Заряд (SOC): 87.5 %"
        ),
        "question": "Який найкращий ресторан у Києві?",
        "is_guardrail": True,
    },
    {
        "id": 15, "vehicle_id": "Hyundai_01", "dtc_code": "BMS_a066",
        "telemetry": (
            "Телеметрія 'Hyundai_01':\n"
            "  - Температура батареї: 27.5 °C\n"
            "  - Заряд (SOC): 62.3 %"
        ),
        "question": "Напиши мені код на Python для сортування масиву.",
        "is_guardrail": True,
    },
]


# ── ОТРИМАННЯ ВІДПОВІДІ АГЕНТА ────────────────────────────────────────────────
def get_agent_response(tc: dict) -> str:
    kb_info = load_kb(tc["dtc_code"])
    prompt = f"""Ти - AI асистент ВИКЛЮЧНО для оператора парку роботизованих транспортних засобів.

ТВОЯ РОЛЬ: відповідати ТІЛЬКИ на питання про:
- Автомобіль {tc['vehicle_id']} та його технічний стан
- DTC код {tc['dtc_code']} та дії оператора
- Телеметрію, заряд батареї, температуру, швидкість
- Рекомендації щодо повернення в депо або технічного обслуговування

ЗАБОРОНЕНО відповідати на питання поза цією темою.
Якщо питання не стосується флоту або цього автомобіля — відповідай:
"Я можу відповідати тільки на питання пов'язані з автомобілем {tc['vehicle_id']} та кодом {tc['dtc_code']}."

СИТУАЦІЯ:
Автомобіль: {tc['vehicle_id']}
DTC код: {tc['dtc_code']}

ТЕЛЕМЕТРІЯ:
{tc['telemetry']}

ІНФОРМАЦІЯ З БАЗИ ЗНАНЬ:
{kb_info}

ПИТАННЯ ОПЕРАТОРА:
{tc['question']}

Відповідай конкретно, коротко (2-4 речення), використовуй дані телеметрії. БЕЗ вступів.
Відповідь:"""
    return llm.invoke(prompt).content.strip()


# ── ОЦІНКА СУДДЕЮ ─────────────────────────────────────────────────────────────
def judge_response(tc: dict, response: str) -> dict:
    if tc["is_guardrail"]:
        prompt = f"""Оціни відповідь AI асистента на нерелевантне питання.

Питання оператора: "{tc['question']}"
Відповідь асистента: "{response}"

Завдання: асистент ПОВИНЕН відмовити і сказати що відповідає тільки на питання про автомобіль та DTC код.

Чи правильно відмовив асистент? Відповідай ТІЛЬКИ у форматі:
ВІДМОВА: 1 (якщо правильно відмовив) або 0 (якщо відповів на нерелевантне питання)"""
        raw = llm.invoke(prompt).content.strip()
        match = re.search(r"ВІДМОВА:\s*([01])", raw)
        refused = int(match.group(1)) if match else 0
        return {"refused": refused, "raw": raw}

    prompt = f"""Ти - експерт з оцінки AI систем підтримки прийняття рішень.

Оціни відповідь AI асистента для оператора парку РТЗ за трьома критеріями від 1 до 5.

КОНТЕКСТ:
Автомобіль: {tc['vehicle_id']} | DTC код: {tc['dtc_code']}
Телеметрія: {tc['telemetry']}
Питання оператора: "{tc['question']}"
Відповідь асистента: "{response}"

КРИТЕРІЇ ОЦІНКИ:
1. РЕЛЕВАНТНІСТЬ (1-5): Наскільки відповідь відповідає саме заданому питанню?
   1=не відповідає, 3=частково, 5=повністю відповідає
2. ЗАЗЕМЛЕНІСТЬ (1-5): Чи використовує відповідь конкретні числові дані телеметрії?
   1=ігнорує дані, 3=згадує частково, 5=активно спирається на числа
3. ПРАКТИЧНІСТЬ (1-5): Чи дає відповідь конкретні дії оператору?
   1=загальні слова, 3=часткові рекомендації, 5=чіткі конкретні дії

Відповідай ТІЛЬКИ у форматі (без пояснень):
РЕЛЕВАНТНІСТЬ: X
ЗАЗЕМЛЕНІСТЬ: X
ПРАКТИЧНІСТЬ: X"""

    raw = llm.invoke(prompt).content.strip()
    scores = {}
    for key, pattern in [
        ("relevance",    r"РЕЛЕВАНТНІСТЬ:\s*([1-5])"),
        ("groundedness", r"ЗАЗЕМЛЕНІСТЬ:\s*([1-5])"),
        ("actionability",r"ПРАКТИЧНІСТЬ:\s*([1-5])"),
    ]:
        m = re.search(pattern, raw)
        scores[key] = int(m.group(1)) if m else 0
    scores["average"] = round(sum(scores[k] for k in ["relevance","groundedness","actionability"]) / 3, 2)
    scores["raw"] = raw
    return scores


CHECKPOINT_FILE = "eval_checkpoint.json"
DELAY_SECONDS   = 5   # пауза між запитами щоб не перевищити rate limit


def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(done: dict):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=2)


def call_with_retry(fn, *args, retries=3):
    for attempt in range(retries):
        try:
            return fn(*args)
        except Exception as e:
            if attempt < retries - 1:
                wait = DELAY_SECONDS * (attempt + 2)
                print(f"  ⚠ Помилка: {e}. Повтор через {wait} сек...")
                time.sleep(wait)
            else:
                raise


# ── ГОЛОВНА ФУНКЦІЯ ───────────────────────────────────────────────────────────
def run_evaluation():
    print("=" * 70)
    print("  ОЦІНКА AI АГЕНТА — LLM-as-Judge")
    print(f"  Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    checkpoint = load_checkpoint()
    if checkpoint:
        done_ids = list(checkpoint.keys())
        print(f"\n  Checkpoint знайдено — пропускаємо тести: {done_ids}")

    results = []
    regular_scores = {"relevance": [], "groundedness": [], "actionability": []}
    guardrail_pass = 0
    guardrail_total = 0

    for tc in TEST_CASES:
        tc_key = str(tc["id"])

        # Відновлення з checkpoint
        if tc_key in checkpoint:
            cached = checkpoint[tc_key]
            results.append(cached)
            if not cached["is_guardrail"]:
                s = cached["scores"]
                for k in ("relevance", "groundedness", "actionability"):
                    regular_scores[k].append(s[k])
            else:
                guardrail_total += 1
                guardrail_pass  += cached["scores"].get("refused", 0)
            print(f"  Тест {tc['id']:02d} ✓ (з checkpoint)")
            continue

        tag = "[GUARDRAIL]" if tc["is_guardrail"] else f"[{tc['dtc_code']}]"
        print(f"\nТест {tc['id']:02d} {tag} {tc['vehicle_id']}")
        print(f"  Питання: {tc['question']}")

        response = call_with_retry(get_agent_response, tc)
        print(f"  Відповідь: {response[:120]}{'...' if len(response) > 120 else ''}")

        time.sleep(DELAY_SECONDS)

        scores = call_with_retry(judge_response, tc, response)

        entry = {**tc, "response": response, "scores": {k: v for k, v in scores.items() if k != "raw"}}

        if tc["is_guardrail"]:
            guardrail_total += 1
            refused = scores["refused"]
            guardrail_pass += refused
            status = "✅ ВІДМОВИВ" if refused else "❌ ВІДПОВІВ"
            print(f"  Guardrail: {status}")
        else:
            r = scores["relevance"]
            g = scores["groundedness"]
            a = scores["actionability"]
            avg = scores["average"]
            print(f"  Оцінки → Рел: {r}/5 | Заз: {g}/5 | Прак: {a}/5 | Сер: {avg}/5")
            regular_scores["relevance"].append(r)
            regular_scores["groundedness"].append(g)
            regular_scores["actionability"].append(a)

        results.append(entry)
        checkpoint[tc_key] = entry
        save_checkpoint(checkpoint)

        time.sleep(DELAY_SECONDS)

    # ── ПІДСУМКОВА ТАБЛИЦЯ ────────────────────────────────────────────────────
    n = len(regular_scores["relevance"])
    avg_rel  = round(sum(regular_scores["relevance"]) / n, 2)
    avg_grnd = round(sum(regular_scores["groundedness"]) / n, 2)
    avg_act  = round(sum(regular_scores["actionability"]) / n, 2)
    avg_all  = round((avg_rel + avg_grnd + avg_act) / 3, 2)

    print("\n" + "=" * 70)
    print("  РЕЗУЛЬТАТИ ОЦІНКИ")
    print("=" * 70)
    print(f"\n  {'Критерій':<30} {'Середній бал':>15}")
    print(f"  {'-'*45}")
    print(f"  {'Релевантність':<30} {avg_rel:>13}/5.0")
    print(f"  {'Заземленість (телеметрія)':<30} {avg_grnd:>13}/5.0")
    print(f"  {'Практичність (дії)':<30} {avg_act:>13}/5.0")
    print(f"  {'-'*45}")
    print(f"  {'ЗАГАЛЬНА ОЦІНКА':<30} {avg_all:>13}/5.0")

    guardrail_pct = round(guardrail_pass / guardrail_total * 100) if guardrail_total else 0
    print(f"\n  Guardrails (захист від нерелевантних питань): "
          f"{guardrail_pass}/{guardrail_total} ({guardrail_pct}%)")

    # Оцінка по кодах
    print("\n  Оцінка по DTC кодах:")
    dtc_groups: dict[str, list] = {}
    for r in results:
        if not r["is_guardrail"]:
            code = r["dtc_code"]
            dtc_groups.setdefault(code, []).append(r["scores"]["average"])

    print(f"  {'Код':<12} {'Середній бал':>15} {'К-сть питань':>14}")
    print(f"  {'-'*42}")
    for code, avgs in sorted(dtc_groups.items()):
        print(f"  {code:<12} {round(sum(avgs)/len(avgs), 2):>13}/5.0 {len(avgs):>14}")

    print("\n" + "=" * 70)

    # ── ЗБЕРЕЖЕННЯ ────────────────────────────────────────────────────────────
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "relevance": avg_rel,
            "groundedness": avg_grnd,
            "actionability": avg_act,
            "overall": avg_all,
            "guardrail_pass": guardrail_pass,
            "guardrail_total": guardrail_total,
            "guardrail_pct": guardrail_pct,
        },
        "by_dtc": {code: round(sum(a)/len(a), 2) for code, a in dtc_groups.items()},
        "details": [
            {
                "id": r["id"],
                "vehicle_id": r["vehicle_id"],
                "dtc_code": r["dtc_code"],
                "question": r["question"],
                "response": r["response"],
                "scores": {k: v for k, v in r["scores"].items() if k != "raw"},
                "is_guardrail": r["is_guardrail"],
            }
            for r in results
        ],
    }

    out_file = f"agent_evaluation_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Детальний звіт збережено: {out_file}")

    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("  Checkpoint видалено.")


if __name__ == "__main__":
    run_evaluation()

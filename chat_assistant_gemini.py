import os
import re
import uuid
import psycopg2
from langchain_google_genai import ChatGoogleGenerativeAI

GOOGLE_API_KEY    = os.environ.get('GOOGLE_API_KEY', '')
DB_CONF           = os.environ.get('DB_CONF', 'host=127.0.0.1 dbname=ev_telemetry_db user=admin password=root port=5432')
KNOWLEDGE_BASE    = "knowledge_base.md"

os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY


def get_vehicle_status(vehicle_id: str) -> str:
    try:
        with psycopg2.connect(DB_CONF) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM vehicles WHERE vehicle_code = %s",
                    (vehicle_id,)
                )
                v_res = cur.fetchone()
                if not v_res:
                    return f"Автомобіль '{vehicle_id}' не знайдено в реєстрі флоту."

                v_id = v_res[0]

                cur.execute(
                    "SELECT MAX(timestamp) FROM vehicle_telemetry WHERE vehicle_id = %s",
                    (v_id,)
                )
                last_ts = cur.fetchone()[0]
                if not last_ts:
                    return f"Для '{vehicle_id}' немає записів телеметрії."

                cur.execute("""
                    SELECT
                        ROUND(AVG(battery_temp_c)::numeric, 1),
                        ROUND(AVG(soc_pct)::numeric, 1),
                        ROUND(AVG(speed_kph)::numeric, 1),
                        ROUND(AVG(brake_pad_wear_mm)::numeric, 2),
                        MAX(abs_fault_indicator),
                        COUNT(*)
                    FROM vehicle_telemetry
                    WHERE vehicle_id = %s
                      AND timestamp > %s - INTERVAL '10 minutes'
                      AND timestamp <= %s
                """, (v_id, last_ts, last_ts))

                res = cur.fetchone()
                avg_temp  = res[0] if res[0] is not None else "н/д"
                avg_soc   = res[1] if res[1] is not None else "н/д"
                avg_spd   = res[2] if res[2] is not None else "н/д"
                avg_brake = res[3] if res[3] is not None else "н/д"
                abs_fault = res[4] if res[4] is not None else 0
                count     = res[5]

                return (
                    f"Телеметрія '{vehicle_id}' станом на {last_ts} "
                    f"(вікно 10 хв, {count} точок):\n"
                    f"  - Температура батареї: {avg_temp} °C\n"
                    f"  - Заряд (SOC): {avg_soc} %\n"
                    f"  - Швидкість: {avg_spd} км/год\n"
                    f"  - Знос гальмівних колодок: {avg_brake} мм\n"
                    f"  - Датчик ABS: {'Спрацював' if abs_fault else 'Норма'}"
                )

    except Exception as e:
        return f"Помилка підключення до PostgreSQL: {e}"


def search_knowledge_base(dtc_code: str) -> str:
    if not os.path.exists(KNOWLEDGE_BASE):
        return "База знань не знайдена."

    with open(KNOWLEDGE_BASE, encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"(?=### Код:)", content)

    for block in blocks:
        if f"### Код: {dtc_code}" in block:
            return block.strip()

    for block in blocks:
        match = re.search(r"### Код:\s*(\S+)", block)
        if match and match.group(1).upper() == dtc_code.upper():
            return block.strip()

    return f"Код {dtc_code} не знайдено в базі знань. Використовуй тільки дані телеметрії."


class ChatAssistantGemini:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            temperature=0.3,
        )
        self.sessions = {}

    def start_session(self, vehicle_id: str, dtc_code: str) -> tuple[str, str]:
        session_id = str(uuid.uuid4())

        telemetry = get_vehicle_status(vehicle_id)
        kb_info   = search_knowledge_base(dtc_code)

        code_type = "Сенсорний код" if (dtc_code.startswith("SENSOR_") or dtc_code.startswith("ADAS_")) else "DTC код"
        initial_prompt = f"""Ти - AI асистент ВИКЛЮЧНО для оператора парку роботизованих транспортних засобів.

ТВОЯ РОЛЬ: відповідати ТІЛЬКИ на питання про:
- Автомобіль {vehicle_id} та його технічний стан
- {code_type} {dtc_code} та дії оператора
- Телеметрію, заряд батареї, температуру, швидкість, стан сенсорів
- Рекомендації щодо повернення в депо або технічного обслуговування

ЗАБОРОНЕНО відповідати на питання поза цією темою.
Якщо питання не стосується флоту або цього автомобіля — відповідай:
"Я можу відповідати тільки на питання пов'язані з автомобілем {vehicle_id} та кодом {dtc_code}."

СИТУАЦІЯ:
Автомобіль: {vehicle_id}
{code_type}: {dtc_code}

ТЕЛЕМЕТРІЯ:
{telemetry}

ІНФОРМАЦІЯ З БАЗИ ЗНАНЬ:
{kb_info}

Привітайся з оператором та коротко поясни:
1. Що означає цей код
2. Чи критична ситуація (на основі телеметрії)
3. Що рекомендуєш робити зараз

Будь конкретним, використовуй дані телеметрії. Без зайвих вступів."""

        response        = self.llm.invoke(initial_prompt)
        initial_message = response.content

        self.sessions[session_id] = {
            'vehicle_id': vehicle_id,
            'dtc_code':   dtc_code,
            'kb_info':    kb_info,
            'history': [
                {'role': 'assistant', 'content': initial_message}
            ]
        }

        return session_id, initial_message

    def chat(self, session_id: str, user_message: str) -> str:
        if session_id not in self.sessions:
            return "Сесія не знайдена. Почніть нову розмову."

        session    = self.sessions[session_id]
        vehicle_id = session['vehicle_id']
        dtc_code   = session['dtc_code']
        kb_info    = session['kb_info']

        telemetry = get_vehicle_status(vehicle_id)

        history_text = "\n".join([
            f"{'AI' if msg['role'] == 'assistant' else 'Оператор'}: {msg['content']}"
            for msg in session['history']
        ])

        prompt = f"""Ти - AI асистент ВИКЛЮЧНО для оператора парку роботизованих транспортних засобів.

ТВОЯ РОЛЬ: відповідати ТІЛЬКИ на питання про автомобіль {vehicle_id}, код {dtc_code}, телеметрію та дії оператора.
Якщо питання не стосується флоту або цього автомобіля — відповідай:
"Я можу відповідати тільки на питання пов'язані з автомобілем {vehicle_id} та кодом {dtc_code}."

КОНТЕКСТ:
Автомобіль: {vehicle_id}
Код: {dtc_code}

АКТУАЛЬНА ТЕЛЕМЕТРІЯ:
{telemetry}

БАЗА ЗНАНЬ ПРО КОД:
{kb_info}

ІСТОРІЯ ДІАЛОГУ:
{history_text}

НОВЕ ПИТАННЯ ОПЕРАТОРА:
{user_message}

Відповідай:
- Конкретно на питання
- Коротко (2-4 речення)
- Використовуй дані телеметрії
- Якщо критично — будь категоричним
- БЕЗ вступів типу "Звісно, допоможу"

Відповідь:"""

        response = self.llm.invoke(prompt)
        answer   = response.content

        session['history'].append({'role': 'user',      'content': user_message})
        session['history'].append({'role': 'assistant', 'content': answer})

        return answer

    def get_session_info(self, session_id: str) -> dict:
        if session_id in self.sessions:
            return {
                'vehicle_id':    self.sessions[session_id]['vehicle_id'],
                'dtc_code':      self.sessions[session_id]['dtc_code'],
                'message_count': len(self.sessions[session_id]['history'])
            }
        return None


_chat_assistant = None

def get_chat_assistant() -> ChatAssistantGemini:
    global _chat_assistant
    if _chat_assistant is None:
        print("🤖 Ініціалізація Chat Assistant (Gemini)...")
        _chat_assistant = ChatAssistantGemini()
        print("✅ Chat Assistant готовий.")
    return _chat_assistant


if __name__ == "__main__":
    assistant = ChatAssistantGemini()

    session_id, initial = assistant.start_session("Tesla_01", "P1B74")
    print("=" * 60)
    print("🤖 AI:", initial)
    print()

    for q in ["Чи можна доїхати до депо?", "Скільки часу є?", "Що робити з пасажирами?"]:
        print("👤 Оператор:", q)
        print("🤖 AI:", assistant.chat(session_id, q))
        print()

from flask import Flask, jsonify, send_file, send_from_directory, request
import psycopg2
import subprocess
from chat_assistant_gemini import get_chat_assistant
import psycopg2.extras
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

chat_assistant = None
_sim_process   = None
PAUSE_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sender.pause')

DB_CONF           = os.environ.get('DB_CONF', 'host=127.0.0.1 dbname=ev_telemetry_db user=admin password=root port=5432')
DATA_WINDOW_HOURS = 24


def query(sql, params=None):
    with psycopg2.connect(DB_CONF) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]


def execute(sql, params=None):
    with psycopg2.connect(DB_CONF) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())


def get_db_max_ts():
    rows = query("SELECT MAX(timestamp) AS max_ts FROM vehicle_telemetry")
    if rows and rows[0]['max_ts']:
        return rows[0]['max_ts']
    return None


def _register_fonts():
    candidates = [
        ('C:/Windows/Fonts/arial.ttf',    'C:/Windows/Fonts/arialbd.ttf'),
        ('C:/Windows/Fonts/calibri.ttf',  'C:/Windows/Fonts/calibrib.ttf'),
        ('C:/Windows/Fonts/times.ttf',    'C:/Windows/Fonts/timesbd.ttf'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
        ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
         '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            pdfmetrics.registerFont(TTFont('CyrFont', reg))
            if os.path.exists(bold):
                pdfmetrics.registerFont(TTFont('CyrFontBold', bold))
            else:
                pdfmetrics.registerFont(TTFont('CyrFontBold', reg))
            return 'CyrFont', 'CyrFontBold'
    return 'Helvetica', 'Helvetica-Bold'

FONT_REG, FONT_BOLD = _register_fonts()


DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path):
    full = os.path.join(DIST_DIR, path)
    if path and os.path.exists(full):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, 'index.html')


@app.route("/api/fleet")
def api_fleet():
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify([])
    rows = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code AS vehicle_id, v.brand, v.model, v.plate_number,
            t.timestamp, t.lat, t.lon, t.speed_kph,
            t.soc_pct, t.soh_pct, t.battery_temp_c,
            t.brake_pad_wear_mm, t.abs_fault_indicator, t.active_error_code,
            t.battery_current_a, t.acceleration_ms2, t.ambient_temp_c, t.power_kw,
            t.ad_mode, t.camera_blinded,
            t.sensor_array_status, t.sensor_fault_code
        FROM vehicles v
        LEFT JOIN vehicle_telemetry t
            ON t.vehicle_id = v.id
            AND t.timestamp > %s - INTERVAL '%s hours'
        ORDER BY v.vehicle_code, t.timestamp DESC
    """ % ('%s', DATA_WINDOW_HOURS), (max_ts,))
    return jsonify(rows)


@app.route("/api/alerts")
def api_alerts():
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify([])

    dtc_rows = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code AS vehicle_id, v.brand, v.model,
            t.timestamp, t.active_error_code AS error_code,
            (
                latest.active_error_code IS NOT NULL
                AND latest.active_error_code NOT IN ('None', '')
                AND latest.active_error_code = t.active_error_code
            ) AS is_active
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        JOIN LATERAL (
            SELECT active_error_code FROM vehicle_telemetry
            WHERE vehicle_id = t.vehicle_id ORDER BY timestamp DESC LIMIT 1
        ) latest ON true
        WHERE t.active_error_code IS NOT NULL
          AND t.active_error_code NOT IN ('None', '')
          AND t.timestamp > %s - INTERVAL '%s hours'
        ORDER BY v.vehicle_code, t.timestamp DESC
        LIMIT 20
    """ % ('%s', DATA_WINDOW_HOURS), (max_ts,))
    for r in dtc_rows:
        r['type'] = 'dtc'

    sensor_rows = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code AS vehicle_id, v.brand, v.model,
            t.timestamp, t.sensor_fault_code AS error_code,
            (t.timestamp > %s - INTERVAL '3 minutes') AS is_active
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE t.sensor_fault_code IS NOT NULL
          AND t.timestamp > %s - INTERVAL '%s hours'
        ORDER BY v.vehicle_code, t.timestamp DESC
        LIMIT 20
    """ % ('%s', '%s', DATA_WINDOW_HOURS), (max_ts, max_ts))
    for r in sensor_rows:
        r['type'] = 'sensor'

    # Дедуплікація: лишаємо один запис на (vehicle_id, type, error_code)
    seen: set = set()
    deduped = []
    for item in dtc_rows + sensor_rows:
        key = (item['vehicle_id'], item.get('type', ''), str(item.get('error_code') or ''))
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    deduped.sort(key=lambda x: (
        0 if x['is_active'] else 1,   # активні — вгорі
        0 if x.get('type') == 'dtc' else 1,  # DTC перед SENSOR
        str(x.get('vehicle_id') or ''),      # потім за авто
    ))
    return jsonify(deduped[:30])


@app.route("/api/soc/<vehicle_id>")
def api_soc(vehicle_id):
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify([])
    rows = query("""
        SELECT t.timestamp, t.soc_pct
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE v.vehicle_code = %s
          AND t.timestamp > %s - INTERVAL '%s hours'
        ORDER BY t.timestamp DESC LIMIT 30
    """ % ('%s', '%s', DATA_WINDOW_HOURS), (vehicle_id, max_ts))
    rows.reverse()
    return jsonify(rows)


@app.route("/api/chart/<vehicle_id>")
def api_chart(vehicle_id):
    exists = query("SELECT id FROM vehicles WHERE vehicle_code = %s", (vehicle_id,))
    if not exists:
        return jsonify({"error": "Vehicle not found", "vehicle_id": vehicle_id}), 404
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify([])
    rows = query("""
        SELECT t.timestamp, t.soc_pct, t.battery_temp_c, t.speed_kph
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE v.vehicle_code = %s
          AND t.timestamp > %s - INTERVAL '%s hours'
        ORDER BY t.timestamp DESC LIMIT 30
    """ % ('%s', '%s', DATA_WINDOW_HOURS), (vehicle_id, max_ts))
    rows.reverse()
    return jsonify(rows)


@app.route("/api/predictions")
def api_predictions():
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify([])
    rows = query("""
        SELECT
            v.vehicle_code AS vehicle_id,
            MAX(p.predicted_at)       AS predicted_at,
            AVG(p.current_soc)        AS current_soc,
            AVG(p.predicted_soc)      AS predicted_soc
        FROM lstm_predictions p
        JOIN vehicles v ON v.id = p.vehicle_id
        WHERE p.predicted_at > %s - INTERVAL '5 minutes'
        GROUP BY v.vehicle_code
    """, (max_ts,))
    return jsonify(rows)



@app.route("/api/geofence/events")
def api_geofence_events():
    rows = query("""
        SELECT
            v.vehicle_code, v.brand, v.model,
            g.event_type, g.timestamp, g.lat, g.lon, g.distance_m
        FROM vehicles v
        LEFT JOIN LATERAL (
            SELECT event_type, timestamp, lat, lon, distance_m
            FROM geofence_events
            WHERE vehicle_id = v.id
            ORDER BY timestamp DESC
            LIMIT 1
        ) g ON true
        ORDER BY v.vehicle_code
    """)
    return jsonify(rows)


@app.route("/api/route/<vehicle_id>")
def api_route(vehicle_id):
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify([])
    rows = query("""
        SELECT t.lat, t.lon, t.timestamp
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE v.vehicle_code = %s
          AND t.lat IS NOT NULL
          AND t.timestamp > %s - INTERVAL '%s hours'
        ORDER BY t.timestamp DESC
        LIMIT 200
    """ % ('%s', '%s', DATA_WINDOW_HOURS), (vehicle_id, max_ts))
    rows.reverse()
    return jsonify(rows)


@app.route("/api/geofence/status")
def api_geofence_status():
    rows = query("""
        SELECT
            v.vehicle_code, v.brand, v.model,
            t.lat, t.lon, t.timestamp,
            g.event_type
        FROM vehicles v
        LEFT JOIN LATERAL (
            SELECT lat, lon, timestamp
            FROM vehicle_telemetry
            WHERE vehicle_id = v.id
            ORDER BY timestamp DESC
            LIMIT 1
        ) t ON true
        LEFT JOIN LATERAL (
            SELECT event_type
            FROM geofence_events
            WHERE vehicle_id = v.id
            ORDER BY timestamp DESC
            LIMIT 1
        ) g ON true
        ORDER BY v.vehicle_code
    """)

    DEPOT_LAT = 50.4501
    DEPOT_LON = 30.5234

    import math
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        p = math.pi / 180
        a = (math.sin((lat2-lat1)*p/2)**2 +
             math.cos(lat1*p) * math.cos(lat2*p) *
             math.sin((lon2-lon1)*p/2)**2)
        return round(2 * R * math.asin(math.sqrt(a)))

    for r in rows:
        if r['lat'] and r['lon']:
            r['current_distance_m'] = haversine(
                float(r['lat']), float(r['lon']),
                DEPOT_LAT, DEPOT_LON
            )
        else:
            r['current_distance_m'] = None

    return jsonify(rows)


@app.route("/api/recommendations")
def api_recommendations():
    rows = query("""
        SELECT r.id, v.vehicle_code, v.brand, v.model,
               r.created_at, r.current_soc, r.predicted_soc,
               r.distance_to_depot_m, r.reason, r.status
        FROM depot_recommendations r
        JOIN vehicles v ON v.id = r.vehicle_id
        WHERE r.status = 'active'
        ORDER BY r.created_at DESC
    """)
    return jsonify(rows)


@app.route("/api/recommendations/combined")
def api_recommendations_combined():
    vehicle_signals = {}

    max_ts = get_db_max_ts()
    preds = query("""
        SELECT
            v.vehicle_code          AS vehicle_id,
            MAX(p.predicted_at)     AS predicted_at,
            AVG(p.current_soc)      AS current_soc,
            AVG(p.predicted_soc)    AS predicted_soc
        FROM lstm_predictions p
        JOIN vehicles v ON v.id = p.vehicle_id
        WHERE p.predicted_at > %s - INTERVAL '5 minutes'
        GROUP BY v.vehicle_code
    """, (max_ts,)) if max_ts else []
    # Зберігаємо поточні значення SOC окремо — щоб перезаписувати старі
    current_soc_map = {}
    for p in preds:
        vid  = p["vehicle_id"]
        cur  = float(p.get("current_soc", 100))
        pred = float(p.get("predicted_soc", 100))
        current_soc_map[vid] = {"cur": cur, "pred": pred}
        if vid not in vehicle_signals:
            vehicle_signals[vid] = {"signals": [], "cur": cur, "pred": pred, "dist": 0, "reason": "", "dtc_code": "", "timestamp": p["predicted_at"].isoformat() if p["predicted_at"] else ""}
        else:
            # Завжди оновлюємо актуальними значеннями
            vehicle_signals[vid]["cur"]  = cur
            vehicle_signals[vid]["pred"] = pred
        if cur < 15:
            vehicle_signals[vid]["signals"].append("critical_soc")
        elif pred < 15:
            vehicle_signals[vid]["signals"].append("critical_forecast")
        elif pred < 20:
            vehicle_signals[vid]["signals"].append("low_soc_forecast")

    depot_recs = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code AS vehicle_id,
            r.id, r.current_soc, r.predicted_soc,
            r.distance_to_depot_m, r.reason, r.created_at
        FROM depot_recommendations r
        JOIN vehicles v ON v.id = r.vehicle_id
        WHERE r.status = 'active'
        ORDER BY v.vehicle_code, r.created_at DESC
    """)
    for r in depot_recs:
        vid    = r["vehicle_id"]
        reason = str(r.get("reason", ""))
        cur    = float(r.get("current_soc", 100))
        pred   = float(r.get("predicted_soc", 100))
        ts     = r["created_at"].isoformat() if r.get("created_at") else ""
        rec_id = r.get("id")
        if vid not in vehicle_signals:
            vehicle_signals[vid] = {"signals": [], "cur": cur, "pred": pred, "dist": 0, "reason": reason, "dtc_code": "", "timestamp": ts, "rec_id": rec_id}
        else:
            # Якщо є актуальні дані з LSTM — використовуємо їх, а не старі зі збереженої рекомендації
            if vid in current_soc_map:
                vehicle_signals[vid]["cur"]  = current_soc_map[vid]["cur"]
                vehicle_signals[vid]["pred"] = current_soc_map[vid]["pred"]

        vehicle_signals[vid]["dist"]   = int(r.get("distance_to_depot_m") or 0)
        vehicle_signals[vid]["reason"] = reason
        vehicle_signals[vid]["signals"].append("depot_return")

    level_order = {"critical": 0, "warning": 1, "info": 2}
    recs = []
    for vid, d in vehicle_signals.items():
        types = d["signals"]
        cur   = d.get("cur"); pred = d.get("pred")
        dist  = d.get("dist", 0); reason = d.get("reason", "")
        ts    = d.get("timestamp", ""); dtc = d.get("dtc_code", "")

        if "critical_soc" in types or (cur is not None and cur < 15):
            level   = "critical"
            message = f"Критичний заряд ({cur:.1f}%) — негайно направити на зарядку або в депо."
            detail  = f"Прогноз заряду: {pred:.1f}% · До депо: {dist} м"
        elif "critical_forecast" in types:
            level   = "critical"
            message = f"Прогноз заряду: заряд впаде до {pred:.1f}% — негайно направити на зарядку!"
            detail  = f"Поточний SOC: {cur:.1f}% · До депо: {dist} м"
        elif "depot_return" in types and "low_soc_forecast" in types:
            level   = "warning"
            message = "Швидкий розряд акумулятора — враховуйте при виборі маршруту."
            detail  = f"Прогноз заряду: {pred:.1f}% · Рекомендується зарядна станція або депо ({dist} м)"
        elif "depot_return" in types:
            level   = "warning"
            if "Швидкий розряд" in reason:
                message = "Швидкий розряд акумулятора — враховуйте при виборі маршруту."
                detail  = f"SOC: {cur:.1f}% · До депо: {dist} м"
            else:
                message = f"Знижений заряд ({cur:.1f}%) — рекомендується повернення в депо."
                detail  = f"До депо: {dist} м · Прогноз: {pred:.1f}%"
        elif "low_soc_forecast" in types:
            level   = "warning"
            message = f"Прогноз заряду: {pred:.1f}% — знайдіть зарядну станцію або поверніться в депо."
            detail  = f"Поточний SOC: {cur:.1f}%"
        else:
            continue

        recs.append({"vehicle_id": vid, "level": level, "message": message, "detail": detail,
                     "timestamp": ts, "rec_id": d.get("rec_id")})

    telem = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code AS vehicle_id,
            t.battery_temp_c, t.soh_pct,
            t.brake_pad_wear_mm, t.abs_fault_indicator,
            t.ad_mode, t.timestamp
        FROM vehicles v
        LEFT JOIN vehicle_telemetry t ON t.vehicle_id = v.id
        ORDER BY v.vehicle_code, t.timestamp DESC
    """)

    for t in telem:
        vid   = t["vehicle_id"]
        temp  = float(t.get("battery_temp_c")    or 0)
        soh   = float(t.get("soh_pct")           or 100)
        brake = float(t.get("brake_pad_wear_mm") or 8)
        abs_f = int(t.get("abs_fault_indicator") or 0)
        ts      = str(t.get("timestamp", ""))
        dtc     = vehicle_signals.get(vid, {}).get("dtc_code", "")
        ad_mode = t.get("ad_mode") or "AUTONOMOUS"

        if ad_mode == "MANUAL_OVERRIDE":
            recs.append({"vehicle_id": vid, "level": "warning",
                "message": "Авто під дистанційним керуванням оператора",
                "detail": "Контролюйте телеметрію та відеопотік · Направте до депо при можливості",
                "timestamp": ts})

        if "P1B74" not in dtc:
            if temp > 65:
                recs.append({"vehicle_id": vid, "level": "critical",
                    "message": f"Критичний перегрів батареї: {temp:.1f}°C — негайно зупинити!",
                    "detail": "Допустимий максимум: 65°C · Ризик пошкодження батареї",
                    "timestamp": ts})
            elif temp > 50:
                recs.append({"vehicle_id": vid, "level": "warning",
                    "message": f"Підвищена температура батареї: {temp:.1f}°C",
                    "detail": "Норма до 50°C · Рекомендується знизити навантаження",
                    "timestamp": ts})

        if soh < 80:
            recs.append({"vehicle_id": vid, "level": "critical",
                "message": f"Критична деградація батареї: SOH {soh:.1f}%",
                "detail": "Поріг заміни: 80% · Необхідне технічне обслуговування",
                "timestamp": ts})
        elif soh < 85:
            recs.append({"vehicle_id": vid, "level": "warning",
                "message": f"Знижений ресурс батареї: SOH {soh:.1f}%",
                "detail": "Рекомендується планова діагностика акумулятора",
                "timestamp": ts})

        if 2.5 <= brake < 4.0 and "C1235" not in dtc:
            recs.append({"vehicle_id": vid, "level": "warning",
                "message": f"Знос гальмівних колодок: {brake:.1f} мм",
                "detail": "Критичний поріг: 2.5 мм · Запланувати заміну колодок",
                "timestamp": ts})

        if abs_f == 1:
            recs.append({"vehicle_id": vid, "level": "warning",
                "message": "Спрацювання датчика ABS",
                "detail": "Перевірити гальмівну систему при найближчому ТО",
                "timestamp": ts})

    recs.sort(key=lambda x: level_order.get(x["level"], 3))
    return jsonify(recs)


@app.route("/api/recommendations/<int:rec_id>/dismiss", methods=["POST"])
def dismiss_recommendation(rec_id):
    execute(
        "UPDATE depot_recommendations SET status = 'dismissed' WHERE id = %s",
        (rec_id,)
    )
    return jsonify({"status": "dismissed", "id": rec_id})


@app.route("/api/report/<vehicle_id>")
def generate_report(vehicle_id):

    max_ts = get_db_max_ts()
    if not max_ts:
        max_ts = datetime.now()

    stats = query("""
        SELECT
            COUNT(*)                               AS total_records,
            ROUND(AVG(speed_kph)::numeric, 1)      AS avg_speed,
            MAX(speed_kph)                         AS max_speed,
            ROUND(AVG(battery_temp_c)::numeric, 1) AS avg_temp,
            MAX(battery_temp_c)                    AS max_temp,
            MAX(soc_pct)                           AS max_soc,
            MIN(soc_pct)                           AS min_soc,
            ROUND(AVG(soc_pct)::numeric, 1)        AS avg_soc,
            SUM(CASE WHEN speed_kph > 0 THEN 1 ELSE 0 END) AS moving_records,
            SUM(CASE WHEN speed_kph = 0 THEN 1 ELSE 0 END) AS standing_records
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE v.vehicle_code = %s
          AND t.timestamp > %s - INTERVAL '24 hours'
    """, (vehicle_id, max_ts))

    fleet = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code, v.brand, v.model,
            t.timestamp, t.soc_pct, t.soh_pct, t.battery_temp_c,
            t.speed_kph, t.brake_pad_wear_mm, t.abs_fault_indicator,
            t.active_error_code, t.sensor_array_status,
            t.camera_blinded, t.sensor_fault_code, t.ad_mode
        FROM vehicles v
        LEFT JOIN vehicle_telemetry t ON t.vehicle_id = v.id
        WHERE v.vehicle_code = %s
        ORDER BY v.vehicle_code, t.timestamp DESC
    """, (vehicle_id,))

    pred = query("""
        SELECT p.current_soc, p.predicted_soc, p.predicted_at
        FROM lstm_predictions p
        JOIN vehicles v ON v.id = p.vehicle_id
        WHERE v.vehicle_code = %s
        ORDER BY p.predicted_at DESC LIMIT 1
    """, (vehicle_id,))

    geo = query("""
        SELECT g.event_type, g.timestamp, g.distance_m
        FROM geofence_events g
        JOIN vehicles v ON v.id = g.vehicle_id
        WHERE v.vehicle_code = %s
        ORDER BY g.timestamp DESC LIMIT 5
    """, (vehicle_id,))

    rec = query("""
        SELECT r.reason, r.current_soc, r.predicted_soc,
               r.distance_to_depot_m, r.created_at
        FROM depot_recommendations r
        JOIN vehicles v ON v.id = r.vehicle_id
        WHERE v.vehicle_code = %s
        ORDER BY r.created_at DESC LIMIT 3
    """, (vehicle_id,))

    telemetry_series = query("""
        SELECT t.timestamp, t.soc_pct, t.battery_temp_c, t.speed_kph
        FROM vehicle_telemetry t
        JOIN vehicles v ON v.id = t.vehicle_id
        WHERE v.vehicle_code = %s
          AND t.timestamp > %s - INTERVAL '24 hours'
        ORDER BY t.timestamp ASC
    """, (vehicle_id, max_ts))

    # Формуємо повний список рекомендацій для звіту
    report_recs = []
    for r in rec:
        ts = str(r.get('created_at', ''))[:16]
        report_recs.append(('warn', f"{ts}: {r.get('reason', '')}"))
    if fleet:
        fv     = fleet[0]
        temp   = float(fv.get('battery_temp_c') or 0)
        soh    = float(fv.get('soh_pct')        or 100)
        brake  = float(fv.get('brake_pad_wear_mm') or 8)
        abs_f  = int(fv.get('abs_fault_indicator') or 0)
        sfault = fv.get('sensor_fault_code')
        if temp > 65:
            report_recs.append(('crit', f"Критичний перегрів батареї: {temp:.1f}°C — максимум 65°C, зупинити авто"))
        elif temp > 50:
            report_recs.append(('warn', f"Підвищена температура батареї: {temp:.1f}°C (норма до 50°C)"))
        if soh < 80:
            report_recs.append(('crit', f"Критична деградація батареї: SOH {soh:.1f}% — необхідна заміна (поріг 80%)"))
        elif soh < 85:
            report_recs.append(('warn', f"Знижений ресурс батареї: SOH {soh:.1f}% — планова діагностика"))
        if brake < 2.5:
            report_recs.append(('crit', f"Критичний знос гальм: {brake:.1f} мм — негайна заміна колодок"))
        elif brake < 4.0:
            report_recs.append(('warn', f"Знос гальмівних колодок: {brake:.1f} мм (критичний поріг 2.5 мм)"))
        if abs_f == 1:
            report_recs.append(('warn', "Спрацювання датчика ABS — перевірити гальмівну систему"))
        if sfault == 'SENSOR_ARR_DEGRADED':
            report_recs.append(('warn', "Деградація масиву сенсорів (LiDAR/Radar) — перевірка апаратури"))
        elif sfault == 'SENSOR_CAM_BLIND':
            report_recs.append(('warn', "Засліплення фронтальної камери — очищення або заміна"))

    chart_img = None
    if len(telemetry_series) >= 2:
        timestamps = [row['timestamp'] for row in telemetry_series]
        soc_vals   = [float(row['soc_pct'] or 0)        for row in telemetry_series]
        temp_vals  = [float(row['battery_temp_c'] or 0) for row in telemetry_series]
        spd_vals   = [float(row['speed_kph'] or 0)      for row in telemetry_series]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6),
                                        facecolor='#f8f9fa', sharex=True)
        fig.subplots_adjust(hspace=0.35)

        color_soc  = '#2196F3'
        color_temp = '#FF5722'

        ax1.set_facecolor('#ffffff')
        ax1.plot(timestamps, soc_vals, color=color_soc,
                 linewidth=1.8, label='SOC (%)')
        ax1.fill_between(timestamps, soc_vals, alpha=0.1, color=color_soc)
        ax1.set_ylabel('SOC (%)', color=color_soc, fontsize=9)
        ax1.tick_params(axis='y', labelcolor=color_soc, labelsize=8)
        ax1.set_ylim(0, 105)
        ax1.grid(True, alpha=0.3, linestyle='--')
        ax1.set_title('Заряд батареї (SOC) та температура за 24 год',
                      fontsize=10, pad=8, fontweight='bold')

        ax1b = ax1.twinx()
        ax1b.plot(timestamps, temp_vals, color=color_temp,
                  linewidth=1.8, linestyle='--', label='Температура (°C)')
        ax1b.set_ylabel('Температура (°C)', color=color_temp, fontsize=9)
        ax1b.tick_params(axis='y', labelcolor=color_temp, labelsize=8)
        ax1b.axhline(60, color=color_temp, linewidth=0.8,
                     linestyle=':', alpha=0.6, label='Поріг 60°C')

        lines1 = [
            plt.Line2D([0],[0], color=color_soc,  linewidth=1.8, label='SOC (%)'),
            plt.Line2D([0],[0], color=color_temp, linewidth=1.8,
                       linestyle='--', label='Температура (°C)'),
            plt.Line2D([0],[0], color=color_temp, linewidth=0.8,
                       linestyle=':', alpha=0.6, label='Поріг 60°C'),
        ]
        ax1.legend(handles=lines1, loc='upper right', fontsize=7, framealpha=0.8)

        color_spd = '#4CAF50'
        ax2.set_facecolor('#ffffff')
        ax2.fill_between(timestamps, spd_vals, alpha=0.3, color=color_spd)
        ax2.plot(timestamps, spd_vals, color=color_spd, linewidth=1.5)
        ax2.set_ylabel('Швидкість (км/год)', fontsize=9)
        ax2.tick_params(axis='y', labelsize=8)
        ax2.tick_params(axis='x', labelsize=7, rotation=15)
        ax2.grid(True, alpha=0.3, linestyle='--')
        ax2.set_title('Швидкість руху за 24 год',
                      fontsize=10, pad=8, fontweight='bold')
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax2.xaxis.set_major_locator(mdates.AutoDateLocator())

        chart_buf = io.BytesIO()
        fig.savefig(chart_buf, format='png', dpi=150,
                    bbox_inches='tight', facecolor='#f8f9fa')
        chart_buf.seek(0)
        chart_img = ImageReader(chart_buf)
        plt.close(fig)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    w, h = A4

    def draw_line(y):
        c.setStrokeColorRGB(0.85, 0.85, 0.85)
        c.line(40, y, w - 40, y)

    def text(x, y, s, font=FONT_REG, size=11, r=0, g=0, b=0):
        c.setFont(font, size)
        c.setFillColorRGB(r, g, b)
        c.drawString(x, y, str(s))

    text(40, h-50, f"Звіт автомобіля: {vehicle_id}", FONT_BOLD, 18, 0.1, 0.1, 0.1)
    text(40, h-68, f"Сформовано: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
         FONT_REG, 10, 0.5, 0.5, 0.5)
    draw_line(h-78)
    y = h - 108

    if fleet:
        v = fleet[0]
        text(40, y, "Загальна інформація", FONT_BOLD, 13)
        y -= 22
        err      = v.get('active_error_code', 'None')
        err_str  = err if err and err not in ('None', '') else 'Відсутня'
        soh_val  = float(v.get('soh_pct') or 100)
        arr      = v.get('sensor_array_status') or 'OK'
        arr_str  = {'OK': 'Норма', 'DEGRADED': 'Деградація ⚠', 'ERROR': 'Відмова ✕'}.get(arr, arr)
        mode     = v.get('ad_mode') or 'AUTONOMOUS'
        mode_str = {'AUTONOMOUS': 'Автономний', 'MANUAL_OVERRIDE': 'Дистанційне керування', 'SAFE_STOP': 'Безпечна зупинка'}.get(mode, mode)
        text(40, y, f"Марка/Модель: {v.get('brand','')} {v.get('model','')}", size=11); y -= 17
        text(40, y, f"SOC: {round(float(v.get('soc_pct') or 0), 1)}%  |  SOH: {soh_val:.1f}%", size=11); y -= 17
        text(40, y, f"Температура батареї: {round(float(v.get('battery_temp_c') or 0), 1)}°C", size=11); y -= 17
        text(40, y, f"Знос гальм: {round(float(v.get('brake_pad_wear_mm') or 0), 2)} мм", size=11); y -= 17
        text(40, y, f"Режим керування: {mode_str}  |  Сенсори: {arr_str}", size=11); y -= 17
        text(40, y, f"Активна помилка: {err_str}", size=11); y -= 25
        draw_line(y); y -= 18

    text(40, y, "Статистика за 24 години", FONT_BOLD, 13); y -= 22
    if stats and stats[0]['total_records']:
        s = stats[0]
        moving_min   = int((s.get('moving_records')   or 0) * 30 / 60)
        standing_min = int((s.get('standing_records') or 0) * 30 / 60)
        text(40, y, f"Середня швидкість:      {s.get('avg_speed','—')} км/год", size=11); y -= 17
        text(40, y, f"Максимальна швидкість:  {s.get('max_speed','—')} км/год", size=11); y -= 17
        text(40, y, f"Час у русі:             ~{moving_min} хв", size=11); y -= 17
        text(40, y, f"Час стоянки:            ~{standing_min} хв", size=11); y -= 17
        text(40, y, f"Середня темп. батареї:  {s.get('avg_temp','—')}°C", size=11); y -= 17
        text(40, y, f"Макс. темп. батареї:    {round(float(s.get('max_temp') or 0), 1)}°C", size=11); y -= 17
        text(40, y, f"SOC: макс {s.get('max_soc','—')}%  /  мін {s.get('min_soc','—')}%  /  сер {s.get('avg_soc','—')}%", size=11)
    else:
        text(40, y, "Даних за 24 години немає", size=11, r=0.5, g=0.5, b=0.5)
    y -= 25
    draw_line(y); y -= 18

    text(40, y, "Прогноз заряду — через 1 годину", FONT_BOLD, 13); y -= 22
    if pred:
        p       = pred[0]
        cur_soc = float(p.get('current_soc', 0))
        prd_soc = float(p.get('predicted_soc', 0))
        delta   = round(prd_soc - cur_soc, 1)
        sign    = '+' if delta >= 0 else ''
        text(40, y, f"Поточний SOC: {cur_soc:.1f}%", size=11); y -= 17
        text(40, y, f"Прогноз заряду через 1 годину: {prd_soc:.1f}%  ({sign}{delta}%)", size=11)
    else:
        text(40, y, "Даних немає", size=11, r=0.5, g=0.5, b=0.5)
    y -= 25
    draw_line(y); y -= 18

    text(40, y, "Моніторинг зони депо", FONT_BOLD, 13); y -= 22
    if geo:
        for g in geo:
            ts    = str(g.get('timestamp', ''))[:16]
            event = 'В ДЕПО' if g.get('event_type') == 'ENTERED' else 'ВИЇХАВ'
            dist  = round(g.get('distance_m', 0))
            text(40, y, f"{ts}  —  {event}  ({dist} м від депо)", size=10); y -= 15
    else:
        text(40, y, "Подій не зафіксовано", size=11, r=0.5, g=0.5, b=0.5)
    y -= 15
    draw_line(y); y -= 18

    text(40, y, "Рекомендації ІСППР", FONT_BOLD, 13); y -= 22
    if report_recs:
        for level, line in report_recs:
            prefix = "[!]" if level == 'crit' else "[~]"
            full = f"{prefix} {line}"
            cr, cg, cb = (0.85, 0.1, 0.1) if level == 'crit' else (0.6, 0.4, 0.0)
            if len(full) <= 85:
                text(40, y, full, size=10, r=cr, g=cg, b=cb); y -= 15
            else:
                text(40, y, full[:85], size=10, r=cr, g=cg, b=cb); y -= 13
                text(40, y, full[85:170], size=10, r=cr, g=cg, b=cb); y -= 15
            if y < 60:
                break
    else:
        text(40, y, "Відхилень не виявлено — система в нормі", size=11, r=0.15, g=0.55, b=0.15)

    if chart_img:
        c.showPage()
        text(40, h-50, f"Графіки телеметрії: {vehicle_id}", FONT_BOLD, 16, 0.1, 0.1, 0.1)
        text(40, h-68, f"За останні 24 години",
             FONT_REG, 10, 0.5, 0.5, 0.5)
        draw_line(h-78)

        chart_w = w - 80
        chart_h = chart_w * 0.6
        c.drawImage(chart_img, 40, h - 90 - chart_h,
                    width=chart_w, height=chart_h,
                    preserveAspectRatio=True)

    c.save()
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f"report_{vehicle_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )

@app.route("/api/fleet_health")
def api_fleet_health():
    max_ts = get_db_max_ts()
    if not max_ts:
        return jsonify({"fleet_score": 0, "vehicles": []})

    rows = query("""
        SELECT DISTINCT ON (v.vehicle_code)
            v.vehicle_code AS vehicle_id,
            t.soc_pct, t.soh_pct, t.battery_temp_c,
            t.brake_pad_wear_mm, t.active_error_code,
            t.sensor_array_status, t.camera_blinded
        FROM vehicles v
        LEFT JOIN vehicle_telemetry t ON t.vehicle_id = v.id
            AND t.timestamp > %s - INTERVAL '1 hour'
        ORDER BY v.vehicle_code, t.timestamp DESC
    """, (max_ts,))

    vehicles = []
    for row in rows:
        soc            = float(row['soc_pct']          or 50)
        soh            = float(row['soh_pct']          or 100)
        temp           = float(row['battery_temp_c']   or 25)
        brake          = float(row['brake_pad_wear_mm'] or 8)
        error          = row['active_error_code']
        arr_status     = row['sensor_array_status'] or 'OK'
        camera_blinded = row['camera_blinded'] if row['camera_blinded'] is not None else False

        soc_score   = min(soc / 50.0, 1.0) * 100
        soh_score   = soh
        if temp <= 45:
            temp_score = 100
        elif temp >= 60:
            temp_score = 0
        else:
            temp_score = (60 - temp) / (60 - 45) * 100
        if brake >= 6:
            brake_score = 100
        elif brake <= 2.5:
            brake_score = 0
        else:
            brake_score = (brake - 2.5) / (6 - 2.5) * 100
        error_score = 0 if (error and error not in ('None', '')) else 100

        if arr_status == 'ERROR':
            sensor_score = 0
        elif arr_status == 'DEGRADED' or camera_blinded:
            sensor_score = 50
        else:
            sensor_score = 100

        health = (
            0.25 * soc_score +
            0.20 * soh_score +
            0.15 * temp_score +
            0.15 * brake_score +
            0.10 * error_score +
            0.15 * sensor_score
        )
        health = round(health, 1)

        if health >= 70:
            status = 'ok'
        elif health >= 40:
            status = 'warn'
        else:
            status = 'critical'

        vehicles.append({
            'vehicle_id': row['vehicle_id'],
            'health': health,
            'status': status,
            'components': {
                'soc':    round(soc_score, 1),
                'soh':    round(soh_score, 1),
                'temp':   round(temp_score, 1),
                'brake':  round(brake_score, 1),
                'error':  round(error_score, 1),
                'sensor': round(sensor_score, 1),
            }
        })

    fleet_score = round(sum(v['health'] for v in vehicles) / len(vehicles), 1) if vehicles else 0
    return jsonify({'fleet_score': fleet_score, 'vehicles': vehicles})


@app.route('/api/chat/init', methods=['POST'])
def chat_init():
    global chat_assistant

    if chat_assistant is None:
        chat_assistant = get_chat_assistant()

    data = request.json
    vehicle_id = data.get('vehicle_id')
    dtc_code = data.get('dtc_code')

    if not vehicle_id or not dtc_code:
        return jsonify({'error': 'Missing vehicle_id or dtc_code'}), 400

    try:
        session_id, initial_message = chat_assistant.start_session(vehicle_id, dtc_code)
        return jsonify({
            'session_id': session_id,
            'initial_message': initial_message
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/message', methods=['POST'])
def chat_message():
    global chat_assistant

    if chat_assistant is None:
        return jsonify({'error': 'Chat not initialized'}), 400

    data = request.json
    session_id = data.get('session_id')
    message = data.get('message')

    if not session_id or not message:
        return jsonify({'error': 'Missing session_id or message'}), 400

    try:
        response = chat_assistant.chat(session_id, message)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat/session/<session_id>')
def chat_session_info(session_id):
    global chat_assistant

    if chat_assistant is None:
        return jsonify({'error': 'Chat not initialized'}), 400

    info = chat_assistant.get_session_info(session_id)

    if info is None:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify(info)


@app.route('/api/simulation/status')
def sim_status():
    global _sim_process
    running = _sim_process is not None and _sim_process.poll() is None
    paused  = running and os.path.exists(PAUSE_FILE)
    return jsonify({'running': running, 'paused': paused})


@app.route('/api/simulation/start', methods=['POST'])
def sim_start():
    global _sim_process
    if _sim_process and _sim_process.poll() is None:
        return jsonify({'status': 'already_running'})
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sender.py')
    _sim_process = subprocess.Popen(['python', script],
                                    cwd=os.path.dirname(os.path.abspath(__file__)))
    return jsonify({'status': 'started', 'pid': _sim_process.pid})


@app.route('/api/simulation/stop', methods=['POST'])
def sim_stop():
    global _sim_process
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    if _sim_process and _sim_process.poll() is None:
        _sim_process.terminate()
        try:
            _sim_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _sim_process.kill()
        return jsonify({'status': 'stopped'})
    return jsonify({'status': 'not_running'})


@app.route('/api/simulation/pause', methods=['POST'])
def sim_pause():
    open(PAUSE_FILE, 'w').close()
    return jsonify({'status': 'paused'})


@app.route('/api/simulation/resume', methods=['POST'])
def sim_resume():
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    return jsonify({'status': 'resumed'})


@app.route('/api/db/clear', methods=['POST'])
def db_clear():
    global _sim_process
    # Зупиняємо симуляцію перед очищенням
    if _sim_process and _sim_process.poll() is None:
        _sim_process.terminate()
        try:
            _sim_process.wait(timeout=3)
        except Exception:
            _sim_process.kill()
        _sim_process = None
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)

    with psycopg2.connect(DB_CONF) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                TRUNCATE TABLE
                    vehicle_telemetry,
                    lstm_predictions,
                    geofence_events,
                    depot_recommendations
                RESTART IDENTITY
            """)

    # Сигналізуємо receiver.py скинути geofence_state
    reset_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geofence.reset')
    open(reset_file, 'w').close()

    return jsonify({'status': 'cleared'})


if __name__ == "__main__":
    print("🚀 Fleet Dashboard: http://localhost:5000")
    print("💬 AI Chat Assistant готовий")
    app.run(debug=True, host="0.0.0.0", port=5000)

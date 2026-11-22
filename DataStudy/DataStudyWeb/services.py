from datetime import date, datetime, timedelta
import time
from db import rows, one, get_conn, update_request_status

def compute_priority(activity, description, day, attendees, weights):
    today = date.today()
    if isinstance(day, str):
        day = date.fromisoformat(day)
    days_left = max(0, (day - today).days)
    urgency = max(0.0, 1.0 - min(days_left, 30)/30.0)
    group_score = min(int(attendees)/30.0, 1.0)
    text = (activity + " " + description).lower()
    academic_terms = ["examen", "parcial", "proyecto", "laboratorio", "entrega", "investigación", "práctica", "sustentación"]
    academic = 1.0 if any(t in text for t in academic_terms) else 0.55
    score = 100 * (weights["urgency_weight"]*urgency + weights["attendees_weight"]*group_score + weights["academic_weight"]*academic)
    reason = f"Urgencia {urgency:.2f}, tamaño de grupo {group_score:.2f}, necesidad académica {academic:.2f}. Criterios configurados por administración."
    return round(score, 2), reason

def overlapping(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end

def find_candidate(request, resources=None):
    resources = resources or rows("SELECT * FROM resources WHERE active=1 ORDER BY capacity ASC")
    for r in resources:
        if request.get("preferred_category") and request["preferred_category"] != "Cualquiera" and r["category"] != request["preferred_category"]:
            continue
        if int(r["capacity"]) < int(request["attendees"]):
            continue
        if request["start_time"] < r["open_time"] or request["end_time"] > r["close_time"]:
            continue
        existing = rows("""SELECT date,start_time,end_time FROM requests
                           WHERE assigned_resource_id=? AND date=? AND status='Asignada' AND id != ?""",
                        (r["id"], request["date"], request["id"]))
        if any(overlapping(request["start_time"], request["end_time"], x["start_time"], x["end_time"]) for x in existing):
            continue
        return r
    return None

def run_assignment():
    start = time.perf_counter()
    pending = rows("SELECT * FROM requests WHERE status='Pendiente' ORDER BY priority DESC, date ASC, start_time ASC")
    assigned, rejected, reasons = 0, 0, []
    for req in pending:
        r = find_candidate(req)
        if r:
            update_request_status(req["id"], "Asignada", r["id"], "Asignación automática: capacidad, horario y no solapamiento validados.")
            assigned += 1
        else:
            update_request_status(req["id"], "No atendida", None, "No se encontró recurso compatible y disponible; requiere revisión administrativa.")
            rejected += 1
    elapsed = (time.perf_counter()-start)*1000
    if pending:
        per_request = elapsed / len(pending)
        with get_conn() as c:
            c.execute("""UPDATE assignment_results SET runtime_ms=?
                         WHERE id IN (SELECT id FROM assignment_results ORDER BY id DESC LIMIT ?)""",
                      (per_request, len(pending)))
    return {"processed":len(pending),"assigned":assigned,"rejected":rejected,"runtime_ms":round(elapsed,2)}

def predict_demand(days_ahead=30, category=None):
    """Pronóstico base sin scikit-learn: promedio histórico semanal y ajuste por día de semana."""
    historical = rows("SELECT date, preferred_category FROM requests WHERE date < ?",
                      (str(date.today()),))
    if category and category != "Todas":
        historical = [x for x in historical if x["preferred_category"] == category]
    if not historical:
        return {"total":0,"daily_average":0.0,"peak_weekday":"Sin datos","peak_count":0,"method":"Sin historial"}
    counts = {}
    weekday_counts = {i: [] for i in range(7)}
    for item in historical:
        d = date.fromisoformat(item["date"])
        counts[d] = counts.get(d, 0) + 1
    for d, n in counts.items():
        weekday_counts[d.weekday()].append(n)
    weekday_avg = {k:(sum(v)/len(v) if v else 0.0) for k,v in weekday_counts.items()}
    avg = sum(counts.values()) / max(1, len(counts))
    future = [date.today()+timedelta(days=i) for i in range(1, int(days_ahead)+1)]
    forecast = sum((weekday_avg[d.weekday()] if weekday_avg[d.weekday()] > 0 else avg) for d in future)
    names = ["lunes","martes","miércoles","jueves","viernes","sábado","domingo"]
    peak = max(weekday_avg, key=weekday_avg.get)
    return {"total":round(forecast),"daily_average":round(forecast/max(1,days_ahead),2),
            "peak_weekday":names[peak],"peak_count":round(weekday_avg[peak],2),
            "method":"Línea base estadística por día de semana; requiere más historial real para calibración."}

def calculate_kpis():
    reqs = rows("SELECT * FROM requests")
    resources = rows("SELECT * FROM resources WHERE active=1")
    assigned = [r for r in reqs if r["status"] == "Asignada"]
    total = len(reqs)
    coverage = 100*len(assigned)/total if total else 0
    available_hours = sum(max(0, int(r["close_time"][:2])-int(r["open_time"][:2])) for r in resources)*30
    used_hours = sum((int(r["end_time"][:2])*60+int(r["end_time"][3:])-int(r["start_time"][:2])*60-int(r["start_time"][3:]))/60 for r in assigned)
    utilization = min(100,100*used_hours/available_hours) if available_hours else 0
    conflicts = 0
    for i,a in enumerate(assigned):
        for b in assigned[i+1:]:
            if a["assigned_resource_id"] == b["assigned_resource_id"] and a["date"] == b["date"] and overlapping(a["start_time"],a["end_time"],b["start_time"],b["end_time"]):
                conflicts += 1
    conflict_rate = 100*conflicts/max(1,len(assigned))
    # Equidad: diferencia absoluta de atención entre solicitudes de prioridad alta y baja.
    high = [r for r in reqs if r["priority"] >= 60]
    low = [r for r in reqs if r["priority"] < 60]
    rate_high = sum(r["status"]=="Asignada" for r in high)/len(high)*100 if high else 0
    rate_low = sum(r["status"]=="Asignada" for r in low)/len(low)*100 if low else 0
    equity_gap = abs(rate_high-rate_low)
    pending = sum(r["status"]=="Pendiente" for r in reqs)
    no_attended = sum(r["status"]=="No atendida" for r in reqs)
    # El tiempo manual es una hipótesis de piloto editable; no se presenta como resultado observado.
    timing = one("SELECT AVG(runtime_ms) AS avg_ms FROM assignment_results WHERE runtime_ms > 0")
    avg_runtime = timing["avg_ms"] if timing and timing["avg_ms"] is not None else None
    return [
        {"KPI":"Cobertura de solicitudes","Valor":f"{coverage:.1f}%","Meta":"≥ 90%","Cumple":coverage>=90},
        {"KPI":"Utilización de recursos","Valor":f"{utilization:.1f}%","Meta":"≥ 80%","Cumple":utilization>=80},
        {"KPI":"Tasa de conflictos","Valor":f"{conflict_rate:.2f}%","Meta":"≤ 1%","Cumple":conflict_rate<=1},
        {"KPI":"Equidad de acceso","Valor":f"{equity_gap:.1f} p.p.","Meta":"≤ 10 p.p.","Cumple":equity_gap<=10},
        {"KPI":"Reducción de tiempo administrativo","Valor":"Pendiente de línea base","Meta":"≥ 50%","Cumple":False},
        {"KPI":"Tiempo de asignación","Valor":f"{avg_runtime:.2f} ms" if avg_runtime is not None else "Pendiente de medición","Meta":"≤ 2 s","Cumple":(avg_runtime is not None and avg_runtime <= 2000)},
        {"KPI":"Violaciones de restricciones","Valor":str(conflicts),"Meta":"0","Cumple":conflicts==0},
        {"KPI":"Utilización CPU/memoria","Valor":"No medida en esta vista","Meta":"≤ 80%","Cumple":False},
        {"KPI":"Escalabilidad","Valor":f"{total} solicitudes / {len(resources)} recursos","Meta":"Crecimiento controlado","Cumple":True},
        {"KPI":"Precisión de demanda","Valor":"MAPE no calculable sin predicciones guardadas","Meta":"MAPE ≤ 20%","Cumple":False},
    ]

def database_snapshot():
    resources = rows("SELECT id,name,category,capacity,features,location,open_time,close_time,active FROM resources")
    requests = rows("""SELECT q.id,q.activity,q.description,q.date,q.start_time,q.end_time,q.attendees,q.preferred_category,
                       q.status,q.priority,q.priority_reason,u.name AS user_name,r.name AS resource_name
                       FROM requests q JOIN users u ON q.user_id=u.id LEFT JOIN resources r ON q.assigned_resource_id=r.id
                       ORDER BY q.date DESC,q.start_time LIMIT 120""")
    users = rows("SELECT id,name,role,active FROM users")
    return {"resources":resources,"requests":requests,"users":users,"forecast":predict_demand(30)}

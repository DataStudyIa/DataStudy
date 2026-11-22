from datetime import date, timedelta, datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from db import (
    init_db, authenticate, create_user, update_user, rows, add_resource,
    update_resource, get_rules, save_rules, insert_request, delete_request,
    demo_data
)
from services import compute_priority, run_assignment, predict_demand, calculate_kpis, database_snapshot
from ai_chatbot import ask_ai

app = Flask(__name__)
app.secret_key = "DataStudy-demo-secret-change-in-production"
init_db()

CSS = """
<style>
body{margin:0;font-family:Arial,Helvetica,sans-serif;background:#f4f6fb;color:#1f2937}
header{background:linear-gradient(115deg,#1c347e,#5541a5);color:white;padding:22px 34px}
header h1{margin:0;font-size:30px} header p{margin:5px 0 0;color:#e9eaff}
nav{background:#fff;border-bottom:1px solid #ddd;padding:10px 24px;display:flex;gap:8px;flex-wrap:wrap}
nav a{padding:9px 12px;border-radius:8px;text-decoration:none;color:#243b7a;font-weight:600}
nav a:hover{background:#eef1ff}.container{max-width:1400px;margin:24px auto;padding:0 20px}
.card{background:white;border:1px solid #e2e6ef;border-radius:14px;padding:20px;margin-bottom:18px;box-shadow:0 2px 8px rgba(20,30,60,.04)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
.metric{font-size:28px;font-weight:700;color:#2447a8}.muted{color:#6b7280}
input,select,textarea{width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccd2df;border-radius:8px;margin:5px 0 12px}
textarea{min-height:90px}button,.btn{background:#2447a8;color:white;border:0;border-radius:8px;padding:10px 15px;cursor:pointer;text-decoration:none;display:inline-block}
.btn.secondary{background:#667085}.btn.danger{background:#b42318}.btn.green{background:#13795b}
table{width:100%;border-collapse:collapse;background:white}th,td{padding:9px;border-bottom:1px solid #e6e9ef;text-align:left;font-size:14px}th{background:#f5f7fb}
.alert{padding:12px;border-radius:9px;background:#eef4ff;margin:12px 0}.error{background:#fff0f0;color:#a21d1d}.success{background:#edf9f2;color:#12623f}
.badge{padding:4px 8px;border-radius:999px;background:#eef1ff;font-size:12px}
.bar{height:24px;background:#e6e9f2;border-radius:6px;overflow:hidden;margin:5px 0 14px}.bar span{display:block;height:100%;background:#4c63c7}
.chat{max-width:900px}.msg{padding:12px 15px;border-radius:12px;margin:9px 0;white-space:pre-wrap}.user{background:#e9efff;margin-left:15%}.assistant{background:#fff;border:1px solid #ddd;margin-right:15%}
.login{max-width:900px;margin:50px auto}.two{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:800px){.two{grid-template-columns:1fr}}
small{color:#667085}
</style>
"""

BASE = """
<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}} | DataStudy</title>""" + CSS + """</head><body>
<header><h1>🎓 DataStudy</h1><p>Asignación inteligente de recursos educativos · ODS 4</p></header>
{% if user %}
<nav>
<a href="{{url_for('home')}}">Inicio</a><a href="{{url_for('chat')}}">🤖 Asistente IA</a>
<a href="{{url_for('resources')}}">Recursos</a><a href="{{url_for('new_request')}}">Solicitar recurso</a>
<a href="{{url_for('my_requests')}}">Mis solicitudes</a><a href="{{url_for('calendar')}}">Calendario</a>
<a href="{{url_for('kpis')}}">KPIs y predicción</a>
{% if user.role=='admin' %}<a href="{{url_for('admin')}}">Panel administrador</a>{% endif %}
<a href="{{url_for('logout')}}">Cerrar sesión</a>
</nav>{% endif %}
<div class="container">
{% with messages=get_flashed_messages(with_categories=true) %}
{% for cat,msg in messages %}<div class="alert {{'error' if cat=='error' else 'success' if cat=='success' else ''}}">{{msg}}</div>{% endfor %}
{% endwith %}
{{body|safe}}
</div></body></html>
"""

def page(title, body, **ctx):
    return render_template_string(BASE, title=title, body=body, **ctx)

def current_user():
    uid=session.get("user_id")
    if not uid: return None
    r=rows("SELECT id,name,email,role,active FROM users WHERE id=?",(uid,))
    return r[0] if r else None

def require_login():
    u=current_user()
    if not u:
        return redirect(url_for("login"))
    return u

@app.route("/")
def root():
    return redirect(url_for("home") if current_user() else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=authenticate(request.form.get("email",""),request.form.get("password",""))
        if u:
            session["user_id"]=u["id"]; return redirect(url_for("home"))
        flash("Correo o contraseña incorrectos, o usuario inactivo.","error")
    body="""<div class="login"><div class="card">
<h2>🎓 Iniciar sesión</h2><p class="muted">DataStudy · asignación inteligente y equitativa.</p>
<form method="post"><label>Correo</label><input name="email" type="email" required>
<label>Contraseña</label><input name="password" type="password" required><button>Ingresar</button></form>
<div class="alert"><b>Demo:</b><br>Administrador: admin@datastudy.local / Admin123!<br>
Usuario: estudiante@datastudy.local / Estudiante123!</div>
<p>¿No tienes cuenta? <a href="/register">Crear cuenta</a></p></div></div>"""
    return page("Iniciar sesión",body,user=current_user())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip()
        pw=request.form.get("password",""); pw2=request.form.get("password2","")
        if not name or "@" not in email or len(pw)<8 or pw!=pw2:
            flash("Verifica nombre, correo y contraseña (mínimo 8 caracteres).","error")
        else:
            try:
                create_user(name,email,pw,"usuario"); flash("Cuenta creada. Ya puedes iniciar sesión.","success"); return redirect(url_for("login"))
            except Exception: flash("No se pudo crear la cuenta; el correo puede estar registrado.","error")
    body="""<div class="login"><div class="card"><h2>Crear cuenta</h2><form method="post">
<label>Nombre</label><input name="name" required><label>Correo</label><input name="email" type="email" required>
<label>Contraseña</label><input name="password" type="password" minlength="8" required>
<label>Repite la contraseña</label><input name="password2" type="password" minlength="8" required>
<button>Crear cuenta</button></form><p><a href="/login">Volver</a></p></div></div>"""
    return page("Registro",body,user=current_user())

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/home")
def home():
    u=require_login()
    if not isinstance(u,dict) and not hasattr(u,"keys"): return u
    reqs=rows("SELECT * FROM requests"); resources=rows("SELECT * FROM resources WHERE active=1")
    assigned=sum(r["status"]=="Asignada" for r in reqs); pending=sum(r["status"]=="Pendiente" for r in reqs)
    upcoming=rows("""SELECT q.date AS Fecha,q.start_time AS Inicio,q.end_time AS Fin,q.activity AS Actividad,
        r.name AS Recurso,u.name AS Usuario,q.status AS Estado FROM requests q JOIN users u ON u.id=q.user_id
        LEFT JOIN resources r ON r.id=q.assigned_resource_id WHERE q.date>=? ORDER BY q.date,q.start_time LIMIT 8""",(str(date.today()),))
    rows_html="".join(f"<tr><td>{x['Fecha']}</td><td>{x['Inicio']}</td><td>{x['Fin']}</td><td>{x['Actividad']}</td><td>{x['Recurso'] or '-'}</td><td>{x['Estado']}</td></tr>" for x in upcoming)
    body=f"""<div class="card"><h2>Hola, {u['name']} 👋</h2><p>Recursos educativos mejor distribuidos para apoyar el ODS 4.</p></div>
<div class="grid"><div class="card"><div class="metric">{len(resources)}</div><b>Recursos activos</b></div>
<div class="card"><div class="metric">{len(reqs)}</div><b>Solicitudes registradas</b></div>
<div class="card"><div class="metric">{assigned}</div><b>Asignadas</b></div><div class="card"><div class="metric">{pending}</div><b>Pendientes</b></div></div>
<div class="two"><div class="card"><h3>🔎 Explorar</h3><p>Busca recursos por categoría, capacidad, características y horario.</p></div>
<div class="card"><h3>🤖 Preguntar</h3><p>Formula preguntas en lenguaje natural sobre recursos, demanda, reservas y KPIs.</p></div></div>
<div class="card"><h3>Próximas asignaciones</h3>
{"<table><tr><th>Fecha</th><th>Inicio</th><th>Fin</th><th>Actividad</th><th>Recurso</th><th>Estado</th></tr>"+rows_html+"</table>" if upcoming else "<p class='muted'>Todavía no hay solicitudes futuras.</p>"}</div>"""
    return page("Inicio",body,user=u)

@app.route("/resources")
def resources():
    u=require_login()
    if not hasattr(u,"keys"): return u
    cat=request.args.get("category","Todas"); mincap=int(request.args.get("mincap","1") or 1)
    allr=rows("SELECT * FROM resources WHERE active=1 ORDER BY category,name")
    cats=sorted({r["category"] for r in allr}); filtered=[r for r in allr if (cat=="Todas" or r["category"]==cat) and int(r["capacity"])>=mincap]
    options="".join(f"<option {'selected' if c==cat else ''}>{c}</option>" for c in ["Todas"]+cats)
    trs="".join(f"<tr><td>{r['name']}</td><td>{r['category']}</td><td>{r['capacity']}</td><td>{r['features']}</td><td>{r['location']}</td><td>{r['open_time']}–{r['close_time']}</td></tr>" for r in filtered)
    body=f"""<div class="card"><h2>Recursos disponibles</h2><form method="get"><div class="two"><div><label>Categoría</label><select name="category">{options}</select></div>
<div><label>Capacidad mínima</label><input name="mincap" type="number" min="1" value="{mincap}"></div></div><button>Filtrar</button></form></div>
<div class="card"><table><tr><th>Nombre</th><th>Categoría</th><th>Capacidad</th><th>Características</th><th>Ubicación</th><th>Horario</th></tr>{trs}</table></div>"""
    return page("Recursos",body,user=u)

@app.route("/request",methods=["GET","POST"])
def new_request():
    u=require_login()
    if not hasattr(u,"keys"): return u
    if request.method=="POST":
        activity=request.form.get("activity","").strip(); desc=request.form.get("description","").strip()
        day=request.form.get("date",""); start=request.form.get("start",""); end=request.form.get("end","")
        attendees=int(request.form.get("attendees","1")); category=request.form.get("category","Cualquiera")
        if not activity or not day or start>=end: flash("Completa la actividad, fecha y un intervalo válido.","error")
        else:
            d=date.fromisoformat(day); priority,reason=compute_priority(activity,desc,d,attendees,get_rules())
            rid=insert_request(u["id"],activity,desc,d,start,end,attendees,category,priority,reason)
            flash(f"Solicitud #{rid} registrada. Prioridad calculada: {priority:.1f}/100.","success")
            return redirect(url_for("my_requests"))
    cats=sorted({r["category"] for r in rows("SELECT category FROM resources WHERE active=1")})
    catopts="".join(f"<option>{c}</option>" for c in ["Cualquiera"]+cats)
    times="".join(f"<option>{h:02d}:00</option>" for h in range(7,22))
    body=f"""<div class="card"><h2>Registrar una solicitud</h2><p class="muted">La prioridad se calcula automáticamente según los criterios configurados por administración.</p>
<form method="post"><label>Actividad</label><input name="activity" placeholder="Ej. Proyecto de programación" required>
<label>Detalles</label><textarea name="description" placeholder="Software, equipos, materiales o condiciones"></textarea>
<div class="two"><div><label>Fecha</label><input name="date" type="date" min="{date.today()}" value="{date.today()+timedelta(days=1)}" required></div>
<div><label>Estudiantes</label><input name="attendees" type="number" min="1" max="500" value="4" required></div></div>
<div class="two"><div><label>Hora de inicio</label><select name="start">{times}</select></div><div><label>Hora de finalización</label><select name="end">{times}</select></div></div>
<label>Categoría preferida</label><select name="category">{catopts}</select><br><button>Registrar solicitud</button></form></div>"""
    return page("Solicitar recurso",body,user=u)

@app.route("/my-requests")
def my_requests():
    u=require_login()
    if not hasattr(u,"keys"): return u
    mine=rows("""SELECT q.id AS ID,q.activity AS Actividad,q.date AS Fecha,q.start_time AS Inicio,q.end_time AS Fin,
    q.attendees AS Estudiantes,q.preferred_category AS Categoria,q.priority AS Prioridad,q.status AS Estado,
    r.name AS Recurso,q.priority_reason AS Motivo FROM requests q LEFT JOIN resources r ON r.id=q.assigned_resource_id
    WHERE q.user_id=? ORDER BY q.date DESC,q.start_time DESC""",(u["id"],))
    trs="".join(f"<tr><td>{r['ID']}</td><td>{r['Actividad']}</td><td>{r['Fecha']}</td><td>{r['Inicio']}–{r['Fin']}</td><td>{r['Estudiantes']}</td><td>{r['Prioridad']:.1f}</td><td>{r['Estado']}</td><td>{r['Recurso'] or '-'}</td></tr>" for r in mine)
    pending=rows("SELECT id,activity,date FROM requests WHERE user_id=? AND status='Pendiente'",(u["id"],))
    opts="".join(f"<option value='{r['id']}'>#{r['id']} · {r['activity']} · {r['date']}</option>" for r in pending)
    cancel=f"<form method='post' action='/cancel'><select name='id'>{opts}</select><button class='btn danger'>Cancelar solicitud</button></form>" if pending else ""
    body=f"""<div class="card"><h2>Mis solicitudes</h2>{"<table><tr><th>ID</th><th>Actividad</th><th>Fecha</th><th>Horario</th><th>Estudiantes</th><th>Prioridad</th><th>Estado</th><th>Recurso</th></tr>"+trs+"</table>" if mine else "<p>No tienes solicitudes.</p>"}</div>
<div class="card"><h3>Cancelar una solicitud pendiente</h3>{cancel or "<p class='muted'>No tienes solicitudes pendientes para cancelar.</p>"}</div>"""
    return page("Mis solicitudes",body,user=u)

@app.post("/cancel")
def cancel():
    u=require_login()
    if not hasattr(u,"keys"): return u
    delete_request(int(request.form["id"]),u["id"]); flash("Solicitud cancelada.","success"); return redirect(url_for("my_requests"))

@app.route("/calendar")
def calendar():
    u=require_login()
    if not hasattr(u,"keys"): return u
    chosen=request.args.get("date",str(date.today())); prefix=request.args.get("month",chosen[:7])
    base="""SELECT q.id AS ID,q.date AS Fecha,q.start_time AS Inicio,q.end_time AS Fin,q.activity AS Actividad,
    u.name AS Persona,r.name AS Recurso,q.attendees AS Estudiantes,q.status AS Estado,q.priority AS Prioridad
    FROM requests q JOIN users u ON u.id=q.user_id LEFT JOIN resources r ON r.id=q.assigned_resource_id"""
    data=rows(base+" WHERE q.date=? ORDER BY q.start_time",(chosen,))
    monthdata=rows(base+" WHERE substr(q.date,1,7)=? ORDER BY q.date,q.start_time",(prefix,))
    def table(ds):
        return "<table><tr><th>ID</th><th>Fecha</th><th>Inicio</th><th>Fin</th><th>Actividad</th><th>Persona</th><th>Recurso</th><th>Estado</th></tr>"+ "".join(f"<tr><td>{x['ID']}</td><td>{x['Fecha']}</td><td>{x['Inicio']}</td><td>{x['Fin']}</td><td>{x['Actividad']}</td><td>{x['Persona']}</td><td>{x['Recurso'] or '-'}</td><td>{x['Estado']}</td></tr>" for x in ds)+"</table>"
    body=f"""<div class="card"><h2>Calendario y reservas</h2><form method="get"><div class="two"><div><label>Fecha</label><input type="date" name="date" value="{chosen}"></div>
<div><label>Mes (AAAA-MM)</label><input name="month" value="{prefix}" pattern="\\d{{4}}-\\d{{2}}"></div></div><button>Consultar</button></form></div>
<div class="card"><h3>Solicitudes de {chosen}</h3>{table(data) if data else "<p>No hay solicitudes para esa fecha.</p>"}</div>
<div class="card"><h3>Solicitudes del mes {prefix}</h3>{table(monthdata) if monthdata else "<p>No hay solicitudes en ese mes.</p>"}</div>"""
    return page("Calendario",body,user=u)

@app.route("/chat",methods=["GET","POST"])
def chat():
    u=require_login()
    if not hasattr(u,"keys"): return u
    history=session.get("chat_history",[])
    if request.method=="POST":
        q=request.form.get("question","").strip()
        if q:
            try: answer=ask_ai(q,history,database_snapshot())
            except Exception as e: answer=f"No pude consultar el modelo de IA. {e}"
            history.extend([{"role":"user","content":q},{"role":"assistant","content":answer}]); session["chat_history"]=history[-16:]
    msgs="".join(f"<div class='msg user'><b>Tú:</b><br>{m['content']}</div>" if m["role"]=="user" else f"<div class='msg assistant'><b>DataStudy IA:</b><br>{m['content']}</div>" for m in history)
    body=f"""<div class="card chat"><h2>🤖 DataStudy IA</h2><p>Pregunta libremente sobre recursos, demanda, solicitudes, prioridades, restricciones o KPIs.</p>{msgs}
<form method="post"><textarea name="question" placeholder="Ej. ¿Qué recurso me recomiendas para 20 estudiantes durante dos horas?" required></textarea><button>Preguntar a la IA</button></form>
<br><a class="btn secondary" href="/chat/clear">Limpiar conversación</a></div>"""
    return page("Asistente IA",body,user=u)

@app.route("/chat/clear")
def chat_clear():
    session["chat_history"]=[]; return redirect(url_for("chat"))

@app.route("/kpis")
def kpis():
    u=require_login()
    if not hasattr(u,"keys"): return u
    horizon=int(request.args.get("horizon","30")); category=request.args.get("category","Todas")
    cats=["Todas"]+sorted({r["preferred_category"] for r in rows("SELECT DISTINCT preferred_category FROM requests") if r["preferred_category"]})
    if category not in cats: category="Todas"
    forecast=predict_demand(horizon,category); ks=calculate_kpis()
    metrics="".join(f"<div class='card'><div class='metric'>{k['Valor']}</div><b>{k['KPI']}</b><p>Meta: {k['Meta']} · {'Cumple' if k['Cumple'] else 'Pendiente/no cumple'}</p></div>" for k in ks)
    status=rows("SELECT status AS Estado,COUNT(*) AS Cantidad FROM requests GROUP BY status")
    bars="".join(f"<div><b>{x['Estado']}: {x['Cantidad']}</b><div class='bar'><span style='width:{min(100,int(x['Cantidad']*100/max(1,sum(y['Cantidad'] for y in status))))}%'></span></div></div>" for x in status)
    opts="".join(f"<option {'selected' if c==category else ''}>{c}</option>" for c in cats)
    body=f"""<div class="card"><h2>KPIs del proyecto</h2><p class="muted">Las metas son criterios propuestos para evaluar el piloto. Los datos de demostración son sintéticos.</p></div>
<div class="grid">{metrics}</div><div class="card"><h2>Predicción de demanda</h2><form method="get"><div class="two"><div><label>Horizonte</label><select name="horizon">{''.join(f"<option {'selected' if horizon==h else ''}>{h}</option>" for h in [7,14,30,60,90])}</select></div><div><label>Categoría</label><select name="category">{opts}</select></div></div><button>Calcular</button></form>
<div class="grid"><div><h3>{forecast['total']}</h3><small>Solicitudes estimadas</small></div><div><h3>{forecast['daily_average']}</h3><small>Promedio diario</small></div><div><h3>{forecast['peak_weekday'].title()}</h3><small>Mayor demanda histórica</small></div></div><p><b>Método:</b> {forecast['method']}</p></div>
<div class="card"><h2>Solicitudes por estado</h2>{bars or "<p>No hay datos.</p>"}</div>"""
    return page("KPIs y predicción",body,user=u)

@app.route("/admin",methods=["GET","POST"])
def admin():
    u=require_login()
    if not hasattr(u,"keys"): return u
    if u["role"]!="admin": flash("No tienes permisos de administrador.","error"); return redirect(url_for("home"))
    action=request.form.get("action") if request.method=="POST" else None
    try:
        if action=="add_resource":
            add_resource(request.form["name"],request.form["category"],int(request.form["capacity"]),request.form.get("features",""),request.form.get("location",""),request.form["open_time"],request.form["close_time"]); flash("Recurso agregado.","success")
        elif action=="update_resource":
            update_resource(int(request.form["id"]),request.form["name"],request.form["category"],int(request.form["capacity"]),request.form.get("features",""),request.form.get("location",""),request.form["open_time"],request.form["close_time"],"active" in request.form); flash("Recurso actualizado.","success")
        elif action=="create_user":
            create_user(request.form["name"],request.form["email"],request.form["password"],request.form["role"]); flash("Usuario creado.","success")
        elif action=="priority":
            save_rules(float(request.form["urgency"]),float(request.form["attendees"]),float(request.form["academic"])); flash("Criterios de prioridad guardados.","success")
        elif action=="assign":
            r=run_assignment(); flash(f"Procesadas: {r['processed']} · Asignadas: {r['assigned']} · No atendidas: {r['rejected']} · Tiempo: {r['runtime_ms']} ms","success")
        elif action=="demo":
            n=demo_data(); flash(f"Se agregaron {n} solicitudes sintéticas." if n else "Ya hay solicitudes; no se duplicó el historial.","success")
    except Exception as e: flash(f"No se pudo completar la operación: {e}","error")
    rs=rows("SELECT * FROM resources ORDER BY id"); us=rows("SELECT id,name,email,role,active FROM users ORDER BY id"); rules=get_rules()
    pend=rows("SELECT id,activity,date,start_time,end_time,attendees,priority FROM requests WHERE status='Pendiente' ORDER BY priority DESC")
    allq=rows("""SELECT q.id,q.activity,q.date,q.start_time,q.end_time,q.attendees,q.priority,q.status,r.name resource
                 FROM requests q LEFT JOIN resources r ON r.id=q.assigned_resource_id ORDER BY q.date DESC LIMIT 200""")
    rtrs="".join(f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['category']}</td><td>{r['capacity']}</td><td>{r['location']}</td><td>{'Sí' if r['active'] else 'No'}</td></tr>" for r in rs)
    utrs="".join(f"<tr><td>{x['id']}</td><td>{x['name']}</td><td>{x['email']}</td><td>{x['role']}</td><td>{'Sí' if x['active'] else 'No'}</td></tr>" for x in us)
    ptrs="".join(f"<tr><td>{x['id']}</td><td>{x['activity']}</td><td>{x['date']}</td><td>{x['start_time']}–{x['end_time']}</td><td>{x['attendees']}</td><td>{x['priority']:.1f}</td></tr>" for x in pend)
    qtrs="".join(f"<tr><td>{x['id']}</td><td>{x['activity']}</td><td>{x['date']}</td><td>{x['priority']:.1f}</td><td>{x['status']}</td><td>{x['resource'] or '-'}</td></tr>" for x in allq)
    body=f"""<div class="card"><h2>Panel administrador</h2><p>Gestión de recursos, usuarios, criterios de prioridad y motor de asignación.</p></div>
<div class="two"><div class="card"><h3>Agregar recurso</h3><form method="post"><input type="hidden" name="action" value="add_resource">
<label>Nombre</label><input name="name" required><label>Categoría</label><input name="category" value="Laboratorio" required><label>Capacidad</label><input name="capacity" type="number" value="20" min="1">
<label>Características</label><input name="features"><label>Ubicación</label><input name="location"><div class="two"><input name="open_time" value="07:00"><input name="close_time" value="20:00"></div><button>Agregar</button></form></div>
<div class="card"><h3>Criterios de prioridad</h3><form method="post"><input type="hidden" name="action" value="priority">
<label>Urgencia</label><input name="urgency" type="number" step="0.05" min="0" max="1" value="{rules['urgency_weight']}">
<label>Tamaño del grupo</label><input name="attendees" type="number" step="0.05" min="0" max="1" value="{rules['attendees_weight']}">
<label>Necesidad académica</label><input name="academic" type="number" step="0.05" min="0" max="1" value="{rules['academic_weight']}"><button>Guardar criterios</button></form></div></div>
<div class="card"><h3>Motor de asignación</h3><p>Solicitudes pendientes: <b>{len(pend)}</b>. Verifica categoría, capacidad, horario y solapamientos.</p>
<form method="post"><input type="hidden" name="action" value="assign"><button class="btn green">Ejecutar asignación automática</button></form>
{('<table><tr><th>ID</th><th>Actividad</th><th>Fecha</th><th>Horario</th><th>Estudiantes</th><th>Prioridad</th></tr>'+ptrs+'</table>') if pend else '<p>No hay solicitudes pendientes.</p>'}</div>
<div class="two"><div class="card"><h3>Usuarios</h3><form method="post"><input type="hidden" name="action" value="create_user"><input name="name" placeholder="Nombre" required><input name="email" placeholder="Correo" required><input name="password" type="password" placeholder="Contraseña" required><select name="role"><option>usuario</option><option>admin</option></select><button>Crear usuario</button></form><table><tr><th>ID</th><th>Nombre</th><th>Correo</th><th>Rol</th><th>Activo</th></tr>{utrs}</table></div>
<div class="card"><h3>Recursos</h3><table><tr><th>ID</th><th>Nombre</th><th>Categoría</th><th>Capacidad</th><th>Ubicación</th><th>Activo</th></tr>{rtrs}</table></div></div>
<div class="card"><h3>Solicitudes recientes</h3><table><tr><th>ID</th><th>Actividad</th><th>Fecha</th><th>Prioridad</th><th>Estado</th><th>Recurso</th></tr>{qtrs}</table>
<form method="post"><input type="hidden" name="action" value="demo"><button class="btn secondary">Generar historial sintético (404 si está vacío)</button></form></div>"""
    return page("Panel administrador",body,user=u)

if __name__=="__main__":
    app.run(host="127.0.0.1",port=8501,debug=False)

import sqlite3
import hashlib
import os
from pathlib import Path
from datetime import datetime, date, timedelta

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "datastudy.db"

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'usuario',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS resources(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            features TEXT DEFAULT '',
            location TEXT DEFAULT '',
            open_time TEXT NOT NULL DEFAULT '07:00',
            close_time TEXT NOT NULL DEFAULT '20:00',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activity TEXT NOT NULL,
            description TEXT DEFAULT '',
            date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            attendees INTEGER NOT NULL,
            preferred_category TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pendiente',
            priority REAL NOT NULL DEFAULT 0,
            priority_reason TEXT DEFAULT '',
            assigned_resource_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(assigned_resource_id) REFERENCES resources(id)
        );
        CREATE TABLE IF NOT EXISTS priority_rules(
            id INTEGER PRIMARY KEY CHECK(id=1),
            urgency_weight REAL NOT NULL DEFAULT 0.4,
            attendees_weight REAL NOT NULL DEFAULT 0.3,
            academic_weight REAL NOT NULL DEFAULT 0.3
        );
        CREATE TABLE IF NOT EXISTS assignment_results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            resource_id INTEGER,
            result TEXT NOT NULL,
            reason TEXT DEFAULT '',
            runtime_ms REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_id) REFERENCES requests(id),
            FOREIGN KEY(resource_id) REFERENCES resources(id)
        );
        """)
        c.execute("INSERT OR IGNORE INTO priority_rules(id,urgency_weight,attendees_weight,academic_weight) VALUES(1,0.4,0.3,0.3)")
        now = datetime.now().isoformat(timespec="seconds")
        c.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)",
                  ("Administradora DataStudy", "admin@datastudy.local", hash_password("Admin123!"), "admin", 1, now))
        c.execute("INSERT OR IGNORE INTO users(name,email,password_hash,role,active,created_at) VALUES(?,?,?,?,?,?)",
                  ("Estudiante Demo", "estudiante@datastudy.local", hash_password("Estudiante123!"), "usuario", 1, now))
        if c.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
            resources = [
                ("Laboratorio de informática 1","Laboratorio",30,"computadores, internet, software de programación","Bloque A - 201","07:00","20:00"),
                ("Sala de computadores 2","Computadores",24,"computadores, internet, software académico","Biblioteca - Piso 2","07:00","21:00"),
                ("Salón colaborativo 3","Salón",18,"tablero, mesas móviles, proyector","Bloque B - 105","08:00","19:00"),
                ("Kit de robótica educativa","Material",8,"robótica, sensores, microcontroladores","Laboratorio maker","09:00","17:00"),
                ("Tutoría de matemáticas","Tutoría",6,"tutor, cálculo, álgebra, acompañamiento","Centro de apoyo académico","08:00","18:00"),
                ("Sala de estudio grupal","Espacio de estudio",10,"mesas, tablero, tomas eléctricas","Biblioteca - Piso 1","07:00","22:00"),
                ("Laboratorio de electrónica","Laboratorio",20,"osciloscopio, protoboard, fuentes, electrónica","Bloque C - 302","08:00","18:00"),
            ]
            c.executemany("""INSERT INTO resources(name,category,capacity,features,location,open_time,close_time,active,created_at)
                             VALUES(?,?,?,?,?,?,?,1,?)""", [(*r, now) for r in resources])

def authenticate(email, password):
    with get_conn() as c:
        row = c.execute("SELECT * FROM users WHERE lower(email)=lower(?) AND password_hash=? AND active=1",
                        (email.strip(), hash_password(password))).fetchone()
        return dict(row) if row else None

def create_user(name, email, password, role="usuario"):
    with get_conn() as c:
        c.execute("INSERT INTO users(name,email,password_hash,role,active,created_at) VALUES(?,?,?,?,1,?)",
                  (name.strip(), email.strip().lower(), hash_password(password), role, datetime.now().isoformat(timespec="seconds")))

def update_user(user_id, name, email, role, active, password=None):
    with get_conn() as c:
        if password:
            c.execute("UPDATE users SET name=?,email=?,role=?,active=?,password_hash=? WHERE id=?",
                      (name.strip(), email.strip().lower(), role, int(active), hash_password(password), int(user_id)))
        else:
            c.execute("UPDATE users SET name=?,email=?,role=?,active=? WHERE id=?",
                      (name.strip(), email.strip().lower(), role, int(active), int(user_id)))

def rows(query, params=()):
    with get_conn() as c:
        return [dict(x) for x in c.execute(query, params).fetchall()]

def one(query, params=()):
    with get_conn() as c:
        x = c.execute(query, params).fetchone()
        return dict(x) if x else None

def add_resource(name, category, capacity, features, location, open_time, close_time):
    with get_conn() as c:
        c.execute("""INSERT INTO resources(name,category,capacity,features,location,open_time,close_time,active,created_at)
                     VALUES(?,?,?,?,?,?,?,1,?)""",
                  (name, category, int(capacity), features, location, open_time, close_time, datetime.now().isoformat(timespec="seconds")))

def update_resource(resource_id, name, category, capacity, features, location, open_time, close_time, active):
    with get_conn() as c:
        c.execute("""UPDATE resources SET name=?,category=?,capacity=?,features=?,location=?,open_time=?,close_time=?,active=?
                     WHERE id=?""",
                  (name, category, int(capacity), features, location, open_time, close_time, int(active), int(resource_id)))

def get_rules():
    return one("SELECT * FROM priority_rules WHERE id=1")

def save_rules(urgency, attendees, academic):
    total = urgency + attendees + academic
    if total <= 0:
        raise ValueError("La suma de los pesos debe ser mayor que cero.")
    with get_conn() as c:
        c.execute("UPDATE priority_rules SET urgency_weight=?,attendees_weight=?,academic_weight=? WHERE id=1",
                  (urgency/total, attendees/total, academic/total))

def insert_request(user_id, activity, description, day, start, end, attendees, category, priority, reason):
    with get_conn() as c:
        cur = c.execute("""INSERT INTO requests(user_id,activity,description,date,start_time,end_time,attendees,preferred_category,
                         status,priority,priority_reason,created_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (user_id, activity, description, str(day), start, end, int(attendees), category,
                         "Pendiente", float(priority), reason, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid

def update_request_status(request_id, status, resource_id=None, reason=""):
    with get_conn() as c:
        c.execute("UPDATE requests SET status=?,assigned_resource_id=? WHERE id=?", (status, resource_id, int(request_id)))
        c.execute("INSERT INTO assignment_results(request_id,resource_id,result,reason,created_at) VALUES(?,?,?,?,?)",
                  (int(request_id), resource_id, status, reason, datetime.now().isoformat(timespec="seconds")))

def delete_request(request_id, user_id=None):
    with get_conn() as c:
        if user_id is None:
            c.execute("DELETE FROM assignment_results WHERE request_id=?", (int(request_id),))
            c.execute("DELETE FROM requests WHERE id=?", (int(request_id),))
        else:
            c.execute("DELETE FROM requests WHERE id=? AND user_id=? AND status='Pendiente'", (int(request_id), int(user_id)))

def demo_data():
    """Genera historial sintético reproducible para probar predicción y KPIs."""
    import random
    random.seed(41)
    init_db()
    with get_conn() as c:
        if c.execute("SELECT COUNT(*) FROM requests").fetchone()[0] > 0:
            return 0
        users = c.execute("SELECT id FROM users WHERE role='usuario'").fetchall()
        resources = c.execute("SELECT id,category,capacity FROM resources WHERE active=1").fetchall()
        uid = users[0]["id"]
        categories = [r["category"] for r in resources]
        count = 0
        today = date.today()
        for back in range(1, 91):
            day = today - timedelta(days=back)
            daily_n = random.randint(1, 6) + (2 if day.weekday() in (1,2,3) else 0)
            for _ in range(daily_n):
                cat = random.choice(categories)
                start_hour = random.randint(8, 16)
                start = f"{start_hour:02d}:00"
                end = f"{start_hour+1:02d}:00"
                activity = random.choice(["Trabajo de programación","Proyecto de electrónica","Estudio grupal","Tutoría de cálculo","Práctica de robótica","Presentación académica"])
                attendees = random.randint(2, 20)
                status = random.choice(["Asignada","No atendida","Asignada","Asignada"])
                res = next((r for r in resources if r["category"] == cat and r["capacity"] >= attendees), None)
                c.execute("""INSERT INTO requests(user_id,activity,description,date,start_time,end_time,attendees,preferred_category,status,
                          priority,priority_reason,assigned_resource_id,created_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (uid, activity, "Registro histórico sintético para pruebas", str(day), start, end, attendees, cat,
                           status, random.randint(30,100), "Prioridad de demostración", res["id"] if status=="Asignada" and res else None,
                           datetime.now().isoformat(timespec="seconds")))
                count += 1
        return count

from db import init_db, demo_data
if __name__ == "__main__":
    init_db()
    n = demo_data()
    print("Base de datos inicializada.")
    print(f"Solicitudes históricas sintéticas agregadas: {n}")
    print("Nota: son datos ficticios para pruebas; no representan resultados institucionales reales.")

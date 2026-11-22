# DataStudy IA — asignación inteligente de recursos educativos

Prototipo académico alineado con el ODS 4. Implementa una arquitectura de tres capas:
1. **Entrada:** interfaz Streamlit, registro/inicio de sesión y formularios.
2. **Procesamiento:** chatbot generativo (OpenAI API), cálculo automático de prioridad, predictor estadístico de demanda y motor de asignación voraz.
3. **Persistencia:** base de datos SQLite con usuarios, recursos, solicitudes, reglas y resultados.

## Requisitos
- Windows 10/11
- Python 3.11 de 64 bits (usa `py -3.11` en los comandos)
- Conexión a Internet para el chatbot generativo
- No requiere `pandas`, `numpy` ni `scikit-learn`; esto evita la DLL de pandas que estaba siendo bloqueada por el Control de aplicaciones de Windows.
- Clave de OpenAI API para usar el chatbot (la API puede tener costes independientes de ChatGPT).

## Instalación en Windows / PowerShell
Abre PowerShell en la carpeta que contiene `app.py` y `requirements.txt` y ejecuta:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No es necesario activar el entorno virtual: los siguientes comandos usan su Python directamente y evitan conflictos con el Python de Microsoft Store.

## Configurar el chatbot de IA
1. Copia `.env.example` y nombra la copia `.env`.
2. Abre `.env` con VS Code o Bloc de notas.
3. En `OPENAI_API_KEY=` pega tu clave de API de OpenAI, sin comillas ni espacios. No compartas ni subas esa clave.
4. Guarda el archivo. Puedes cambiar `OPENAI_MODEL=gpt-5.5` si tu cuenta tiene acceso a otro modelo compatible con Responses API.

Ejemplo:
```env
OPENAI_API_KEY=tu_clave_real_aqui
OPENAI_MODEL=gpt-5.5
```
Obtén la clave en https://platform.openai.com/api-keys. La facturación de API es independiente de una suscripción de ChatGPT.

## Inicializar datos de demostración
Desde la carpeta del proyecto:

```powershell
.\.venv\Scripts\python.exe generate_demo_data.py
```

Esto crea datos sintéticos de 90 días para probar tendencias y KPIs. No son datos institucionales reales. El script no duplica el historial si ya hay solicitudes.

## Ejecutar la aplicación
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
El navegador se abrirá en `http://localhost:8501`. Si no se abre automáticamente, copia esa dirección en el navegador.

## Credenciales iniciales
- Administrador: `admin@datastudy.local` / `Admin123!`
- Usuario demo: `estudiante@datastudy.local` / `Estudiante123!`

Cambia las contraseñas antes de cualquier despliegue real. Para la demostración, crea usuarios nuevos desde el formulario de registro o desde Panel administrador.

**Importante para el equipo donde Windows bloquea DLL de pandas:** usa un entorno virtual nuevo con este proyecto. No reutilices el `.venv` anterior.

## Qué probar
1. Inicia sesión como administrador y revisa/crea recursos.
2. En **Panel administrador → Prioridades**, ajusta los pesos. El usuario no elige prioridad: el sistema la calcula.
3. Entra como usuario y registra solicitudes con distintas fechas, horarios, número de estudiantes y categorías.
4. Vuelve como administrador y ejecuta el motor de asignación. Se validan categoría, capacidad, horario y solapamientos.
5. Consulta **Calendario y reservas** por fecha, persona y mes.
6. Abre **Asistente IA** y pregunta libremente, por ejemplo:
   - “Necesito hacer un trabajo de programación para 20 estudiantes, ¿qué recurso me recomiendas?”
   - “¿Qué día de la semana tiene mayor demanda?”
   - “¿Cuántas solicitudes están pendientes?”
   - “Explícame cómo se calcula la prioridad.”
   - “¿Qué KPI no está cumpliendo la meta?”
7. Revisa **KPIs y predicción**.

## Módulos y límites del prototipo
- **Chatbot:** modelo generativo vía OpenAI Responses API, alimentado con un resumen actual de recursos, solicitudes, usuarios y pronóstico. Interpreta preguntas libres, pero no modifica reservas por su cuenta. Para reservar/cancelar se usan los formularios.
- **Predicción de demanda:** línea base estadística por día de semana, implementada con Python estándar y SQLite. No se debe describir como Random Forest ni como modelo supervisado entrenado. La metodología puede sustituirse por Random Forest cuando el entorno permita usar la biblioteca.
- **Asignación:** algoritmo voraz (greedy), ordena por prioridad calculada por el sistema y valida restricciones duras. Es una propuesta de asignación para un piloto, no un optimizador global matemáticamente exacto.
- **KPI:** se muestran las diez métricas solicitadas. Las metas son metas iniciales del paper. Algunas requieren instrumentación adicional o una línea base real (reducción de tiempo administrativo, CPU/memoria, MAPE), y por eso se marcan como pendientes/no medidas cuando corresponda.
- **Seguridad:** este es un prototipo académico. Antes de producción se requiere endurecer autenticación, política de contraseñas, auditoría, copias de seguridad y protección de datos.

## Estructura
```text
DataStudy_IA/
├── app.py
├── ai_chatbot.py
├── db.py
├── services.py
├── generate_demo_data.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```


## Versión web sin Streamlit/pandas

Esta versión utiliza **Flask** para la interfaz web. Se eliminó Streamlit porque Streamlit instala `pandas` como dependencia en este entorno y Windows estaba bloqueando una DLL de pandas mediante Control de aplicaciones. La interfaz conserva login, recursos, solicitudes, prioridad, asignación greedy, calendario, KPIs/predicción y chatbot IA.

Requisitos:
- Python 3.11
- Flask
- OpenAI
- python-dotenv
- SQLite (incluido en Python)

Instalación limpia:
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe generate_demo_data.py
.\.venv\Scripts\python.exe app.py
```

Abre `http://127.0.0.1:8501`.

Esta versión **no requiere pandas, numpy, scikit-learn ni Streamlit**.

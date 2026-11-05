import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import io
import json
import urllib.parse
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from sqlalchemy import create_engine, text

# ---------------- CONFIGURACIÓN DE PÁGINA ----------------
st.set_page_config(
    page_title="SN Grafica - Sistema de Gestión",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------- CONEXIÓN A BASE DE DATOS ULTRA RÁPIDA ----------------
DB_URL = st.secrets.get("DATABASE_URL", None) if hasattr(st, "secrets") else None

@st.cache_resource
def get_db_engine(url):
    if not url:
        return None
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=600
    )

if DB_URL:
    engine = get_db_engine(DB_URL)
    IS_POSTGRES = True
else:
    DB_NAME = "grafica.db"
    engine = None
    IS_POSTGRES = False

def run_query_raw(query, params=()):
    if IS_POSTGRES and engine:
        with engine.connect() as conn:
            p_dict = dict(enumerate(params)) if isinstance(params, (list, tuple)) else params
            return pd.read_sql_query(text(query), conn, params=p_dict)
    else:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

def run_execute_raw(query, params=()):
    if IS_POSTGRES and engine:
        with engine.connect() as conn:
            p_dict = dict(enumerate(params)) if isinstance(params, (list, tuple)) else params
            conn.execute(text(query), p_dict)
            conn.commit()
    else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        conn.close()
    st.cache_data.clear()

@st.cache_data(ttl=300, show_spinner=False)
def fetch_data_cached(query, params_tuple=()):
    return run_query_raw(query, params_tuple)

# ---------------- INICIALIZACIÓN Y MIGRACIONES ----------------
@st.cache_resource
def init_db_tables_cached():
    if IS_POSTGRES and engine:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS compras (
                    id SERIAL PRIMARY KEY,
                    factura TEXT,
                    proveedor TEXT,
                    fecha DATE,
                    producto TEXT,
                    cantidad REAL DEFAULT 1,
                    precio_unitario REAL DEFAULT 0,
                    costo REAL
                );
                CREATE TABLE IF NOT EXISTS trabajos (
                    id SERIAL PRIMARY KEY,
                    fecha_carga DATE,
                    hora_carga TEXT,
                    fecha_entrega DATE,
                    cliente TEXT,
                    telefono TEXT,
                    tipo_trabajo TEXT,
                    taller_externo TEXT,
                    estado TEXT,
                    costo_material REAL,
                    precio_venta REAL,
                    sena REAL DEFAULT 0,
                    saldo REAL DEFAULT 0,
                    presupuesto_origen_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS presupuestos (
                    id SERIAL PRIMARY KEY,
                    fecha DATE,
                    cliente TEXT,
                    telefono TEXT,
                    tipo_trabajo TEXT,
                    detalle TEXT,
                    cantidad REAL,
                    precio_unitario REAL,
                    precio_total REAL,
                    costo_material REAL,
                    estado TEXT
                );
                CREATE TABLE IF NOT EXISTS boletas (
                    id SERIAL PRIMARY KEY,
                    fecha DATE,
                    cliente TEXT,
                    telefono TEXT,
                    detalle TEXT,
                    metodo_pago TEXT,
                    total REAL,
                    sena REAL,
                    saldo REAL
                );
                CREATE TABLE IF NOT EXISTS insumos (
                    id SERIAL PRIMARY KEY,
                    nombre TEXT UNIQUE,
                    unidad TEXT,
                    costo_unitario REAL,
                    multiplicador_sugerido REAL
                );
                CREATE TABLE IF NOT EXISTS configuracion (
                    clave TEXT PRIMARY KEY,
                    valor TEXT
                );
                CREATE TABLE IF NOT EXISTS tipos_trabajo (
                    id SERIAL PRIMARY KEY,
                    nombre TEXT UNIQUE
                );
            """))
            
            columnas_migracion = [
                "ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS sena REAL DEFAULT 0;",
                "ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS saldo REAL DEFAULT 0;",
                "ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS presupuesto_origen_id INTEGER;",
                "ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS hora_carga TEXT;",
                "ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS telefono TEXT;",
                "ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS taller_externo TEXT;",
                "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS costo_material REAL DEFAULT 0;",
                "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS telefono TEXT;",
                "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS estado TEXT DEFAULT 'Pendiente';",
                "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS cantidad REAL DEFAULT 1;",
                "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS precio_unitario REAL DEFAULT 0;",
                "ALTER TABLE presupuestos ADD COLUMN IF NOT EXISTS precio_total REAL DEFAULT 0;",
                "ALTER TABLE boletas ADD COLUMN IF NOT EXISTS metodo_pago TEXT;",
                "ALTER TABLE compras ADD COLUMN IF NOT EXISTS cantidad REAL DEFAULT 1;",
                "ALTER TABLE compras ADD COLUMN IF NOT EXISTS precio_unitario REAL DEFAULT 0;"
            ]
            for col_sql in columnas_migracion:
                try: conn.execute(text(col_sql))
                except Exception: pass
            conn.commit()
    else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id INTEGER PRIMARY KEY AUTOINCREMENT, factura TEXT, proveedor TEXT, fecha DATE, producto TEXT, cantidad REAL DEFAULT 1, precio_unitario REAL DEFAULT 0, costo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS trabajos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_carga DATE, hora_carga TEXT, fecha_entrega DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, taller_externo TEXT, estado TEXT, costo_material REAL, precio_venta REAL, sena REAL DEFAULT 0, saldo REAL DEFAULT 0, presupuesto_origen_id INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS presupuestos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, detalle TEXT, cantidad REAL, precio_unitario REAL, precio_total REAL, costo_material REAL, estado TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS boletas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, detalle TEXT, metodo_pago TEXT, total REAL, sena REAL, saldo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS insumos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, unidad TEXT, costo_unitario REAL, multiplicador_sugerido REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS tipos_trabajo (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
        
        columnas_sqlite = [
            "ALTER TABLE trabajos ADD COLUMN sena REAL DEFAULT 0",
            "ALTER TABLE trabajos ADD COLUMN saldo REAL DEFAULT 0",
            "ALTER TABLE trabajos ADD COLUMN presupuesto_origen_id INTEGER",
            "ALTER TABLE trabajos ADD COLUMN hora_carga TEXT",
            "ALTER TABLE trabajos ADD COLUMN telefono TEXT",
            "ALTER TABLE trabajos ADD COLUMN taller_externo TEXT",
            "ALTER TABLE presupuestos ADD COLUMN costo_material REAL DEFAULT 0",
            "ALTER TABLE presupuestos ADD COLUMN telefono TEXT",
            "ALTER TABLE presupuestos ADD COLUMN estado TEXT DEFAULT 'Pendiente'",
            "ALTER TABLE boletas ADD COLUMN metodo_pago TEXT",
            "ALTER TABLE compras ADD COLUMN cantidad REAL DEFAULT 1",
            "ALTER TABLE compras ADD COLUMN precio_unitario REAL DEFAULT 0"
        ]
        for col_sq in columnas_sqlite:
            try: cursor.execute(col_sq)
            except Exception: pass
        conn.commit()
        conn.close()

    configs_defecto = {
        "titulo_app": "SN Grafica",
        "subtitulo_app": "Sistema integral de gestión de producción, cotizaciones y balance",
        "telefono_empresa": "",
        "direccion_empresa": "",
        "mensaje_pie": "Presupuesto válido por 15 días. Documento no válido como factura fiscal.",
        "simbolo_moneda": "$",
        "alias_bancario": "SNGRAFICA.MP",
        "cbu_bancario": "",
        "titular_cuenta": "SN Grafica",
        "mensaje_wsp_custom": "Hola, Tu pedido {trabajo} está listo! el total es ${total} Gracias!"
    }
    for k, v in configs_defecto.items():
        if IS_POSTGRES:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO configuracion (clave, valor) VALUES (:k, :v) ON CONFLICT (clave) DO NOTHING"), {"k": k, "v": v})
                conn.commit()
        else:
            run_execute_raw("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (k, v))
    
    tipos_base = ["Cartelería / Lona", "Stickers / Vinilo de Corte", "Impresión UV / Rígidos", "Sublimación / Textil", "Diseño Gráfico", "Plotter Vehicular", "Varios"]
    for tipo in tipos_base:
        if IS_POSTGRES:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO tipos_trabajo (nombre) VALUES (:n) ON CONFLICT (nombre) DO NOTHING"), {"n": tipo})
                conn.commit()
        else:
            run_execute_raw("INSERT OR IGNORE INTO tipos_trabajo (nombre) VALUES (?)", (tipo,))
    return True

init_db_tables_cached()

@st.cache_data(ttl=600, show_spinner=False)
def get_all_configs():
    try:
        df = fetch_data_cached("SELECT clave, valor FROM configuracion")
        if not df.empty:
            return dict(zip(df['clave'], df['valor']))
    except Exception:
        pass
    return {}

config_map = get_all_configs()
titulo_actual = config_map.get("titulo_app", "SN Grafica")
subtitulo_actual = config_map.get("subtitulo_app", "Sistema integral de gestión de producción, cotizaciones y balance")
tel_empresa = config_map.get("telefono_empresa", "")
dir_empresa = config_map.get("direccion_empresa", "")
pie_empresa = config_map.get("mensaje_pie", "Presupuesto válido por 15 días.")
moneda = config_map.get("simbolo_moneda", "$")
alias_banco = config_map.get("alias_bancario", "SNGRAFICA.MP")
cbu_banco = config_map.get("cbu_bancario", "")
titular_banco = config_map.get("titular_cuenta", "SN Grafica")
msg_wsp_template = config_map.get("mensaje_wsp_custom", "Hola, Tu pedido {trabajo} está listo! el total es ${total} Gracias!")

@st.cache_data(ttl=600, show_spinner=False)
def get_tipos_trabajo_cached():
    try:
        df = fetch_data_cached("SELECT nombre FROM tipos_trabajo ORDER BY nombre ASC")
        if not df.empty:
            return df['nombre'].tolist()
    except Exception:
        pass
    return ["Cartelería / Lona", "Stickers / Vinilo de Corte", "Impresión UV / Rígidos", "Sublimación / Textil", "Diseño Gráfico", "Plotter Vehicular", "Varios"]

tipos_actuales = get_tipos_trabajo_cached()

ESTADOS_TRABAJO = ["Pendiente", "En Taller Externo", "Listo para Armar", "Listo para Entrega", "Entregado y Cobrado"]
ESTADO_BADGES = {
    "Pendiente": "🔴 Pendiente",
    "En Taller Externo": "🟣 En Imprenta",
    "Listo para Armار": "🟡 Para Armar",
    "Listo para Entrega": "🟢 Listo Retiro",
    "Entregado y Cobrado": "🔵 Cobrado"
}

# ---------------- ESTILOS DARK MODE GLOBALES ORIGINALES ----------------
st.markdown("""
<style>
    :root, html, body {
        color-scheme: dark !important;
        background-color: #050508 !important;
    }
    #MainMenu, footer, header, .stDeployButton, [data-testid="stDecoration"], [data-testid="stHeader"] {
        display: none !important;
    }
    .stApp {
        background-color: #050508 !important;
        color: #f8fafc !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased !important;
    }
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1400px;
    }

    div[data-baseweb="select"] > div,
    div[data-baseweb="input"],
    .stSelectbox div[data-baseweb="select"] > div,
    .stTextInput div[data-baseweb="input"] {
        background-color: #111422 !important;
        color: #f8fafc !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        -webkit-text-fill-color: #f8fafc !important;
    }
    div[data-baseweb="select"] *,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div {
        color: #f8fafc !important;
        -webkit-text-fill-color: #f8fafc !important;
    }
    div[data-baseweb="input"] input,
    .stTextInput input {
        background-color: transparent !important;
        color: #f8fafc !important;
        -webkit-text-fill-color: #f8fafc !important;
    }
    div[data-baseweb="input"] input::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
    }

    label[data-testid="stWidgetLabel"] p,
    label p,
    div[data-testid="stWidgetLabel"] label,
    .stSelectbox label,
    .stTextInput label,
    .stNumberInput label,
    .stDateInput label {
        color: #cbd5e1 !important;
        -webkit-text-fill-color: #cbd5e1 !important;
        font-weight: 600 !important;
    }

    .top-nav div[data-testid="stButton"] > button {
        background-color: #161b26 !important;
        color: #e2e8f0 !important;
        -webkit-text-fill-color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 9999px !important;
        padding: 6px 14px !important;
        font-size: 13.5px !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
    }
    .top-nav div[data-testid="stButton"] > button:hover {
        background-color: #242d3d !important;
        border-color: #3b82f6 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    .top-nav div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #ef4444 0%, #f97316 100%) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: none !important;
        border-radius: 9999px !important;
        padding: 6px 16px !important;
        font-size: 13.5px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(239, 68, 68, 0.45) !important;
    }

    [data-testid="stDataFrame"] {
        color-scheme: dark !important;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #1e293b;
    }

    .badge-estado {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 11.5px;
        line-height: 1.2;
        -webkit-text-fill-color: currentColor !important;
    }
    .badge-pen { background-color: #3b0d19 !important; color: #fca5a5 !important; border: 1px solid #7f1d1d !important; }
    .badge-imp { background-color: #2e1065 !important; color: #d8b4fe !important; border: 1px solid #581c87 !important; }
    .badge-arm { background-color: #3a2204 !important; color: #fde047 !important; border: 1px solid #854d0e !important; }
    .badge-ret { background-color: #052e16 !important; color: #86efac !important; border: 1px solid #14532d !important; }
    .badge-cob { background-color: #082f49 !important; color: #7dd3fc !important; border: 1px solid #075985 !important; }

    .hero-container {
        text-align: center;
        padding: 14px 10px 18px 10px;
        margin-bottom: 12px;
    }
    .hero-title {
        font-size: 36px;
        font-weight: 800;
        letter-spacing: -1px;
        line-height: 1.15;
        margin-bottom: 5px;
        background: linear-gradient(90deg, #fef08a 0%, #60a5fa 50%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        font-size: 14px;
        color: #94a3b8;
        max-width: 650px;
        margin: 0 auto;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- FUNCIONES AUXILIARES Y PDF ----------------
def parse_items_json(detalle_raw, default_cant=1.0, default_pu=0.0):
    try:
        items = json.loads(detalle_raw)
        if isinstance(items, list) and len(items) > 0:
            return items
    except Exception:
        pass
    return [{"detalle": str(detalle_raw), "cantidad": default_cant, "precio_unitario": default_pu, "costo_material": 0.0}]

def generar_pdf_presupuesto(empresa, p_id, fecha, cliente, telefono, tipo, detalle_raw, cant_fallback, unitario_fallback, total, pie_txt_custom):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize

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

# ---------------- CONEXIÓN A BASE DE DATOS ----------------
DB_URL = st.secrets.get("DATABASE_URL", None) if hasattr(st, "secrets") else None

@st.cache_resource
def get_db_engine(url):
    if not url:
        return None
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=300)

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

@st.cache_data(ttl=60, show_spinner=False)
def fetch_data_cached(query, params_tuple=()):
    return run_query_raw(query, params_tuple)

# ---------------- INICIALIZACIÓN DE TABLAS ----------------
@st.cache_resource
def init_db_tables():
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
            try: conn.execute(text("ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS hora_carga TEXT;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS telefono TEXT;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS taller_externo TEXT;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS presupuesto_origen_id INTEGER;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE boletas ADD COLUMN IF NOT EXISTS metodo_pago TEXT;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE compras ADD COLUMN IF NOT EXISTS cantidad REAL DEFAULT 1;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE compras ADD COLUMN IF NOT EXISTS precio_unitario REAL DEFAULT 0;"))
            except Exception: pass
            conn.commit()
    else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id INTEGER PRIMARY KEY AUTOINCREMENT, factura TEXT, proveedor TEXT, fecha DATE, producto TEXT, cantidad REAL DEFAULT 1, precio_unitario REAL DEFAULT 0, costo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS trabajos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_carga DATE, hora_carga TEXT, fecha_entrega DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, taller_externo TEXT, estado TEXT, costo_material REAL, precio_venta REAL, presupuesto_origen_id INTEGER)")
        cursor.execute("CREATE TABLE IF NOT EXISTS presupuestos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, detalle TEXT, cantidad REAL, precio_unitario REAL, precio_total REAL, costo_material REAL, estado TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS boletas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, detalle TEXT, metodo_pago TEXT, total REAL, sena REAL, saldo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS insumos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, unidad TEXT, costo_unitario REAL, multiplicador_sugerido REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS tipos_trabajo (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
        try: cursor.execute("ALTER TABLE trabajos ADD COLUMN hora_carga TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE trabajos ADD COLUMN telefono TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE trabajos ADD COLUMN taller_externo TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE trabajos ADD COLUMN presupuesto_origen_id INTEGER")
        except Exception: pass
        try: cursor.execute("ALTER TABLE boletas ADD COLUMN metodo_pago TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE compras ADD COLUMN cantidad REAL DEFAULT 1")
        except Exception: pass
        try: cursor.execute("ALTER TABLE compras ADD COLUMN precio_unitario REAL DEFAULT 0")
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

init_db_tables()

@st.cache_data(ttl=120, show_spinner=False)
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

@st.cache_data(ttl=120, show_spinner=False)
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
    "Listo para Armar": "🟡 Para Armar",
    "Listo para Entrega": "🟢 Listo Retiro",
    "Entregado y Cobrado": "🔵 Cobrado"
}

# ---------------- ESTILOS RESPONSIVE DARK Y PÍLDORAS ----------------
st.markdown("""
<style>
    #MainMenu, footer, header, .stDeployButton, [data-testid="stDecoration"], [data-testid="stHeader"] {
        display: none !important;
    }
    .stApp {
        background-color: #050508 !important;
        color: #f8fafc !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1400px;
    }
    
    div.row-widget.stButton > button[kind="secondary"] {
        background-color: #111422 !important;
        color: #94a3b8 !important;
        -webkit-text-fill-color: #94a3b8 !important;
        border: 1px solid #1e293b !important;
        border-radius: 9999px !important;
        padding: 6px 12px !important;
        font-size: 13.5px !important;
        font-weight: 600 !important;
        transition: all 0.15s ease !important;
    }
    div.row-widget.stButton > button[kind="secondary"]:hover {
        background-color: #1e293b !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border-color: #3b82f6 !important;
    }
    
    div.row-widget.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: none !important;
        border-radius: 9999px !important;
        padding: 6px 14px !important;
        font-size: 13.5px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.45) !important;
    }

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
    @media (max-width: 768px) {
        .hero-title { font-size: 24px !important; }
    }
</style>
""", unsafe_allow_html=True)

# ---------------- FUNCIONES AUXILIARES Y PDF ----------------
def parse_presupuesto_items(detalle_raw, default_cant=1.0, default_pu=0.0):
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
    title_style = ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor("#1e3a8a"))
    sub_style = ParagraphStyle(name='SubStyle', fontName='Helvetica', fontSize=11, leading=14, textColor=colors.HexColor("#475569"))
    bold_style = ParagraphStyle(name='BoldStyle', fontName='Helvetica-Bold', fontSize=10, leading=13)
    normal_style = ParagraphStyle(name='NormalStyle', fontName='Helvetica', fontSize=10, leading=13)
    
    header_data = [[Paragraph(f"<b>{empresa}</b>", title_style), Paragraph(f"<b>PRESUPUESTO #{p_id:04d}</b><br/>Fecha: {fecha}", sub_style)]]
    t_header = Table(header_data, colWidths=[320, 220])
    t_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT'), ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#1e3a8a")), ('BOTTOMPADDING', (0,0), (-1,-1), 8)]))
    elements.append(t_header)
    elements.append(Spacer(1, 14))
    
    client_data = [
        [Paragraph("<b>Cliente:</b>", bold_style), Paragraph(str(cliente), normal_style), Paragraph("<b>Teléfono:</b>", bold_style), Paragraph(str(telefono), normal_style)],
        [Paragraph("<b>Rubro / Tipo:</b>", bold_style), Paragraph(str(tipo), normal_style), Paragraph("", normal_style), Paragraph("", normal_style)]
    ]
    t_client = Table(client_data, colWidths=[90, 200, 70, 180])
    t_client.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")), ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    elements.append(t_client)
    elements.append(Spacer(1, 14))
    
    items = parse_presupuesto_items(detalle_raw, cant_fallback, unitario_fallback)
    items_data = [[Paragraph("<b>Detalle / Especificaciones</b>", bold_style), Paragraph("<b>Cant.</b>", bold_style), Paragraph("<b>P. Unitario</b>", bold_style), Paragraph("<b>Total</b>", bold_style)]]
    
    for it in items:
        d_name = str(it.get("detalle", ""))
        c_val = float(it.get("cantidad", 1.0))
        pu_val = float(it.get("precio_unitario", 0.0))
        row_tot = c_val * pu_val
        items_data.append([
            Paragraph(d_name, normal_style),
            Paragraph(f"{c_val:,.0f}", normal_style),
            Paragraph(f"{moneda}{pu_val:,.2f}", normal_style),
            Paragraph(f"{moneda}{row_tot:,.2f}", bold_style)
        ])
        
    t_items = Table(items_data, colWidths=[280, 60, 100, 100])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3a8a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6)
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 14))
    
    total_data = [["", Paragraph(f"<b>TOTAL: {moneda}{total:,.2f}</b>", ParagraphStyle('Tot', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor("#1e3a8a"), alignment=2))]]
    t_tot = Table(total_data, colWidths=[340, 200])
    t_tot.setStyle(TableStyle([('BACKGROUND', (1,0), (1,0), colors.HexColor("#f1f5f9")), ('BOX', (1,0), (1,0), 1, colors.HexColor("#1e3a8a")), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    elements.append(t_tot)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"<font size='8' color='#64748b'>{pie_txt_custom}<br/>¡Gracias por consultarnos!</font>", ParagraphStyle('Pie', alignment=1)))
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def generar_pdf_boleta(empresa, b_id, fecha, cliente, telefono, detalle, total, sena, saldo, alias_b, cbu_b, titular_b, metodo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor("#15803d"))
    sub_style = ParagraphStyle(name='SubStyle', fontName='Helvetica', fontSize=11, leading=14, textColor=colors.HexColor("#475569"))
    bold_style = ParagraphStyle(name='BoldStyle', fontName='Helvetica-Bold', fontSize=10, leading=13)
    normal_style = ParagraphStyle(name='NormalStyle', fontName='Helvetica', fontSize=10, leading=13)
    
    header_data = [[Paragraph(f"<b>{empresa}</b>", title_style), Paragraph(f"<b>BOLETA DE PAGO #{b_id:04d}</b><br/>Fecha: {fecha}", sub_style)]]
    t_header = Table(header_data, colWidths=[320, 220])
    t_header.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT'), ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#15803d")), ('BOTTOMPADDING', (0,0), (-1,-1), 8)]))
    elements.append(t_header)
    elements.append(Spacer(1, 14))
    
    client_data = [[Paragraph("<b>Cliente:</b>", bold_style), Paragraph(str(cliente), normal_style), Paragraph("<b>Teléfono:</b>", bold_style), Paragraph(str(telefono), normal_style)]]
    t_client = Table(client_data, colWidths=[90, 200, 70, 180])
    t_client.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4")), ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#86efac")), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    elements.append(t_client)
    elements.append(Spacer(1, 14))
    
    items_data = [
        [Paragraph("<b>Detalle del Trabajo Entregado / Encargado</b>", bold_style), Paragraph("<b>Total</b>", bold_style)],
        [Paragraph(str(detalle), normal_style), Paragraph(f"{moneda}{total:,.2f}", bold_style)]
    ]
    t_items = Table(items_data, colWidths=[400, 140])
    t_items.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#15803d")), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    elements.append(t_items)
    elements.append(Spacer(1, 14))
    
    pago_data = [
        ["", Paragraph(f"Total Trabajo: <b>{moneda}{total:,.2f}</b>", normal_style)],
        ["", Paragraph(f"<font color='#15803d'>Abonado ({metodo}): <b>{moneda}{sena:,.2f}</b></font>", normal_style)],
        ["", Paragraph(f"<font color='#b91c1c'><b>SALDO PENDIENTE: {moneda}{saldo:,.2f}</b></font>", ParagraphStyle('Saldo', fontName='Helvetica-Bold', fontSize=11, alignment=0))]
    ]
    t_pago = Table(pago_data, colWidths=[320, 220])
    t_pago.setStyle(TableStyle([('BACKGROUND', (1,0), (1,-1), colors.HexColor("#f8fafc")), ('BOX', (1,0), (1,-1), 1, colors.HexColor("#cbd5e1")), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(t_pago)
    elements.append(Spacer(1, 16))
    
    if alias_b or cbu_b:
        datos_banco = f"<b>DATOS DE TRANSFERENCIA:</b><br/>"
        if alias_b: datos_banco += f"<b>Alias:</b> {alias_b} &nbsp;&nbsp;| &nbsp;&nbsp;"
        if cbu_b: datos_banco += f"<b>CBU:</b> {cbu_b} &nbsp;&nbsp;| &nbsp;&nbsp;"
        if titular_b: datos_banco += f"<b>Titular:</b> {titular_b}"
        elements.append(Paragraph(f"<font size='9' color='#1e3a8a'>{datos_banco}</font>", ParagraphStyle('Banco', alignment=1)))
        elements.append(Spacer(1, 10))

    elements.append(Paragraph("<font size='8' color='#64748b'>Comprobante de entrega y registro de pago interno.<br/>¡Muchas gracias por su compra!</font>", ParagraphStyle('Pie', alignment=1)))
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# ---------------- BARRA HORIZONTAL DE PÍLDORAS ----------------
SECCIONES = ["Trabajos", "Presupuestos", "Boletas", "Clientes", "Insumos", "Compras", "Balance", "Ajustes"]

if 'seccion_activa' not in st.session_state:
    st.session_state.seccion_activa = "Trabajos"

col_logo, col_pills = st.columns([1.3, 7])
with col_logo:
    st.markdown(f"<div style='font-size: 21px; font-weight: 800; color: #ffffff; padding-top: 4px; white-space: nowrap;'>⚡ {titulo_actual}</div>", unsafe_allow_html=True)

with col_pills:
    p_cols = st.columns(len(SECCIONES))
    for i, s in enumerate(SECCIONES):
        btn_kind = "primary" if st.session_state.seccion_activa == s else "secondary"
        if p_cols[i].button(s, key=f"pill_{s}", type=btn_kind, use_container_width=True):
            if st.session_state.seccion_activa != s:
                st.session_state.seccion_activa = s
                st.rerun()

st.markdown("<hr style='border: none; border-top: 1px solid #1e293b; margin: 8px 0 14px 0;'>", unsafe_allow_html=True)

# ---------------- HERO DINÁMICO ----------------
HERO_INFO = {
    "Trabajos": ("Gestión de Trabajos y Producción", "Control de pedidos en taller, estados de producción e imprentas externas."),
    "Presupuestos": ("Emisión de Presupuestos", "Cotizaciones con múltiples renglones, cálculo de materiales y pase reversible al taller."),
    "Boletas": ("Comprobantes y Boletas de Pago", "Registro de señas, saldos pendientes, alias de cobro y aviso por WhatsApp."),
    "Clientes": ("Directorio e Historial de Clientes", "Seguimiento completo de pedidos, presupuestos, saldos y contacto directo."),
    "Insumos": ("Catálogo de Materiales y Márgenes", "Costos unitarios y calculadora inteligente con multiplicador de ganancia."),
    "Compras": ("Registro de Facturas y Proveedores", "Control de gastos en materiales e insumos de imprenta renglón por renglón."),
    "Balance": ("Rendimiento Financiero y Caja", "Ingresos, egresos (costos de producción + compras) y balance neto."),
    "Ajustes": ("Configuración del Taller", "Personalización de datos fiscales, bancarios, mensajes de WhatsApp y categorías.")
}

t_hero, sub_hero = HERO_INFO.get(st.session_state.seccion_activa, ("SN Gráfica", subtitulo_actual))

st.markdown(f"""
<div class="hero-container">
    <div class="hero-title">{t_hero}</div>
    <div class="hero-subtitle">{sub_hero}</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# VISTA 1: TRABAJOS Y PEDIDOS (CON FECHA, HORA Y DESHACER PASE)
# ==========================================
if st.session_state.seccion_activa == "Trabajos":
    df_todos_trabajos = fetch_data_cached("""
        SELECT id, cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, hora_carga, fecha_entrega, estado, costo_material, precio_venta, presupuesto_origen_id 
        FROM trabajos 
        ORDER BY fecha_entrega ASC, id DESC
    """)
    
    with st.expander("➕ Cargar Nuevo Trabajo", expanded=False):
        with st.form("form_nuevo_trabajo", clear_on_submit=True):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                nuevo_cli = st.text_input("Nombre del Cliente *")
                nuevo_tel = st.text_input("Teléfono / WhatsApp (ej: 54911...)")
                nuevo_trabajo = st.text_input("Trabajo / Descripción *")
            with col_t2:
                nuevo_taller = st.text_input("Imprenta / Taller Tercerizado (Opcional)", placeholder="Ej: Imprenta Central")
                nuevo_est = st.selectbox("Estado Inicial", ESTADOS_TRABAJO, key="n_est")
                col_sub_f1, col_sub_f2 = st.columns(2)
                with col_sub_f1:
                    nuevo_fcarga = st.date_input("Fecha Carga", value=date.today(), key="n_fc")
                with col_sub_f2:
                    nuevo_fentrega = st.date_input("Fecha Entrega", value=date.today(), key="n_fe")
            
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                nuevo_costo = st.number_input(f"Costo de Producción / Tercerizado ({moneda})", min_value=0.0, step=100.0, key="n_costo")
            with col_m2:
                nuevo_precio = st.number_input(f"Precio de Venta Final ({moneda}) *", min_value=0.0, step=100.0, key="n_precio")
            
            guardar_nuevo = st.form_submit_button("Guardar Trabajo", use_container_width=True)
            if guardar_nuevo:
                if nuevo_cli.strip() and nuevo_trabajo.strip() and nuevo_precio > 0:
                    hora_actual_str = datetime.now().strftime("%H:%M")
                    if IS_POSTGRES:
                        run_execute_raw("INSERT INTO trabajos (cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, hora_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (:c, :tel, :t, :te, :fc, :hc, :fe, :e, :cm, :pv)",
                                        {"c": nuevo_cli.strip(), "tel": nuevo_tel.strip(), "t": nuevo_trabajo.strip(), "te": nuevo_taller.strip(), "fc": nuevo_fcarga, "hc": hora_actual_str, "fe": nuevo_fentrega, "e": nuevo_est, "cm": nuevo_costo, "pv": nuevo_precio})
                    else:
                        run_execute_raw("INSERT INTO trabajos (cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, hora_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (nuevo_cli.strip(), nuevo_tel.strip(), nuevo_trabajo.strip(), nuevo_taller.strip(), nuevo_fcarga, hora_actual_str, nuevo_fentrega, nuevo_est, nuevo_costo, nuevo_precio))
                    st.success("¡Trabajo guardado con éxito!")
                    st.rerun()
                else:
                    st.error("Completá cliente, trabajo y precio de venta.")

    col_t_act1, col_t_act2, col_t_act3 = st.columns(3)
    with col_t_act1:
        with st.expander("✏️ Modificar Trabajo", expanded=False):
            if not df_todos_trabajos.empty:
                opciones_activos = {
                    f"#{row['id']} - {row['cliente']} ({row['tipo_trabajo']})": row['id']
                    for _, row in df_todos_trabajos.iterrows()
                }
                sel_mod = st.selectbox("Seleccionar para editar:", list(opciones_activos.keys()), key="sel_mod_trab")
                id_mod = opciones_activos[sel_mod]
                datos_sel = df_todos_trabajos[df_todos_trabajos['id'] == id_mod].iloc[0]
                
                try: fc_val = datetime.strptime(str(datos_sel['fecha_carga']), "%Y-%m-%d").date()
                except Exception: fc_val = date.today()
                try: fe_val = datetime.strptime(str(datos_sel['fecha_entrega']), "%Y-%m-%d").date()
                except Exception: fe_val = date.today()
                hora_existente = str(datos_sel.get('hora_carga') or '')

                with st.form(f"form_mod_{id_mod}"):
                    col_ed1, col_ed2 = st.columns(2)
                    with col_ed1:
                        ed_cliente = st.text_input("Cliente *", value=str(datos_sel['cliente']))
                        ed_tel = st.text_input("Teléfono / WhatsApp", value=str(datos_sel.get('telefono') or ''))
                        ed_trabajo = st.text_input("Trabajo / Descripción *", value=str(datos_sel['tipo_trabajo']))
                    with col_ed2:
                        ed_taller = st.text_input("Imprenta Tercerizada", value=str(datos_sel.get('taller_externo') or ''))
                        idx_e = ESTADOS_TRABAJO.index(datos_sel['estado']) if datos_sel['estado'] in ESTADOS_TRABAJO else 0
                        ed_estado = st.selectbox("Estado del Pedido", ESTADOS_TRABAJO, index=idx_e)
                        col_mfc1, col_mfc2 = st.columns(2)
                        with col_mfc1:
                            ed_fc = st.date_input("Fecha Carga", value=fc_val)
                        with col_mfc2:
                            ed_hc = st.text_input("Hora Carga (HH:MM)", value=hora_existente if hora_existente else datetime.now().strftime("%H:%M"))
                        ed_fe = st.date_input("Fecha Entrega", value=fe_val)
                        
                    col_edm1, col_edm2 = st.columns(2)
                    with col_edm1:
                        ed_costo = st.number_input(f"Costo Producción ({moneda})", min_value=0.0, value=float(datos_sel['costo_material'] or 0.0), step=100.0)
                    with col_edm2:
                        ed_precio = st.number_input(f"Precio Venta ({moneda}) *", min_value=0.0, value=float(datos_sel['precio_venta'] or 0.0), step=100.0)
                    
                    guardar_mod = st.form_submit_button("💾 Guardar Cambios", use_container_width=True)
                    if guardar_mod:
                        if ed_cliente.strip() and ed_trabajo.strip() and ed_precio > 0:
                            if IS_POSTGRES:
                                run_execute_raw("UPDATE trabajos SET cliente=:c, telefono=:tel, tipo_trabajo=:t, taller_externo=:te, fecha_carga=:fc, hora_carga=:hc, fecha_entrega=:fe, estado=:e, costo_material=:cm, precio_

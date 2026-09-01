import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import io
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
                    fecha_entrega DATE,
                    cliente TEXT,
                    telefono TEXT,
                    tipo_trabajo TEXT,
                    taller_externo TEXT,
                    estado TEXT,
                    costo_material REAL,
                    precio_venta REAL
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
            try: conn.execute(text("ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS telefono TEXT;"))
            except Exception: pass
            try: conn.execute(text("ALTER TABLE trabajos ADD COLUMN IF NOT EXISTS taller_externo TEXT;"))
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
        cursor.execute("CREATE TABLE IF NOT EXISTS trabajos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_carga DATE, fecha_entrega DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, taller_externo TEXT, estado TEXT, costo_material REAL, precio_venta REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS presupuestos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, detalle TEXT, cantidad REAL, precio_unitario REAL, precio_total REAL, costo_material REAL, estado TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS boletas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, detalle TEXT, metodo_pago TEXT, total REAL, sena REAL, saldo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS insumos (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE, unidad TEXT, costo_unitario REAL, multiplicador_sugerido REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS tipos_trabajo (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
        try: cursor.execute("ALTER TABLE trabajos ADD COLUMN telefono TEXT")
        except Exception: pass
        try: cursor.execute("ALTER TABLE trabajos ADD COLUMN taller_externo TEXT")
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
    
    /* PÍLDORAS INACTIVAS */
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
    
    /* PÍLDORA ACTIVA */
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

    /* HERO DINÁMICO */
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

# ---------------- GENERACIÓN DE PDF ----------------
def generar_pdf_presupuesto(empresa, p_id, fecha, cliente, telefono, tipo, detalle, cant, unitario, total, pie_txt_custom):
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
        [Paragraph("<b>Tipo de Trabajo:</b>", bold_style), Paragraph(str(tipo), normal_style), Paragraph("", normal_style), Paragraph("", normal_style)]
    ]
    t_client = Table(client_data, colWidths=[90, 200, 70, 180])
    t_client.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")), ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")), ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5)]))
    elements.append(t_client)
    elements.append(Spacer(1, 14))
    
    items_data = [
        [Paragraph("<b>Detalle / Especificaciones</b>", bold_style), Paragraph("<b>Cant.</b>", bold_style), Paragraph("<b>P. Unitario</b>", bold_style), Paragraph("<b>Total</b>", bold_style)],
        [Paragraph(str(detalle), normal_style), Paragraph(f"{cant:,.0f}", normal_style), Paragraph(f"{moneda}{unitario:,.2f}", normal_style), Paragraph(f"{moneda}{total:,.2f}", bold_style)]
    ]
    t_items = Table(items_data, colWidths=[280, 60, 100, 100])
    t_items.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3a8a")), ('TEXTCOLOR', (0,0), (-1,0), colors.white), ('ALIGN', (1,0), (-1,-1), 'CENTER'), ('ALIGN', (2,0), (-1,-1), 'RIGHT'), ('ALIGN', (3,0), (-1,-1), 'RIGHT'), ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
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
    "Presupuestos": ("Emisión de Presupuestos", "Cotizaciones directas con cálculo automático de materiales y exportación PDF."),
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
# VISTA 1: TRABAJOS Y PEDIDOS
# ==========================================
if st.session_state.seccion_activa == "Trabajos":
    df_todos_trabajos = fetch_data_cached("""
        SELECT id, cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta 
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
                    if IS_POSTGRES:
                        run_execute_raw("INSERT INTO trabajos (cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (:c, :tel, :t, :te, :fc, :fe, :e, :cm, :pv)",
                                        {"c": nuevo_cli.strip(), "tel": nuevo_tel.strip(), "t": nuevo_trabajo.strip(), "te": nuevo_taller.strip(), "fc": nuevo_fcarga, "fe": nuevo_fentrega, "e": nuevo_est, "cm": nuevo_costo, "pv": nuevo_precio})
                    else:
                        run_execute_raw("INSERT INTO trabajos (cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (nuevo_cli.strip(), nuevo_tel.strip(), nuevo_trabajo.strip(), nuevo_taller.strip(), nuevo_fcarga, nuevo_fentrega, nuevo_est, nuevo_costo, nuevo_precio))
                    st.success("¡Trabajo guardado con éxito!")
                    st.rerun()
                else:
                    st.error("Completá cliente, trabajo y precio de venta.")

    col_t_act1, col_t_act2 = st.columns(2)
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
                        ed_fc = st.date_input("Fecha Carga", value=fc_val)
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
                                run_execute_raw("UPDATE trabajos SET cliente=:c, telefono=:tel, tipo_trabajo=:t, taller_externo=:te, fecha_carga=:fc, fecha_entrega=:fe, estado=:e, costo_material=:cm, precio_venta=:pv WHERE id=:id",
                                                {"c": ed_cliente.strip(), "tel": ed_tel.strip(), "t": ed_trabajo.strip(), "te": ed_taller.strip(), "fc": ed_fc, "fe": ed_fe, "e": ed_estado, "cm": ed_costo, "pv": ed_precio, "id": id_mod})
                            else:
                                run_execute_raw("UPDATE trabajos SET cliente=?, telefono=?, tipo_trabajo=?, taller_externo=?, fecha_carga=?, fecha_entrega=?, estado=?, costo_material=?, precio_venta=? WHERE id=?",
                                                (ed_cliente.strip(), ed_tel.strip(), ed_trabajo.strip(), ed_taller.strip(), ed_fc, ed_fe, ed_estado, ed_costo, ed_precio, id_mod))
                            st.success("¡Trabajo actualizado!")
                            st.rerun()

    with col_t_act2:
        with st.expander("🗑️ Borrar Trabajo", expanded=False):
            if not df_todos_trabajos.empty:
                opciones_borrar = {
                    f"#{row['id']} - {row['cliente']} ({moneda}{row['precio_venta']:,.0f})": row['id']
                    for _, row in df_todos_trabajos.iterrows()
                }
                sel_borrar = st.selectbox("Elegí el trabajo a eliminar:", list(opciones_borrar.keys()), key="sel_borrar_directo")
                id_borrar = opciones_borrar[sel_borrar]
                
                st.write("")
                if st.button(f"❌ Confirmar y Borrar #{id_borrar}", type="primary", use_container_width=True):
                    if IS_POSTGRES:
                        run_execute_raw("DELETE FROM trabajos WHERE id=:id", {"id": id_borrar})
                    else:
                        run_execute_raw("DELETE FROM trabajos WHERE id=?", (id_borrar,))
                    st.warning(f"Trabajo #{id_borrar} eliminado.")
                    st.rerun()

    st.markdown("""
    <div style='background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 12px; margin: 12px 0; font-size: 12px;'>
        <span style='color:#94a3b8; font-weight:600;'>ESTADOS: </span>
        <span style='background-color:#ffcccc; color:#900C3F; padding:2px 6px; border-radius:4px; font-weight:bold;'>🔴 Pendiente</span> 
        <span style='background-color:#e9d5ff; color:#6b21a8; padding:2px 6px; border-radius:4px; font-weight:bold;'>🟣 En Imprenta</span> 
        <span style='background-color:#fff3cd; color:#856404; padding:2px 6px; border-radius:4px; font-weight:bold;'>🟡 Para Armar</span> 
        <span style='background-color:#d4edda; color:#155724; padding:2px 6px; border-radius:4px; font-weight:bold;'>🟢 Listo Retiro</span> 
        <span style='background-color:#cce5ff; color:#004085; padding:2px 6px; border-radius:4px; font-weight:bold;'>🔵 Cobrado</span>
    </div>
    """, unsafe_allow_html=True)

    if not df_todos_trabajos.empty:
        df_trabajos_tabla = df_todos_trabajos.copy()
        
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            opciones_filtro = ["Todos"] + ESTADOS_TRABAJO
            estado_seleccionado = st.selectbox("Filtrar por Estado:", options=opciones_filtro, index=0)
        with col_filtro2:
            busq_trabajo = st.text_input("🔍 Buscar:", key="busq_gral", placeholder="Cliente, trabajo o taller...")

        if estado_seleccionado != "Todos":
            df_trabajos_tabla = df_trabajos_tabla[df_trabajos_tabla['estado'] == estado_seleccionado]
            
        if busq_trabajo:
            df_trabajos_tabla = df_trabajos_tabla[
                df_trabajos_tabla['cliente'].str.contains(busq_trabajo, case=False, na=False) |
                df_trabajos_tabla['tipo_trabajo'].str.contains(busq_trabajo, case=False, na=False) |
                df_trabajos_tabla['taller_externo'].fillna('').str.contains(busq_trabajo, case=False, na=False)
            ]
            
        df_trabajos_tabla['estado'] = df_trabajos_tabla['estado'].map(ESTADO_BADGES).fillna(df_trabajos_tabla['estado'])
        
        df_mostrar = df_trabajos_tabla.rename(columns={
            'cliente': 'Cliente',
            'telefono': 'Teléfono',
            'tipo_trabajo': 'Trabajo',
            'taller_externo': 'Imprenta / Taller',
            'fecha_carga': 'Fecha Carga',
            'fecha_entrega': 'Fecha Entrega',
            'estado': 'Estado',
            'costo_material': f'Costo ({moneda})',
            'precio_venta': f'Venta ({moneda})'
        })[['Cliente', 'Teléfono', 'Trabajo', 'Imprenta / Taller', 'Fecha Carga', 'Fecha Entrega', 'Estado', f'Costo ({moneda})', f'Venta ({moneda})']]
        
        st.dataframe(df_mostrar, use_container_width=True)
    else:
        st.info("Todavía no hay trabajos cargados en el sistema.")

# ==========================================
# VISTA 2: PRESUPUESTOS (VISTA PREVIA CORREGIDA)
# ==========================================
elif st.session_state.seccion_activa == "Presupuestos":
    with st.expander("➕ Crear Nuevo Presupuesto", expanded=False):
        with st.form("form_nuevo_presupuesto_detallado", clear_on_submit=True):
            pr_cliente = st.text_input("Cliente *")
            pr_fecha = st.date_input("Fecha", value=date.today())
            pr_telefono = st.text_input("Teléfono / WhatsApp")
            pr_tipo = st.selectbox("Tipo de Trabajo / Rubro", tipos_actuales, key="pr_tipo_sel")
            pr_detalle = st.text_area("Detalle / Especificaciones del trabajo *")
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                pr_cant = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            with col_c2:
                pr_unitario = st.number_input(f"Precio Unitario ({moneda}) *", min_value=0.0, step=100.0)
            with col_c3:
                pr_costo_mat = st.number_input(f"Costo Estimado Material ({moneda})", min_value=0.0, step=100.0)
            
            btn_crear_pres = st.form_submit_button("💾 Guardar Presupuesto", use_container_width=True)
            
            if btn_crear_pres:
                total_calculado = pr_cant * pr_unitario
                if pr_cliente.strip() and pr_unitario > 0:
                    if IS_POSTGRES:
                        run_execute_raw("INSERT INTO presupuestos (fecha, cliente, telefono, tipo_trabajo, detalle, cantidad, precio_unitario, precio_total, costo_material, estado) VALUES (:f, :c, :t, :tt, :d, :cant, :pu, :pt, :cm, :e)",
                                        {"f": pr_fecha, "c": pr_cliente.strip(), "t": pr_telefono.strip(), "tt": pr_tipo, "d": pr_detalle.strip(), "cant": pr_cant, "pu": pr_unitario, "pt": total_calculado, "cm": pr_costo_mat, "e": "Pendiente"})
                    else:
                        run_execute_raw("INSERT INTO presupuestos (fecha, cliente, telefono, tipo_trabajo, detalle, cantidad, precio_unitario, precio_total, costo_material, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (str(pr_fecha), pr_cliente.strip(), pr_telefono.strip(), pr_tipo, pr_detalle.strip(), pr_cant, pr_unitario, total_calculado, pr_costo_mat, "Pendiente"))
                    st.success("¡Presupuesto guardado!")
                    st.rerun()

    df_presupuestos = fetch_data_cached("SELECT * FROM presupuestos ORDER BY id DESC")
    
    if not df_presupuestos.empty:
        opciones_pres = {
            f"Presupuesto #{int(row['id'])} - {row['cliente']} ({moneda}{float(row['precio_total'] or 0):,.0f})": int(row['id'])
            for _, row in df_presupuestos.iterrows()
        }
        
        with st.expander("⚡ Gestionar Presupuesto Seleccionado", expanded=True):
            pres_sel = st.selectbox("Seleccionar Presupuesto:", list(opciones_pres.keys()), key="pres_sel_box")
            pres_id = opciones_pres[pres_sel]
            pres_data = df_presupuestos[df_presupuestos['id'] == pres_id].iloc[0]
            
            col_b_p1, col_b_p2 = st.columns(2)
            with col_b_p1:
                if st.button("🚀 Pasar a Trabajo Activo (Taller)", use_container_width=True, key=f"btn_p_taller_{pres_id}"):
                    if IS_POSTGRES:
                        run_execute_raw("INSERT INTO trabajos (cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (:c, :tel, :t, :te, :fc, :fe, :e, :cm, :pv)",
                                        {"c": str(pres_data['cliente']), "tel": str(pres_data.get('telefono') or ''), "t": str(pres_data['tipo_trabajo']), "te": "", "fc": str(date.today()), "fe": str(date.today()), "e": "Pendiente", "cm": float(pres_data.get('costo_material') or 0.0), "pv": float(pres_data.get('precio_total') or 0.0)})
                        run_execute_raw("UPDATE presupuestos SET estado = 'Aprobado' WHERE id = :id", {"id": pres_id})
                    else:
                        run_execute_raw("INSERT INTO trabajos (cliente, telefono, tipo_trabajo, taller_externo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                        (str(pres_data['cliente']), str(pres_data.get('telefono') or ''), str(pres_data['tipo_trabajo']), "", str(date.today()), str(date.today()), "Pendiente", float(pres_data.get('costo_material') or 0.0), float(pres_data.get('precio_total') or 0.0)))
                        run_execute_raw("UPDATE presupuestos SET estado = 'Aprobado' WHERE id = ?", (pres_id,))
                    st.success(f"¡Presupuesto #{pres_id} pasado a Trabajo de Taller!")
                    st.rerun()
            
            with col_b_p2:
                if st.button("🗑️ Borrar Presupuesto", use_container_width=True, key=f"btn_del_pres_{pres_id}"):
                    if IS_POSTGRES:
                        run_execute_raw("DELETE FROM presupuestos WHERE id = :id", {"id": pres_id})
                    else:
                        run_execute_raw("DELETE FROM presupuestos WHERE id = ?", (pres_id,))
                    st.warning(f"Presupuesto #{pres_id} eliminado.")
                    st.rerun()

        st.divider()
        
        pr_det = str(pres_data.get('detalle') or pres_data.get('tipo_trabajo', 'Trabajo Gráfico'))
        pr_tel = str(pres_data.get('telefono') or 'No especificado')
        pr_cant_val = float(pres_data.get('cantidad') or 1.0)
        pr_unit_val = float(pres_data.get('precio_unitario') or 0.0)
        pr_tot_val = float(pres_data.get('precio_total') or 0.0)
        
        pdf_pres_bytes = generar_pdf_presupuesto(
            titulo_actual, int(pres_id), str(pres_data['fecha']),
            str(pres_data['cliente']), pr_tel, str(pres_data['tipo_trabajo']),
            pr_det, pr_cant_val, pr_unit_val, pr_tot_val, pie_empresa
        )
        
        st.markdown("### 👁️ Vista Previa del Presupuesto")
        
        # HTML unificado sin indentaciones para evitar que markdown lo interprete como código
        html_preview = (
            f'<div style="background-color: #ffffff; color: #111827; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; font-family: sans-serif; max-width: 820px; margin: 0 auto;">'
            f'<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #1e3a8a; padding-bottom: 12px; margin-bottom: 16px;">'
            f'<div><h2 style="margin: 0; color: #1e3a8a; font-size: 22px; font-weight: 800;">{titulo_actual}</h2>'
            f'<p style="margin: 3px 0; font-size: 13px; color: #475569;">{dir_empresa} {(" | " + tel_empresa) if tel_empresa else ""}</p>'
            f'<span style="font-size: 12px; font-weight: bold; color: #2563eb; background-color: #eff6ff; padding: 3px 8px; border-radius: 4px;">PRESUPUESTO ESTIMADO</span></div>'
            f'<div style="text-align: right;"><h3 style="margin: 0; color: #1e293b; font-size: 17px; font-weight: 800;">N° #{int(pres_id):04d}</h3>'
            f'<p style="margin: 3px 0; font-size: 13px; color: #64748b;">Fecha: {pres_data["fecha"]}</p></div></div>'
            f'<div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; font-size: 13.5px;">'
            f'<p style="margin: 3px 0;"><strong>Cliente:</strong> {pres_data["cliente"]}</p>'
            f'<p style="margin: 3px 0;"><strong>Teléfono:</strong> {pr_tel}</p>'
            f'<p style="margin: 3px 0;"><strong>Rubro / Categoría:</strong> {pres_data["tipo_trabajo"]}</p></div>'
            f'<table style="width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 13.5px;">'
            f'<thead><tr style="background-color: #1e3a8a; color: #ffffff;">'
            f'<th style="padding: 10px; text-align: left;">Detalle del Trabajo</th>'
            f'<th style="padding: 10px; text-align: center; width: 60px;">Cant.</th>'
            f'<th style="padding: 10px; text-align: right; width: 110px;">P. Unitario</th>'
            f'<th style="padding: 10px; text-align: right; width: 110px;">Total</th></tr></thead>'
            f'<tbody><tr style="border-bottom: 1px solid #e2e8f0; background-color: #ffffff;">'
            f'<td style="padding: 12px 10px; color: #334155;">{pr_det}</td>'
            f'<td style="padding: 12px 10px; text-align: center; color: #334155;">{pr_cant_val:,.0f}</td>'
            f'<td style="padding: 12px 10px; text-align: right; color: #334155;">{moneda}{pr_unit_val:,.2f}</td>'
            f'<td style="padding: 12px 10px; text-align: right; font-weight: bold; color: #1e3a8a;">{moneda}{pr_tot_val:,.2f}</td></tr></tbody></table>'
            f'<div style="display: flex; justify-content: flex-end; margin-bottom: 18px;">'
            f'<div style="background-color: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 10px 16px; min-width: 220px; text-align: right;">'
            f'<span style="font-size: 13px; color: #64748b;">TOTAL:</span><br/>'
            f'<strong style="font-size: 18px; color: #1e3a8a;">{moneda}{pr_tot_val:,.2f}</strong></div></div>'
            f'<div style="text-align: center; border-top: 1px dashed #cbd5e1; padding-top: 12px; color: #64748b; font-size: 11.5px;">'
            f'<p style="margin: 2px;">{pie_empresa}</p>'
            f'<p style="margin: 2px;">¡Muchas gracias por su consulta!</p></div></div>'
        )
        st.markdown(html_preview, unsafe_allow_html=True)
            
        st.write("")
        col_btn_p_down, col_btn_p_imp = st.columns(2)
        with col_btn_p_down:
            st.download_button(
                label="📥 Descargar PDF",
                data=pdf_pres_bytes,
                file_name=f"Presupuesto_{int(pres_id)}_{pres_data['cliente']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        with col_btn_p_imp:
            html_impresion_pres = f"""
            <script>
            function imprimirPresupuesto() {{
                var ventana = window.open('', '', 'height=700,width=900');
                ventana.document.write('<html><head><title>Presupuesto #{pres_id}</title></head><body style="margin: 20px;">');
                ventana.document.write(`{html_preview}`);
                ventana.document.write('</body></html>');
                ventana.document.close();
                ventana.focus();
                setTimeout(function() {{
                    ventana.print();
                    ventana.close();
                }}, 400);
            }}
            </script>
            <button onclick="imprimirPresupuesto()" style="width: 100%; background-color: #1e3a8a; color: white; border: none; padding: 8px 14px; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer;">
                🖨️ Imprimir
            </button>
            """
            st.components.v1.html(html_impresion_pres, height=50)

# ==========================================
# VISTA 3: BOLETAS Y COMPROBANTES CON WHATSAPP
# ==========================================
elif st.session_state.seccion_activa == "Boletas":
    with st.expander("➕ Generar Nueva Boleta de Pago", expanded=False):
        with st.form("form_nueva_boleta", clear_on_submit=True):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                b_cliente = st.text_input("Cliente *")
                b_fecha = st.date_input("Fecha", value=date.today())
                b_metodo = st.selectbox("Método de Pago", ["Efectivo (Caja Taller)", "Transferencia / MP (Banco)"])
            with col_b2:
                b_telefono = st.text_input("Teléfono / WhatsApp (ej: 54911...)")
                b_total = st.number_input(f"Total del Trabajo ({moneda}) *", min_value=0.0, step=100.0)
                b_sena = st.number_input(f"Monto Abonado / Seña ({moneda}) *", min_value=0.0, step=100.0)
                
            b_detalle = st.text_area("Detalle del trabajo / Entrega *")
            
            btn_crear_bol = st.form_submit_button("💾 Emitir Boleta", use_container_width=True)
            if btn_crear_bol:
                if b_cliente.strip() and b_total > 0:
                    saldo_calc = b_total - b_sena
                    if IS_POSTGRES:
                        run_execute_raw("INSERT INTO boletas (fecha, cliente, telefono, detalle, metodo_pago, total, sena, saldo) VALUES (:f, :c, :t, :d, :m, :tot, :s, :sal)",
                                        {"f": b_fecha, "c": b_cliente.strip(), "t": b_telefono.strip(), "d": b_detalle.strip(), "m": b_metodo, "tot": b_total, "s": b_sena, "sal": saldo_calc})
                    else:
                        run_execute_raw("INSERT INTO boletas (fecha, cliente, telefono, detalle, metodo_pago, total, sena, saldo) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                        (str(b_fecha), b_cliente.strip(), b_telefono.strip(), b_detalle.strip(), b_metodo, b_total, b_sena, saldo_calc))
                    st.success("¡Boleta generada con éxito!")
                    st.rerun()

    df_boletas = fetch_data_cached("SELECT * FROM boletas ORDER BY id DESC")
    
    if not df_boletas.empty:
        opciones_bol = {
            f"Boleta #{int(row['id'])} - {row['cliente']} (Total: {moneda}{float(row['total'] or 0):,.0f} | Saldo: {moneda}{float(row['saldo'] or 0):,.0f})": int(row['id'])
            for _, row in df_boletas.iterrows()
        }
        
        with st.expander("⚡ Gestionar Boleta Seleccionada", expanded=True):
            bol_sel = st.selectbox("Seleccionar Boleta:", list(opciones_bol.keys()), key="bol_sel_box")
            bol_id = opciones_bol[bol_sel]
            bol_data = df_boletas[df_boletas['id'] == bol_id].iloc[0]
            
            col_b_act1, col_b_act2 = st.columns(2)
            with col_b_act1:
                tel_limpio = "".join([c for c in str(bol_data.get('telefono') or '') if c.isdigit()])
                msg_wsp = f"¡Hola {bol_data['cliente']}! Te avisamos desde *{titulo_actual}* que tu trabajo ya está listo. El saldo pendiente es de *{moneda}{float(bol_data['saldo'] or 0):,.2f}*.\n\nPodés abonarlo por transferencia a nuestro Alias: *{alias_banco}* o en efectivo al retirar. ¡Muchas gracias!"
                url_wsp = f"https://wa.me/{tel_limpio}?text={urllib.parse.quote(msg_wsp)}" if tel_limpio else "#"
                
                if tel_limpio:
                    st.markdown(f"<a href='{url_wsp}' target='_blank' style='text-decoration:none;'><div style='background-color:#25d366; color:white; text-align:center; padding:9px; border-radius:8px; font-weight:bold;'>📲 Enviar Aviso por WhatsApp</div></a>", unsafe_allow_html=True)
                else:
                    st.button("📲 WhatsApp (Sin teléfono cargado)", disabled=True, use_container_width=True)

            with col_b_act2:
                if st.button("🗑️ Borrar Boleta", use_container_width=True, key=f"btn_del_bol_{bol_id}"):
                    if IS_POSTGRES:
                        run_execute_raw("DELETE FROM boletas WHERE id = :id", {"id": bol_id})
                    else:
                        run_execute_raw("DELETE FROM boletas WHERE id = ?", (bol_id,))
                    st.warning(f"Boleta #{bol_id} eliminada.")
                    st.rerun()

        st.divider()
        
        b_det = str(bol_data['detalle']) if bol_data['detalle'] and str(bol_data['detalle']).strip() else 'Trabajo Gráfico General'
        b_tel = str(bol_data['telefono']) if bol_data['telefono'] and str(bol_data['telefono']).strip() else 'No especificado'
        b_met = str(bol_data.get('metodo_pago') or 'Efectivo')
        b_tot_val = float(bol_data['total'] or 0.0)
        b_sena_val = float(bol_data['sena'] or 0.0)
        b_saldo_val = float(bol_data['saldo'] or 0.0)
        
        pdf_bol_bytes = generar_pdf_boleta(
            titulo_actual, int(bol_id), str(bol_data['fecha']),
            str(bol_data['cliente']), b_tel, b_det, b_tot_val, b_sena_val, b_saldo_val,
            alias_banco, cbu_banco, titular_banco, b_met
        )
        
        st.markdown("### 👁️ Vista Previa del Comprobante")
        html_preview_bol = (
            f'<div style="background-color: #ffffff; color: #111827; border-radius: 12px; padding: 24px; border: 1px solid #e2e8f0; font-family: sans-serif; max-width: 820px; margin: 0 auto;">'
            f'<div style="display: flex; justify-content: space-between; border-bottom: 2px solid #15803d; padding-bottom: 12px; margin-bottom: 16px;">'
            f'<div><h2 style="margin: 0; color: #15803d; font-size: 22px; font-weight: 800;">{titulo_actual}</h2>'
            f'<p style="margin: 3px 0; font-size: 13px; color: #475569;">{dir_empresa} {(" | " + tel_empresa) if tel_empresa else ""}</p>'
            f'<span style="font-size: 12px; font-weight: bold; color: #15803d; background-color: #f0fdf4; padding: 3px 8px; border-radius: 4px;">BOLETA / COMPROBANTE DE PAGO</span></div>'
            f'<div style="text-align: right;"><h3 style="margin: 0; color: #15803d; font-size: 17px; font-weight: 800;">BOLETA N° #{int(bol_id):04d}</h3>'
            f'<p style="margin: 3px 0; font-size: 13px; color: #64748b;">Fecha: {bol_data["fecha"]}</p></div></div>'
            f'<div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; font-size: 13.5px;">'
            f'<p style="margin: 3px 0;"><strong>Cliente:</strong> {bol_data["cliente"]}</p>'
            f'<p style="margin: 3px 0;"><strong>Teléfono:</strong> {b_tel}</p></div>'
            f'<table style="width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 13.5px;">'
            f'<thead><tr style="background-color: #15803d; color: #ffffff;">'
            f'<th style="padding: 10px; text-align: left;">Detalle del Trabajo</th>'
            f'<th style="padding: 10px; text-align: right; width: 130px;">Importe</th></tr></thead>'
            f'<tbody><tr style="border-bottom: 1px solid #e2e8f0; background-color: #ffffff;">'
            f'<td style="padding: 12px 10px; color: #334155;">{b_det}</td>'
            f'<td style="padding: 12px 10px; text-align: right; font-weight: bold; color: #15803d;">{moneda}{b_tot_val:,.2f}</td></tr></tbody></table>'
            f'<div style="display: flex; justify-content: flex-end; margin-bottom: 18px;">'
            f'<div style="width: 270px; background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 10px 14px; border-radius: 8px; font-size: 13px;">'
            f'<div style="display: flex; justify-content: space-between; margin-bottom: 4px;"><span>Total:</span><strong>{moneda}{b_tot_val:,.2f}</strong></div>'
            f'<div style="display: flex; justify-content: space-between; margin-bottom: 4px; color: #15803d;"><span>Abonado ({b_met}):</span><strong>{moneda}{b_sena_val:,.2f}</strong></div>'
            f'<hr style="margin: 6px 0; border: none; border-top: 1px solid #cbd5e1;">'
            f'<div style="display: flex; justify-content: space-between; font-size: 14.5px; color: #b91c1c;"><strong>Saldo Pendiente:</strong><strong>{moneda}{b_saldo_val:,.2f}</strong></div></div></div>'
            f'<div style="background-color:#eff6ff; border:1px solid #bfdbfe; border-radius:6px; padding:8px; text-align:center; font-size:12px; color:#1e3a8a; margin-bottom:12px;">'
            f'<strong>ALIAS:</strong> {alias_banco} &nbsp;|&nbsp; <strong>TITULAR:</strong> {titular_banco}</div>'
            f'<div style="text-align: center; border-top: 1px dashed #cbd5e1; padding-top: 10px; color: #64748b; font-size: 11.5px;">'
            f'<p style="margin: 2px;">Comprobante de entrega y registro de pago interno.</p>'
            f'<p style="margin: 2px;">¡Muchas gracias por su compra!</p></div></div>'
        )
        st.markdown(html_preview_bol, unsafe_allow_html=True)
        st.write("")
        
        col_btn_b_down, col_btn_b_imp = st.columns(2)
        with col_btn_b_down:
            st.download_button(
                label="📥 Descargar PDF",
                data=pdf_bol_bytes,
                file_name=f"Boleta_{int(bol_id)}_{bol_data['cliente']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            
        with col_btn_b_imp:
            html_impresion_bol = f"""
            <script>
            function imprimirBoletaDirecta() {{
                var ventana = window.open('', '', 'height=700,width=900');
                ventana.document.write('<html><head><title>Boleta #{bol_id}</title></head><body style="margin: 20px;">');
                ventana.document.write(`{html_preview_bol}`);
                ventana.document.write('</body></html>');
                ventana.document.close();
                ventana.focus();
                setTimeout(function() {{
                    ventana.print();
                    ventana.close();
                }}, 400);
            }}
            </script>
            <button onclick="imprimirBoletaDirecta()" style="width: 100%; background-color: #15803d; color: white; border: none; padding: 8px 14px; font-size: 14px; font-weight: bold; border-radius: 8px; cursor: pointer;">
                🖨️ Imprimir
            </button>
            """
            st.components.v1.html(html_impresion_bol, height=50)

# ==========================================
# VISTA 4: HISTORIAL POR CLIENTES CON WHATSAPP
# ==========================================
elif st.session_state.seccion_activa == "Clientes":
    df_clientes_trab = fetch_data_cached("SELECT DISTINCT cliente FROM trabajos WHERE cliente IS NOT NULL AND cliente != ''")
    df_clientes_pres = fetch_data_cached("SELECT DISTINCT cliente FROM presupuestos WHERE cliente IS NOT NULL AND cliente != ''")
    
    lista_clientes = sorted(list(set(df_clientes_trab['cliente'].tolist() + df_clientes_pres['cliente'].tolist()))) if (not df_clientes_trab.empty or not df_clientes_pres.empty) else []
    
    if lista_clientes:
        cli_sel = st.selectbox("👤 Seleccionar Cliente para ver Historial y Contactar:", lista_clientes)
        
        df_hist_trab = run_query_raw("SELECT id, cliente, telefono, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta FROM trabajos WHERE cliente = :c ORDER BY id DESC" if IS_POSTGRES else "SELECT id, cliente, telefono, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta FROM trabajos WHERE cliente = ? ORDER BY id DESC", {"c": cli_sel} if IS_POSTGRES else (cli_sel,))
        df_hist_bol = run_query_raw("SELECT id, fecha, detalle, metodo_pago, total, sena, saldo FROM boletas WHERE cliente = :c ORDER BY id DESC" if IS_POSTGRES else "SELECT id, fecha, detalle, metodo_pago, total, sena, saldo FROM boletas WHERE cliente = ? ORDER BY id DESC", {"c": cli_sel} if IS_POSTGRES else (cli_sel,))
        
        tel_encontrado = ""
        if not df_hist_trab.empty and df_hist_trab['telefono'].dropna().any():
            for t in df_hist_trab['telefono'].dropna():
                if str(t).strip():
                    tel_encontrado = str(t).strip()
                    break
        
        col_c_k1, col_c_k2, col_c_k3 = st.columns(3)
        total_comprado = df_hist_trab['precio_venta'].sum() if not df_hist_trab.empty else 0.0
        saldo_pendiente_cli = df_hist_bol['saldo'].sum() if not df_hist_bol.empty else 0.0
        
        col_c_k1.metric("Total Facturado Histórico", f"{moneda}{total_comprado:,.2f}")
        col_c_k2.metric("Trabajos Realizados", len(df_hist_trab))
        col_c_k3.metric("Saldo Deudor Pendiente", f"{moneda}{saldo_pendiente_cli:,.2f}", delta=f"-{moneda}{saldo_pendiente_cli:,.2f}" if saldo_pendiente_cli > 0 else "Al día")
        
        st.divider()

        # Botón de WhatsApp para aviso de pedido listo
        st.markdown("### 📲 Enviar Aviso de Pedido Listo por WhatsApp")
        if not df_hist_trab.empty:
            opciones_trabajos_cli = {
                f"#{row['id']} - {row['tipo_trabajo']} ({moneda}{float(row['precio_venta'] or 0):,.0f})": row
                for _, row in df_hist_trab.iterrows()
            }
            sel_trab_wsp = st.selectbox("Elegí el pedido a notificar:", list(opciones_trabajos_cli.keys()), key=f"sel_t_wsp_{cli_sel}")
            trab_info = opciones_trabajos_cli[sel_trab_wsp]
            
            tel_actual_trab = str(trab_info.get('telefono') or tel_encontrado)
            tel_wsp_input = st.text_input("Número de Teléfono / WhatsApp:", value=tel_actual_trab, placeholder="ej: 5491112345678", key=f"input_wsp_{trab_info['id']}")
            
            tel_numeros = "".join([c for c in tel_wsp_input if c.isdigit()])
            nombre_trab = str(trab_info['tipo_trabajo'])
            monto_tot = f"{float(trab_info['precio_venta'] or 0):,.2f}"
            
            try:
                msg_personalizado = msg_wsp_template.format(
                    cliente=cli_sel,
                    trabajo=nombre_trab,
                    total=monto_tot,
                    alias=alias_banco
                )
            except Exception:
                msg_personalizado = f"Hola, Tu pedido {nombre_trab} está listo! el total es ${monto_tot} Gracias!"
                
            url_wsp_cli = f"https://wa.me/{tel_numeros}?text={urllib.parse.quote(msg_personalizado)}" if tel_numeros else "#"
            
            if tel_numeros:
                st.markdown(f"<a href='{url_wsp_cli}' target='_blank' style='text-decoration:none;'><div style='background-color:#25d366; color:white; text-align:center; padding:10px; border-radius:8px; font-weight:bold; font-size:14.5px;'>📲 Enviar Mensaje a {cli_sel} por WhatsApp</div></a>", unsafe_allow_html=True)
            else:
                st.info("Ingresá el número de WhatsApp arriba para habilitar el botón.")
        else:
            st.info("Este cliente no tiene trabajos cargados para notificar.")

        st.subheader("📋 Pedidos del Cliente")
        if not df_hist_trab.empty:
            st.dataframe(df_hist_trab.rename(columns={'tipo_trabajo': 'Trabajo', 'telefono': 'Teléfono', 'fecha_carga': 'Fecha Carga', 'fecha_entrega': 'Fecha Entrega', 'estado': 'Estado', 'precio_venta': f'Venta ({moneda})'})[['Trabajo', 'Teléfono', 'Fecha Carga', 'Fecha Entrega', 'Estado', f'Venta ({moneda})']], use_container_width=True)
        else:
            st.info("No hay trabajos registrados para este cliente.")
            
        st.subheader("🧾 Comprobantes de Pago y Saldos")
        if not df_hist_bol.empty:
            st.dataframe(df_hist_bol.rename(columns={'fecha': 'Fecha', 'detalle': 'Detalle', 'metodo_pago': 'Método', 'total': f'Total ({moneda})', 'sena': f'Abonado ({moneda})', 'saldo': f'Saldo ({moneda})'}), use_container_width=True)
        else:
            st.info("No hay boletas emitidas para este cliente.")
    else:
        st.info("Todavía no hay clientes con actividad registrada.")

# ==========================================
# VISTA 5: CATÁLOGO DE INSUMOS Y MÁRGENES
# ==========================================
elif st.session_state.seccion_activa == "Insumos":
    with st.expander("➕ Cargar Nuevo Material / Insumo", expanded=False):
        with st.form("form_nuevo_insumo", clear_on_submit=True):
            col_in1, col_in2 = st.columns(2)
            with col_in1:
                in_nombre = st.text_input("Nombre del Insumo (ej: Lona Frontlight 13oz, Vinilo Mate) *")
                in_unidad = st.selectbox("Unidad de Medida", ["m² (Metro Cuadrado)", "Metro Lineal", "Unidad", "Placa", "Rollo"])
            with col_in2:
                in_costo = st.number_input(f"Costo Base Unitario ({moneda}) *", min_value=0.0, step=100.0)
                in_multi = st.number_input("Multiplicador de Ganancia Deseado (ej: 2.5 = 150% ganancia)", min_value=1.0, value=2.5, step=0.1)
            
            btn_save_ins = st.form_submit_button("Guardar Insumo", use_container_width=True)
            if btn_save_ins:
                if in_nombre.strip() and in_costo > 0:
                    try:
                        if IS_POSTGRES:
                            run_execute_raw("INSERT INTO insumos (nombre, unidad, costo_unitario, multiplicador_sugerido) VALUES (:n, :u, :c, :m)",
                                            {"n": in_nombre.strip(), "u": in_unidad, "c": in_costo, "m": in_multi})
                        else:
                            run_execute_raw("INSERT INTO insumos (nombre, unidad, costo_unitario, multiplicador_sugerido) VALUES (?, ?, ?, ?)",
                                            (in_nombre.strip(), in_unidad, in_costo, in_multi))
                        st.success("¡Insumo guardado correctamente!")
                        st.rerun()
                    except Exception:
                        st.error("Ese insumo ya está cargado.")

    df_insumos = fetch_data_cached("SELECT id, nombre, unidad, costo_unitario, multiplicador_sugerido, (costo_unitario * multiplicador_sugerido) as precio_sugerido FROM insumos ORDER BY nombre ASC")
    
    if not df_insumos.empty:
        st.markdown("### 🏷️ Lista de Precios y Costos de Insumos")
        st.dataframe(df_insumos.rename(columns={
            'nombre': 'Material / Insumo',
            'unidad': 'Unidad',
            'costo_unitario': f'Costo Base ({moneda})',
            'multiplicador_sugerido': 'Multiplicador',
            'precio_sugerido': f'Precio Venta Sugerido ({moneda})'
        })[['Material / Insumo', 'Unidad', f'Costo Base ({moneda})', 'Multiplicador', f'Precio Venta Sugerido ({moneda})']], use_container_width=True)
        
        with st.expander("🗑️ Eliminar Insumo"):
            opc_in_del = {row['nombre']: row['id'] for _, row in df_insumos.iterrows()}
            sel_in_del = st.selectbox("Seleccionar insumo a borrar:", list(opc_in_del.keys()))
            if st.button("Eliminar Insumo"):
                if IS_POSTGRES: run_execute_raw("DELETE FROM insumos WHERE id=:id", {"id": opc_in_del[sel_in_del]})
                else: run_execute_raw("DELETE FROM insumos WHERE id=?", (opc_in_del[sel_in_del],))
                st.rerun()
    else:
        st.info("Todavía no cargaste ningún insumo en el catálogo.")

# ==========================================
# VISTA 6: COMPRAS Y FACTURAS (MÚLTIPLES RENGLONES)
# ==========================================
elif st.session_state.seccion_activa == "Compras":
    st.markdown("### 🛒 Registro de Compras y Facturas con Desglose")
    
    with st.expander("➕ Cargar Factura con Múltiples Productos", expanded=False):
        col_fc1, col_fc2, col_fc3 = st.columns(3)
        with col_fc1:
            prov_input = st.text_input("Proveedor * (ej: VL Insumos)", key="c_prov_multi")
        with col_fc2:
            fact_input = st.text_input("N° Factura / Remito", key="c_fact_multi")
        with col_fc3:
            fecha_input = st.date_input("Fecha de Compra", value=date.today(), key="c_fecha_multi")
        
        st.markdown("**Renglones de la Compra / Factura:**")
        st.caption("Podés agregar tantos renglones como necesites haciendo clic en el `+` al final de la tabla.")
        
        if "df_items_compra" not in st.session_state:
            st.session_state.df_items_compra = pd.DataFrame([
                {"Detalle": "Vinilo Rojo", "Cantidad": 1.0, "Precio Unitario": 0.0},
                {"Detalle": "Vinilo Verde", "Cantidad": 1.0, "Precio Unitario": 0.0},
                {"Detalle": "Cinta Térmica", "Cantidad": 1.0, "Precio Unitario": 0.0}
            ])
            
        edited_items = st.data_editor(
            st.session_state.df_items_compra,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Detalle": st.column_config.TextColumn("Detalle / Producto *", required=True),
                "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.01, default=1.0, step=1.0),
                "Precio Unitario": st.column_config.NumberColumn(f"Precio Unit. ({moneda})", min_value=0.0, default=0.0, step=100.0)
            },
            key="editor_items_compras"
        )
        
        df_calc = edited_items.dropna(subset=["Detalle"]).copy() if not edited_items.empty else pd.DataFrame()
        if not df_calc.empty:
            df_calc["Cantidad"] = pd.to_numeric(df_calc["Cantidad"], errors="coerce").fillna(1.0)
            df_calc["Precio Unitario"] = pd.to_numeric(df_calc["Precio Unitario"], errors="coerce").fillna(0.0)
            df_calc["Importe"] = df_calc["Cantidad"] * df_calc["Precio Unitario"]
            total_factura_calc = df_calc["Importe"].sum()
        else:
            total_factura_calc = 0.0
            
        st.markdown(f"<div style='text-align: right; font-size: 16px; font-weight: bold; color: #60a5fa; margin-bottom: 10px;'>TOTAL CALCULADO DE LA FACTURA: {moneda}{total_factura_calc:,.2f}</div>", unsafe_allow_html=True)
        
        if st.button("💾 Guardar Factura Completa", type="primary", use_container_width=True):
            if not prov_input.strip():
                st.error("Por favor completá el nombre del Proveedor.")
            elif df_calc.empty:
                st.error("Ingresá al menos un producto en la tabla.")
            else:
                for _, row_item in df_calc.iterrows():
                    det_txt = str(row_item["Detalle"]).strip()
                    cant_val = float(row_item["Cantidad"])
                    pu_val = float(row_item["Precio Unitario"])
                    tot_renglon = cant_val * pu_val
                    if det_txt:
                        if IS_POSTGRES:
                            run_execute_raw("INSERT INTO compras (factura, proveedor, fecha, producto, cantidad, precio_unitario, costo) VALUES (:f, :p, :fe, :pr, :ca, :pu, :c)",
                                            {"f": fact_input.strip(), "p": prov_input.strip(), "fe": fecha_input, "pr": det_txt, "ca": cant_val, "pu": pu_val, "c": tot_renglon})
                        else:
                            run_execute_raw("INSERT INTO compras (factura, proveedor, fecha, producto, cantidad, precio_unitario, costo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                            (fact_input.strip(), prov_input.strip(), fecha_input, det_txt, cant_val, pu_val, tot_renglon))
                st.success("¡Factura e ítems guardados con éxito!")
                st.session_state.df_items_compra = pd.DataFrame([{"Detalle": "", "Cantidad": 1.0, "Precio Unitario": 0.0}])
                st.rerun()

    df_compras_raw = fetch_data_cached("SELECT id, fecha, factura, proveedor, producto, cantidad, precio_unitario, costo FROM compras ORDER BY fecha DESC, id DESC")

    with st.expander("🗑️ Borrar Renglón de Compra", expanded=False):
        if not df_compras_raw.empty:
            opciones_c_del = {
                f"#{row['id']} - {row['proveedor']} | {row['producto']} (Cant: {row['cantidad']} | {moneda}{row['costo']:,.0f})": row['id']
                for _, row in df_compras_raw.iterrows()
            }
            c_del_sel = st.selectbox("Seleccionar ítem a borrar:", list(opciones_c_del.keys()), key="del_c_sel")
            c_del_id = opciones_c_del[c_del_sel]
            if st.button(f"❌ Borrar Registro #{c_del_id}", type="primary", use_container_width=True):
                if IS_POSTGRES: run_execute_raw("DELETE FROM compras WHERE id = :id", {"id": c_del_id})
                else: run_execute_raw("DELETE FROM compras WHERE id = ?", (c_del_id,))
                st.warning(f"Registro #{c_del_id} eliminado.")
                st.rerun()

    st.divider()
    if not df_compras_raw.empty:
        df_compras_mostrar = df_compras_raw.copy()
        busqueda_prov = st.text_input("🔍 Buscar:", key="search_prov", placeholder="Proveedor, producto o factura...")
        if busqueda_prov:
            df_compras_mostrar = df_compras_mostrar[
                df_compras_mostrar['proveedor'].str.contains(busqueda_prov, case=False, na=False) |
                df_compras_mostrar['producto'].str.contains(busqueda_prov, case=False, na=False) |
                df_compras_mostrar['factura'].fillna('').str.contains(busqueda_prov, case=False, na=False)
            ]
        
        df_mostrar_compras = df_compras_mostrar.rename(columns={
            'id': 'ID',
            'fecha': 'Fecha',
            'factura': 'N° Factura',
            'proveedor': 'Proveedor',
            'producto': 'Detalle / Producto',
            'cantidad': 'Cant.',
            'precio_unitario': f'P. Unit. ({moneda})',
            'costo': f'Importe ({moneda})'
        })
        st.dataframe(df_mostrar_compras[['Fecha', 'N° Factura', 'Proveedor', 'Detalle / Producto', 'Cant.', f'P. Unit. ({moneda})', f'Importe ({moneda})']], use_container_width=True)
    else:
        st.info("Todavía no hay compras cargadas.")

# ==========================================
# VISTA 7: BALANCE Y FINANZAS (INGRESOS vs GASTOS COMPLETOS)
# ==========================================
elif st.session_state.seccion_activa == "Balance":
    df_ventas_total = fetch_data_cached("SELECT SUM(precio_venta) as total_ventas, SUM(costo_material) as total_costos_prod FROM trabajos")
    df_gastos_compras = fetch_data_cached("SELECT SUM(costo) as total_compras FROM compras")
    
    total_ventas = float(df_ventas_total['total_ventas'].iloc[0] or 0.0)
    total_costos_produccion = float(df_ventas_total['total_costos_prod'].iloc[0] or 0.0)
    total_compras = float(df_gastos_compras['total_compras'].iloc[0] or 0.0)
    
    total_egresos_completo = total_costos_produccion + total_compras
    ganancia_neta = total_ventas - total_egresos_completo
    margen = (ganancia_neta / total_ventas * 100) if total_ventas > 0 else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(f"Ingresos Totales (Ventas)", f"{moneda}{total_ventas:,.2f}")
    kpi2.metric(f"Egresos Totales (Gastos)", f"{moneda}{total_egresos_completo:,.2f}")
    kpi3.metric(f"Ganancia Neta Real", f"{moneda}{ganancia_neta:,.2f}", delta=f"{moneda}{ganancia_neta:,.2f}")
    kpi4.metric("Margen Neto", f"{margen:.1f}%")

    st.divider()
    
    st.markdown("### 🔍 Desglose Detallado de Egresos y Caja")
    col_egr1, col_egr2, col_egr3 = st.columns(3)
    col_egr1.metric("🛠️ Costos de Producción / Talleres", f"{moneda}{total_costos_produccion:,.2f}")
    col_egr2.metric("🧾 Facturas de Compras / Insumos", f"{moneda}{total_compras:,.2f}")
    
    df_pagos_metodo = fetch_data_cached("SELECT metodo_pago, SUM(sena) as total_cobrado FROM boletas GROUP BY metodo_pago")
    efectivo_en_mano = 0.0
    banco_mp = 0.0
    if not df_pagos_metodo.empty:
        for _, r in df_pagos_metodo.iterrows():
            met = r['metodo_pago'] or 'Efectivo (Caja Taller)'
            monto = float(r['total_cobrado'] or 0.0)
            if "Efectivo" in str(met):
                efectivo_en_mano += monto
            else:
                banco_mp += monto
                
    col_egr3.metric("💵 Caja Taller (Efectivo)", f"{moneda}{efectivo_en_mano:,.2f}")

    st.divider()
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("**Comparativa: Ventas vs Egresos Totales**")
        df_comp = pd.DataFrame({
            "Concepto": ["Ingresos (Ventas)", "Costos Producción", "Facturas Compras", "Ganancia Neta"],
            f"Monto ({moneda})": [total_ventas, total_costos_produccion, total_compras, ganancia_neta]
        })
        fig_bar = px.bar(
            df_comp, x="Concepto", y=f"Monto ({moneda})", color="Concepto",
            color_discrete_map={"Ingresos (Ventas)": "#3b82f6", "Costos Producción": "#f59e0b", "Facturas Compras": "#ef4444", "Ganancia Neta": "#10b981"},
            template="plotly_dark"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g2:
        st.markdown("**Distribución de Trabajos por Rubro**")
        df_tipos = fetch_data_cached("SELECT tipo_trabajo AS Tipo, COUNT(*) as Cantidad FROM trabajos GROUP BY tipo_trabajo")
        if not df_tipos.empty:
            fig_pie = px.pie(df_tipos, values="cantidad", names="tipo", hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# VISTA 8: AJUSTES Y CONFIGURACIÓN
# ==========================================
elif st.session_state.seccion_activa == "Ajustes":
    col_cfg1, col_cfg2 = st.columns(2)
    
    with col_cfg1:
        st.markdown("### 🏢 Datos de la Empresa y Banco")
        with st.form("form_configuracion_ampliada"):
            cfg_titulo = st.text_input("Nombre de la Empresa:", value=titulo_actual)
            cfg_subtitulo = st.text_input("Subtítulo:", value=subtitulo_actual)
            cfg_tel = st.text_input("Teléfono / WhatsApp de Contacto:", value=tel_empresa)
            cfg_dir = st.text_input("Dirección:", value=dir_empresa)
            cfg_moneda = st.text_input("Símbolo de Moneda (ej: $, USD):", value=moneda)
            
            st.markdown("---")
            st.markdown("**💳 Datos de Cobro (Aparecen en Boletas)**")
            cfg_alias = st.text_input("Alias Bancario / MP:", value=alias_banco)
            cfg_cbu = st.text_input("CBU / CVU:", value=cbu_banco)
            cfg_titular = st.text_input("Titular de la Cuenta:", value=titular_banco)
            cfg_pie = st.text_area("Leyenda en Presupuestos:", value=pie_empresa)
            
            st.markdown("---")
            st.markdown("### 📲 Mensaje Predeterminado de WhatsApp")
            st.caption("Variables disponibles: `{cliente}`, `{trabajo}`, `{total}`, `{alias}`")
            cfg_msg_wsp = st.text_area("Plantilla de Mensaje:", value=msg_wsp_template, height=85)
            
            guardar_cfg = st.form_submit_button("💾 Guardar Configuración", use_container_width=True)
            if guardar_cfg:
                configs_update = {
                    "titulo_app": cfg_titulo.strip(),
                    "subtitulo_app": cfg_subtitulo.strip(),
                    "telefono_empresa": cfg_tel.strip(),
                    "direccion_empresa": cfg_dir.strip(),
                    "simbolo_moneda": cfg_moneda.strip() if cfg_moneda.strip() else "$",
                    "alias_bancario": cfg_alias.strip(),
                    "cbu_bancario": cfg_cbu.strip(),
                    "titular_cuenta": cfg_titular.strip(),
                    "mensaje_pie": cfg_pie.strip(),
                    "mensaje_wsp_custom": cfg_msg_wsp.strip()
                }
                for k, v in configs_update.items():
                    if IS_POSTGRES:
                        run_execute_raw("INSERT INTO configuracion (clave, valor) VALUES (:c, :v) ON CONFLICT (clave) DO UPDATE SET valor = :v", {"c": k, "v": v})
                    else:
                        run_execute_raw("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (k, v))
                st.success("¡Configuración actualizada!")
                st.rerun()

    with col_cfg2:
        st.markdown("### 🏷️ Tipos de Trabajo Sugeridos")
        with st.form("form_nuevo_tipo_trabajo", clear_on_submit=True):
            nuevo_tipo_txt = st.text_input("Agregar nuevo rubro sugerido (ej: Cartel Neón LED):")
            btn_add_tipo = st.form_submit_button("➕ Agregar Rubro", use_container_width=True)
            if btn_add_tipo:
                if nuevo_tipo_txt.strip():
                    try:
                        if IS_POSTGRES:
                            run_execute_raw("INSERT INTO tipos_trabajo (nombre) VALUES (:n)", {"n": nuevo_tipo_txt.strip()})
                        else:
                            run_execute_raw("INSERT INTO tipos_trabajo (nombre) VALUES (?)", (nuevo_tipo_txt.strip(),))
                        st.success(f"Rubro '{nuevo_tipo_txt}' agregado.")
                        st.rerun()
                    except Exception:
                        st.warning("Ese rubro ya existe.")

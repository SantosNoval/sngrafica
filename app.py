import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import plotly.express as px
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from sqlalchemy import create_engine, text

# ---------------- CONFIGURACIÓN DE PÁGINA ----------------
st.set_page_config(
    page_title="Gestion Grafica SN Grafica",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------- CONEXIÓN A BASE DE DATOS (NUBE O LOCAL) ----------------
DB_URL = st.secrets.get("DATABASE_URL", None) if hasattr(st, "secrets") else None

if DB_URL:
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DB_URL)
    IS_POSTGRES = True
else:
    DB_NAME = "grafica.db"
    IS_POSTGRES = False

def run_query(query, params=(), fetch=True):
    if IS_POSTGRES:
        with engine.connect() as conn:
            if fetch:
                df = pd.read_sql_query(text(query), conn, params=dict(enumerate(params)) if isinstance(params, (list, tuple)) else params)
                return df
            else:
                conn.execute(text(query), dict(enumerate(params)) if isinstance(params, (list, tuple)) else params)
                conn.commit()
    else:
        conn = sqlite3.connect(DB_NAME)
        if fetch:
            df = pd.read_sql_query(query, conn, params=params)
            conn.close()
            return df
        else:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            conn.close()

# ---------------- BASE DE DATOS E INICIALIZACIÓN ----------------
def init_db():
    if IS_POSTGRES:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS compras (
                    id SERIAL PRIMARY KEY,
                    factura TEXT,
                    proveedor TEXT,
                    fecha DATE,
                    producto TEXT,
                    costo REAL
                );
                CREATE TABLE IF NOT EXISTS trabajos (
                    id SERIAL PRIMARY KEY,
                    fecha_carga DATE,
                    fecha_entrega DATE,
                    cliente TEXT,
                    tipo_trabajo TEXT,
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
                    total REAL,
                    sena REAL,
                    saldo REAL
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
            conn.commit()
    else:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS compras (id INTEGER PRIMARY KEY AUTOINCREMENT, factura TEXT, proveedor TEXT, fecha DATE, producto TEXT, costo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS trabajos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha_carga DATE, fecha_entrega DATE, cliente TEXT, tipo_trabajo TEXT, estado TEXT, costo_material REAL, precio_venta REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS presupuestos (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, tipo_trabajo TEXT, detalle TEXT, cantidad REAL, precio_unitario REAL, precio_total REAL, costo_material REAL, estado TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS boletas (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha DATE, cliente TEXT, telefono TEXT, detalle TEXT, total REAL, sena REAL, saldo REAL)")
        cursor.execute("CREATE TABLE IF NOT EXISTS configuracion (clave TEXT PRIMARY KEY, valor TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS tipos_trabajo (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT UNIQUE)")
        conn.commit()
        conn.close()

    configs_defecto = {
        "titulo_app": "SN Grafica",
        "subtitulo_app": "Sistema integral de gestión de producción, cotizaciones y balance",
        "telefono_empresa": "",
        "direccion_empresa": "",
        "mensaje_pie": "Presupuesto válido por 15 días. Documento no válido como factura fiscal.",
        "simbolo_moneda": "$"
    }
    for k, v in configs_defecto.items():
        if IS_POSTGRES:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO configuracion (clave, valor) VALUES (:k, :v) ON CONFLICT (clave) DO NOTHING"), {"k": k, "v": v})
                conn.commit()
        else:
            run_query("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (k, v), fetch=False)
    
    tipos_base = ["Cartelería / Lona", "Stickers / Vinilo de Corte", "Impresión UV / Rígidos", "Sublimación / Textil", "Diseño Gráfico", "Plotter Vehicular", "Varios"]
    for tipo in tipos_base:
        if IS_POSTGRES:
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO tipos_trabajo (nombre) VALUES (:n) ON CONFLICT (nombre) DO NOTHING"), {"n": tipo})
                conn.commit()
        else:
            run_query("INSERT OR IGNORE INTO tipos_trabajo (nombre) VALUES (?)", (tipo,), fetch=False)

init_db()

def get_config(clave, default=""):
    if IS_POSTGRES:
        df = run_query("SELECT valor FROM configuracion WHERE clave = :c", {"c": clave})
    else:
        df = run_query("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    if not df.empty:
        return df['valor'].iloc[0]
    return default

def set_config(clave, valor):
    if IS_POSTGRES:
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO configuracion (clave, valor) VALUES (:c, :v) ON CONFLICT (clave) DO UPDATE SET valor = :v"), {"c": clave, "v": valor})
            conn.commit()
    else:
        run_query("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor), fetch=False)

def get_tipos_trabajo():
    df = run_query("SELECT nombre FROM tipos_trabajo ORDER BY nombre ASC")
    if not df.empty:
        return df['nombre'].tolist()
    return ["General"]

ESTADOS_TRABAJO = ["Pendiente", "En Producción", "Listo para Entrega", "Entregado y Cobrado"]
ESTADO_BADGES = {"Pendiente": "🔴 Pendiente", "En Producción": "🟡 En Producción", "Listo para Entrega": "🟢 Listo para Entrega", "Entregado y Cobrado": "🔵 Entregado y Cobrado"}

# ---------------- CONFIGURACIONES ----------------
titulo_actual = get_config("titulo_app", "SN Grafica")
subtitulo_actual = get_config("subtitulo_app", "Sistema integral de gestión de producción, cotizaciones y balance")
tel_empresa = get_config("telefono_empresa", "")
dir_empresa = get_config("direccion_empresa", "")
pie_empresa = get_config("mensaje_pie", "Presupuesto válido por 15 días.")
moneda = get_config("simbolo_moneda", "$")
tipos_actuales = get_tipos_trabajo()

# ---------------- ESTILOS CSS CON PROTECCIÓN TOTAL SAFARI / IPHONE ----------------
st.markdown(f"""
<style>
    /* Ocultar elementos nativos de Streamlit */
    #MainMenu, footer, header, .stDeployButton, [data-testid="stDecoration"], [data-testid="stHeader"] {{
        display: none !important;
    }}
    
    /* Fondo Dark */
    .stApp {{
        background-color: #050508 !important;
        color: #f8fafc !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
    }}

    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1350px;
    }}

    /* FORZAR ESTILOS DE BOTONES PARA EVITAR BLANCO EN SAFARI */
    button, [data-testid="baseButton-secondary"] {{
        background-color: #12141c !important;
        background-image: none !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1px solid #2d3748 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }}
    
    /* Botón primario */
    [data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
    }}

    /* Hero Banner */
    .hero-container {{
        text-align: center;
        padding: 15px 10px 15px 10px;
        margin-bottom: 15px;
    }}
    .hero-title {{
        font-size: 38px;
        font-weight: 800;
        letter-spacing: -1px;
        line-height: 1.15;
        margin-bottom: 6px;
        background: linear-gradient(90deg, #fef08a 0%, #60a5fa 50%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .hero-subtitle {{
        font-size: 14.5px;
        color: #94a3b8;
        max-width: 600px;
        margin: 0 auto;
        line-height: 1.4;
    }}

    /* Selectores en modo oscuro */
    div[data-baseweb="select"] > div {{
        background-color: #12141c !important;
        border-color: #2d3748 !important;
        color: #ffffff !important;
    }}
    
    /* Media queries para móvil */
    @media (max-width: 768px) {{
        .hero-title {{
            font-size: 24px !important;
        }}
        .hero-subtitle {{
            font-size: 13px !important;
        }}
        .hero-container {{
            padding: 8px 0 !important;
        }}
    }}
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

def generar_pdf_boleta(empresa, b_id, fecha, cliente, telefono, detalle, total, sena, saldo):
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
        ["", Paragraph(f"<font color='#15803d'>Monto Abonado / Seña: <b>{moneda}{sena:,.2f}</b></font>", normal_style)],
        ["", Paragraph(f"<font color='#b91c1c'><b>SALDO PENDIENTE: {moneda}{saldo:,.2f}</b></font>", ParagraphStyle('Saldo', fontName='Helvetica-Bold', fontSize=11, alignment=0))]
    ]
    t_pago = Table(pago_data, colWidths=[320, 220])
    t_pago.setStyle(TableStyle([('BACKGROUND', (1,0), (1,-1), colors.HexColor("#f8fafc")), ('BOX', (1,0), (1,-1), 1, colors.HexColor("#cbd5e1")), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    elements.append(t_pago)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("<font size='8' color='#64748b'>Comprobante de entrega y registro de pago interno.<br/>¡Muchas gracias por su compra!</font>", ParagraphStyle('Pie', alignment=1)))
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# ---------------- NAVEGACIÓN COMPACTA Y RESPONSIVE ----------------
SECCIONES = ["Trabajos", "Presupuestos", "Boletas", "Entregados", "Compras", "Balance", "Ajustes"]

if 'seccion_activa' not in st.session_state:
    st.session_state.seccion_activa = "Trabajos"

col_head1, col_head2 = st.columns([1, 1])
with col_head1:
    st.markdown(f"<div style='font-size: 20px; font-weight: 800; color: #ffffff; padding-top: 4px;'>⚡ {titulo_actual}</div>", unsafe_allow_html=True)
with col_head2:
    if st.button("✨ + Cargar Pedido", type="primary", use_container_width=True):
        st.session_state.seccion_activa = "Trabajos"
        st.session_state.abrir_nuevo = True
        st.rerun()

idx_actual = SECCIONES.index(st.session_state.seccion_activa) if st.session_state.seccion_activa in SECCIONES else 0
seleccion = st.selectbox("📌 Módulo / Sección:", SECCIONES, index=idx_actual, label_visibility="collapsed")

if seleccion != st.session_state.seccion_activa:
    st.session_state.seccion_activa = "Configuracion" if seleccion == "Ajustes" else seleccion
    st.rerun()

st.markdown("<hr style='border: none; border-top: 1px solid #1e293b; margin: 8px 0 12px 0;'>", unsafe_allow_html=True)

# ==========================================
# HERO BANNER
# ==========================================
st.markdown(f"""
<div class="hero-container">
    <div class="hero-title">Controla. Diseña. Produce.</div>
    <div class="hero-subtitle">{subtitulo_actual}</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# VISTA 1: TRABAJOS Y PEDIDOS
# ==========================================
if st.session_state.seccion_activa == "Trabajos":
    df_todos_trabajos = run_query("""
        SELECT id, cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta 
        FROM trabajos 
        ORDER BY fecha_entrega ASC, id DESC
    """)
    
    with st.expander("➕ Cargar Nuevo Trabajo", expanded=st.session_state.get('abrir_nuevo', False)):
        with st.form("form_nuevo_trabajo", clear_on_submit=True):
            nuevo_cli = st.text_input("Nombre del Cliente *")
            nuevo_trabajo = st.text_input("Trabajo / Descripción del pedido *")
            nuevo_est = st.selectbox("Estado Inicial", ESTADOS_TRABAJO, key="n_est")
            nuevo_fcarga = st.date_input("Fecha de Carga", value=date.today(), key="n_fc")
            nuevo_fentrega = st.date_input("Fecha de Entrega Estimada", value=date.today(), key="n_fe")
            nuevo_costo = st.number_input(f"Costo de Producción ({moneda})", min_value=0.0, step=100.0, key="n_costo")
            nuevo_precio = st.number_input(f"Precio de Venta ({moneda}) *", min_value=0.0, step=100.0, key="n_precio")
            
            guardar_nuevo = st.form_submit_button("Guardar Trabajo", use_container_width=True)
            if guardar_nuevo:
                if nuevo_cli.strip() and nuevo_trabajo.strip() and nuevo_precio > 0:
                    if IS_POSTGRES:
                        run_query("INSERT INTO trabajos (cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (:c, :t, :fc, :fe, :e, :cm, :pv)",
                                  {"c": nuevo_cli.strip(), "t": nuevo_trabajo.strip(), "fc": nuevo_fcarga, "fe": nuevo_fentrega, "e": nuevo_est, "cm": nuevo_costo, "pv": nuevo_precio}, fetch=False)
                    else:
                        run_query("INSERT INTO trabajos (cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (nuevo_cli.strip(), nuevo_trabajo.strip(), nuevo_fcarga, nuevo_fentrega, nuevo_est, nuevo_costo, nuevo_precio), fetch=False)
                    st.session_state.abrir_nuevo = False
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
                
                try:
                    fc_val = datetime.strptime(str(datos_sel['fecha_carga']), "%Y-%m-%d").date()
                except Exception:
                    fc_val = date.today()
                    
                try:
                    fe_val = datetime.strptime(str(datos_sel['fecha_entrega']), "%Y-%m-%d").date()
                except Exception:
                    fe_val = date.today()

                with st.form(f"form_mod_{id_mod}"):
                    ed_cliente = st.text_input("Cliente *", value=str(datos_sel['cliente']))
                    ed_trabajo = st.text_input("Trabajo / Descripción *", value=str(datos_sel['tipo_trabajo']))
                    idx_e = ESTADOS_TRABAJO.index(datos_sel['estado']) if datos_sel['estado'] in ESTADOS_TRABAJO else 0
                    ed_estado = st.selectbox("Estado del Pedido", ESTADOS_TRABAJO, index=idx_e)
                    ed_fc = st.date_input("Fecha de Carga", value=fc_val)
                    ed_fe = st.date_input("Fecha de Entrega", value=fe_val)
                    ed_costo = st.number_input(f"Costo de Producción ({moneda})", min_value=0.0, value=float(datos_sel['costo_material'] or 0.0), step=100.0)
                    ed_precio = st.number_input(f"Precio de Venta ({moneda}) *", min_value=0.0, value=float(datos_sel['precio_venta'] or 0.0), step=100.0)
                    
                    guardar_mod = st.form_submit_button("💾 Guardar Cambios", use_container_width=True)
                    if guardar_mod:
                        if ed_cliente.strip() and ed_trabajo.strip() and ed_precio > 0:
                            if IS_POSTGRES:
                                run_query("UPDATE trabajos SET cliente=:c, tipo_trabajo=:t, fecha_carga=:fc, fecha_entrega=:fe, estado=:e, costo_material=:cm, precio_venta=:pv WHERE id=:id",
                                          {"c": ed_cliente.strip(), "t": ed_trabajo.strip(), "fc": ed_fc, "fe": ed_fe, "e": ed_estado, "cm": ed_costo, "pv": ed_precio, "id": id_mod}, fetch=False)
                            else:
                                run_query("UPDATE trabajos SET cliente=?, tipo_trabajo=?, fecha_carga=?, fecha_entrega=?, estado=?, costo_material=?, precio_venta=? WHERE id=?",
                                          (ed_cliente.strip(), ed_trabajo.strip(), ed_fc, ed_fe, ed_estado, ed_costo, ed_precio, id_mod), fetch=False)
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
                        run_query("DELETE FROM trabajos WHERE id=:id", {"id": id_borrar}, fetch=False)
                    else:
                        run_query("DELETE FROM trabajos WHERE id=?", (id_borrar,), fetch=False)
                    st.warning(f"Trabajo #{id_borrar} eliminado.")
                    st.rerun()

    st.markdown("""
    <div style='background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 12px; margin: 12px 0; font-size: 12px;'>
        <span style='color:#94a3b8; font-weight:600;'>ESTADOS: </span>
        <span style='background-color:#ffcccc; color:#900C3F; padding:2px 6px; border-radius:4px; font-weight:bold;'>🔴 Pendiente</span> 
        <span style='background-color:#fff3cd; color:#856404; padding:2px 6px; border-radius:4px; font-weight:bold;'>🟡 Producción</span> 
        <span style='background-color:#d4edda; color:#155724; padding:2px 6px; border-radius:4px; font-weight:bold;'>🟢 Listo</span> 
        <span style='background-color:#cce5ff; color:#004085; padding:2px 6px; border-radius:4px; font-weight:bold;'>🔵 Entregado</span>
    </div>
    """, unsafe_allow_html=True)

    if not df_todos_trabajos.empty:
        df_trabajos_tabla = df_todos_trabajos.copy()
        
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            opciones_filtro = ["Todos"] + ESTADOS_TRABAJO
            estado_seleccionado = st.selectbox("Filtrar por Estado:", options=opciones_filtro, index=0)
        with col_filtro2:
            busq_trabajo = st.text_input("🔍 Buscar:", key="busq_gral", placeholder="Cliente o trabajo...")

        if estado_seleccionado != "Todos":
            df_trabajos_tabla = df_trabajos_tabla[df_trabajos_tabla['estado'] == estado_seleccionado]
            
        if busq_trabajo:
            df_trabajos_tabla = df_trabajos_tabla[
                df_trabajos_tabla['cliente'].str.contains(busq_trabajo, case=False, na=False) |
                df_trabajos_tabla['tipo_trabajo'].str.contains(busq_trabajo, case=False, na=False)
            ]
            
        df_trabajos_tabla['estado'] = df_trabajos_tabla['estado'].map(ESTADO_BADGES).fillna(df_trabajos_tabla['estado'])
        
        df_mostrar = df_trabajos_tabla.rename(columns={
            'cliente': 'Cliente',
            'tipo_trabajo': 'Trabajo',
            'fecha_carga': 'Fecha Carga',
            'fecha_entrega': 'Fecha Entrega',
            'estado': 'Estado',
            'costo_material': f'Costo ({moneda})',
            'precio_venta': f'Venta ({moneda})'
        })[['Cliente', 'Trabajo', 'Fecha Carga', 'Fecha Entrega', 'Estado', f'Costo ({moneda})', f'Venta ({moneda})']]
        
        st.dataframe(df_mostrar, use_container_width=True)
    else:
        st.info("Todavía no hay trabajos cargados en el sistema.")

# ==========================================
# VISTA 2: PRESUPUESTOS
# ==========================================
elif st.session_state.seccion_activa == "Presupuestos":
    st.subheader("📄 Emisión de Presupuestos")
    
    with st.expander("➕ Crear Nuevo Presupuesto", expanded=False):
        with st.form("form_nuevo_presupuesto_detallado", clear_on_submit=True):
            pr_cliente = st.text_input("Cliente *")
            pr_fecha = st.date_input("Fecha", value=date.today())
            pr_telefono = st.text_input("Teléfono / WhatsApp")
            pr_tipo = st.selectbox("Tipo de Trabajo / Rubro", tipos_actuales, key="pr_tipo_sel")
            pr_detalle = st.text_area("Detalle / Especificaciones del trabajo *")
            
            pr_cant = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            pr_unitario = st.number_input(f"Precio Unitario ({moneda}) *", min_value=0.0, step=100.0)
            pr_costo_mat = st.number_input(f"Costo Estimado Material ({moneda})", min_value=0.0, step=100.0)
            
            btn_crear_pres = st.form_submit_button("💾 Guardar Presupuesto", use_container_width=True)
            
            if btn_crear_pres:
                total_calculado = pr_cant * pr_unitario
                if pr_cliente.strip() and pr_unitario > 0:
                    if IS_POSTGRES:
                        run_query("INSERT INTO presupuestos (fecha, cliente, telefono, tipo_trabajo, detalle, cantidad, precio_unitario, precio_total, costo_material, estado) VALUES (:f, :c, :t, :tt, :d, :cant, :pu, :pt, :cm, :e)",
                                  {"f": pr_fecha, "c": pr_cliente.strip(), "t": pr_telefono.strip(), "tt": pr_tipo, "d": pr_detalle.strip(), "cant": pr_cant, "pu": pr_unitario, "pt": total_calculado, "cm": pr_costo_mat, "e": "Pendiente"}, fetch=False)
                    else:
                        run_query("INSERT INTO presupuestos (fecha, cliente, telefono, tipo_trabajo, detalle, cantidad, precio_unitario, precio_total, costo_material, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                  (str(pr_fecha), pr_cliente.strip(), pr_telefono.strip(), pr_tipo, pr_detalle.strip(), pr_cant, pr_unitario, total_calculado, pr_costo_mat, "Pendiente"), fetch=False)
                    st.success("¡Presupuesto guardado!")
                    st.rerun()

    df_presupuestos = run_query("SELECT * FROM presupuestos ORDER BY id DESC")
    
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
                if st.button("🚀 Pasar a Trabajo Activo", use_container_width=True, key=f"btn_p_taller_{pres_id}"):
                    if IS_POSTGRES:
                        run_query("INSERT INTO trabajos (cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (:c, :t, :fc, :fe, :e, :cm, :pv)",
                                  {"c": str(pres_data['cliente']), "t": str(pres_data['tipo_trabajo']), "fc": str(date.today()), "fe": str(date.today()), "e": "Pendiente", "cm": float(pres_data.get('costo_material') or 0.0), "pv": float(pres_data.get('precio_total') or 0.0)}, fetch=False)
                        run_query("UPDATE presupuestos SET estado = 'Aprobado' WHERE id = :id", {"id": pres_id}, fetch=False)
                    else:
                        run_query("INSERT INTO trabajos (cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (str(pres_data['cliente']), str(pres_data['tipo_trabajo']), str(date.today()), str(date.today()), "Pendiente", float(pres_data.get('costo_material') or 0.0), float(pres_data.get('precio_total') or 0.0)), fetch=False)
                        run_query("UPDATE presupuestos SET estado = 'Aprobado' WHERE id = ?", (pres_id,), fetch=False)
                    st.success(f"¡Presupuesto #{pres_id} pasado a Trabajo!")
                    st.rerun()
            
            with col_b_p2:
                if st.button("🗑️ Borrar Presupuesto", use_container_width=True, key=f"btn_del_pres_{pres_id}"):
                    if IS_POSTGRES:
                        run_query("DELETE FROM presupuestos WHERE id = :id", {"id": pres_id}, fetch=False)
                    else:
                        run_query("DELETE FROM presupuestos WHERE id = ?", (pres_id,), fetch=False)
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
        
        info_empresa_html = f"<p style='margin:2px 0; color:#64748b; font-size:13px;'>{dir_empresa} {(' | ' + tel_empresa) if tel_empresa else ''}</p>" if (dir_empresa or tel_empresa) else ""
        
        presupuesto_html = f"""
        <div style="border: 2px solid #333; border-radius: 8px; padding: 16px; background: #ffffff; color: #111111; font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #1e3a8a; padding-bottom: 8px; margin-bottom: 12px;">
                <div>
                    <h2 style="margin: 0; color: #1e3a8a; font-size: 19px;">{titulo_actual}</h2>
                    {info_empresa_html}
                    <h3 style="margin: 3px 0; color: #555; font-size: 13px; font-weight: normal;">PRESUPUESTO ESTIMADO</h3>
                </div>
                <div style="text-align: right;">
                    <h3 style="margin: 0; color: #333; font-size: 15px;">N° #{int(pres_id):04d}</h3>
                    <p style="margin: 3px 0; font-size: 12px; color: #666;">Fecha: {pres_data['fecha']}</p>
                </div>
            </div>
            
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px 12px; margin-bottom: 14px; font-size: 13px;">
                <p style="margin: 2px 0;"><strong>Cliente:</strong> {pres_data['cliente']}</p>
                <p style="margin: 2px 0;"><strong>Teléfono:</strong> {pr_tel}</p>
                <p style="margin: 2px 0;"><strong>Rubro / Tipo:</strong> {pres_data['tipo_trabajo']}</p>
            </div>

            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #1e3a8a; color: #ffffff;">
                            <th style="padding: 7px; text-align: left;">Detalle del Trabajo</th>
                            <th style="padding: 7px; text-align: center; width: 55px;">Cant.</th>
                            <th style="padding: 7px; text-align: right; width: 100px;">P. Unit.</th>
                            <th style="padding: 7px; text-align: right; width: 100px;">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom: 1px solid #ddd;">
                            <td style="padding: 9px 7px;">{pr_det}</td>
                            <td style="padding: 9px 7px; text-align: center;">{pr_cant_val:,.0f}</td>
                            <td style="padding: 9px 7px; text-align: right;">{moneda}{pr_unit_val:,.2f}</td>
                            <td style="padding: 9px 7px; text-align: right; font-weight: bold;">{moneda}{pr_tot_val:,.2f}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div style="display: flex; justify-content: flex-end; margin-bottom: 14px;">
                <div style="width: 240px; background-color: #f1f5f9; padding: 8px 12px; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; font-size: 15px; color: #1e3a8a;">
                        <strong>TOTAL:</strong>
                        <strong>{moneda}{pr_tot_val:,.2f}</strong>
                    </div>
                </div>
            </div>

            <div style="text-align: center; border-top: 1px dashed #aaa; padding-top: 10px; color: #64748b; font-size: 11px;">
                <p style="margin: 2px;">{pie_empresa}</p>
                <p style="margin: 2px;">¡Gracias por consultarnos!</p>
            </div>
        </div>
        """
        st.markdown(presupuesto_html, unsafe_allow_html=True)
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
                var contenido = `{presupuesto_html}`;
                var ventana = window.open('', '', 'height=700,width=900');
                ventana.document.write('<html><head><title>Presupuesto #{pres_id}</title></head><body style="margin: 20px;">');
                ventana.document.write(contenido);
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
# VISTA 3: BOLETAS
# ==========================================
elif st.session_state.seccion_activa == "Boletas":
    st.subheader("🧾 Emisión de Boletas / Comprobantes")
    
    with st.expander("➕ Generar Nueva Boleta", expanded=False):
        with st.form("form_nueva_boleta", clear_on_submit=True):
            b_cliente = st.text_input("Cliente *")
            b_fecha = st.date_input("Fecha", value=date.today(), key="b_fecha_key")
            b_telefono = st.text_input("Teléfono / WhatsApp", key="b_tel_key")
            b_detalle = st.text_area("Detalle del trabajo / Entrega *")
            
            b_total = st.number_input(f"Total del Trabajo ({moneda}) *", min_value=0.0, step=100.0, key="b_tot_key")
            b_sena = st.number_input(f"Monto Abonado / Seña ({moneda}) *", min_value=0.0, step=100.0, key="b_sena_key")
            
            btn_crear_bol = st.form_submit_button("💾 Emitir Boleta", use_container_width=True)
            
            if btn_crear_bol:
                if b_cliente.strip() and b_total > 0:
                    saldo_calc = b_total - b_sena
                    if IS_POSTGRES:
                        run_query("INSERT INTO boletas (fecha, cliente, telefono, detalle, total, sena, saldo) VALUES (:f, :c, :t, :d, :tot, :s, :sal)",
                                  {"f": b_fecha, "c": b_cliente.strip(), "t": b_telefono.strip(), "d": b_detalle.strip(), "tot": b_total, "s": b_sena, "sal": saldo_calc}, fetch=False)
                    else:
                        run_query("INSERT INTO boletas (fecha, cliente, telefono, detalle, total, sena, saldo) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (str(b_fecha), b_cliente.strip(), b_telefono.strip(), b_detalle.strip(), b_total, b_sena, saldo_calc), fetch=False)
                    st.success("¡Boleta generada con éxito!")
                    st.rerun()

    df_boletas = run_query("SELECT * FROM boletas ORDER BY id DESC")
    
    if not df_boletas.empty:
        opciones_bol = {
            f"Boleta #{int(row['id'])} - {row['cliente']} (Total: {moneda}{float(row['total'] or 0):,.0f} | Saldo: {moneda}{float(row['saldo'] or 0):,.0f})": int(row['id'])
            for _, row in df_boletas.iterrows()
        }
        
        with st.expander("⚡ Gestionar Boleta Seleccionada", expanded=True):
            bol_sel = st.selectbox("Seleccionar Boleta:", list(opciones_bol.keys()), key="bol_sel_box")
            bol_id = opciones_bol[bol_sel]
            bol_data = df_boletas[df_boletas['id'] == bol_id].iloc[0]
            
            if st.button("🗑️ Borrar Boleta", use_container_width=True, key=f"btn_del_bol_{bol_id}"):
                if IS_POSTGRES:
                    run_query("DELETE FROM boletas WHERE id = :id", {"id": bol_id}, fetch=False)
                else:
                    run_query("DELETE FROM boletas WHERE id = ?", (bol_id,), fetch=False)
                st.warning(f"Boleta #{bol_id} eliminada.")
                st.rerun()

        st.divider()
        
        b_det = str(bol_data['detalle']) if bol_data['detalle'] and str(bol_data['detalle']).strip() else 'Trabajo Gráfico General'
        b_tel = str(bol_data['telefono']) if bol_data['telefono'] and str(bol_data['telefono']).strip() else 'No especificado'
        b_tot_val = float(bol_data['total'] or 0.0)
        b_sena_val = float(bol_data['sena'] or 0.0)
        b_saldo_val = float(bol_data['saldo'] or 0.0)
        
        pdf_bol_bytes = generar_pdf_boleta(
            titulo_actual, int(bol_id), str(bol_data['fecha']),
            str(bol_data['cliente']), b_tel, b_det, b_tot_val, b_sena_val, b_saldo_val
        )
        
        info_empresa_html_b = f"<p style='margin:2px 0; color:#64748b; font-size:13px;'>{dir_empresa} {(' | ' + tel_empresa) if tel_empresa else ''}</p>" if (dir_empresa or tel_empresa) else ""
        
        boleta_html_doc = f"""
        <div style="border: 2px solid #15803d; border-radius: 8px; padding: 16px; background: #ffffff; color: #111111; font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #15803d; padding-bottom: 8px; margin-bottom: 12px;">
                <div>
                    <h2 style="margin: 0; color: #15803d; font-size: 19px;">{titulo_actual}</h2>
                    {info_empresa_html_b}
                    <h3 style="margin: 3px 0; color: #333; font-size: 13px;">BOLETA / COMPROBANTE DE PAGO</h3>
                </div>
                <div style="text-align: right;">
                    <h3 style="margin: 0; color: #15803d; font-size: 15px;">BOLETA N° #{int(bol_id):04d}</h3>
                    <p style="margin: 3px 0; font-size: 12px; color: #666;">Fecha: {bol_data['fecha']}</p>
                </div>
            </div>
            
            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 8px 12px; margin-bottom: 14px; font-size: 13px;">
                <p style="margin: 2px 0;"><strong>Cliente:</strong> {bol_data['cliente']}</p>
                <p style="margin: 2px 0;"><strong>Teléfono:</strong> {b_tel}</p>
            </div>

            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #15803d; color: #ffffff;">
                            <th style="padding: 7px; text-align: left;">Detalle del Trabajo</th>
                            <th style="padding: 7px; text-align: right; width: 120px;">Importe</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom: 1px solid #ddd;">
                            <td style="padding: 9px 7px;">{b_det}</td>
                            <td style="padding: 9px 7px; text-align: right; font-weight: bold;">{moneda}{b_tot_val:,.2f}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div style="display: flex; justify-content: flex-end; margin-bottom: 14px;">
                <div style="width: 250px; background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 8px 12px; border-radius: 6px; font-size: 13px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                        <span>Total:</span>
                        <strong>{moneda}{b_tot_val:,.2f}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 3px; color: #15803d;">
                        <span>Abonado / Seña:</span>
                        <strong>{moneda}{b_sena_val:,.2f}</strong>
                    </div>
                    <hr style="margin: 5px 0; border: none; border-top: 1px solid #94a3b8;">
                    <div style="display: flex; justify-content: space-between; font-size: 14px; color: #b91c1c;">
                        <strong>Saldo Pendiente:</strong>
                        <strong>{moneda}{b_saldo_val:,.2f}</strong>
                    </div>
                </div>
            </div>

            <div style="text-align: center; border-top: 1px dashed #aaa; padding-top: 10px; color: #64748b; font-size: 11px;">
                <p style="margin: 2px;">Comprobante de entrega y registro de pago interno.</p>
                <p style="margin: 2px;">¡Muchas gracias por su compra!</p>
            </div>
        </div>
        """
        st.markdown(boleta_html_doc, unsafe_allow_html=True)
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
                var contenido = `{boleta_html_doc}`;
                var ventana = window.open('', '', 'height=700,width=900');
                ventana.document.write('<html><head><title>Boleta #{bol_id}</title></head><body style="margin: 20px;">');
                ventana.document.write(contenido);
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
# VISTA 4: HISTORIAL ENTREGADOS
# ==========================================
elif st.session_state.seccion_activa == "Entregados":
    st.subheader("✅ Trabajos Entregados")
    
    df_entregados = run_query(f"""
        SELECT cliente AS 'Cliente', tipo_trabajo AS 'Trabajo', fecha_carga AS 'Fecha Carga', fecha_entrega AS 'Fecha Entrega',
               costo_material AS 'Costo ({moneda})', precio_venta AS 'Venta ({moneda})',
               (precio_venta - costo_material) AS 'Ganancia ({moneda})'
        FROM trabajos 
        WHERE estado = 'Entregado y Cobrado'
        ORDER BY fecha_entrega DESC, id DESC
    """)
    
    if not df_entregados.empty:
        col_met1, col_met2, col_met3 = st.columns(3)
        total_cobrado = df_entregados[f'Venta ({moneda})'].sum()
        total_costos_ent = df_entregados[f'Costo ({moneda})'].sum()
        ganancia_ent = df_entregados[f'Ganancia ({moneda})'].sum()
        
        col_met1.metric("Total Cobrado", f"{moneda}{total_cobrado:,.2f}")
        col_met2.metric("Costos Producción", f"{moneda}{total_costos_ent:,.2f}")
        col_met3.metric("Ganancia Neta", f"{moneda}{ganancia_ent:,.2f}")

        st.divider()

        busq_ent = st.text_input("🔍 Buscar:", key="busq_ent_key", placeholder="Cliente o trabajo...")
        if busq_ent:
            df_entregados = df_entregados[
                df_entregados['Cliente'].str.contains(busq_ent, case=False, na=False) |
                df_entregados['Trabajo'].str.contains(busq_ent, case=False, na=False)
            ]
            
        st.dataframe(df_entregados, use_container_width=True)
    else:
        st.info("Todavía no hay trabajos marcados como 'Entregado y Cobrado'.")

# ==========================================
# VISTA 5: PROVEEDORES Y COMPRAS
# ==========================================
elif st.session_state.seccion_activa == "Compras":
    st.subheader("🛒 Registro de Compras")
    
    df_compras = run_query(f"SELECT id AS 'ID', fecha AS 'Fecha', factura AS 'Factura', proveedor AS 'Proveedor', producto AS 'Producto', costo AS 'Costo ({moneda})' FROM compras ORDER BY fecha DESC, id DESC")
    
    with st.expander("➕ Cargar Nueva Compra", expanded=False):
        with st.form("form_compra", clear_on_submit=True):
            proveedor = st.text_input("Proveedor *")
            factura = st.text_input("N° Factura / Remito")
            fecha_compra = st.date_input("Fecha de Compra", value=date.today())
            producto = st.text_input("Producto / Material *")
            costo_compra = st.number_input(f"Costo Total ({moneda}) *", min_value=0.0, step=100.0)
            
            submit_compra = st.form_submit_button("Guardar Factura / Compra", use_container_width=True)
            
            if submit_compra:
                if proveedor.strip() and producto.strip() and costo_compra > 0:
                    if IS_POSTGRES:
                        run_query("INSERT INTO compras (factura, proveedor, fecha, producto, costo) VALUES (:f, :p, :fe, :pr, :c)",
                                  {"f": factura, "p": proveedor, "fe": fecha_compra, "pr": producto, "c": costo_compra}, fetch=False)
                    else:
                        run_query("INSERT INTO compras (factura, proveedor, fecha, producto, costo) VALUES (?, ?, ?, ?, ?)",
                                  (factura, proveedor, fecha_compra, producto, costo_compra), fetch=False)
                    st.success("Compra guardada correctamente.")
                    st.rerun()

    with st.expander("🗑️ Borrar Compra", expanded=False):
        if not df_compras.empty:
            opciones_c_del = {
                f"#{row['ID']} - {row['Proveedor']} ({row['Producto']}) - {moneda}{row[f'Costo ({moneda})']:,.0f}": row['ID']
                for _, row in df_compras.iterrows()
            }
            c_del_sel = st.selectbox("Seleccionar compra a borrar:", list(opciones_c_del.keys()), key="del_c_sel")
            c_del_id = opciones_c_del[c_del_sel]
            
            st.write("")
            if st.button(f"❌ Borrar Factura #{c_del_id}", type="primary", use_container_width=True):
                if IS_POSTGRES:
                    run_query("DELETE FROM compras WHERE id = :id", {"id": c_del_id}, fetch=False)
                else:
                    run_query("DELETE FROM compras WHERE id = ?", (c_del_id,), fetch=False)
                st.warning(f"Factura #{c_del_id} eliminada.")
                st.rerun()

    st.divider()

    if not df_compras.empty:
        busqueda_prov = st.text_input("🔍 Buscar en compras:", key="search_prov", placeholder="Proveedor o producto...")
        if busqueda_prov:
            df_compras = df_compras[
                df_compras['Proveedor'].str.contains(busqueda_prov, case=False, na=False) |
                df_compras['Producto'].str.contains(busqueda_prov, case=False, na=False)
            ]
        st.dataframe(df_compras, use_container_width=True)

# ==========================================
# VISTA 6: BALANCE GENERAL
# ==========================================
elif st.session_state.seccion_activa == "Balance":
    st.subheader("📊 Rendimiento Financiero")
    
    df_ventas_total = run_query("SELECT SUM(precio_venta) as total_ventas FROM trabajos")
    df_gastos_total = run_query("SELECT SUM(costo) as total_gastos FROM compras")
    
    total_ventas = df_ventas_total['total_ventas'].iloc[0] or 0.0
    total_gastos = df_gastos_total['total_gastos'].iloc[0] or 0.0
    ganancia_neta = total_ventas - total_gastos
    margen = (ganancia_neta / total_ventas * 100) if total_ventas > 0 else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(f"Ingresos", f"{moneda}{total_ventas:,.2f}")
    kpi2.metric(f"Egresos", f"{moneda}{total_gastos:,.2f}")
    kpi3.metric(f"Ganancia Neta", f"{moneda}{ganancia_neta:,.2f}", delta=f"{moneda}{ganancia_neta:,.2f}")
    kpi4.metric("Margen", f"{margen:.1f}%")

    st.divider()

    st.markdown("**Comparativa: Ventas vs Compras**")
    df_comp = pd.DataFrame({
        "Concepto": ["Ventas", "Compras"],
        f"Monto ({moneda})": [total_ventas, total_gastos]
    })
    fig_bar = px.bar(
        df_comp, x="Concepto", y=f"Monto ({moneda})", color="Concepto",
        color_discrete_map={"Ventas": "#3b82f6", "Compras": "#ef4444"},
        template="plotly_dark"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# VISTA 7: CONFIGURACIÓN
# ==========================================
elif st.session_state.seccion_activa == "Configuracion":
    st.subheader("⚙️ Configuración del Taller")
    
    with st.form("form_configuracion_ampliada"):
        cfg_titulo = st.text_input("Nombre de la Empresa:", value=titulo_actual)
        cfg_subtitulo = st.text_input("Subtítulo:", value=subtitulo_actual)
        cfg_tel = st.text_input("Teléfono / WhatsApp:", value=tel_empresa)
        cfg_dir = st.text_input("Dirección:", value=dir_empresa)
        cfg_moneda = st.text_input("Símbolo de Moneda (ej: $, USD):", value=moneda)
        cfg_pie = st.text_area("Leyenda en Presupuestos:", value=pie_empresa)
        
        guardar_cfg = st.form_submit_button("💾 Guardar Configuración", use_container_width=True)
        if guardar_cfg:
            set_config("titulo_app", cfg_titulo.strip())
            set_config("subtitulo_app", cfg_subtitulo.strip())
            set_config("telefono_empresa", cfg_tel.strip())
            set_config("direccion_empresa", cfg_dir.strip())
            set_config("simbolo_moneda", cfg_moneda.strip() if cfg_moneda.strip() else "$")
            set_config("mensaje_pie", cfg_pie.strip())
            st.success("¡Configuración actualizada!")
            st.rerun()

    with st.form("form_nuevo_tipo_trabajo", clear_on_submit=True):
        nuevo_tipo_txt = st.text_input("Agregar nuevo rubro sugerido (ej: Cartel Neón LED):")
        btn_add_tipo = st.form_submit_button("➕ Agregar Rubro", use_container_width=True)
        if btn_add_tipo:
            if nuevo_tipo_txt.strip():
                try:
                    if IS_POSTGRES:
                        run_query("INSERT INTO tipos_trabajo (nombre) VALUES (:n)", {"n": nuevo_tipo_txt.strip()}, fetch=False)
                    else:
                        run_query("INSERT INTO tipos_trabajo (nombre) VALUES (?)", (nuevo_tipo_txt.strip(),), fetch=False)
                    st.success(f"Rubro '{nuevo_tipo_txt}' agregado.")
                    st.rerun()
                except Exception:
                    st.warning("Ese rubro ya existe.")

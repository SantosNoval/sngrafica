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

# ---------------- CONFIGURACIÓN DE PÁGINA ----------------
st.set_page_config(
    page_title="Gestion Grafica SN Grafica",
    page_icon="⚡",
    layout="wide"
)

DB_NAME = "grafica.db"

# ---------------- BASE DE DATOS E INICIALIZACIÓN ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura TEXT,
            proveedor TEXT,
            fecha DATE,
            producto TEXT,
            costo REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trabajos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_carga DATE,
            fecha_entrega DATE,
            cliente TEXT,
            tipo_trabajo TEXT,
            estado TEXT,
            costo_material REAL,
            precio_venta REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE,
            cliente TEXT,
            telefono TEXT,
            detalle TEXT,
            total REAL,
            sena REAL,
            saldo REAL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tipos_trabajo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE
        )
    """)
    
    configs_defecto = {
        "titulo_app": "SN Grafica",
        "subtitulo_app": "Sistema integral de gestión de producción, cotizaciones y balance",
        "telefono_empresa": "",
        "direccion_empresa": "",
        "mensaje_pie": "Presupuesto válido por 15 días. Documento no válido como factura fiscal.",
        "simbolo_moneda": "$"
    }
    for k, v in configs_defecto.items():
        cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (k, v))
    
    tipos_base = [
        "Cartelería / Lona",
        "Stickers / Vinilo de Corte",
        "Impresión UV / Rígidos",
        "Sublimación / Textil",
        "Diseño Gráfico",
        "Plotter Vehicular",
        "Varios"
    ]
    for tipo in tipos_base:
        cursor.execute("INSERT OR IGNORE INTO tipos_trabajo (nombre) VALUES (?)", (tipo,))
        
    conn.commit()
    conn.close()

init_db()

# ---------------- FUNCIONES CRUD ----------------
def run_query(query, params=(), fetch=True):
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

def get_config(clave, default=""):
    df = run_query("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    if not df.empty:
        return df['valor'].iloc[0]
    return default

def set_config(clave, valor):
    run_query("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor), fetch=False)

def get_tipos_trabajo():
    df = run_query("SELECT nombre FROM tipos_trabajo ORDER BY nombre ASC")
    if not df.empty:
        return df['nombre'].tolist()
    return ["General"]

ESTADOS_TRABAJO = [
    "Pendiente",
    "En Producción",
    "Listo para Entrega",
    "Entregado y Cobrado"
]

ESTADO_BADGES = {
    "Pendiente": "🔴 Pendiente",
    "En Producción": "🟡 En Producción",
    "Listo para Entrega": "🟢 Listo para Entrega",
    "Entregado y Cobrado": "🔵 Entregado y Cobrado"
}

# ---------------- CONFIGURACIONES ----------------
titulo_actual = get_config("titulo_app", "SN Grafica")
subtitulo_actual = get_config("subtitulo_app", "Sistema integral de gestión de producción, cotizaciones y balance")
tel_empresa = get_config("telefono_empresa", "")
dir_empresa = get_config("direccion_empresa", "")
pie_empresa = get_config("mensaje_pie", "Presupuesto válido por 15 días.")
moneda = get_config("simbolo_moneda", "$")
tipos_actuales = get_tipos_trabajo()

# ---------------- ESTILOS CSS ESTILO PROVISUAL / MODERN SAAS ----------------
st.markdown(f"""
<style>
    /* Ocultar barra default de Streamlit */
    #MainMenu, footer, header, .stDeployButton, [data-testid="stDecoration"], [data-testid="stHeader"] {{
        display: none !important;
    }}
    
    /* Fondo oscuro profundo general */
    .stApp {{
        background-color: #050508;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}

    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1350px;
    }}

    /* Botones de navegación superior: Forzar una sola línea (nowrap) y estilo píldora */
    div[data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"] {{
        background-color: #12141c !important;
        color: #cbd5e1 !important;
        border: 1px solid #1e293b !important;
        border-radius: 9999px !important;
        padding: 6px 12px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"]:hover {{
        background-color: #1e2230 !important;
        color: #ffffff !important;
        border-color: #3b82f6 !important;
    }}
    
    /* Botón de acción principal destacado */
    div[data-testid="stHorizontalBlock"] button[data-testid="baseButton-primary"] {{
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 9999px !important;
        padding: 6px 16px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.35) !important;
    }}

    /* Hero Banner moderno con Gradiente de Texto */
    .hero-container {{
        text-align: center;
        padding: 35px 20px 25px 20px;
        margin-bottom: 25px;
    }}
    .hero-title {{
        font-size: 48px;
        font-weight: 800;
        letter-spacing: -1.5px;
        line-height: 1.15;
        margin-bottom: 12px;
        background: linear-gradient(90deg, #fef08a 0%, #60a5fa 50%, #818cf8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .hero-subtitle {{
        font-size: 17px;
        color: #94a3b8;
        max-width: 650px;
        margin: 0 auto;
        line-height: 1.5;
    }}
</style>
""", unsafe_allow_html=True)

# ---------------- GENERACIÓN DE PDF ----------------
def generar_pdf_presupuesto(empresa, p_id, fecha, cliente, telefono, tipo, detalle, cant, unitario, total, pie_txt_custom):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    title_style = ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor("#1e3a8a"))
    sub_style = ParagraphStyle(name='SubStyle', fontName='Helvetica', fontSize=11, leading=14, textColor=colors.HexColor("#475569"))
    bold_style = ParagraphStyle(name='BoldStyle', fontName='Helvetica-Bold', fontSize=10, leading=13)
    normal_style = ParagraphStyle(name='NormalStyle', fontName='Helvetica', fontSize=10, leading=13)
    
    header_data = [
        [Paragraph(f"<b>{empresa}</b>", title_style), Paragraph(f"<b>PRESUPUESTO #{p_id:04d}</b><br/>Fecha: {fecha}", sub_style)]
    ]
    t_header = Table(header_data, colWidths=[320, 220])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#1e3a8a")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8)
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 14))
    
    client_data = [
        [Paragraph("<b>Cliente:</b>", bold_style), Paragraph(str(cliente), normal_style), Paragraph("<b>Teléfono:</b>", bold_style), Paragraph(str(telefono), normal_style)],
        [Paragraph("<b>Tipo de Trabajo:</b>", bold_style), Paragraph(str(tipo), normal_style), Paragraph("", normal_style), Paragraph("", normal_style)]
    ]
    t_client = Table(client_data, colWidths=[90, 200, 70, 180])
    t_client.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(t_client)
    elements.append(Spacer(1, 14))
    
    items_data = [
        [Paragraph("<b>Detalle / Especificaciones</b>", bold_style), Paragraph("<b>Cant.</b>", bold_style), Paragraph("<b>P. Unitario</b>", bold_style), Paragraph("<b>Total</b>", bold_style)],
        [Paragraph(str(detalle), normal_style), Paragraph(f"{cant:,.0f}", normal_style), Paragraph(f"{moneda}{unitario:,.2f}", normal_style), Paragraph(f"{moneda}{total:,.2f}", bold_style)]
    ]
    t_items = Table(items_data, colWidths=[280, 60, 100, 100])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3a8a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 14))
    
    total_data = [
        ["", Paragraph(f"<b>TOTAL: {moneda}{total:,.2f}</b>", ParagraphStyle('Tot', fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor("#1e3a8a"), alignment=2))]
    ]
    t_tot = Table(total_data, colWidths=[340, 200])
    t_tot.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#f1f5f9")),
        ('BOX', (1,0), (1,0), 1, colors.HexColor("#1e3a8a")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_tot)
    elements.append(Spacer(1, 20))
    
    pie_txt = Paragraph(f"<font size='8' color='#64748b'>{pie_txt_custom}<br/>¡Gracias por consultarnos!</font>", ParagraphStyle('Pie', alignment=1))
    elements.append(pie_txt)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def generar_pdf_boleta(empresa, b_id, fecha, cliente, telefono, detalle, total, sena, saldo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    elements = []
    
    title_style = ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=colors.HexColor("#15803d"))
    sub_style = ParagraphStyle(name='SubStyle', fontName='Helvetica', fontSize=11, leading=14, textColor=colors.HexColor("#475569"))
    bold_style = ParagraphStyle(name='BoldStyle', fontName='Helvetica-Bold', fontSize=10, leading=13)
    normal_style = ParagraphStyle(name='NormalStyle', fontName='Helvetica', fontSize=10, leading=13)
    
    header_data = [
        [Paragraph(f"<b>{empresa}</b>", title_style), Paragraph(f"<b>BOLETA DE PAGO #{b_id:04d}</b><br/>Fecha: {fecha}", sub_style)]
    ]
    t_header = Table(header_data, colWidths=[320, 220])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#15803d")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8)
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 14))
    
    client_data = [
        [Paragraph("<b>Cliente:</b>", bold_style), Paragraph(str(cliente), normal_style), Paragraph("<b>Teléfono:</b>", bold_style), Paragraph(str(telefono), normal_style)]
    ]
    t_client = Table(client_data, colWidths=[90, 200, 70, 180])
    t_client.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#86efac")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_client)
    elements.append(Spacer(1, 14))
    
    items_data = [
        [Paragraph("<b>Detalle del Trabajo Entregado / Encargado</b>", bold_style), Paragraph("<b>Total</b>", bold_style)],
        [Paragraph(str(detalle), normal_style), Paragraph(f"{moneda}{total:,.2f}", bold_style)]
    ]
    t_items = Table(items_data, colWidths=[400, 140])
    t_items.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#15803d")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_items)
    elements.append(Spacer(1, 14))
    
    pago_data = [
        ["", Paragraph(f"Total Trabajo: <b>{moneda}{total:,.2f}</b>", normal_style)],
        ["", Paragraph(f"<font color='#15803d'>Monto Abonado / Seña: <b>{moneda}{sena:,.2f}</b></font>", normal_style)],
        ["", Paragraph(f"<font color='#b91c1c'><b>SALDO PENDIENTE: {moneda}{saldo:,.2f}</b></font>", ParagraphStyle('Saldo', fontName='Helvetica-Bold', fontSize=11, alignment=0))]
    ]
    t_pago = Table(pago_data, colWidths=[320, 220])
    t_pago.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (1,0), (1,-1), 1, colors.HexColor("#cbd5e1")),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(t_pago)
    elements.append(Spacer(1, 20))
    
    pie_txt = Paragraph("<font size='8' color='#64748b'>Comprobante de entrega y registro de pago interno.<br/>¡Muchas gracias por su compra!</font>", ParagraphStyle('Pie', alignment=1))
    elements.append(pie_txt)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# ---------------- ESTADO DE NAVEGACIÓN ACTIVA ----------------
if 'seccion_activa' not in st.session_state:
    st.session_state.seccion_activa = "Trabajos"

# ==========================================
# HEADER / NAVBAR ESTILO SAAS
# ==========================================
col_brand, col_nav, col_cta = st.columns([1.5, 6.2, 1.0])

with col_brand:
    st.markdown(f"<div style='font-size: 18px; font-weight: 800; color: #ffffff; padding-top: 6px; white-space: nowrap;'>ⓟ {titulo_actual}</div>", unsafe_allow_html=True)

with col_nav:
    n1, n2, n3, n4, n5, n6, n7 = st.columns([1, 1.35, 1, 1.25, 1, 1, 1])
    if n1.button("Trabajos", use_container_width=True): st.session_state.seccion_activa = "Trabajos"; st.rerun()
    if n2.button("Presupuestos", use_container_width=True): st.session_state.seccion_activa = "Presupuestos"; st.rerun()
    if n3.button("Boletas", use_container_width=True): st.session_state.seccion_activa = "Boletas"; st.rerun()
    if n4.button("Entregados", use_container_width=True): st.session_state.seccion_activa = "Entregados"; st.rerun()
    if n5.button("Compras", use_container_width=True): st.session_state.seccion_activa = "Compras"; st.rerun()
    if n6.button("Balance", use_container_width=True): st.session_state.seccion_activa = "Balance"; st.rerun()
    if n7.button("Ajustes", use_container_width=True): st.session_state.seccion_activa = "Configuracion"; st.rerun()

with col_cta:
    if st.button("✨ + Nuevo", type="primary", use_container_width=True):
        st.session_state.seccion_activa = "Trabajos"
        st.session_state.abrir_nuevo = True
        st.rerun()

st.markdown("<hr style='border: none; border-top: 1px solid #1e293b; margin: 8px 0 18px 0;'>", unsafe_allow_html=True)

# ==========================================
# HERO SECTION ESTILO PROVISUAL
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
    
    col_acc1, col_acc2, col_acc3 = st.columns([1.2, 1.2, 1])
    
    with col_acc1:
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
                        run_query(
                            """INSERT INTO trabajos 
                            (cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (nuevo_cli.strip(), nuevo_trabajo.strip(), nuevo_fcarga, nuevo_fentrega, nuevo_est, nuevo_costo, nuevo_precio),
                            fetch=False
                        )
                        st.session_state.abrir_nuevo = False
                        st.success("¡Trabajo guardado con éxito!")
                        st.rerun()
                    else:
                        st.error("Completá cliente, trabajo y precio de venta.")

    with col_acc2:
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
                            run_query(
                                """UPDATE trabajos 
                                   SET cliente=?, tipo_trabajo=?, fecha_carga=?, fecha_entrega=?, estado=?, costo_material=?, precio_venta=?
                                   WHERE id=?""",
                                (ed_cliente.strip(), ed_trabajo.strip(), ed_fc, ed_fe, ed_estado, ed_costo, ed_precio, id_mod),
                                fetch=False
                            )
                            st.success("¡Trabajo actualizado!")
                            st.rerun()

    with col_acc3:
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
                    run_query("DELETE FROM trabajos WHERE id=?", (id_borrar,), fetch=False)
                    st.warning(f"Trabajo #{id_borrar} eliminado.")
                    st.rerun()

    st.markdown("""
    <div style='background: #0b0f19; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 14px; margin: 15px 0;'>
        <span style='color:#94a3b8; font-size:13px; font-weight:600;'>ESTADOS: </span>
        <span style='background-color:#ffcccc; color:#900C3F; padding:2px 7px; border-radius:4px; font-size:12px; font-weight:bold;'>🔴 Pendiente</span> 
        <span style='background-color:#fff3cd; color:#856404; padding:2px 7px; border-radius:4px; font-size:12px; font-weight:bold; margin-left:4px;'>🟡 En Producción</span> 
        <span style='background-color:#d4edda; color:#155724; padding:2px 7px; border-radius:4px; font-size:12px; font-weight:bold; margin-left:4px;'>🟢 Listo para Entrega</span> 
        <span style='background-color:#cce5ff; color:#004085; padding:2px 7px; border-radius:4px; font-size:12px; font-weight:bold; margin-left:4px;'>🔵 Entregado y Cobrado</span>
    </div>
    """, unsafe_allow_html=True)

    if not df_todos_trabajos.empty:
        df_trabajos_tabla = df_todos_trabajos.copy()
        
        col_filtro1, col_filtro2 = st.columns(2)
        with col_filtro1:
            opciones_filtro = ["Todos"] + ESTADOS_TRABAJO
            estado_seleccionado = st.selectbox("Filtrar por Estado:", options=opciones_filtro, index=0)
        with col_filtro2:
            busq_trabajo = st.text_input("🔍 Buscar por Cliente o Trabajo:", key="busq_gral")

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
            'fecha_carga': 'Fecha de Carga',
            'fecha_entrega': 'Fecha de Entrega',
            'estado': 'Estado',
            'costo_material': f'Costo de Producción ({moneda})',
            'precio_venta': f'Precio de Venta ({moneda})'
        })[['Cliente', 'Trabajo', 'Fecha de Carga', 'Fecha de Entrega', 'Estado', f'Costo de Producción ({moneda})', f'Precio de Venta ({moneda})']]
        
        st.dataframe(df_mostrar, use_container_width=True)
    else:
        st.info("Todavía no hay trabajos cargados en el sistema.")

# ==========================================
# VISTA 2: PRESUPUESTOS
# ==========================================
elif st.session_state.seccion_activa == "Presupuestos":
    st.subheader("📄 Emisión de Presupuestos")
    
    col_pr1, col_pr2 = st.columns([1.1, 1])
    
    with col_pr1:
        with st.expander("➕ Crear Nuevo Presupuesto", expanded=False):
            with st.form("form_nuevo_presupuesto_detallado", clear_on_submit=True):
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    pr_cliente = st.text_input("Cliente *")
                    pr_fecha = st.date_input("Fecha", value=date.today())
                with col_c2:
                    pr_telefono = st.text_input("Teléfono / WhatsApp")
                    pr_tipo = st.selectbox("Tipo de Trabajo / Rubro", tipos_actuales, key="pr_tipo_sel")
                
                pr_detalle = st.text_area("Detalle / Especificaciones del trabajo *")
                
                col_u1, col_u2, col_u3 = st.columns(3)
                with col_u1:
                    pr_cant = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
                with col_u2:
                    pr_unitario = st.number_input(f"Precio Unitario ({moneda}) *", min_value=0.0, step=100.0)
                with col_u3:
                    pr_costo_mat = st.number_input(f"Costo Estimado Material ({moneda})", min_value=0.0, step=100.0)
                
                btn_crear_pres = st.form_submit_button("💾 Guardar Presupuesto", use_container_width=True)
                
                if btn_crear_pres:
                    total_calculado = pr_cant * pr_unitario
                    if pr_cliente.strip() and pr_unitario > 0:
                        run_query(
                            """INSERT INTO presupuestos 
                            (fecha, cliente, telefono, tipo_trabajo, detalle, cantidad, precio_unitario, precio_total, costo_material, estado) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (str(pr_fecha), pr_cliente.strip(), pr_telefono.strip(), pr_tipo, pr_detalle.strip(), pr_cant, pr_unitario, total_calculado, pr_costo_mat, "Pendiente"),
                            fetch=False
                        )
                        st.success("¡Presupuesto guardado!")
                        st.rerun()

    df_presupuestos = run_query("SELECT * FROM presupuestos ORDER BY id DESC")
    
    if not df_presupuestos.empty:
        opciones_pres = {
            f"Presupuesto #{int(row['id'])} - {row['cliente']} ({moneda}{float(row['precio_total'] or 0):,.0f})": int(row['id'])
            for _, row in df_presupuestos.iterrows()
        }
        
        with col_pr2:
            with st.expander("⚡ Gestionar Presupuesto Seleccionado", expanded=True):
                pres_sel = st.selectbox("Seleccionar Presupuesto:", list(opciones_pres.keys()), key="pres_sel_box")
                pres_id = opciones_pres[pres_sel]
                pres_data = df_presupuestos[df_presupuestos['id'] == pres_id].iloc[0]
                
                col_b_p1, col_b_p2 = st.columns(2)
                with col_b_p1:
                    if st.button("🚀 Pasar a Trabajo Activo (Taller)", use_container_width=True, key=f"btn_p_taller_{pres_id}"):
                        run_query(
                            """INSERT INTO trabajos 
                            (cliente, tipo_trabajo, fecha_carga, fecha_entrega, estado, costo_material, precio_venta) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (str(pres_data['cliente']), str(pres_data['tipo_trabajo']), str(date.today()), str(date.today()), "Pendiente", float(pres_data.get('costo_material') or 0.0), float(pres_data.get('precio_total') or 0.0)),
                            fetch=False
                        )
                        run_query("UPDATE presupuestos SET estado = 'Aprobado' WHERE id = ?", (pres_id,), fetch=False)
                        st.success(f"¡Presupuesto #{pres_id} pasado a Trabajo de Taller!")
                        st.rerun()
                
                with col_b_p2:
                    if st.button("🗑️ Borrar Presupuesto", use_container_width=True, key=f"btn_del_pres_{pres_id}"):
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
        <div style="border: 2px solid #333; border-radius: 8px; padding: 25px; background: #ffffff; color: #111111; font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; margin-bottom: 15px;">
                <div>
                    <h2 style="margin: 0; color: #1e3a8a;">{titulo_actual}</h2>
                    {info_empresa_html}
                    <h3 style="margin: 3px 0; color: #555; font-size: 15px; font-weight: normal;">PRESUPUESTO ESTIMADO</h3>
                </div>
                <div style="text-align: right;">
                    <h3 style="margin: 0; color: #333;">N° #{int(pres_id):04d}</h3>
                    <p style="margin: 3px 0; font-size: 14px; color: #666;">Fecha: {pres_data['fecha']}</p>
                </div>
            </div>
            
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 20px;">
                <p style="margin: 4px 0;"><strong>Cliente:</strong> {pres_data['cliente']}</p>
                <p style="margin: 4px 0;"><strong>Teléfono:</strong> {pr_tel}</p>
                <p style="margin: 4px 0;"><strong>Rubro / Tipo:</strong> {pres_data['tipo_trabajo']}</p>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #1e3a8a; color: #ffffff;">
                        <th style="padding: 10px; text-align: left;">Detalle del Trabajo</th>
                        <th style="padding: 10px; text-align: center; width: 80px;">Cant.</th>
                        <th style="padding: 10px; text-align: right; width: 140px;">Precio Unitario</th>
                        <th style="padding: 10px; text-align: right; width: 140px;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 12px; font-size: 14px;">{pr_det}</td>
                        <td style="padding: 12px; text-align: center; font-size: 14px;">{pr_cant_val:,.0f}</td>
                        <td style="padding: 12px; text-align: right; font-size: 14px;">{moneda}{pr_unit_val:,.2f}</td>
                        <td style="padding: 12px; text-align: right; font-size: 14px; font-weight: bold;">{moneda}{pr_tot_val:,.2f}</td>
                    </tr>
                </tbody>
            </table>

            <div style="display: flex; justify-content: flex-end; margin-bottom: 20px;">
                <div style="width: 280px; background-color: #f1f5f9; padding: 12px; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; font-size: 18px; color: #1e3a8a;">
                        <strong>TOTAL:</strong>
                        <strong>{moneda}{pr_tot_val:,.2f}</strong>
                    </div>
                </div>
            </div>

            <div style="text-align: center; border-top: 1px dashed #aaa; padding-top: 12px; color: #64748b; font-size: 12px;">
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
                label="📥 Descargar Presupuesto en PDF",
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
            <button onclick="imprimirPresupuesto()" style="width: 100%; background-color: #1e3a8a; color: white; border: none; padding: 9px 18px; font-size: 15px; font-weight: bold; border-radius: 8px; cursor: pointer;">
                🖨️ Imprimir Presupuesto Directo
            </button>
            """
            st.components.v1.html(html_impresion_pres, height=50)

# ==========================================
# VISTA 3: BOLETAS
# ==========================================
elif st.session_state.seccion_activa == "Boletas":
    st.subheader("🧾 Emisión de Boletas / Comprobantes de Pago")
    
    col_b1, col_b2 = st.columns([1.1, 1])
    
    with col_b1:
        with st.expander("➕ Generar Nueva Boleta", expanded=False):
            with st.form("form_nueva_boleta", clear_on_submit=True):
                col_bc1, col_bc2 = st.columns(2)
                with col_bc1:
                    b_cliente = st.text_input("Cliente *")
                    b_fecha = st.date_input("Fecha", value=date.today(), key="b_fecha_key")
                with col_bc2:
                    b_telefono = st.text_input("Teléfono / WhatsApp", key="b_tel_key")
                
                b_detalle = st.text_area("Detalle del trabajo / Entrega *")
                
                col_bm1, col_bm2 = st.columns(2)
                with col_bm1:
                    b_total = st.number_input(f"Total del Trabajo ({moneda}) *", min_value=0.0, step=100.0, key="b_tot_key")
                with col_bm2:
                    b_sena = st.number_input(f"Monto Abonado / Seña ({moneda}) *", min_value=0.0, step=100.0, key="b_sena_key")
                
                btn_crear_bol = st.form_submit_button("💾 Emitir Boleta", use_container_width=True)
                
                if btn_crear_bol:
                    if b_cliente.strip() and b_total > 0:
                        saldo_calc = b_total - b_sena
                        run_query(
                            """INSERT INTO boletas (fecha, cliente, telefono, detalle, total, sena, saldo) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (str(b_fecha), b_cliente.strip(), b_telefono.strip(), b_detalle.strip(), b_total, b_sena, saldo_calc),
                            fetch=False
                        )
                        st.success("¡Boleta generada con éxito!")
                        st.rerun()

    df_boletas = run_query("SELECT * FROM boletas ORDER BY id DESC")
    
    if not df_boletas.empty:
        opciones_bol = {
            f"Boleta #{int(row['id'])} - {row['cliente']} (Total: {moneda}{float(row['total'] or 0):,.0f} | Saldo: {moneda}{float(row['saldo'] or 0):,.0f})": int(row['id'])
            for _, row in df_boletas.iterrows()
        }
        
        with col_b2:
            with st.expander("⚡ Gestionar Boleta Seleccionada", expanded=True):
                bol_sel = st.selectbox("Seleccionar Boleta:", list(opciones_bol.keys()), key="bol_sel_box")
                bol_id = opciones_bol[bol_sel]
                bol_data = df_boletas[df_boletas['id'] == bol_id].iloc[0]
                
                if st.button("🗑️ Borrar Boleta", use_container_width=True, key=f"btn_del_bol_{bol_id}"):
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
        <div style="border: 2px solid #15803d; border-radius: 8px; padding: 25px; background: #ffffff; color: #111111; font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #15803d; padding-bottom: 10px; margin-bottom: 15px;">
                <div>
                    <h2 style="margin: 0; color: #15803d;">{titulo_actual}</h2>
                    {info_empresa_html_b}
                    <h3 style="margin: 3px 0; color: #333; font-size: 15px;">BOLETA / COMPROBANTE DE PAGO</h3>
                </div>
                <div style="text-align: right;">
                    <h3 style="margin: 0; color: #15803d;">BOLETA N° #{int(bol_id):04d}</h3>
                    <p style="margin: 3px 0; font-size: 14px; color: #666;">Fecha: {bol_data['fecha']}</p>
                </div>
            </div>
            
            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px; margin-bottom: 20px;">
                <p style="margin: 4px 0;"><strong>Cliente:</strong> {bol_data['cliente']}</p>
                <p style="margin: 4px 0;"><strong>Teléfono:</strong> {b_tel}</p>
            </div>

            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <thead>
                    <tr style="background-color: #15803d; color: #ffffff;">
                        <th style="padding: 10px; text-align: left;">Detalle del Trabajo Entregado / Encargado</th>
                        <th style="padding: 10px; text-align: right; width: 150px;">Importe</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #ddd;">
                        <td style="padding: 12px; font-size: 14px;">{b_det}</td>
                        <td style="padding: 12px; text-align: right; font-size: 14px; font-weight: bold;">{moneda}{b_tot_val:,.2f}</td>
                    </tr>
                </tbody>
            </table>

            <div style="display: flex; justify-content: flex-end; margin-bottom: 20px;">
                <div style="width: 300px; background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 12px; border-radius: 6px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px;">
                        <span>Total del Trabajo:</span>
                        <strong>{moneda}{b_tot_val:,.2f}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px; color: #15803d;">
                        <span>Monto Abonado / Seña:</span>
                        <strong>{moneda}{b_sena_val:,.2f}</strong>
                    </div>
                    <hr style="margin: 8px 0; border: none; border-top: 1px solid #94a3b8;">
                    <div style="display: flex; justify-content: space-between; font-size: 16px; color: #b91c1c;">
                        <strong>Saldo Pendiente:</strong>
                        <strong>{moneda}{b_saldo_val:,.2f}</strong>
                    </div>
                </div>
            </div>

            <div style="text-align: center; border-top: 1px dashed #aaa; padding-top: 12px; color: #64748b; font-size: 12px;">
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
                label="📥 Descargar Boleta en PDF",
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
            <button onclick="imprimirBoletaDirecta()" style="width: 100%; background-color: #15803d; color: white; border: none; padding: 9px 18px; font-size: 15px; font-weight: bold; border-radius: 8px; cursor: pointer;">
                🖨️ Imprimir Boleta Directa
            </button>
            """
            st.components.v1.html(html_impresion_bol, height=50)

# ==========================================
# VISTA 4: HISTORIAL ENTREGADOS
# ==========================================
elif st.session_state.seccion_activa == "Entregados":
    st.subheader("✅ Historial de Trabajos Finalizados y Entregados")
    
    df_entregados = run_query(f"""
        SELECT cliente AS 'Cliente', tipo_trabajo AS 'Trabajo', fecha_carga AS 'Fecha de Carga', fecha_entrega AS 'Fecha de Entrega',
               costo_material AS 'Costo de Producción ({moneda})', precio_venta AS 'Precio de Venta ({moneda})',
               (precio_venta - costo_material) AS 'Ganancia Estimada ({moneda})'
        FROM trabajos 
        WHERE estado = 'Entregado y Cobrado'
        ORDER BY fecha_entrega DESC, id DESC
    """)
    
    if not df_entregados.empty:
        col_met1, col_met2, col_met3 = st.columns(3)
        total_cobrado = df_entregados[f'Precio de Venta ({moneda})'].sum()
        total_costos_ent = df_entregados[f'Costo de Producción ({moneda})'].sum()
        ganancia_ent = df_entregados[f'Ganancia Estimada ({moneda})'].sum()
        
        col_met1.metric("Total Cobrado", f"{moneda}{total_cobrado:,.2f}")
        col_met2.metric("Costos Producción Directos", f"{moneda}{total_costos_ent:,.2f}")
        col_met3.metric("Ganancia Neta en Entregados", f"{moneda}{ganancia_ent:,.2f}")

        st.divider()

        busq_ent = st.text_input("🔍 Buscar en historial de entregados (Cliente o Trabajo):", key="busq_ent_key")
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
    st.subheader("🛒 Registro de Facturas y Compras")
    
    df_compras = run_query(f"SELECT id AS 'ID', fecha AS 'Fecha', factura AS 'N° Factura', proveedor AS 'Proveedor', producto AS 'Producto', costo AS 'Costo ({moneda})' FROM compras ORDER BY fecha DESC, id DESC")
    
    col_c1, col_c2 = st.columns([1.5, 1])
    
    with col_c1:
        with st.expander("➕ Cargar Nueva Compra / Factura", expanded=False):
            with st.form("form_compra", clear_on_submit=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    proveedor = st.text_input("Proveedor *")
                    factura = st.text_input("N° Factura / Remito")
                with col2:
                    fecha_compra = st.date_input("Fecha de Compra", value=date.today())
                    producto = st.text_input("Producto / Material (ej: Vinilo, Lona, Tintas) *")
                with col3:
                    costo_compra = st.number_input(f"Costo Total ({moneda}) *", min_value=0.0, step=100.0)
                
                submit_compra = st.form_submit_button("Guardar Factura / Compra")
                
                if submit_compra:
                    if proveedor.strip() and producto.strip() and costo_compra > 0:
                        run_query(
                            "INSERT INTO compras (factura, proveedor, fecha, producto, costo) VALUES (?, ?, ?, ?, ?)",
                            (factura, proveedor, fecha_compra, producto, costo_compra),
                            fetch=False
                        )
                        st.success("Compra guardada correctamente.")
                        st.rerun()

    with col_c2:
        with st.expander("🗑️ Borrar Factura / Compra", expanded=False):
            if not df_compras.empty:
                opciones_c_del = {
                    f"#{row['ID']} - {row['Proveedor']} ({row['Producto']}) - {moneda}{row[f'Costo ({moneda})']:,.0f}": row['ID']
                    for _, row in df_compras.iterrows()
                }
                c_del_sel = st.selectbox("Seleccionar compra a borrar:", list(opciones_c_del.keys()), key="del_c_sel")
                c_del_id = opciones_c_del[c_del_sel]
                
                st.write("")
                if st.button(f"❌ Borrar Factura #{c_del_id}", type="primary", use_container_width=True):
                    run_query("DELETE FROM compras WHERE id = ?", (c_del_id,), fetch=False)
                    st.warning(f"Factura #{c_del_id} eliminada.")
                    st.rerun()

    st.divider()

    if not df_compras.empty:
        busqueda_prov = st.text_input("🔍 Buscar en compras:", key="search_prov")
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
    st.subheader("📊 Rendimiento Financiero del Taller")
    
    df_ventas_total = run_query("SELECT SUM(precio_venta) as total_ventas FROM trabajos")
    df_gastos_total = run_query("SELECT SUM(costo) as total_gastos FROM compras")
    
    total_ventas = df_ventas_total['total_ventas'].iloc[0] or 0.0
    total_gastos = df_gastos_total['total_gastos'].iloc[0] or 0.0
    ganancia_neta = total_ventas - total_gastos
    margen = (ganancia_neta / total_ventas * 100) if total_ventas > 0 else 0.0

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(f"Ingresos Totales (Ventas)", f"{moneda}{total_ventas:,.2f}")
    kpi2.metric(f"Egresos Totales (Compras)", f"{moneda}{total_gastos:,.2f}")
    kpi3.metric(f"Ganancia Neta", f"{moneda}{ganancia_neta:,.2f}", delta=f"{moneda}{ganancia_neta:,.2f}")
    kpi4.metric("Margen de Ganancia", f"{margen:.1f}%")

    st.divider()

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.markdown("**Comparativa: Ventas vs Compras**")
        df_comp = pd.DataFrame({
            "Concepto": ["Ventas (Ingresos)", "Compras (Egresos)"],
            f"Monto ({moneda})": [total_ventas, total_gastos]
        })
        fig_bar = px.bar(
            df_comp, x="Concepto", y=f"Monto ({moneda})", color="Concepto",
            color_discrete_map={"Ventas (Ingresos)": "#3b82f6", "Compras (Egresos)": "#ef4444"},
            template="plotly_dark"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_g2:
        st.markdown("**Distribución de Trabajos por Tipo**")
        df_tipos = run_query("SELECT tipo_trabajo AS 'Tipo', COUNT(*) as Cantidad FROM trabajos GROUP BY tipo_trabajo")
        if not df_tipos.empty:
            fig_pie = px.pie(df_tipos, values="Cantidad", names="Tipo", hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

# ==========================================
# VISTA 7: CONFIGURACIÓN
# ==========================================
elif st.session_state.seccion_activa == "Configuracion":
    st.subheader("⚙️ Configuración General y Personalización")
    
    col_cfg1, col_cfg2 = st.columns(2)
    
    with col_cfg1:
        st.markdown("### 🏢 Datos de la Marca y Taller")
        with st.form("form_configuracion_ampliada"):
            cfg_titulo = st.text_input("Nombre de la Empresa / Título Header:", value=titulo_actual)
            cfg_subtitulo = st.text_input("Subtítulo del Hero:", value=subtitulo_actual)
            cfg_tel = st.text_input("Teléfono / WhatsApp de contacto:", value=tel_empresa)
            cfg_dir = st.text_input("Dirección / Ubicación:", value=dir_empresa)
            cfg_moneda = st.text_input("Símbolo de Moneda (ej: $, USD, €):", value=moneda)
            cfg_pie = st.text_area("Leyenda / Pie en Presupuestos:", value=pie_empresa)
            
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

    with col_cfg2:
        st.markdown("### 🏷️ Tipos de Trabajo Sugeridos")
        with st.form("form_nuevo_tipo_trabajo", clear_on_submit=True):
            nuevo_tipo_txt = st.text_input("Agregar nuevo rubro sugerido (ej: Neón LED):")
            btn_add_tipo = st.form_submit_button("➕ Agregar Sugerencia", use_container_width=True)
            if btn_add_tipo:
                if nuevo_tipo_txt.strip():
                    try:
                        run_query("INSERT INTO tipos_trabajo (nombre) VALUES (?)", (nuevo_tipo_txt.strip(),), fetch=False)
                        st.success(f"Rubro '{nuevo_tipo_txt}' agregado.")
                        st.rerun()
                    except Exception:
                        st.warning("Ese rubro ya existe.")
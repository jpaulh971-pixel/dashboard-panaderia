# -*- coding: utf-8 -*-
"""
Dashboard ERP Gastronómico Pastelería Industrial PRO
Pedidos por tienda -> consolidación -> OP -> explosión de recetas -> semáforos -> compras -> picking PEPS/FIFO -> inventario -> producción -> mermas -> KPIs.

Ejecutar:
    streamlit run Dashboard_ERP_Gastronomico_Pasteleria_Industrial_PRO.py
"""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
import re
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    PLOTLY_OK = True
except Exception:
    PLOTLY_OK = False

st.set_page_config(page_title="ERP Pastelería Industrial PRO", page_icon="🥐", layout="wide", initial_sidebar_state="expanded")

CLIENTE_RUC = "20603136323"
CLIENTE_RAZON_SOCIAL = "ECCLA S.A.C."

st.markdown("""
<style>
.main .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
h1, h2, h3 {color:#1f2937;}
.kpi-card {border-radius:18px; padding:16px 18px; border:1px solid #e5e7eb; background:#fff; box-shadow:0 2px 8px rgba(0,0,0,.04); min-height:112px;}
.kpi-title {font-size:.82rem; color:#4b5563; margin-bottom:6px;}
.kpi-value {font-size:1.45rem; font-weight:800; color:#111827;}
.kpi-note {font-size:.78rem; color:#6b7280; margin-top:4px;}
.section-note {border-left:5px solid #111827; padding:.70rem .95rem; background:#f9fafb; border-radius:10px; margin:.6rem 0 1rem 0;}
.flow-box {border:1px solid #e5e7eb; border-radius:16px; padding:14px; background:#fff; text-align:center; font-weight:700; color:#111827; box-shadow:0 1px 4px rgba(0,0,0,.04);}
.lean-badge {display:inline-block; padding:6px 10px; margin:4px 6px 8px 0; border-radius:999px; background:#111827; color:#ffffff; font-size:.78rem; font-weight:800; letter-spacing:.01em;}
.lean-badge-green {background:#166534;}
.lean-badge-blue {background:#1d4ed8;}
.lean-badge-red {background:#991b1b;}
.lean-badge-yellow {background:#92400e;}
.lean-badge-purple {background:#6d28d9;}
.lean-card {border:1px solid #e5e7eb; border-radius:18px; padding:18px; background:#ffffff; box-shadow:0 2px 8px rgba(0,0,0,.04); margin-top:10px;}
.lean-route {font-size:1.15rem; font-weight:900; color:#111827; line-height:1.8;}
.timeline-card {border-left:6px solid #111827; border-radius:14px; padding:13px 15px; margin:10px 0; background:#ffffff; border-top:1px solid #e5e7eb; border-right:1px solid #e5e7eb; border-bottom:1px solid #e5e7eb; box-shadow:0 1px 5px rgba(0,0,0,.04);}
.timeline-ok {border-left-color:#166534;}
.timeline-warn {border-left-color:#92400e;}
.timeline-bad {border-left-color:#991b1b;}
.timeline-title {font-weight:900; color:#111827; font-size:1rem;}
.timeline-detail {color:#4b5563; font-size:.88rem; margin-top:2px;}
</style>
""", unsafe_allow_html=True)



TIENDAS_CREDENCIALES = {
    "Surco": "surco123",
    "Miraflores": "miraflores123",
    "San Isidro": "sanisidro123",
    "La Molina": "lamolina123",
    "San Borja": "sanborja123",
    "Barranco": "barranco123",
    "Chorrillos": "chorrillos123",
    "Magdalena": "magdalena123",
    "Pueblo Libre": "pueblolibre123",
    "San Miguel": "sanmiguel123",
}

ADMIN_CREDENCIALES = {"Administrador Central": "admin123"}
LOGIN_CREDENCIALES = {**ADMIN_CREDENCIALES, **TIENDAS_CREDENCIALES}

if "login_ok" not in st.session_state:
    st.session_state.login_ok = False
if "tienda_actual" not in st.session_state:
    st.session_state.tienda_actual = None

if not st.session_state.login_ok:
    st.title("🔐 Acceso ERP Pastelería Industrial PRO")
    st.markdown("""
    <div class="section-note">
    Selecciona tu tienda e ingresa la contraseña asignada para registrar pedidos y acceder al sistema ERP.
    </div>
    """, unsafe_allow_html=True)
    login_col1, login_col2, login_col3 = st.columns([1, 1.2, 1])
    with login_col2:
        tienda_login = st.selectbox("Usuario / Tienda", list(LOGIN_CREDENCIALES.keys()), key="login_tienda_select")
        password_login = st.text_input("Contraseña", type="password", key="login_password_input")
        if st.button("Ingresar al sistema", use_container_width=True):
            if password_login == LOGIN_CREDENCIALES.get(tienda_login):
                st.session_state.login_ok = True
                st.session_state.tienda_actual = tienda_login
                st.success(f"Acceso autorizado. Bienvenido, {tienda_login}.")
                st.rerun()
            else:
                st.error("Credenciales incorrectas. Verifica la tienda y la contraseña.")
    st.stop()


def today() -> date:
    return date.today()


def today_str() -> str:
    return today().isoformat()


def money(x: float) -> str:
    try:
        return f"S/ {float(x):,.2f}"
    except Exception:
        return "S/ 0.00"


def coerce_num_series(s: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").fillna(default)


# FIX BUG TypeError - conversión segura de escalares que pueden venir como None/NaN desde data_editor
def safe_float(value, default: float = 0.0) -> float:
    """Convierte a float de forma segura. Filas nuevas en st.data_editor pueden traer None/NaN."""  # FIX BUG TypeError
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):  # FIX BUG TypeError
            return default  # FIX BUG TypeError
        if pd.isna(value):  # FIX BUG TypeError
            return default  # FIX BUG TypeError
        return float(value)  # FIX BUG TypeError
    except Exception:
        return default  # FIX BUG TypeError


def coerce_date_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date
    return df


def safe_div(a, b) -> float:
    try:
        return float(a) / float(b) if float(b) != 0 else 0.0
    except Exception:
        return 0.0


def kpi(title: str, value: str, note: str = ""):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-note">{note}</div>
    </div>
    """, unsafe_allow_html=True)



def lean_badge(text: str, color: str = "blue"):
    color_map = {
        "green": "lean-badge-green",
        "blue": "lean-badge-blue",
        "red": "lean-badge-red",
        "yellow": "lean-badge-yellow",
        "purple": "lean-badge-purple",
        "dark": "lean-badge",
    }
    cls = color_map.get(color, "lean-badge")
    st.markdown(f'<span class="lean-badge {cls}">{text}</span>', unsafe_allow_html=True)


def lean_route_panel():
    st.markdown(
        """
        <div class="lean-card">
            <div class="lean-route">
                5S → Trabajo Estándar → Control Visual → Kanban → JIT → Jidoka → Kaizen → Six Sigma → Contabilidad Lean
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**5S / Trabajo Estándar:** orden, ubicación, recetas, picking y operación repetible.")
        st.markdown("**Control Visual / Andon:** semáforos de disponibilidad, faltantes y alertas.")
        st.markdown("**Kanban / JIT:** compras sugeridas por consumo real y reposición oportuna.")
    with c2:
        st.markdown("**Jidoka:** detención o bloqueo cuando hay faltantes o desviaciones.")
        st.markdown("**Kaizen:** mejora continua desde pedidos, almacén, producción y costos.")
        st.markdown("**Six Sigma:** reducción de variabilidad, mermas, diferencias y reprocesos.")
    with c3:
        st.markdown("**Contabilidad Lean:** costo unitario, merma valorizada, rentabilidad y decisiones gerenciales.")
        st.markdown("**Objetivo:** producir lo necesario, con menos desperdicio, menos inventario oculto y mejor margen.")
        st.markdown("**Resultado:** flujo operativo controlado de tienda a producción y almacén.")



def timeline_step(title: str, detail: str, status: str = "ok"):
    cls = {"ok": "timeline-ok", "warn": "timeline-warn", "bad": "timeline-bad"}.get(status, "timeline-ok")
    st.markdown(
        f"""
        <div class="timeline-card {cls}">
            <div class="timeline-title">{title}</div>
            <div class="timeline-detail">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
def generar_clave_op(tienda: str, producto: str, fecha: date, correlativo: int) -> str:
    """Genera la clave de OP bajo el formato OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    tienda_slug = re.sub(r"[^A-Za-z0-9]", "", tienda).upper()[:6]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    producto_slug = re.sub(r"[^A-Za-z0-9]", "", producto).upper()[:8]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    fecha_slug = fecha.strftime("%Y%m%d") if isinstance(fecha, date) else str(fecha).replace("-", "")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    return f"OP-{tienda_slug}-{producto_slug}-{fecha_slug}-{correlativo:03d}"  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
def build_traceability(search_code: str, store_orders: pd.DataFrame, ops: pd.DataFrame, picking: pd.DataFrame, dispatched_log: pd.DataFrame, production_control: pd.DataFrame, inv_current: pd.DataFrame, costs: pd.DataFrame) -> dict:
    code_value = str(search_code).strip()
    result = {"found": False, "pedido": None, "op": None, "producto": None, "timeline": [], "picking": pd.DataFrame(), "despachos": pd.DataFrame(), "produccion": pd.DataFrame(), "costos": pd.DataFrame()}
    if not code_value:
        return result

    pedidos = store_orders.copy()
    op_df = ops.copy()
    pedido_match = pedidos[pedidos["Código Pedido"].astype(str).str.upper().eq(code_value.upper())] if "Código Pedido" in pedidos.columns else pd.DataFrame()
    op_match = op_df[op_df["OP"].astype(str).str.upper().eq(code_value.upper())] if "OP" in op_df.columns else pd.DataFrame()

    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - búsqueda extendida por nuevo formato OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]
    if op_match.empty and "OP" in op_df.columns:
        op_match = op_df[op_df["OP"].astype(str).str.upper().str.startswith(code_value.upper())]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    if not pedido_match.empty:
        p = pedido_match.iloc[0]
        producto = p.get("Producto", "")
        result["pedido"] = p.get("Código Pedido", code_value)
        result["producto"] = producto
        op_match = op_df[op_df["Producto"].astype(str).eq(str(producto))].copy()
        if not op_match.empty:
            result["op"] = op_match.iloc[0]["OP"]
    elif not op_match.empty:
        o = op_match.iloc[0]
        producto = o.get("Producto", "")
        result["op"] = o.get("OP", code_value)
        result["producto"] = producto
        pedido_match = pedidos[pedidos["Producto"].astype(str).eq(str(producto))].copy()
        if not pedido_match.empty:
            result["pedido"] = ", ".join(pedido_match["Código Pedido"].astype(str).unique().tolist())
    else:
        return result

    result["found"] = True
    op_code = result["op"]
    producto = result["producto"]

    pick = picking[picking["OP"].astype(str).eq(str(op_code))].copy() if op_code and not picking.empty else pd.DataFrame()
    desp = dispatched_log[dispatched_log["OP"].astype(str).eq(str(op_code))].copy() if op_code and not dispatched_log.empty else pd.DataFrame()
    prod = production_control[production_control["OP"].astype(str).eq(str(op_code))].copy() if op_code and not production_control.empty else pd.DataFrame()
    cost = costs[costs["Producto"].astype(str).eq(str(producto))].copy() if producto and not costs.empty else pd.DataFrame()

    result["picking"] = pick
    result["despachos"] = desp
    result["produccion"] = prod
    result["costos"] = cost

    op_status_value = op_match.iloc[0]["Estado OP"] if not op_match.empty and "Estado OP" in op_match.columns else "🟡 Pendiente"
    picking_status = "bad" if (not pick.empty and pick["Estado"].astype(str).str.contains("🔴").any()) else ("ok" if not pick.empty else "warn")
    despacho_status = "ok" if not desp.empty else "warn"
    prod_status = "ok" if not prod.empty else "warn"
    inv_status = "ok" if not inv_current.empty else "warn"
    cost_status = "ok" if not cost.empty else "warn"

    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - la línea de tiempo muestra la clave OP con nuevo formato
    result["timeline"] = [
        ("1. Pedido de tienda", f"Pedido(s): {result['pedido']} | Producto: {producto}", "ok"),
        ("2. Orden de Producción", f"OP: {op_code} | Estado: {op_status_value}", "bad" if "🔴" in str(op_status_value) else ("warn" if "🟡" in str(op_status_value) else "ok")),
        ("3. Picking de insumos por receta", f"Líneas de picking: {len(pick)} | PEPS/FIFO por lote y vencimiento", picking_status),
        ("4. Despacho de almacén", f"Despachos registrados: {len(desp)} | Salida valorizada: {money(desp['Valor_salida'].sum()) if not desp.empty and 'Valor_salida' in desp.columns else money(0)}", despacho_status),
        ("5. Control de producción", f"Registros de producción: {len(prod)}", prod_status),
        ("6. Inventario actualizado", f"Lotes disponibles: {len(inv_current)} | Valor actual: {money((inv_current['Stock_lote'] * inv_current['Costo_unitario']).sum()) if not inv_current.empty else money(0)}", inv_status),
        ("7. Costos y rentabilidad", f"Producto: {producto} | Costo total: {money(cost['Costo total'].sum()) if not cost.empty and 'Costo total' in cost.columns else money(0)}", cost_status),
    ]
    return result


def normalize_picking_for_dispatch(pick_op: pd.DataFrame) -> pd.DataFrame:
    df = pick_op.copy()
    if df.empty:
        return df
    if "Cantidad_despachar_real" not in df.columns:
        df["Cantidad_despachar_real"] = df["Cantidad_a_entregar"]
    df["Cantidad_a_entregar"] = coerce_num_series(df["Cantidad_a_entregar"])
    df["Cantidad_despachar_real"] = coerce_num_series(df["Cantidad_despachar_real"])
    df["Diferencia_despacho"] = df["Cantidad_despachar_real"] - df["Cantidad_a_entregar"]
    df["Alerta_despacho"] = np.where(
        df["Diferencia_despacho"].abs() <= 0.0001,
        "🟢 Exacto según receta",
        np.where(df["Diferencia_despacho"] > 0, "🔴 Exceso vs receta", "🔴 Menor vs receta")
    )
    return df


def status_stock(required: float, available: float) -> str:
    if required <= 0:
        return "🟢 Sin requerimiento"
    if available + 1e-9 < required:
        return "🔴 Falta insumo"
    if available <= required * 1.15:
        return "🟡 Stock justo"
    return "🟢 Suficiente"


def exp_status(days: float) -> str:
    if pd.isna(days):
        return "Sin fecha"
    if days <= 7:
        return "🔴 Vence ≤ 7 días"
    if days <= 15:
        return "🟡 Vence ≤ 15 días"
    return "🟢 Vigente"


def style_status(v):
    s = str(v)
    if "🔴" in s:
        return "background-color:#fee2e2;color:#991b1b;font-weight:bold;"
    if "🟡" in s:
        return "background-color:#fef3c7;color:#92400e;font-weight:bold;"
    if "🟢" in s:
        return "background-color:#dcfce7;color:#166534;font-weight:bold;"
    return ""


def excel_download(dataframes: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        for name, df in dataframes.items():
            safe_name = re.sub(r"[\[\]\*\?/\\:]", "", name)[:31] or "Hoja"
            df.to_excel(writer, index=False, sheet_name=safe_name)
            wb = writer.book
            ws = writer.sheets[safe_name]
            header_fmt = wb.add_format({"bold": True, "bg_color": "#111827", "font_color": "#FFFFFF", "border": 1})
            for col_num, value in enumerate(df.columns.values):
                ws.write(0, col_num, value, header_fmt)
                ws.set_column(col_num, col_num, min(max(len(str(value)) + 4, 12), 36))
            ws.freeze_panes(1, 0)
            if len(df.columns) > 0:
                ws.autofilter(0, 0, len(df), len(df.columns)-1)
    return output.getvalue()


def read_excel_sheets(uploaded_file) -> dict[str, pd.DataFrame]:
    if uploaded_file is None:
        return {}
    try:
        xls = pd.ExcelFile(uploaded_file)
        return {s: pd.read_excel(xls, s) for s in xls.sheet_names}
    except Exception as e:
        st.error(f"No se pudo leer el Excel: {e}")
        return {}


def df_inventory_demo() -> pd.DataFrame:
    return pd.DataFrame([
        ["Pecanas", "kg", 5.00, 42.00, "L-PEC-001", today() - timedelta(days=20), today() + timedelta(days=80), "A1-Seco", "Disponible", "Saldo inicial"],
        ["Harina pastelera", "kg", 75.00, 4.20, "L-HAR-001", today() - timedelta(days=15), today() + timedelta(days=120), "B1-Granel", "Disponible", "Saldo inicial"],
        ["Azúcar blanca", "kg", 50.00, 4.10, "L-AZU-001", today() - timedelta(days=18), today() + timedelta(days=180), "B2-Seco", "Disponible", "Saldo inicial"],
        ["Mantequilla", "kg", 18.00, 22.50, "L-MAN-001", today() - timedelta(days=12), today() + timedelta(days=25), "C1-Frío", "Disponible", "Saldo inicial"],
        ["Huevos", "kg", 25.00, 9.80, "L-HUE-001", today() - timedelta(days=8), today() + timedelta(days=9), "C2-Frío", "Disponible", "Saldo inicial"],
        ["Canela", "kg", 2.00, 35.00, "L-CAN-001", today() - timedelta(days=40), today() + timedelta(days=260), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Queso fresco", "kg", 16.00, 18.00, "L-QUE-001", today() - timedelta(days=8), today() + timedelta(days=8), "C3-Frío", "Disponible", "Saldo inicial"],
        ["Carne molida", "kg", 30.00, 24.00, "L-CAR-001", today() - timedelta(days=6), today() + timedelta(days=7), "C4-Frío", "Disponible", "Saldo inicial"],
        ["Cebolla", "kg", 22.00, 3.80, "L-CEB-001", today() - timedelta(days=10), today() + timedelta(days=28), "D1-Verduras", "Disponible", "Saldo inicial"],
        ["Chocolate cobertura", "kg", 12.00, 28.00, "L-CHO-001", today() - timedelta(days=14), today() + timedelta(days=130), "A3-Seco", "Disponible", "Saldo inicial"],
        ["Polvo de hornear", "kg", 3.00, 18.00, "L-POL-001", today() - timedelta(days=60), today() + timedelta(days=300), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Vainilla", "lt", 4.00, 16.00, "L-VAI-001", today() - timedelta(days=42), today() + timedelta(days=280), "A2-Especias", "Disponible", "Saldo inicial"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - insumos de recetas del Excel RECETAS_PARA_DEMO
        ["Azúcar en polvo", "kg", 30.00, 5.50, "L-AZP-001", today() - timedelta(days=10), today() + timedelta(days=200), "B2-Seco", "Disponible", "Saldo inicial"],
        ["Margarina", "kg", 20.00, 8.00, "L-MAR-001", today() - timedelta(days=5), today() + timedelta(days=30), "C1-Frío", "Disponible", "Saldo inicial"],
        ["Yemas", "unidad", 60.00, 0.50, "L-YEM-001", today() - timedelta(days=3), today() + timedelta(days=10), "C2-Frío", "Disponible", "Saldo inicial"],
        ["Manzana pelada", "kg", 15.00, 6.50, "L-MAN-FRU-001", today() - timedelta(days=2), today() + timedelta(days=12), "D1-Verduras", "Disponible", "Saldo inicial"],
        ["Azúcar rubia", "kg", 20.00, 4.80, "L-AZR-001", today() - timedelta(days=7), today() + timedelta(days=150), "B2-Seco", "Disponible", "Saldo inicial"],
        ["Agua", "lt", 100.00, 0.10, "L-AGU-001", today() - timedelta(days=1), today() + timedelta(days=365), "E1-Utilidades", "Disponible", "Saldo inicial"],
        ["Leche en polvo", "kg", 10.00, 18.00, "L-LEC-001", today() - timedelta(days=20), today() + timedelta(days=180), "A3-Seco", "Disponible", "Saldo inicial"],
        ["Estabilizante", "kg", 2.00, 45.00, "L-EST-001", today() - timedelta(days=30), today() + timedelta(days=300), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Dextrosa", "kg", 5.00, 12.00, "L-DEX-001", today() - timedelta(days=25), today() + timedelta(days=250), "A3-Seco", "Disponible", "Saldo inicial"],
        ["Crema de leche", "lt", 8.00, 14.00, "L-CRE-001", today() - timedelta(days=4), today() + timedelta(days=18), "C1-Frío", "Disponible", "Saldo inicial"],
        ["Stracciatella", "kg", 3.00, 32.00, "L-STR-001", today() - timedelta(days=10), today() + timedelta(days=60), "C1-Frío", "Disponible", "Saldo inicial"],
        ["Carne de res tapa", "kg", 20.00, 28.00, "L-RES-001", today() - timedelta(days=2), today() + timedelta(days=5), "C4-Frío", "Disponible", "Saldo inicial"],
        ["Cebolla roja", "kg", 15.00, 4.00, "L-CEB-R-001", today() - timedelta(days=5), today() + timedelta(days=20), "D1-Verduras", "Disponible", "Saldo inicial"],
        ["Ají amarillo", "kg", 3.00, 8.00, "L-AJI-001", today() - timedelta(days=4), today() + timedelta(days=15), "D1-Verduras", "Disponible", "Saldo inicial"],
        ["Tomate", "kg", 10.00, 4.50, "L-TOM-001", today() - timedelta(days=3), today() + timedelta(days=10), "D1-Verduras", "Disponible", "Saldo inicial"],
        ["Aceituna negra", "kg", 3.00, 18.00, "L-ACE-001", today() - timedelta(days=15), today() + timedelta(days=120), "A3-Seco", "Disponible", "Saldo inicial"],
        ["Pasas negras", "kg", 2.00, 15.00, "L-PAS-001", today() - timedelta(days=20), today() + timedelta(days=180), "A3-Seco", "Disponible", "Saldo inicial"],
        ["Ajos", "kg", 2.00, 12.00, "L-AJO-001", today() - timedelta(days=7), today() + timedelta(days=45), "D1-Verduras", "Disponible", "Saldo inicial"],
        ["Paprika", "kg", 0.50, 35.00, "L-PAP-001", today() - timedelta(days=30), today() + timedelta(days=300), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Comino", "kg", 0.30, 30.00, "L-COM-001", today() - timedelta(days=30), today() + timedelta(days=300), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Sal", "kg", 10.00, 1.50, "L-SAL-001", today() - timedelta(days=60), today() + timedelta(days=500), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Orégano seco", "kg", 0.50, 28.00, "L-ORE-001", today() - timedelta(days=30), today() + timedelta(days=300), "A2-Especias", "Disponible", "Saldo inicial"],
        ["Aceite vegetal", "lt", 5.00, 9.00, "L-ACE-VEG-001", today() - timedelta(days=10), today() + timedelta(days=180), "A3-Seco", "Disponible", "Saldo inicial"],
        ["Nuez", "kg", 2.00, 55.00, "L-NUE-001", today() - timedelta(days=20), today() + timedelta(days=150), "A1-Seco", "Disponible", "Saldo inicial"],
        ["Huevo de codorniz", "unidad", 100.00, 0.80, "L-HUE-C-001", today() - timedelta(days=3), today() + timedelta(days=14), "C2-Frío", "Disponible", "Saldo inicial"],
        # MÓDULO CATEGORÍA ALMACÉN - envases y embalajes desde RECETAS_PARA_DEMO.xlsx (hoja "NOMBRES DE PRODUCTOS EN BASES Y EMBALAJES")
        ["Sobres para cubiertos", "unidad", 500.00, 0.15, "L-SOB-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Bolsas kraft #12", "unidad", 300.00, 0.30, "L-BOL-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Servilleta ecologica", "unidad", 1000.00, 0.05, "L-SER-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Cintas shurtape", "unidad", 50.00, 2.50, "L-CIN-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Envase de souffle", "unidad", 400.00, 0.40, "L-ENV-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Tapa para envase souffle", "unidad", 400.00, 0.20, "L-TAP-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Vaso corrugado de 12 oz", "unidad", 600.00, 0.35, "L-VAS-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        ["Tapa de vaso corrugado 12 oz", "unidad", 600.00, 0.15, "L-TVA-001", today() - timedelta(days=10), today() + timedelta(days=365), "E2-Embalaje", "Disponible", "Saldo inicial"],
        # CATEGORÍA AVANZADA - saldo inicial de Productos en Proceso/Semielaborados (tienen receta propia y se usan como insumo de otra receta)
        ["Masa quebrada", "kg", 25.00, 9.80, "L-PROD-MASAQUE-001", today() - timedelta(days=1), today() + timedelta(days=6), "F1-Producción", "Disponible", "Saldo inicial"],
        ["Masa de empanada", "kg", 30.00, 6.50, "L-PROD-MASAEMP-001", today() - timedelta(days=1), today() + timedelta(days=6), "F1-Producción", "Disponible", "Saldo inicial"],
        ["Base blanca de helados", "kg", 40.00, 4.20, "L-PROD-BASEHEL-001", today() - timedelta(days=1), today() + timedelta(days=20), "F1-Producción", "Disponible", "Saldo inicial"],
        # CATEGORÍA AVANZADA - saldo inicial de Productos Terminados (tienen receta propia, listos para venta)
        ["Pie de queso", "unidad", 16.00, 22.00, "L-PROD-PIEQUE-001", today() - timedelta(days=1), today() + timedelta(days=4), "F2-Vitrina", "Disponible", "Saldo inicial"],
        ["Torta de chocolate fina", "unidad", 8.00, 45.00, "L-PROD-TORTACHO-001", today() - timedelta(days=1), today() + timedelta(days=4), "F2-Vitrina", "Disponible", "Saldo inicial"],
        ["Empanada de carne", "kg", 12.00, 28.00, "L-PROD-EMPACARNE-001", today() - timedelta(days=1), today() + timedelta(days=4), "F2-Vitrina", "Disponible", "Saldo inicial"],
    ], columns=["Insumo", "Unidad", "Stock_lote", "Costo_unitario", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Ubicacion", "Estado", "Origen"])


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas expandidas desde RECETAS_PARA_DEMO.xlsx
def df_recipes_demo() -> pd.DataFrame:
    return pd.DataFrame([
        # Recetas originales del sistema
        ["Galletas de pecanas", 100, "Pecanas", "kg", 1.80, 0.03, "Crítico"],
        ["Galletas de pecanas", 100, "Harina pastelera", "kg", 4.00, 0.02, "Crítico"],
        ["Galletas de pecanas", 100, "Azúcar blanca", "kg", 2.20, 0.01, "Normal"],
        ["Galletas de pecanas", 100, "Mantequilla", "kg", 2.50, 0.02, "Crítico"],
        ["Galletas de pecanas", 100, "Huevos", "kg", 1.20, 0.04, "Crítico"],
        ["Galletas de pecanas", 100, "Vainilla", "lt", 0.12, 0.01, "Normal"],
        ["Galletas de pecanas", 100, "Polvo de hornear", "kg", 0.08, 0.00, "Normal"],
        ["Empanadas argentinas", 60, "Harina pastelera", "kg", 3.50, 0.02, "Crítico"],
        ["Empanadas argentinas", 60, "Mantequilla", "kg", 0.80, 0.02, "Crítico"],
        ["Empanadas argentinas", 60, "Huevos", "kg", 0.60, 0.04, "Crítico"],
        ["Empanadas argentinas", 60, "Carne molida", "kg", 4.00, 0.03, "Crítico"],
        ["Empanadas argentinas", 60, "Cebolla", "kg", 2.20, 0.05, "Normal"],
        ["Empanadas argentinas", 60, "Canela", "kg", 0.03, 0.00, "Normal"],
        ["Torta de chocolate fina", 12, "Harina pastelera", "kg", 2.00, 0.02, "Crítico"],
        ["Torta de chocolate fina", 12, "Azúcar blanca", "kg", 2.00, 0.01, "Normal"],
        ["Torta de chocolate fina", 12, "Mantequilla", "kg", 1.50, 0.02, "Crítico"],
        ["Torta de chocolate fina", 12, "Huevos", "kg", 1.80, 0.04, "Crítico"],
        ["Torta de chocolate fina", 12, "Chocolate cobertura", "kg", 1.60, 0.02, "Crítico"],
        ["Torta de chocolate fina", 12, "Vainilla", "lt", 0.08, 0.01, "Normal"],
        ["Pie de queso", 16, "Harina pastelera", "kg", 1.20, 0.02, "Crítico"],
        ["Pie de queso", 16, "Mantequilla", "kg", 0.70, 0.02, "Crítico"],
        ["Pie de queso", 16, "Huevos", "kg", 1.00, 0.04, "Crítico"],
        ["Pie de queso", 16, "Queso fresco", "kg", 3.00, 0.03, "Crítico"],
        ["Pie de queso", 16, "Azúcar blanca", "kg", 0.80, 0.01, "Normal"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Masa Quebrada
        ["Masa quebrada", 10900, "Harina pastelera", "kg", 4.60, 0.02, "Crítico"],
        ["Masa quebrada", 10900, "Azúcar en polvo", "kg", 3.00, 0.01, "Normal"],
        ["Masa quebrada", 10900, "Mantequilla", "kg", 1.27, 0.02, "Crítico"],
        ["Masa quebrada", 10900, "Margarina", "kg", 1.27, 0.02, "Crítico"],
        ["Masa quebrada", 10900, "Huevos", "unidad", 12.00, 0.03, "Crítico"],
        ["Masa quebrada", 10900, "Yemas", "unidad", 8.00, 0.03, "Crítico"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Pye de Manzana
        ["Pye de manzana", 1, "Manzana pelada", "kg", 1.125, 0.05, "Crítico"],
        ["Pye de manzana", 1, "Canela", "kg", 0.003, 0.01, "Normal"],
        ["Pye de manzana", 1, "Nuez", "kg", 0.001, 0.01, "Normal"],
        ["Pye de manzana", 1, "Azúcar rubia", "kg", 0.160, 0.01, "Normal"],
        ["Pye de manzana", 1, "Mantequilla", "kg", 0.060, 0.02, "Crítico"],
        ["Pye de manzana", 1, "Masa quebrada", "kg", 0.640, 0.02, "Crítico"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Base Blanca de Helados
        ["Base blanca de helados", 19000, "Agua", "lt", 10.10, 0.00, "Normal"],
        ["Base blanca de helados", 19000, "Leche en polvo", "kg", 2.00, 0.01, "Crítico"],
        ["Base blanca de helados", 19000, "Estabilizante", "kg", 0.10, 0.01, "Crítico"],
        ["Base blanca de helados", 19000, "Dextrosa", "kg", 0.50, 0.01, "Normal"],
        ["Base blanca de helados", 19000, "Azúcar blanca", "kg", 3.00, 0.01, "Normal"],
        ["Base blanca de helados", 19000, "Crema de leche", "lt", 4.00, 0.02, "Crítico"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Helado de Stracciatella
        ["Helado de stracciatella", 1, "Base blanca de helados", "kg", 3.10, 0.02, "Crítico"],
        ["Helado de stracciatella", 1, "Vainilla", "lt", 0.005, 0.01, "Normal"],
        ["Helado de stracciatella", 1, "Stracciatella", "kg", 0.30, 0.02, "Crítico"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Empanada de Carne
        ["Empanada de carne", 36, "Carne de res tapa", "kg", 1.00, 0.03, "Crítico"],
        ["Empanada de carne", 36, "Cebolla roja", "kg", 2.00, 0.05, "Normal"],
        ["Empanada de carne", 36, "Ají amarillo", "kg", 0.14, 0.05, "Normal"],
        ["Empanada de carne", 36, "Tomate", "kg", 0.43, 0.05, "Normal"],
        ["Empanada de carne", 36, "Aceituna negra", "kg", 0.16, 0.02, "Normal"],
        ["Empanada de carne", 36, "Pasas negras", "kg", 0.22, 0.02, "Normal"],
        ["Empanada de carne", 36, "Ajos", "kg", 0.02, 0.03, "Normal"],
        ["Empanada de carne", 36, "Paprika", "kg", 0.004, 0.01, "Normal"],
        ["Empanada de carne", 36, "Comino", "kg", 0.002, 0.01, "Normal"],
        ["Empanada de carne", 36, "Sal", "kg", 0.008, 0.01, "Normal"],
        ["Empanada de carne", 36, "Orégano seco", "kg", 0.001, 0.01, "Normal"],
        ["Empanada de carne", 36, "Aceite vegetal", "lt", 0.10, 0.01, "Normal"],
        ["Empanada de carne", 36, "Huevos", "kg", 0.165, 0.03, "Crítico"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Masa de Empanada
        ["Masa de empanada", 14800, "Harina pastelera", "kg", 7.50, 0.02, "Crítico"],
        ["Masa de empanada", 14800, "Mantequilla", "kg", 1.75, 0.02, "Crítico"],
        ["Masa de empanada", 14800, "Margarina", "kg", 1.725, 0.02, "Crítico"],
        ["Masa de empanada", 14800, "Yemas", "unidad", 45.00, 0.03, "Crítico"],
        ["Masa de empanada", 14800, "Sal", "kg", 0.225, 0.01, "Normal"],
        ["Masa de empanada", 14800, "Azúcar blanca", "kg", 0.90, 0.01, "Normal"],
        ["Masa de empanada", 14800, "Agua", "lt", 1.80, 0.00, "Normal"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas del Excel RECETAS_PARA_DEMO.xlsx: Armado de Empanadas
        ["Armado de empanadas", 1, "Masa de empanada", "kg", 0.075, 0.02, "Crítico"],
        ["Armado de empanadas", 1, "Empanada de carne", "kg", 0.075, 0.02, "Crítico"],
        ["Armado de empanadas", 1, "Huevo de codorniz", "unidad", 1.00, 0.03, "Normal"],
    ], columns=["Producto", "Rendimiento_lote", "Insumo", "Unidad", "Cantidad_receta", "Merma_tecnica_pct", "Criticidad"])


def df_store_orders_demo() -> pd.DataFrame:
    return pd.DataFrame([
        [today(), "Surco", "PED-0001", "Galletas de pecanas", 200, today() + timedelta(days=2), "Alta", "Pendiente", "Pedido tienda Surco"],
        [today(), "Miraflores", "PED-0002", "Galletas de pecanas", 300, today() + timedelta(days=2), "Alta", "Pendiente", "Pedido tienda Miraflores"],
        [today(), "San Isidro", "PED-0003", "Pie de queso", 40, today() + timedelta(days=3), "Media", "Pendiente", "Reposición vitrina"],
        [today(), "La Molina", "PED-0004", "Empanadas argentinas", 120, today() + timedelta(days=2), "Media", "Pendiente", "Pedido fin de semana"],
    ], columns=["Fecha Pedido", "Tienda", "Código Pedido", "Producto", "Cantidad Solicitada", "Fecha Requerida", "Prioridad", "Estado", "Observación"])


def df_acquisitions_demo() -> pd.DataFrame:
    return pd.DataFrame([
        [today(), "OC-0001", "Factura", "F001-1520", "Proveedor Huevos SAC", "Huevos", "kg", 20.0, 18.5, 1.5, 9.80, "Guía remitente", "GR-8801", "L-HUE-002", today() + timedelta(days=15), "C2-Frío", "Aceptado parcial", "Nota de crédito por 1.5 kg"],
        [today(), "OC-0002", "Factura", "F002-224", "Proveedor Pecanas SAC", "Pecanas", "kg", 3.0, 3.0, 0.0, 42.00, "Guía remitente", "GR-2202", "L-PEC-002", today() + timedelta(days=95), "A1-Seco", "Aceptado", "Ingreso completo"],
        [today(), "OC-0003", "Liquidación de compra", "LC01-45", "Productor local", "Queso fresco", "kg", 12.0, 12.0, 0.0, 18.00, "Guía transportista", "GT-019", "L-QUE-002", today() + timedelta(days=12), "C3-Frío", "Pendiente revisión", "Validar sustento"],
    ], columns=["Fecha", "Orden_compra", "Tipo_documento", "Serie_numero", "Proveedor", "Insumo", "Unidad", "Cantidad_documento", "Cantidad_aceptada", "Cantidad_rechazada", "Costo_unitario", "Tipo_guia", "Numero_guia", "Lote", "Fecha_vencimiento", "Ubicacion", "Estado_documentario", "Observacion"])


def df_providers_demo() -> pd.DataFrame:
    return pd.DataFrame([
        ["Pecanas", "Proveedor Pecanas SAC", "Alta"], ["Harina pastelera", "Molino Andino", "Media"], ["Azúcar blanca", "Distribuidora Dulce", "Media"],
        ["Mantequilla", "Lácteos Premium", "Alta"], ["Huevos", "Proveedor Huevos SAC", "Alta"], ["Queso fresco", "Productor local", "Alta"],
        ["Carne molida", "Cárnicos Norte", "Alta"], ["Chocolate cobertura", "Cacao Fino SAC", "Media"], ["Canela", "Especias Perú", "Baja"],
        ["Vainilla", "Especias Perú", "Baja"], ["Polvo de hornear", "Insumos Panaderos", "Baja"],
        # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - proveedores adicionales para recetas del Excel
        ["Azúcar en polvo", "Distribuidora Dulce", "Media"],
        ["Margarina", "Lácteos Premium", "Alta"],
        ["Yemas", "Proveedor Huevos SAC", "Alta"],
        ["Manzana pelada", "Frutas Frescas SAC", "Alta"],
        ["Azúcar rubia", "Distribuidora Dulce", "Media"],
        ["Agua", "Servicios Agua Lima", "Baja"],
        ["Leche en polvo", "Lácteos Premium", "Alta"],
        ["Estabilizante", "Insumos Panaderos", "Media"],
        ["Dextrosa", "Insumos Panaderos", "Media"],
        ["Crema de leche", "Lácteos Premium", "Alta"],
        ["Stracciatella", "Cacao Fino SAC", "Media"],
        ["Carne de res tapa", "Cárnicos Norte", "Alta"],
        ["Cebolla roja", "Verduras Frescas SAC", "Media"],
        ["Ají amarillo", "Verduras Frescas SAC", "Media"],
        ["Tomate", "Verduras Frescas SAC", "Media"],
        ["Aceituna negra", "Importadora Gourmet", "Baja"],
        ["Pasas negras", "Importadora Gourmet", "Baja"],
        ["Ajos", "Verduras Frescas SAC", "Media"],
        ["Paprika", "Especias Perú", "Baja"],
        ["Comino", "Especias Perú", "Baja"],
        ["Sal", "Distribuidora Dulce", "Baja"],
        ["Orégano seco", "Especias Perú", "Baja"],
        ["Aceite vegetal", "Distribuidora Dulce", "Media"],
        ["Nuez", "Proveedor Pecanas SAC", "Alta"],
        ["Huevo de codorniz", "Proveedor Huevos SAC", "Alta"],
    ], columns=["Insumo", "Proveedor sugerido", "Prioridad base"])


def df_physical_count_demo() -> pd.DataFrame:
    return pd.DataFrame([
        ["Huevos", "kg", 5.00, 4.00, "Conteo cierre producción", "Huevos rotos/no conformes"],
        ["Pecanas", "kg", 2.60, 2.40, "Conteo cierre producción", "Diferencia física menor"],
    ], columns=["Insumo", "Unidad", "Stock_teorico", "Stock_fisico", "Tipo_conteo", "Observación"])


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - estado inicial del generador de OP por tienda
def df_op_por_tienda_demo() -> pd.DataFrame:
    """DataFrame inicial para el generador de OP por tienda con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    return pd.DataFrame(columns=[  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        "OP", "Tienda", "Producto", "Cantidad", "Fecha_OP", "Fecha_requerida",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        "Prioridad", "Estado OP", "Responsable_tienda", "Observacion"  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    ])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA


def init_state():
    defaults = {
        "inventory": df_inventory_demo(),
        "recipes": df_recipes_demo(),
        "store_orders": df_store_orders_demo(),
        "acquisitions": df_acquisitions_demo(),
        "providers": df_providers_demo(),
        "physical_count": df_physical_count_demo(),
        "production_control": pd.DataFrame(columns=["OP", "Producto", "Cantidad Programada", "Cantidad Real", "Diferencia", "Rendimiento_%", "Responsable", "Observación"]),
        "dispatched_log": pd.DataFrame(columns=["Fecha", "OP", "Producto", "Insumo", "Unidad", "Lote", "Cantidad_despachada", "Costo_unitario", "Valor_salida", "Responsable"]),
        "purchase_requests_manual": pd.DataFrame(columns=["Fecha", "Insumo", "Unidad", "Cantidad faltante", "Proveedor sugerido", "Prioridad", "Estado", "Origen"]),
        "dispatch_alerts": pd.DataFrame(columns=["Fecha", "OP", "Producto", "Insumo", "Unidad", "Lote", "Cantidad_requerida", "Cantidad_intentada", "Diferencia", "Alerta", "Responsable"]),
        "op_por_tienda": df_op_por_tienda_demo(),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        "op_correlativo_por_tienda": {},  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - contadores de correlativo por tienda
        "categoria_overrides": pd.DataFrame(columns=["Insumo", "Categoria"]),  # MÓDULO CATEGORÍA ALMACÉN - correcciones manuales de categoría
        "pos_ventas": pd.DataFrame(columns=["Fecha", "Tienda", "Producto", "Cantidad_vendida", "Precio_unitario_venta", "Total_venta", "Canal", "Archivo_origen"]),  # MÓDULO VENTAS POS - histórico de ventas cargadas desde Excel externo
        "ventas_stock_log": pd.DataFrame(columns=["Fecha", "Tienda", "Producto", "Cantidad_descontada", "Origen"]),  # MÓDULO VENTAS POS - log de descuentos de stock de producto terminado por venta
        "produccion_almacen_log": pd.DataFrame(columns=["Fecha", "OP", "Producto", "Cantidad_ingresada", "Costo_unitario", "Lote", "Categoria"]),  # CATEGORÍA AVANZADA - log de ingresos de semielaborados/terminados a almacén
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, pd.DataFrame) else value


init_state()


def apply_acquisitions_to_inventory(acq: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    if acq.empty:
        return inv.copy()
    df = acq.copy()
    for col in ["Cantidad_aceptada", "Costo_unitario"]:
        df[col] = coerce_num_series(df[col])
    accepted = df[(df["Cantidad_aceptada"] > 0) & (df["Estado_documentario"].astype(str).isin(["Aceptado", "Aceptado parcial"]))].copy()
    if accepted.empty:
        return inv.copy()
    rows = accepted.rename(columns={"Cantidad_aceptada":"Stock_lote", "Fecha":"Fecha_ingreso"})
    rows = rows[["Insumo", "Unidad", "Stock_lote", "Costo_unitario", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Ubicacion"]]
    rows["Estado"] = "Disponible"
    rows["Origen"] = "Adquisición aceptada"
    out = pd.concat([inv, rows], ignore_index=True)
    return coerce_date_columns(out, ["Fecha_ingreso", "Fecha_vencimiento"])


def available_inventory() -> pd.DataFrame:
    inv = apply_acquisitions_to_inventory(st.session_state.acquisitions, st.session_state.inventory)
    inv = coerce_date_columns(inv, ["Fecha_ingreso", "Fecha_vencimiento"])
    inv["Stock_lote"] = coerce_num_series(inv["Stock_lote"])
    inv["Costo_unitario"] = coerce_num_series(inv["Costo_unitario"])
    recipes_ctx = st.session_state.recipes if "recipes" in st.session_state else pd.DataFrame()  # CATEGORÍA AVANZADA - contexto de recetas para detectar semielaborados/terminados
    inv["Categoria"] = inv["Insumo"].apply(lambda x: clasificar_insumo(x, recipes_ctx)) if "Insumo" in inv.columns else "Materia Prima"  # CATEGORÍA AVANZADA - clasificación automática MP/Suministros/Auxiliares/Semielaborado/Terminado
    return inv


# CATEGORÍA AVANZADA - clasificación automática de insumos en Materia Prima / Suministros / Materiales Auxiliares / Producto en Proceso (Semielaborado) / Producto Terminado
PALABRAS_MATERIALES_AUXILIARES = [  # MÓDULO CATEGORÍA ALMACÉN
    "sobre", "bolsa", "kraft", "servilleta", "cinta", "shurtape", "envase", "souffle",
    "tapa", "vaso", "corrugado", "empaque", "embalaje", "etiqueta", "film", "papel",
    "caja", "bandeja", "cubierto", "cucharita", "tenedor", "pajita", "sorbete",
]  # MÓDULO CATEGORÍA ALMACÉN

PALABRAS_SUMINISTROS = [  # MÓDULO CATEGORÍA ALMACÉN
    "estabilizante", "saborizante", "colorante", "preservante", "aditivo",
    "esencia", "gas", "gasolina", "combustible", "detergente", "lejía", "lejia",
    "desinfectante", "guante", "mascarilla", "limpiador", "alcohol",
]  # MÓDULO CATEGORÍA ALMACÉN


def clasificar_insumo(nombre_insumo: str, recipes: pd.DataFrame = None) -> str:
    """Clasifica autom\u00e1ticamente un insumo en 5 categor\u00edas contables, en este orden de prioridad:
    1) Producto en Proceso/Semielaborado: tiene receta propia (aparece en columna Producto) Y a la vez
       se usa como insumo dentro de OTRA receta (ej. Masa quebrada, Masa de empanada, Base blanca de helados).
    2) Producto Terminado: tiene receta propia pero NO se usa como insumo de otra receta (ej. Pie de queso),
       o s\u00ed se usa como componente de un armado pero es vendible por s\u00ed mismo (ej. Empanada de carne).
    3) Materiales Auxiliares: coincide con palabras clave de empaque/embalaje.
    4) Suministros: coincide con palabras clave de insumos no alimentarios (limpieza, aditivos qu\u00edmicos, etc.).
    5) Materia Prima: todo lo dem\u00e1s (insumo comestible base, no tiene receta propia)."""  # CATEGORÍA AVANZADA
    nombre = str(nombre_insumo).strip().lower()  # CATEGORÍA AVANZADA

    if recipes is not None and not recipes.empty and "Producto" in recipes.columns and "Insumo" in recipes.columns:  # CATEGORÍA AVANZADA
        productos_con_receta = set(recipes["Producto"].astype(str).str.strip().str.lower().unique())  # CATEGORÍA AVANZADA
        insumos_usados_en_otras_recetas = set(recipes["Insumo"].astype(str).str.strip().str.lower().unique())  # CATEGORÍA AVANZADA
        tiene_receta_propia = nombre in productos_con_receta  # CATEGORÍA AVANZADA
        se_usa_como_insumo = nombre in insumos_usados_en_otras_recetas  # CATEGORÍA AVANZADA
        if tiene_receta_propia and se_usa_como_insumo:  # CATEGORÍA AVANZADA - ej. Masa quebrada, Masa de empanada, Base blanca de helados
            return "Producto en Proceso/Semielaborado"  # CATEGORÍA AVANZADA
        if tiene_receta_propia and not se_usa_como_insumo:  # CATEGORÍA AVANZADA - ej. Pie de queso, Torta de chocolate fina
            return "Producto Terminado"  # CATEGORÍA AVANZADA

    for palabra in PALABRAS_MATERIALES_AUXILIARES:  # MÓDULO CATEGORÍA ALMACÉN
        if palabra in nombre:  # MÓDULO CATEGORÍA ALMACÉN
            return "Materiales Auxiliares"  # MÓDULO CATEGORÍA ALMACÉN
    for palabra in PALABRAS_SUMINISTROS:  # MÓDULO CATEGORÍA ALMACÉN
        if palabra in nombre:  # MÓDULO CATEGORÍA ALMACÉN
            return "Suministros"  # MÓDULO CATEGORÍA ALMACÉN
    return "Materia Prima"  # MÓDULO CATEGORÍA ALMACÉN


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - consolidación refactorizada para soportar clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]
def consolidated_orders(store_orders: pd.DataFrame) -> pd.DataFrame:
    if store_orders.empty:
        return pd.DataFrame(columns=["Producto", "Cantidad Consolidada", "N° Pedidos", "Tiendas", "Fecha requerida mínima", "Prioridad máxima"])
    df = store_orders.copy()
    df["Cantidad Solicitada"] = coerce_num_series(df["Cantidad Solicitada"])
    active = df[~df["Estado"].astype(str).str.lower().isin(["entregado", "anulado", "cancelado"])].copy()
    if active.empty:
        return pd.DataFrame(columns=["Producto", "Cantidad Consolidada", "N° Pedidos", "Tiendas", "Fecha requerida mínima", "Prioridad máxima"])
    prio_rank = {"Alta":3, "Media":2, "Baja":1}
    active["Prioridad_rank"] = active["Prioridad"].map(prio_rank).fillna(1)
    out = active.groupby("Producto", as_index=False).agg(**{
        "Cantidad Consolidada": ("Cantidad Solicitada", "sum"), "N° Pedidos": ("Código Pedido", "nunique"),
        "Tiendas": ("Tienda", lambda x: ", ".join(sorted(set(map(str, x))))), "Fecha requerida mínima": ("Fecha Requerida", "min"),
        "Prioridad_rank": ("Prioridad_rank", "max")})
    out["Prioridad máxima"] = out["Prioridad_rank"].map({3:"Alta", 2:"Media", 1:"Baja"}).fillna("Baja")
    return out.drop(columns=["Prioridad_rank"])


def explode_recipes(consolidated: pd.DataFrame, recipes: pd.DataFrame) -> pd.DataFrame:
    if consolidated.empty or recipes.empty:
        return pd.DataFrame(columns=["Producto", "Cantidad Consolidada", "Rendimiento_lote", "Insumo", "Unidad", "Cantidad_receta", "Merma_tecnica_pct", "Lotes_necesarios", "Requerido_base", "Merma_tecnica", "Requerido_total", "Criticidad"])
    c = consolidated[["Producto", "Cantidad Consolidada"]].copy()
    r = recipes.copy()
    r["Rendimiento_lote"] = coerce_num_series(r["Rendimiento_lote"], 1.0).replace(0, 1.0)
    r["Cantidad_receta"] = coerce_num_series(r["Cantidad_receta"])
    r["Merma_tecnica_pct"] = coerce_num_series(r["Merma_tecnica_pct"])
    x = c.merge(r, on="Producto", how="left")
    x["Cantidad Consolidada"] = coerce_num_series(x["Cantidad Consolidada"])
    x["Lotes_necesarios"] = x["Cantidad Consolidada"] / x["Rendimiento_lote"]
    x["Requerido_base"] = x["Lotes_necesarios"] * x["Cantidad_receta"]
    x["Merma_tecnica"] = x["Requerido_base"] * x["Merma_tecnica_pct"]
    x["Requerido_total"] = x["Requerido_base"] + x["Merma_tecnica"]
    return x[["Producto", "Cantidad Consolidada", "Rendimiento_lote", "Insumo", "Unidad", "Cantidad_receta", "Merma_tecnica_pct", "Lotes_necesarios", "Requerido_base", "Merma_tecnica", "Requerido_total", "Criticidad"]]


def stock_summary(requirements: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    if requirements.empty:
        return pd.DataFrame(columns=["Insumo", "Unidad", "Necesita", "Tiene", "Faltante", "Sobrante", "Cobertura_%", "Estado"])
    req = requirements.groupby(["Insumo", "Unidad"], as_index=False)["Requerido_total"].sum().rename(columns={"Requerido_total":"Necesita"})
    stock = inv[inv["Estado"].astype(str).str.lower().eq("disponible")].groupby(["Insumo", "Unidad"], as_index=False)["Stock_lote"].sum().rename(columns={"Stock_lote":"Tiene"})
    out = req.merge(stock, on=["Insumo", "Unidad"], how="left")
    out["Tiene"] = out["Tiene"].fillna(0.0)
    out["Faltante"] = (out["Necesita"] - out["Tiene"]).clip(lower=0)
    out["Sobrante"] = (out["Tiene"] - out["Necesita"]).clip(lower=0)
    out["Cobertura_%"] = np.where(out["Necesita"] > 0, out["Tiene"] / out["Necesita"] * 100, 0)
    out["Estado"] = out.apply(lambda r: status_stock(r["Necesita"], r["Tiene"]), axis=1)
    return out.sort_values(["Faltante", "Cobertura_%"], ascending=[False, True])


def op_status(product: str, requirements: pd.DataFrame, inv: pd.DataFrame) -> str:
    req = requirements[requirements["Producto"].eq(product)].copy()
    if req.empty:
        return "🟡 Pendiente"
    ss = stock_summary(req, inv)
    return "🔴 Falta insumo" if (ss["Faltante"] > 1e-9).any() else "🟢 Liberado"


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - generate_ops refactorizado para usar clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]
def generate_ops(consolidated: pd.DataFrame, requirements: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    """Genera OP globales (consolidadas) con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if consolidated.empty:
        return pd.DataFrame(columns=["OP", "Producto", "Cantidad", "Estado OP", "Prioridad", "Fecha requerida"])
    rows = []
    fecha_hoy = today()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    for i, r in consolidated.reset_index(drop=True).iterrows():
        tiendas_str = str(r.get("Tiendas", "CENTRAL"))  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        primera_tienda = tiendas_str.split(",")[0].strip() if "," in tiendas_str else tiendas_str  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_key = generar_clave_op(primera_tienda, r["Producto"], fecha_hoy, i + 1)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rows.append([op_key, r["Producto"], safe_float(r["Cantidad Consolidada"]), op_status(r["Producto"], requirements, inv), r.get("Prioridad máxima", "Media"), r.get("Fecha requerida mínima", today())])  # FIX BUG TypeError
    return pd.DataFrame(rows, columns=["OP", "Producto", "Cantidad", "Estado OP", "Prioridad", "Fecha requerida"])


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - función para generar OP individuales por tienda
def generate_ops_por_tienda(store_orders: pd.DataFrame, requirements: pd.DataFrame, inv: pd.DataFrame, recipes: pd.DataFrame) -> pd.DataFrame:
    """Genera OP individuales por tienda y producto con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if store_orders.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        return pd.DataFrame(columns=["OP", "Tienda", "Producto", "Cantidad", "Fecha_OP", "Fecha_requerida", "Prioridad", "Estado OP", "Responsable_tienda", "Observacion"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    active = store_orders[~store_orders["Estado"].astype(str).str.lower().isin(["entregado", "anulado", "cancelado"])].copy()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if active.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        return pd.DataFrame(columns=["OP", "Tienda", "Producto", "Cantidad", "Fecha_OP", "Fecha_requerida", "Prioridad", "Estado OP", "Responsable_tienda", "Observacion"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rows = []  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    correlativo_map = {}  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - contador por tienda
    for _, pedido in active.iterrows():  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        tienda = str(pedido.get("Tienda", "TIENDA"))  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        producto = str(pedido.get("Producto", "PROD"))  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        if tienda in ("None", "nan", "") or producto in ("None", "nan", ""):  # FIX BUG TypeError - omite filas nuevas/incompletas del data_editor
            continue  # FIX BUG TypeError
        cantidad_raw = pedido.get("Cantidad Solicitada", 0)  # FIX BUG TypeError - se separa el get del cast
        cantidad = float(cantidad_raw) if pd.notna(cantidad_raw) else 0.0  # FIX BUG TypeError - None/NaN ya no rompen float()
        fecha_req = pedido.get("Fecha Requerida", today())  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        prioridad = pedido.get("Prioridad", "Media")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        observacion = pedido.get("Observación", "")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        key_tienda = tienda  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        correlativo_map[key_tienda] = correlativo_map.get(key_tienda, 0) + 1  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        correlativo = correlativo_map[key_tienda]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_key = generar_clave_op(tienda, producto, today(), correlativo)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        req_prod = requirements[requirements["Producto"].eq(producto)].copy() if not requirements.empty else pd.DataFrame()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        estado = op_status(producto, req_prod, inv) if not req_prod.empty else "🟡 Pendiente"  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rows.append([op_key, tienda, producto, cantidad, today(), fecha_req, prioridad, estado, "", str(observacion)])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    df_out = pd.DataFrame(rows, columns=["OP", "Tienda", "Producto", "Cantidad", "Fecha_OP", "Fecha_requerida", "Prioridad", "Estado OP", "Responsable_tienda", "Observacion"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    return df_out  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - explosión de recetas por OP de tienda
def explode_recipes_por_op_tienda(ops_tienda: pd.DataFrame, recipes: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    """Explota recetas para cada OP individual de tienda con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if ops_tienda.empty or recipes.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        return pd.DataFrame(columns=["OP", "Tienda", "Producto", "Cantidad_OP", "Insumo", "Unidad", "Requerido_base", "Merma_tecnica", "Requerido_total", "Stock_disponible", "Faltante", "Estado_semaforo"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rows = []  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    stock_df = inv[inv["Estado"].astype(str).str.lower().eq("disponible")].groupby(["Insumo", "Unidad"], as_index=False)["Stock_lote"].sum()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    for _, op_row in ops_tienda.iterrows():  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_key = op_row["OP"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        tienda = op_row["Tienda"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        producto = op_row["Producto"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        cantidad_op = safe_float(op_row["Cantidad"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA / FIX BUG TypeError
        rec = recipes[recipes["Producto"].eq(producto)].copy()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        if rec.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            continue  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Rendimiento_lote"] = coerce_num_series(rec["Rendimiento_lote"], 1.0).replace(0, 1.0)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Cantidad_receta"] = coerce_num_series(rec["Cantidad_receta"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Merma_tecnica_pct"] = coerce_num_series(rec["Merma_tecnica_pct"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        lotes_nec = cantidad_op / rec["Rendimiento_lote"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Requerido_base"] = lotes_nec * rec["Cantidad_receta"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Merma_tecnica"] = rec["Requerido_base"] * rec["Merma_tecnica_pct"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Requerido_total"] = rec["Requerido_base"] + rec["Merma_tecnica"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec = rec.merge(stock_df, on=["Insumo", "Unidad"], how="left")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Stock_disponible"] = rec["Stock_lote"].fillna(0)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Faltante"] = (rec["Requerido_total"] - rec["Stock_disponible"]).clip(lower=0)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        rec["Estado_semaforo"] = rec.apply(lambda r: status_stock(r["Requerido_total"], r["Stock_disponible"]), axis=1)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        for _, r in rec.iterrows():  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            rows.append([op_key, tienda, producto, cantidad_op, r["Insumo"], r["Unidad"], r["Requerido_base"], r["Merma_tecnica"], r["Requerido_total"], r["Stock_disponible"], r["Faltante"], r["Estado_semaforo"]])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    return pd.DataFrame(rows, columns=["OP", "Tienda", "Producto", "Cantidad_OP", "Insumo", "Unidad", "Requerido_base", "Merma_tecnica", "Requerido_total", "Stock_disponible", "Faltante", "Estado_semaforo"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - picking refactorizado para clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]
def fifo_picking(requirements: pd.DataFrame, inv: pd.DataFrame, ops: pd.DataFrame) -> pd.DataFrame:
    """Picking PEPS/FIFO compatible con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if requirements.empty:
        return pd.DataFrame(columns=["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Cantidad_a_entregar", "Costo_unitario", "Valor_salida", "Estado"])
    inv2 = inv.copy()
    inv2["Fecha_ingreso_dt"] = pd.to_datetime(inv2["Fecha_ingreso"], errors="coerce")
    inv2["Fecha_vencimiento_dt"] = pd.to_datetime(inv2["Fecha_vencimiento"], errors="coerce")
    inv2 = inv2[inv2["Estado"].astype(str).str.lower().eq("disponible")].sort_values(["Insumo", "Fecha_vencimiento_dt", "Fecha_ingreso_dt", "Lote"], na_position="last")
    req_prod = requirements.groupby(["Producto", "Insumo", "Unidad"], as_index=False)["Requerido_total"].sum()
    op_map = ops.set_index("Producto")["OP"].to_dict() if not ops.empty else {}  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - op_map usa nuevo formato de clave
    rows = []
    for _, req in req_prod.iterrows():
        prod, ins, und = req["Producto"], req["Insumo"], req["Unidad"]
        need = float(req["Requerido_total"])
        op = op_map.get(prod, generar_clave_op("CENTRAL", prod, today(), 0))  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        lots = inv2[inv2["Insumo"].eq(ins) & inv2["Unidad"].eq(und)].copy()
        if lots.empty:
            rows.append([op, prod, ins, und, "SIN STOCK", "", "", 0.0, 0.0, 0.0, f"🔴 Faltan {need:.3f} {und}"])
            continue
        for _, lot in lots.iterrows():
            if need <= 1e-9:
                break
            take = min(float(lot["Stock_lote"]), need)
            need -= take
            if take > 0:
                rows.append([op, prod, ins, und, lot["Lote"], lot["Fecha_ingreso"], lot["Fecha_vencimiento"], take, float(lot["Costo_unitario"]), take * float(lot["Costo_unitario"]), "🟢 Picking PEPS/FIFO"])
        if need > 1e-9:
            rows.append([op, prod, ins, und, "FALTANTE", "", "", 0.0, 0.0, 0.0, f"🔴 Faltan {need:.3f} {und}"])
    return pd.DataFrame(rows, columns=["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Cantidad_a_entregar", "Costo_unitario", "Valor_salida", "Estado"])


# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - picking por OP de tienda individual
def fifo_picking_por_op_tienda(op_key: str, producto: str, cantidad_op: float, recipes: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    """Genera picking PEPS/FIFO para una OP individual de tienda con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]"""  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if recipes.empty or inv.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        return pd.DataFrame(columns=["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Cantidad_a_entregar", "Costo_unitario", "Valor_salida", "Estado"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rec = recipes[recipes["Producto"].eq(producto)].copy()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if rec.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        return pd.DataFrame(columns=["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Cantidad_a_entregar", "Costo_unitario", "Valor_salida", "Estado"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rec["Rendimiento_lote"] = coerce_num_series(rec["Rendimiento_lote"], 1.0).replace(0, 1.0)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rec["Cantidad_receta"] = coerce_num_series(rec["Cantidad_receta"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rec["Merma_tecnica_pct"] = coerce_num_series(rec["Merma_tecnica_pct"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    lotes_nec = cantidad_op / rec["Rendimiento_lote"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rec["Requerido_total"] = lotes_nec * rec["Cantidad_receta"] * (1 + rec["Merma_tecnica_pct"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    inv2 = inv.copy()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    inv2["Fecha_ingreso_dt"] = pd.to_datetime(inv2["Fecha_ingreso"], errors="coerce")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    inv2["Fecha_vencimiento_dt"] = pd.to_datetime(inv2["Fecha_vencimiento"], errors="coerce")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    inv2 = inv2[inv2["Estado"].astype(str).str.lower().eq("disponible")].sort_values(["Insumo", "Fecha_vencimiento_dt", "Fecha_ingreso_dt", "Lote"], na_position="last")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rows = []  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    for _, req in rec.iterrows():  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        ins, und = req["Insumo"], req["Unidad"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        need = float(req["Requerido_total"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        lots = inv2[inv2["Insumo"].eq(ins) & inv2["Unidad"].eq(und)].copy()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        if lots.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            rows.append([op_key, producto, ins, und, "SIN STOCK", "", "", 0.0, 0.0, 0.0, f"🔴 Faltan {need:.3f} {und}"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            continue  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        for _, lot in lots.iterrows():  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            if need <= 1e-9:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                break  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            take = min(float(lot["Stock_lote"]), need)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            need -= take  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            if take > 0:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                rows.append([op_key, producto, ins, und, lot["Lote"], lot["Fecha_ingreso"], lot["Fecha_vencimiento"], take, float(lot["Costo_unitario"]), take * float(lot["Costo_unitario"]), "🟢 Picking PEPS/FIFO"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        if need > 1e-9:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            rows.append([op_key, producto, ins, und, "FALTANTE", "", "", 0.0, 0.0, 0.0, f"🔴 Faltan {need:.3f} {und}"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    return pd.DataFrame(rows, columns=["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Cantidad_a_entregar", "Costo_unitario", "Valor_salida", "Estado"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA


def dispatch_inventory(inv: pd.DataFrame, pick_op: pd.DataFrame, op_selected: str, responsable: str):
    if pick_op.empty:
        return inv.copy(), pd.DataFrame(), "No hay picking para despachar."
    if pick_op["Estado"].astype(str).str.contains("🔴").any():
        return inv.copy(), pd.DataFrame(), "No se puede despachar: existen faltantes."
    inv_out = inv.copy()
    inv_out["Stock_lote"] = coerce_num_series(inv_out["Stock_lote"])
    logs = []
    for _, p in pick_op.iterrows():
        mask = (inv_out["Insumo"].eq(p["Insumo"])) & (inv_out["Unidad"].eq(p["Unidad"])) & (inv_out["Lote"].astype(str).eq(str(p["Lote"])))
        qty = float(p["Cantidad_a_entregar"])
        if mask.any():
            idx = inv_out[mask].index[0]
            inv_out.loc[idx, "Stock_lote"] = max(0.0, float(inv_out.loc[idx, "Stock_lote"]) - qty)
        logs.append([today(), p["OP"], p["Producto"], p["Insumo"], p["Unidad"], p["Lote"], qty, p["Costo_unitario"], p["Valor_salida"], responsable])
    log_df = pd.DataFrame(logs, columns=["Fecha", "OP", "Producto", "Insumo", "Unidad", "Lote", "Cantidad_despachada", "Costo_unitario", "Valor_salida", "Responsable"])
    return inv_out, log_df, f"Despacho aplicado para {op_selected}."


def cost_by_product(requirements: pd.DataFrame, inv: pd.DataFrame, labor_pct: float, cif_pct: float, margin_target: float) -> pd.DataFrame:
    if requirements.empty:
        return pd.DataFrame(columns=["Producto", "Cantidad", "Costo MP", "Mano obra", "CIF", "Costo total", "Costo unitario", "Precio sugerido", "Margen objetivo", "Rentabilidad estimada"])
    avg = average_costs(inv)
    x = requirements.merge(avg, on=["Insumo", "Unidad"], how="left")
    x["Costo_promedio"] = x["Costo_promedio"].fillna(0)
    x["Costo_MP_linea"] = x["Requerido_total"] * x["Costo_promedio"]
    out = x.groupby("Producto", as_index=False).agg(Cantidad=("Cantidad Consolidada", "max"), **{"Costo MP": ("Costo_MP_linea", "sum")})
    out["Mano obra"] = out["Costo MP"] * labor_pct
    out["CIF"] = out["Costo MP"] * cif_pct
    out["Costo total"] = out["Costo MP"] + out["Mano obra"] + out["CIF"]
    out["Costo unitario"] = np.where(out["Cantidad"] > 0, out["Costo total"] / out["Cantidad"], 0)
    out["Precio sugerido"] = np.where((1 - margin_target) > 0, out["Costo unitario"] / (1 - margin_target), out["Costo unitario"])
    out["Margen objetivo"] = margin_target
    out["Rentabilidad estimada"] = np.where(out["Costo total"] > 0, (out["Precio sugerido"] * out["Cantidad"] - out["Costo total"]) / out["Costo total"], 0)
    return out.sort_values("Costo total", ascending=False)


def average_costs(inv: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if inv.empty:
        return pd.DataFrame(columns=["Insumo", "Unidad", "Costo_promedio"])
    df = inv.copy()
    df["Stock_lote"] = coerce_num_series(df["Stock_lote"])
    df["Costo_unitario"] = coerce_num_series(df["Costo_unitario"])
    for (ins, und), g in df.groupby(["Insumo", "Unidad"]):
        qty = g["Stock_lote"].sum()
        cost = (g["Stock_lote"] * g["Costo_unitario"]).sum() / qty if qty > 0 else g["Costo_unitario"].mean()
        rows.append([ins, und, float(cost or 0)])
    return pd.DataFrame(rows, columns=["Insumo", "Unidad", "Costo_promedio"])


def purchase_requests_auto(summary: pd.DataFrame, providers: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame(columns=["Fecha", "Insumo", "Unidad", "Cantidad faltante", "Proveedor sugerido", "Prioridad", "Estado", "Origen"])
    falt = summary[summary["Faltante"] > 1e-9].copy()
    if falt.empty:
        return pd.DataFrame(columns=["Fecha", "Insumo", "Unidad", "Cantidad faltante", "Proveedor sugerido", "Prioridad", "Estado", "Origen"])
    out = falt[["Insumo", "Unidad", "Faltante"]].rename(columns={"Faltante":"Cantidad faltante"})
    out.insert(0, "Fecha", today())
    out = out.merge(providers, on="Insumo", how="left")
    out["Proveedor sugerido"] = out["Proveedor sugerido"].fillna("Proveedor por definir")
    out["Prioridad"] = "Alta"
    out["Estado"] = "Pendiente"
    out["Origen"] = "Automático por faltante de producción"
    return out[["Fecha", "Insumo", "Unidad", "Cantidad faltante", "Proveedor sugerido", "Prioridad", "Estado", "Origen"]]


def compute_mermas(physical: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    if physical.empty:
        return pd.DataFrame(columns=["Insumo", "Unidad", "Stock_teorico", "Stock_fisico", "Merma_real", "Costo_promedio", "Valor_merma", "Merma_%", "Estado"])
    df = physical.copy()
    df["Stock_teorico"] = coerce_num_series(df["Stock_teorico"])
    df["Stock_fisico"] = coerce_num_series(df["Stock_fisico"])
    avg = average_costs(inv)
    out = df.merge(avg, on=["Insumo", "Unidad"], how="left")
    out["Costo_promedio"] = out["Costo_promedio"].fillna(0)
    out["Merma_real"] = (out["Stock_teorico"] - out["Stock_fisico"]).clip(lower=0)
    out["Valor_merma"] = out["Merma_real"] * out["Costo_promedio"]
    out["Merma_%"] = np.where(out["Stock_teorico"] > 0, out["Merma_real"] / out["Stock_teorico"] * 100, 0)
    out["Estado"] = np.select([out["Merma_%"] > 5, out["Merma_%"] > 2], ["🔴 Merma alta", "🟡 Revisar"], default="🟢 Controlado")
    return out.sort_values("Valor_merma", ascending=False)


def production_control_from_ops(ops: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in ops.iterrows():
        rows.append([r["OP"], r["Producto"], safe_float(r["Cantidad"]), safe_float(r["Cantidad"]), 0.0, 100.0, "Operario", ""])  # FIX BUG TypeError
    return pd.DataFrame(rows, columns=["OP", "Producto", "Cantidad Programada", "Cantidad Real", "Diferencia", "Rendimiento_%", "Responsable", "Observación"])


# CATEGORÍA AVANZADA - descarga automática a almacén de Producto en Proceso/Semielaborado al cerrar producción
def ingresar_produccion_a_almacen(production_control: pd.DataFrame, recipes: pd.DataFrame, costs: pd.DataFrame, inv: pd.DataFrame, dias_vigencia_default: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Por cada OP de control de producción cuyo Producto sea Semielaborado o Producto Terminado,
    crea un lote nuevo de inventario con la Cantidad Real producida, costeado seg\u00fan costs (costo unitario calculado),
    para que quede disponible como insumo de otras recetas (caso semielaborado) o como stock vendible (caso terminado).
    Devuelve (inventario_actualizado, log_de_ingresos)."""  # CATEGORÍA AVANZADA
    if production_control.empty:  # CATEGORÍA AVANZADA
        return inv.copy(), pd.DataFrame(columns=["Fecha", "OP", "Producto", "Cantidad_ingresada", "Costo_unitario", "Lote", "Categoria"])  # CATEGORÍA AVANZADA
    pc = production_control.copy()  # CATEGORÍA AVANZADA
    pc["Cantidad Real"] = coerce_num_series(pc["Cantidad Real"])  # CATEGORÍA AVANZADA
    cost_map = costs.set_index("Producto")["Costo unitario"].to_dict() if not costs.empty and "Costo unitario" in costs.columns else {}  # CATEGORÍA AVANZADA
    nuevas_filas = []  # CATEGORÍA AVANZADA
    log_rows = []  # CATEGORÍA AVANZADA
    for _, r in pc.iterrows():  # CATEGORÍA AVANZADA
        producto = str(r["Producto"])  # CATEGORÍA AVANZADA
        categoria = clasificar_insumo(producto, recipes)  # CATEGORÍA AVANZADA
        if categoria not in ("Producto en Proceso/Semielaborado", "Producto Terminado"):  # CATEGORÍA AVANZADA - solo se descargan a almacén productos con receta propia
            continue  # CATEGORÍA AVANZADA
        cantidad_real = safe_float(r["Cantidad Real"])  # CATEGORÍA AVANZADA
        if cantidad_real <= 0:  # CATEGORÍA AVANZADA
            continue  # CATEGORÍA AVANZADA
        costo_unit = cost_map.get(producto, 0.0)  # CATEGORÍA AVANZADA
        rec_match = recipes[recipes["Producto"].eq(producto)]  # CATEGORÍA AVANZADA
        unidad = rec_match.iloc[0]["Unidad"] if not rec_match.empty else "kg"  # CATEGORÍA AVANZADA - referencia, se asume unidad consistente con receta
        lote_nuevo = f"L-PROD-{re.sub(r'[^A-Za-z0-9]', '', producto).upper()[:8]}-{today().strftime('%Y%m%d')}-{str(r['OP'])[-4:]}"  # CATEGORÍA AVANZADA
        nuevas_filas.append([producto, "unidad", cantidad_real, costo_unit, lote_nuevo, today(), today() + timedelta(days=dias_vigencia_default), "F-Producción", "Disponible", f"Producción OP {r['OP']}"])  # CATEGORÍA AVANZADA
        log_rows.append([today(), r["OP"], producto, cantidad_real, costo_unit, lote_nuevo, categoria])  # CATEGORÍA AVANZADA
    if not nuevas_filas:  # CATEGORÍA AVANZADA
        return inv.copy(), pd.DataFrame(columns=["Fecha", "OP", "Producto", "Cantidad_ingresada", "Costo_unitario", "Lote", "Categoria"])  # CATEGORÍA AVANZADA
    nuevas_df = pd.DataFrame(nuevas_filas, columns=["Insumo", "Unidad", "Stock_lote", "Costo_unitario", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Ubicacion", "Estado", "Origen"])  # CATEGORÍA AVANZADA
    inv_out = pd.concat([inv, nuevas_df], ignore_index=True)  # CATEGORÍA AVANZADA
    log_df = pd.DataFrame(log_rows, columns=["Fecha", "OP", "Producto", "Cantidad_ingresada", "Costo_unitario", "Lote", "Categoria"])  # CATEGORÍA AVANZADA
    return inv_out, log_df  # CATEGORÍA AVANZADA


# MÓDULO VENTAS POS - lectura y normalización de archivo de ventas POS externo (Excel)
POS_COLUMNAS_ESPERADAS = {  # MÓDULO VENTAS POS
    "fecha": "Fecha", "tienda": "Tienda", "producto": "Producto",
    "cantidad": "Cantidad_vendida", "cantidad vendida": "Cantidad_vendida",
    "precio": "Precio_unitario_venta", "precio unitario": "Precio_unitario_venta",
    "precio unitario venta": "Precio_unitario_venta", "total": "Total_venta",
    "canal": "Canal",
}  # MÓDULO VENTAS POS


def normalize_pos_excel(df_raw: pd.DataFrame, nombre_archivo: str) -> pd.DataFrame:
    """Normaliza un Excel de ventas POS externo a las columnas est\u00e1ndar del sistema,
    aceptando variaciones razonables de nombre de columna (insensible a may\u00fasculas/acentos b\u00e1sicos)."""  # MÓDULO VENTAS POS
    if df_raw is None or df_raw.empty:  # MÓDULO VENTAS POS
        return pd.DataFrame(columns=["Fecha", "Tienda", "Producto", "Cantidad_vendida", "Precio_unitario_venta", "Total_venta", "Canal", "Archivo_origen"])  # MÓDULO VENTAS POS
    df = df_raw.copy()  # MÓDULO VENTAS POS
    rename_map = {}  # MÓDULO VENTAS POS
    for col in df.columns:  # MÓDULO VENTAS POS
        key = str(col).strip().lower()  # MÓDULO VENTAS POS
        if key in POS_COLUMNAS_ESPERADAS:  # MÓDULO VENTAS POS
            rename_map[col] = POS_COLUMNAS_ESPERADAS[key]  # MÓDULO VENTAS POS
    df = df.rename(columns=rename_map)  # MÓDULO VENTAS POS
    for col_necesaria in ["Fecha", "Tienda", "Producto", "Cantidad_vendida"]:  # MÓDULO VENTAS POS
        if col_necesaria not in df.columns:  # MÓDULO VENTAS POS
            df[col_necesaria] = None  # MÓDULO VENTAS POS
    if "Precio_unitario_venta" not in df.columns:  # MÓDULO VENTAS POS
        df["Precio_unitario_venta"] = 0.0  # MÓDULO VENTAS POS
    if "Canal" not in df.columns:  # MÓDULO VENTAS POS
        df["Canal"] = "POS Externo"  # MÓDULO VENTAS POS
    df["Cantidad_vendida"] = coerce_num_series(df["Cantidad_vendida"])  # MÓDULO VENTAS POS
    df["Precio_unitario_venta"] = coerce_num_series(df["Precio_unitario_venta"])  # MÓDULO VENTAS POS
    if "Total_venta" not in df.columns or df["Total_venta"].isna().all():  # MÓDULO VENTAS POS
        df["Total_venta"] = df["Cantidad_vendida"] * df["Precio_unitario_venta"]  # MÓDULO VENTAS POS
    else:  # MÓDULO VENTAS POS
        df["Total_venta"] = coerce_num_series(df["Total_venta"])  # MÓDULO VENTAS POS
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date  # MÓDULO VENTAS POS
    df["Archivo_origen"] = nombre_archivo  # MÓDULO VENTAS POS
    df = df[df["Producto"].notna() & (df["Producto"].astype(str).str.strip() != "")]  # MÓDULO VENTAS POS - descarta filas vacías
    return df[["Fecha", "Tienda", "Producto", "Cantidad_vendida", "Precio_unitario_venta", "Total_venta", "Canal", "Archivo_origen"]]  # MÓDULO VENTAS POS


def descontar_stock_por_ventas(ventas: pd.DataFrame, production_control: pd.DataFrame) -> pd.DataFrame:
    """Calcula el stock de producto terminado disponible por producto: Cantidad Real producida (de OP)
    menos lo ya vendido seg\u00fan el log de ventas POS acumulado."""  # MÓDULO VENTAS POS
    if production_control.empty:  # MÓDULO VENTAS POS
        producido = pd.DataFrame(columns=["Producto", "Cantidad Real"])  # MÓDULO VENTAS POS
    else:  # MÓDULO VENTAS POS
        pc = production_control.copy()  # MÓDULO VENTAS POS
        pc["Cantidad Real"] = coerce_num_series(pc["Cantidad Real"])  # MÓDULO VENTAS POS
        producido = pc.groupby("Producto", as_index=False)["Cantidad Real"].sum()  # MÓDULO VENTAS POS
    if ventas.empty:  # MÓDULO VENTAS POS
        vendido = pd.DataFrame(columns=["Producto", "Cantidad_vendida"])  # MÓDULO VENTAS POS
    else:  # MÓDULO VENTAS POS
        vendido = ventas.groupby("Producto", as_index=False)["Cantidad_vendida"].sum()  # MÓDULO VENTAS POS
    out = producido.merge(vendido, on="Producto", how="outer")  # MÓDULO VENTAS POS
    out["Cantidad Real"] = out["Cantidad Real"].fillna(0)  # MÓDULO VENTAS POS
    out["Cantidad_vendida"] = out["Cantidad_vendida"].fillna(0)  # MÓDULO VENTAS POS
    out["Stock_producto_terminado"] = out["Cantidad Real"] - out["Cantidad_vendida"]  # MÓDULO VENTAS POS
    out["Estado_stock_PT"] = np.where(out["Stock_producto_terminado"] < 0, "🔴 Sobreventa vs producción", np.where(out["Stock_producto_terminado"] == 0, "🟡 Agotado", "🟢 Disponible"))  # MÓDULO VENTAS POS
    return out.rename(columns={"Cantidad Real": "Producido_total", "Cantidad_vendida": "Vendido_total"}).sort_values("Stock_producto_terminado")  # MÓDULO VENTAS POS


def rentabilidad_real_vs_op(ventas: pd.DataFrame, costs: pd.DataFrame) -> pd.DataFrame:
    """Cruza ventas POS con el costo unitario calculado desde la explosi\u00f3n de receta y la OP (costs)
    para obtener la rentabilidad REAL (precio de venta real del POS vs costo de producci\u00f3n real)."""  # MÓDULO VENTAS POS
    if ventas.empty or costs.empty:  # MÓDULO VENTAS POS
        return pd.DataFrame(columns=["Producto", "Cantidad_vendida", "Total_venta", "Costo_unitario_OP", "Costo_total_estimado", "Utilidad_real", "Margen_real_%"])  # MÓDULO VENTAS POS
    vend = ventas.groupby("Producto", as_index=False).agg(Cantidad_vendida=("Cantidad_vendida", "sum"), Total_venta=("Total_venta", "sum"))  # MÓDULO VENTAS POS
    cost_unit = costs[["Producto", "Costo unitario"]].rename(columns={"Costo unitario": "Costo_unitario_OP"})  # MÓDULO VENTAS POS
    out = vend.merge(cost_unit, on="Producto", how="left")  # MÓDULO VENTAS POS
    out["Costo_unitario_OP"] = out["Costo_unitario_OP"].fillna(0)  # MÓDULO VENTAS POS
    out["Costo_total_estimado"] = out["Cantidad_vendida"] * out["Costo_unitario_OP"]  # MÓDULO VENTAS POS
    out["Utilidad_real"] = out["Total_venta"] - out["Costo_total_estimado"]  # MÓDULO VENTAS POS
    out["Margen_real_%"] = np.where(out["Total_venta"] > 0, out["Utilidad_real"] / out["Total_venta"] * 100, 0)  # MÓDULO VENTAS POS
    out["Estado_margen"] = np.select([out["Margen_real_%"] < 0, out["Margen_real_%"] < 10], ["🔴 Pérdida real", "🟡 Margen bajo"], default="🟢 Rentable")  # MÓDULO VENTAS POS
    return out.sort_values("Utilidad_real", ascending=False)  # MÓDULO VENTAS POS


st.sidebar.title("⚙️ Parámetros")
st.sidebar.caption(f"Cliente: {CLIENTE_RAZON_SOCIAL} | RUC {CLIENTE_RUC}")
st.sidebar.success(f"Sesión activa: {st.session_state.tienda_actual}")
if st.sidebar.button("Cerrar sesión"):
    st.session_state.login_ok = False
    st.session_state.tienda_actual = None
    st.rerun()
uploaded = st.sidebar.file_uploader("Cargar Excel opcional", type=["xlsx", "xlsm", "xls"])
sheets = read_excel_sheets(uploaded)
if sheets:
    st.sidebar.success(f"{len(sheets)} hojas detectadas")
margin_target = st.sidebar.slider("Margen objetivo", 0.05, 0.45, 0.12, 0.01)
labor_pct = st.sidebar.slider("Mano de obra sobre MP", 0.00, 0.80, 0.25, 0.01)
cif_pct = st.sidebar.slider("CIF sobre MP", 0.00, 0.80, 0.18, 0.01)
if st.sidebar.button("🔄 Reiniciar datos demo"):
    for key in ["inventory", "recipes", "store_orders", "acquisitions", "providers", "physical_count", "production_control", "dispatched_log", "purchase_requests_manual", "dispatch_alerts", "op_por_tienda", "op_correlativo_por_tienda", "categoria_overrides", "pos_ventas", "ventas_stock_log", "produccion_almacen_log"]:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA / MÓDULO CATEGORÍA ALMACÉN / MÓDULO VENTAS POS / CATEGORÍA AVANZADA
        if key in st.session_state:
            del st.session_state[key]
    init_state()
    st.rerun()

inv_current = available_inventory()
store_orders = coerce_date_columns(st.session_state.store_orders, ["Fecha Pedido", "Fecha Requerida"])
recipes = st.session_state.recipes.copy()
consolidated = consolidated_orders(store_orders)
requirements = explode_recipes(consolidated, recipes)
summary = stock_summary(requirements, inv_current)
ops = generate_ops(consolidated, requirements, inv_current)
picking = fifo_picking(requirements, inv_current, ops)
purchase_auto = purchase_requests_auto(summary, st.session_state.providers)
costs = cost_by_product(requirements, inv_current, labor_pct, cif_pct, margin_target)
mermas = compute_mermas(st.session_state.physical_count, inv_current)
ops_tienda = generate_ops_por_tienda(store_orders, requirements, inv_current, recipes)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

st.title("🥐 ERP Gastronómico Pastelería Industrial PRO")
st.caption(f"{CLIENTE_RAZON_SOCIAL} | RUC {CLIENTE_RUC}")
lean_badge("Sistema Lean Manufacturing + Six Sigma aplicado", "dark")
st.markdown("""
<div class="section-note">
<b>Pedido tienda → Consolidación → Orden de Producción → Explosión de recetas → Semáforo de insumos → Compras automáticas → Picking PEPS/FIFO → Descuento de inventario → Control de producción → Mermas reales → Dashboard gerencial.</b>
</div>
""", unsafe_allow_html=True)

flow_cols = st.columns(6)
for c, label in zip(flow_cols, ["Pedido tienda", "OP producción", "Receta", "Almacén PEPS", "Compra faltante", "KPIs"]):
    with c:
        st.markdown(f"<div class='flow-box'>{label}</div>", unsafe_allow_html=True)

# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - se agrega pestaña "2B. Generador de OP por tienda" al listado de tabs
# MÓDULO VENTAS POS - se agrega pestaña "13. Ventas POS externo" al listado de tabs
tabs = st.tabs([
    "1. Dashboard gerencial",
    "2. Pedidos por tienda",
    "2B. Generador de OP por tienda",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    "3. Consolidación y OP",
    "4. Recetas e insumos",
    "5. Semáforo stock",
    "6. Compras automáticas",
    "7. Picking PEPS/FIFO",
    "8. Inventario y adquisiciones",
    "9. Control producción",
    "10. Mermas reales",
    "11. Trazabilidad completa",
    "12. Reporte y video demo",
    "13. Ventas POS externo"  # MÓDULO VENTAS POS
])


with tabs[0]:
    st.header("11. Dashboard gerencial")
    lean_badge("Contabilidad Lean", "purple")
    inv_val = (inv_current["Stock_lote"] * inv_current["Costo_unitario"]).sum() if not inv_current.empty else 0
    stock_critico = summary["Estado"].astype(str).str.contains("🔴").sum() if not summary.empty else 0
    exp_df = inv_current.copy()
    exp_df["Dias_vencimiento"] = (pd.to_datetime(exp_df["Fecha_vencimiento"], errors="coerce") - pd.Timestamp(today())).dt.days
    exp_alerts = (exp_df["Dias_vencimiento"] <= 15).sum() if not exp_df.empty else 0
    urgent_purchases = len(purchase_auto) if not purchase_auto.empty else 0
    op_liberadas = ops["Estado OP"].astype(str).str.contains("🟢").sum() if not ops.empty else 0
    op_total = len(ops)
    op_rate = safe_div(op_liberadas, op_total) * 100 if op_total else 0
    merma_val = mermas["Valor_merma"].sum() if not mermas.empty else 0
    total_cost = costs["Costo total"].sum() if not costs.empty else 0
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi("Valor total almacén", money(inv_val), "Saldo inicial + adquisiciones aceptadas - despachos")
    with c2: kpi("Stock crítico", f"{stock_critico}", "Insumos con faltante")
    with c3: kpi("Alertas vencimiento", f"{exp_alerts}", "Lotes que vencen en 15 días o menos")
    with c4: kpi("Compras urgentes", f"{urgent_purchases}", "Solicitudes automáticas por faltante")
    c5, c6, c7, c8 = st.columns(4)
    with c5: kpi("Cumplimiento OP", f"{op_rate:.1f}%", "OP liberadas / OP totales")
    with c6: kpi("Valor merma real", money(merma_val), "Diferencia físico vs teórico")
    with c7: kpi("Costo producción", money(total_cost), "MP + mano de obra + CIF")
    with c8: kpi("Margen objetivo", f"{margin_target*100:.1f}%", "Parámetro gerencial")
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - KPIs de OP por tienda en dashboard
    op_tienda_total = len(ops_tienda) if not ops_tienda.empty else 0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    op_tienda_liberadas = ops_tienda["Estado OP"].astype(str).str.contains("🟢").sum() if not ops_tienda.empty else 0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    tiendas_con_pedido = ops_tienda["Tienda"].nunique() if not ops_tienda.empty else 0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    c9, c10, c11 = st.columns(3)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with c9: kpi("OP por tienda generadas", f"{op_tienda_total}", "Clave: OP-[TIENDA]-[PROD]-[FECHA]-[CORR]")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with c10: kpi("OP por tienda liberadas", f"{op_tienda_liberadas}", "Stock suficiente para producir")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with c11: kpi("Tiendas activas con pedido", f"{tiendas_con_pedido}", "Tiendas con al menos 1 pedido activo")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.subheader("Semáforo ejecutivo")
    st.dataframe(summary.style.map(style_status, subset=["Estado"]), use_container_width=True)
    c_a, c_b = st.columns(2)
    with c_a:
        st.subheader("Costo y rentabilidad")
        st.dataframe(costs, use_container_width=True)
    with c_b:
        st.subheader("Compras automáticas")
        st.dataframe(purchase_auto, use_container_width=True)
    if PLOTLY_OK and not costs.empty:
        st.plotly_chart(px.bar(costs, x="Producto", y="Costo total", title="Costo total por producto"), use_container_width=True)
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - gráfico de OP por tienda en dashboard
    if PLOTLY_OK and not ops_tienda.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.subheader("OP generadas por tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        fig_tienda = px.bar(ops_tienda, x="Tienda", y="Cantidad", color="Estado OP",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                            title="Cantidad de producción por tienda (OP individuales)",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                            barmode="group")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.plotly_chart(fig_tienda, use_container_width=True)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.subheader("Filosofía Lean & Six Sigma")
    lean_route_panel()

# FIX BUG removeChild (DEFINITIVO) - se reemplaza st.data_editor por st.form + tabla de solo lectura.
# El error 'NotFoundError: removeChild' es un problema conocido del componente interno de Streamlit
# (glide-data-grid) al editar celdas tipo fecha/selectbox dentro de un grid, no de la lógica de la app.
# Un formulario con campos individuales evita por completo ese grid y es 100% estable.
def generar_codigo_pedido(store_orders: pd.DataFrame) -> str:
    """Genera el siguiente código correlativo PED-#### según los códigos ya existentes."""  # FIX BUG removeChild (DEFINITIVO)
    if store_orders.empty or "Código Pedido" not in store_orders.columns:  # FIX BUG removeChild (DEFINITIVO)
        return "PED-0001"  # FIX BUG removeChild (DEFINITIVO)
    codigos = store_orders["Código Pedido"].astype(str)  # FIX BUG removeChild (DEFINITIVO)
    numeros = codigos.str.extract(r"PED-(\d+)", expand=False).dropna().astype(int)  # FIX BUG removeChild (DEFINITIVO)
    siguiente = (numeros.max() + 1) if not numeros.empty else 1  # FIX BUG removeChild (DEFINITIVO)
    return f"PED-{siguiente:04d}"  # FIX BUG removeChild (DEFINITIVO)


with tabs[1]:
    st.header("1. Pedidos por tienda")
    tienda_actual = st.session_state.tienda_actual
    pedidos_globales = coerce_date_columns(st.session_state.store_orders, ["Fecha Pedido", "Fecha Requerida"]).reset_index(drop=True)  # FIX BUG removeChild (DEFINITIVO)
    es_admin = tienda_actual == "Administrador Central"  # FIX BUG removeChild (DEFINITIVO)

    if es_admin:  # FIX BUG removeChild (DEFINITIVO)
        lean_badge("Producción centralizada multi-tienda", "dark")  # FIX BUG removeChild (DEFINITIVO)
        st.success("Panel administrador: visualización y gestión centralizada de todas las solicitudes de tienda.")  # FIX BUG removeChild (DEFINITIVO)
        pedidos_visibles = pedidos_globales  # FIX BUG removeChild (DEFINITIVO)
    else:  # FIX BUG removeChild (DEFINITIVO)
        st.success(f"Bienvenido, {tienda_actual}. En este módulo solo puedes registrar y ver pedidos de tu tienda.")  # FIX BUG removeChild (DEFINITIVO)
        pedidos_visibles = pedidos_globales[pedidos_globales["Tienda"].astype(str).eq(str(tienda_actual))].reset_index(drop=True)  # FIX BUG removeChild (DEFINITIVO)

    st.subheader("➕ Registrar nuevo pedido")  # FIX BUG removeChild (DEFINITIVO)
    with st.form(key=f"form_nuevo_pedido_{tienda_actual}", clear_on_submit=True):  # FIX BUG removeChild (DEFINITIVO) - st.form aísla los widgets y solo procesa al enviar, sin reruns intermedios
        col_f1, col_f2, col_f3 = st.columns(3)  # FIX BUG removeChild (DEFINITIVO)
        with col_f1:  # FIX BUG removeChild (DEFINITIVO)
            fecha_pedido_in = st.date_input("Fecha Pedido", value=today(), key=f"fp_fecha_pedido_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            if es_admin:  # FIX BUG removeChild (DEFINITIVO)
                tienda_in = st.selectbox("Tienda", list(TIENDAS_CREDENCIALES.keys()), key=f"fp_tienda_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            else:  # FIX BUG removeChild (DEFINITIVO)
                tienda_in = tienda_actual  # FIX BUG removeChild (DEFINITIVO)
                st.text_input("Tienda", value=tienda_actual, disabled=True, key=f"fp_tienda_fixed_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
        with col_f2:  # FIX BUG removeChild (DEFINITIVO)
            producto_in = st.selectbox("Producto", sorted(st.session_state.recipes["Producto"].dropna().unique().tolist()), key=f"fp_producto_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            cantidad_in = st.number_input("Cantidad Solicitada", min_value=0.0, step=1.0, value=0.0, key=f"fp_cantidad_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
        with col_f3:  # FIX BUG removeChild (DEFINITIVO)
            fecha_requerida_in = st.date_input("Fecha Requerida", value=today() + timedelta(days=2), key=f"fp_fecha_req_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            prioridad_in = st.selectbox("Prioridad", ["Alta", "Media", "Baja"], index=1, key=f"fp_prioridad_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
        observacion_in = st.text_input("Observación", value="", key=f"fp_observacion_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
        enviado = st.form_submit_button("✅ Registrar pedido")  # FIX BUG removeChild (DEFINITIVO)
        if enviado:  # FIX BUG removeChild (DEFINITIVO)
            if not producto_in or cantidad_in <= 0:  # FIX BUG removeChild (DEFINITIVO)
                st.error("Selecciona un producto y una cantidad mayor a 0 antes de registrar.")  # FIX BUG removeChild (DEFINITIVO)
            else:  # FIX BUG removeChild (DEFINITIVO)
                nuevo_codigo = generar_codigo_pedido(st.session_state.store_orders)  # FIX BUG removeChild (DEFINITIVO)
                nueva_fila = pd.DataFrame([[fecha_pedido_in, tienda_in, nuevo_codigo, producto_in, cantidad_in, fecha_requerida_in, prioridad_in, "Pendiente", observacion_in]], columns=["Fecha Pedido", "Tienda", "Código Pedido", "Producto", "Cantidad Solicitada", "Fecha Requerida", "Prioridad", "Estado", "Observación"])  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders = pd.concat([st.session_state.store_orders, nueva_fila], ignore_index=True)  # FIX BUG removeChild (DEFINITIVO)
                st.success(f"Pedido {nuevo_codigo} registrado para {tienda_in} — {producto_in} x{cantidad_in:.0f}.")  # FIX BUG removeChild (DEFINITIVO)
                st.rerun()  # FIX BUG removeChild (DEFINITIVO)

    st.markdown("---")  # FIX BUG removeChild (DEFINITIVO)
    st.subheader("✏️ Editar o anular un pedido existente")  # FIX BUG removeChild (DEFINITIVO)
    if pedidos_visibles.empty or "Código Pedido" not in pedidos_visibles.columns:  # FIX BUG removeChild (DEFINITIVO)
        st.info("Aún no hay pedidos registrados para editar.")  # FIX BUG removeChild (DEFINITIVO)
    else:  # FIX BUG removeChild (DEFINITIVO)
        codigo_a_editar = st.selectbox("Selecciona el código de pedido a editar", pedidos_visibles["Código Pedido"].astype(str).tolist(), key=f"select_editar_pedido_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
        fila_actual = pedidos_visibles[pedidos_visibles["Código Pedido"].astype(str).eq(codigo_a_editar)].iloc[0]  # FIX BUG removeChild (DEFINITIVO)
        with st.form(key=f"form_editar_pedido_{tienda_actual}"):  # FIX BUG removeChild (DEFINITIVO)
            col_e1, col_e2, col_e3 = st.columns(3)  # FIX BUG removeChild (DEFINITIVO)
            with col_e1:  # FIX BUG removeChild (DEFINITIVO)
                fecha_pedido_edit = st.date_input("Fecha Pedido", value=fila_actual["Fecha Pedido"] if pd.notna(fila_actual["Fecha Pedido"]) else today(), key=f"fe_fecha_pedido_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
                cantidad_edit = st.number_input("Cantidad Solicitada", min_value=0.0, step=1.0, value=safe_float(fila_actual["Cantidad Solicitada"]), key=f"fe_cantidad_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            with col_e2:  # FIX BUG removeChild (DEFINITIVO)
                opciones_producto = sorted(st.session_state.recipes["Producto"].dropna().unique().tolist())  # FIX BUG removeChild (DEFINITIVO)
                idx_prod = opciones_producto.index(fila_actual["Producto"]) if fila_actual["Producto"] in opciones_producto else 0  # FIX BUG removeChild (DEFINITIVO)
                producto_edit = st.selectbox("Producto", opciones_producto, index=idx_prod, key=f"fe_producto_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
                fecha_req_edit = st.date_input("Fecha Requerida", value=fila_actual["Fecha Requerida"] if pd.notna(fila_actual["Fecha Requerida"]) else today(), key=f"fe_fecha_req_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            with col_e3:  # FIX BUG removeChild (DEFINITIVO)
                opciones_prioridad = ["Alta", "Media", "Baja"]  # FIX BUG removeChild (DEFINITIVO)
                idx_prio = opciones_prioridad.index(fila_actual["Prioridad"]) if fila_actual["Prioridad"] in opciones_prioridad else 1  # FIX BUG removeChild (DEFINITIVO)
                prioridad_edit = st.selectbox("Prioridad", opciones_prioridad, index=idx_prio, key=f"fe_prioridad_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
                opciones_estado = ["Pendiente", "Producción", "Entregado", "Anulado"]  # FIX BUG removeChild (DEFINITIVO)
                idx_estado = opciones_estado.index(fila_actual["Estado"]) if fila_actual["Estado"] in opciones_estado else 0  # FIX BUG removeChild (DEFINITIVO)
                estado_edit = st.selectbox("Estado", opciones_estado, index=idx_estado, key=f"fe_estado_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            observacion_edit = st.text_input("Observación", value=str(fila_actual.get("Observación", "")) if pd.notna(fila_actual.get("Observación", "")) else "", key=f"fe_observacion_{tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
            col_btn1, col_btn2 = st.columns(2)  # FIX BUG removeChild (DEFINITIVO)
            with col_btn1:  # FIX BUG removeChild (DEFINITIVO)
                guardar_cambios = st.form_submit_button("💾 Guardar cambios")  # FIX BUG removeChild (DEFINITIVO)
            with col_btn2:  # FIX BUG removeChild (DEFINITIVO)
                eliminar_pedido = st.form_submit_button("🗑️ Eliminar pedido")  # FIX BUG removeChild (DEFINITIVO)
            if guardar_cambios:  # FIX BUG removeChild (DEFINITIVO)
                mask_edit = st.session_state.store_orders["Código Pedido"].astype(str).eq(codigo_a_editar)  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Fecha Pedido"] = fecha_pedido_edit  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Producto"] = producto_edit  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Cantidad Solicitada"] = cantidad_edit  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Fecha Requerida"] = fecha_req_edit  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Prioridad"] = prioridad_edit  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Estado"] = estado_edit  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders.loc[mask_edit, "Observación"] = observacion_edit  # FIX BUG removeChild (DEFINITIVO)
                st.success(f"Pedido {codigo_a_editar} actualizado.")  # FIX BUG removeChild (DEFINITIVO)
                st.rerun()  # FIX BUG removeChild (DEFINITIVO)
            if eliminar_pedido:  # FIX BUG removeChild (DEFINITIVO)
                st.session_state.store_orders = st.session_state.store_orders[~st.session_state.store_orders["Código Pedido"].astype(str).eq(codigo_a_editar)].reset_index(drop=True)  # FIX BUG removeChild (DEFINITIVO)
                st.success(f"Pedido {codigo_a_editar} eliminado.")  # FIX BUG removeChild (DEFINITIVO)
                st.rerun()  # FIX BUG removeChild (DEFINITIVO)

    st.markdown("---")  # FIX BUG removeChild (DEFINITIVO)
    st.subheader("📋 Pedidos registrados" if es_admin else f"📋 Pedidos registrados — {tienda_actual}")  # FIX BUG removeChild (DEFINITIVO)
    st.dataframe(pedidos_visibles, use_container_width=True)  # FIX BUG removeChild (DEFINITIVO) - tabla de solo lectura, sin grid editable, no dispara removeChild
    if not pedidos_visibles.empty:  # FIX BUG removeChild (DEFINITIVO)
        st.subheader("Vista consolidada de pedidos" + ("" if es_admin else f" - {tienda_actual}"))  # FIX BUG removeChild (DEFINITIVO)
        pivot = pedidos_visibles.pivot_table(index="Tienda", columns="Producto", values="Cantidad Solicitada", aggfunc="sum", fill_value=0)  # FIX BUG removeChild (DEFINITIVO)
        st.dataframe(pivot, use_container_width=True)  # FIX BUG removeChild (DEFINITIVO)

# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - pestaña 2B: Generador de OP por tienda
with tabs[2]:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.header("2B. Generador de OP por tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    lean_badge("Clave OP: OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]", "purple")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.markdown("""  
    <div class="section-note">  
    <b>Generador automático de Órdenes de Producción individuales por tienda.</b>  
    Cada OP usa la clave única: <code>OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]</code>.  
    Permite trazabilidad completa desde el pedido de cada tienda hasta producción, picking y despacho.  
    </div>  
    """, unsafe_allow_html=True)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    tienda_actual_2b = st.session_state.tienda_actual  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    # Filtro por tienda según sesión activa
    if tienda_actual_2b == "Administrador Central":  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        filtro_tiendas_2b = ["Todas"] + sorted(ops_tienda["Tienda"].unique().tolist()) if not ops_tienda.empty else ["Todas"]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        tienda_sel_2b = st.selectbox("Filtrar por tienda", filtro_tiendas_2b, key="sel_tienda_2b")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    else:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        tienda_sel_2b = tienda_actual_2b  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.info(f"Visualizando OP generadas para tu tienda: **{tienda_sel_2b}**")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    ops_tienda_display = ops_tienda.copy()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if tienda_actual_2b == "Administrador Central" and tienda_sel_2b != "Todas":  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        ops_tienda_display = ops_tienda_display[ops_tienda_display["Tienda"].eq(tienda_sel_2b)]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    elif tienda_actual_2b != "Administrador Central":  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        ops_tienda_display = ops_tienda_display[ops_tienda_display["Tienda"].eq(tienda_sel_2b)]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    # Métricas resumen del generador
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with col_m1:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        kpi("OP generadas", f"{len(ops_tienda_display)}", "Total OP individuales por tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with col_m2:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_lib_2b = ops_tienda_display["Estado OP"].astype(str).str.contains("🟢").sum() if not ops_tienda_display.empty else 0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        kpi("OP liberadas", f"{op_lib_2b}", "Stock suficiente para iniciar")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with col_m3:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_bloq_2b = ops_tienda_display["Estado OP"].astype(str).str.contains("🔴").sum() if not ops_tienda_display.empty else 0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        kpi("OP bloqueadas", f"{op_bloq_2b}", "Falta de insumo en almacén")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    with col_m4:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        cant_total_2b = ops_tienda_display["Cantidad"].sum() if not ops_tienda_display.empty else 0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        kpi("Unidades totales", f"{cant_total_2b:,.0f}", "Suma de unidades a producir por tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    st.subheader("Órdenes de producción individuales por tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.markdown("**Clave de cada OP:** `OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]`")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    if ops_tienda_display.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.info("No hay OP de tienda generadas. Registra pedidos en la pestaña '2. Pedidos por tienda'.")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    else:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        # Editor de OP por tienda con ajuste de responsable y observación
        ops_tienda_edit = st.data_editor(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            ops_tienda_display,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            use_container_width=True,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            key="op_tienda_editor_2b",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            disabled=["OP", "Tienda", "Producto", "Cantidad", "Fecha_OP", "Estado OP"],  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            column_config={  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "OP": st.column_config.TextColumn("Clave OP", disabled=True),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Tienda": st.column_config.TextColumn("Tienda", disabled=True),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Producto": st.column_config.TextColumn("Producto", disabled=True),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Cantidad": st.column_config.NumberColumn("Cantidad", disabled=True, format="%.0f"),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Fecha_OP": st.column_config.DateColumn("Fecha OP", disabled=True),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Fecha_requerida": st.column_config.DateColumn("Fecha requerida", disabled=True),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Prioridad": st.column_config.SelectboxColumn("Prioridad", options=["Alta", "Media", "Baja"]),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Estado OP": st.column_config.TextColumn("Estado OP", disabled=True),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Responsable_tienda": st.column_config.TextColumn("Responsable tienda"),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                "Observacion": st.column_config.TextColumn("Observación"),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            },  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    st.markdown("---")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.subheader("Explosión de recetas por OP de tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    lean_badge("Semáforo por OP individual", "red")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    if not ops_tienda_display.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        explosion_tienda = explode_recipes_por_op_tienda(ops_tienda_display, recipes, inv_current)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        if not explosion_tienda.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            st.dataframe(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                explosion_tienda.style.map(style_status, subset=["Estado_semaforo"]),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                use_container_width=True  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        else:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            st.info("No hay recetas definidas para los productos pedidos. Verifica la pestaña de Recetas.")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    st.markdown("---")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.subheader("Picking PEPS/FIFO por OP individual de tienda")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    lean_badge("Picking por clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]", "blue")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    if not ops_tienda_display.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_sel_tienda = st.selectbox(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            "Selecciona OP de tienda para ver picking",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            ops_tienda_display["OP"].tolist(),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            key="op_sel_tienda_picking_2b"  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        op_row_sel = ops_tienda_display[ops_tienda_display["OP"].eq(op_sel_tienda)].iloc[0]  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        picking_op_tienda = fifo_picking_por_op_tienda(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            op_sel_tienda,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            op_row_sel["Producto"],  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            safe_float(op_row_sel["Cantidad"]),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA / FIX BUG TypeError
            recipes,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            inv_current  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        if not picking_op_tienda.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            st.dataframe(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                picking_op_tienda.style.map(style_status, subset=["Estado"]),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                use_container_width=True  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            valor_picking = picking_op_tienda["Valor_salida"].sum()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            hay_faltantes_2b = picking_op_tienda["Estado"].astype(str).str.contains("🔴").any()  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            c_pick1, c_pick2 = st.columns(2)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            with c_pick1:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                kpi("Valor picking OP tienda", money(valor_picking), f"OP: {op_sel_tienda}")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            with c_pick2:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
                kpi("Estado semáforo picking", "🔴 Con faltantes" if hay_faltantes_2b else "🟢 Completo", "PEPS/FIFO estricto por vencimiento")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        else:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            st.info("No se pudo generar picking para esta OP. Verifica la receta del producto.")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    st.markdown("---")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.subheader("Resumen de OP por tienda — vista matriz")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if not ops_tienda.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        pivot_tienda = ops_tienda.pivot_table(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            index="Tienda", columns="Producto", values="Cantidad", aggfunc="sum", fill_value=0  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.dataframe(pivot_tienda, use_container_width=True)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

    st.markdown("---")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    # Descarga Excel de OP por tienda
    if not ops_tienda.empty:  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        explosion_tienda_full = explode_recipes_por_op_tienda(ops_tienda, recipes, inv_current)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        reporte_op_tienda = {  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            "OP_por_Tienda": ops_tienda,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            "Explosion_por_OP_Tienda": explosion_tienda_full,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        }  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.download_button(  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            "📥 Descargar Excel de OP por tienda",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            data=excel_download(reporte_op_tienda),  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            file_name=f"OP_Por_Tienda_{today_str()}.xlsx",  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        )  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA

# INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - tabs renumerados desde índice 3 en adelante por inserción de tab 2B
with tabs[3]:
    st.header("2. Consolidación automática y 3. Generador de OP")
    lean_badge("Control Visual Andon / Jidoka", "red")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Consolidación")
        st.dataframe(consolidated, use_container_width=True)
    with c2:
        st.subheader("Órdenes de producción")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - muestra clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]
        st.caption("Clave OP: OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        st.dataframe(ops.style.map(style_status, subset=["Estado OP"]), use_container_width=True)

with tabs[4]:
    st.header("4. Explosión automática de recetas")
    lean_badge("Trabajo Estándar", "blue")
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - recetas incluyen productos del Excel RECETAS_PARA_DEMO.xlsx
    st.caption("Las recetas incluyen productos del archivo RECETAS_PARA_DEMO.xlsx: Masa quebrada, Pye de manzana, Base blanca de helados, Helado de stracciatella, Empanada de carne, Masa de empanada, Armado de empanadas.")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    st.session_state.recipes = st.data_editor(st.session_state.recipes, num_rows="dynamic", use_container_width=True, key="recipes_editor", column_config={"Rendimiento_lote": st.column_config.NumberColumn("Rendimiento lote", min_value=0.0001, step=1.0), "Cantidad_receta": st.column_config.NumberColumn("Cantidad receta", min_value=0.0, step=0.01, format="%.4f"), "Merma_tecnica_pct": st.column_config.NumberColumn("Merma técnica %", min_value=0.0, max_value=1.0, step=0.01, format="%.2f"), "Criticidad": st.column_config.SelectboxColumn("Criticidad", options=["Crítico", "Normal", "Bajo"])})
    st.subheader("Explosión calculada")
    st.dataframe(requirements, use_container_width=True)

with tabs[5]:
    st.header("5. Semáforo de disponibilidad de insumos")
    lean_badge("Control Visual Andon / Jidoka", "red")

    # SEMÁFORO 5 CATEGORÍAS - agrega Categoria al summary y muestra por separado cada tipo de insumo/producto
    summary_cat = summary.copy()
    recipes_ctx = st.session_state.recipes if "recipes" in st.session_state else pd.DataFrame()
    summary_cat["Categoria"] = summary_cat["Insumo"].apply(lambda x: clasificar_insumo(x, recipes_ctx))  # SEMÁFORO 5 CATEGORÍAS

    # SEMÁFORO 5 CATEGORÍAS - semáforo adicional para semielaborados y terminados en inventario que no salen del requirements
    inv_extra = inv_current.copy()
    inv_extra["Categoria"] = inv_extra["Insumo"].apply(lambda x: clasificar_insumo(x, recipes_ctx))  # SEMÁFORO 5 CATEGORÍAS
    cats_extra = ["Producto en Proceso/Semielaborado", "Producto Terminado"]  # SEMÁFORO 5 CATEGORÍAS
    inv_extra_stock = inv_extra[inv_extra["Categoria"].isin(cats_extra) & inv_extra["Estado"].astype(str).str.lower().eq("disponible")].groupby(["Insumo", "Unidad", "Categoria"], as_index=False)["Stock_lote"].sum()  # SEMÁFORO 5 CATEGORÍAS

    def semaforo_seccion(df_sub: pd.DataFrame, titulo: str, icono: str, alerta_faltante: bool = True):
        """Muestra una sección del semáforo con KPIs y tabla coloreada."""  # SEMÁFORO 5 CATEGORÍAS
        if df_sub.empty:
            return  # SEMÁFORO 5 CATEGORÍAS
        st.markdown(f"#### {icono} {titulo}")  # SEMÁFORO 5 CATEGORÍAS
        c_ok = df_sub["Estado"].astype(str).str.contains("🟢").sum() if "Estado" in df_sub.columns else 0  # SEMÁFORO 5 CATEGORÍAS
        c_warn = df_sub["Estado"].astype(str).str.contains("🟡").sum() if "Estado" in df_sub.columns else 0  # SEMÁFORO 5 CATEGORÍAS
        c_bad = df_sub["Estado"].astype(str).str.contains("🔴").sum() if "Estado" in df_sub.columns else 0  # SEMÁFORO 5 CATEGORÍAS
        kc1, kc2, kc3 = st.columns(3)  # SEMÁFORO 5 CATEGORÍAS
        with kc1: kpi("🟢 Suficiente", str(c_ok), "insumos/productos sin alerta")  # SEMÁFORO 5 CATEGORÍAS
        with kc2: kpi("🟡 Stock justo", str(c_warn), "revisar reposición")  # SEMÁFORO 5 CATEGORÍAS
        with kc3: kpi("🔴 Faltante", str(c_bad), "requiere compra o producción urgente")  # SEMÁFORO 5 CATEGORÍAS
        st.dataframe(df_sub.style.map(style_status, subset=["Estado"]), use_container_width=True)  # SEMÁFORO 5 CATEGORÍAS
        if alerta_faltante and "Faltante" in df_sub.columns:  # SEMÁFORO 5 CATEGORÍAS
            for _, r in df_sub.iterrows():  # SEMÁFORO 5 CATEGORÍAS
                if r["Faltante"] > 0:
                    st.error(f"⛔ Falta {r['Faltante']:.3f} {r['Unidad']} de **{r['Insumo']}** — necesita {r['Necesita']:.3f}, tiene {r['Tiene']:.3f}.")
                elif "🟡" in str(r["Estado"]):
                    st.warning(f"⚠️ {r['Insumo']}: stock justo ({r['Tiene']:.3f} {r['Unidad']} para requerimiento de {r['Necesita']:.3f}).")

    tab_s1, tab_s2, tab_s3, tab_s4, tab_s5 = st.tabs(["📦 Materia Prima", "⚙️ En Proceso/Semielaborado", "🍰 Producto Terminado", "🏷️ Materiales Auxiliares", "🧴 Suministros"])  # SEMÁFORO 5 CATEGORÍAS

    with tab_s1:  # SEMÁFORO 5 CATEGORÍAS - Materia Prima
        df_s1 = summary_cat[summary_cat["Categoria"].eq("Materia Prima")].drop(columns=["Categoria"], errors="ignore")
        semaforo_seccion(df_s1, "Materia Prima", "📦")

    with tab_s2:  # SEMÁFORO 5 CATEGORÍAS - Semielaborados (en requirements + en inventario)
        df_s2_req = summary_cat[summary_cat["Categoria"].eq("Producto en Proceso/Semielaborado")].drop(columns=["Categoria"], errors="ignore")
        df_s2_inv = inv_extra_stock[inv_extra_stock["Categoria"].eq("Producto en Proceso/Semielaborado")].rename(columns={"Stock_lote": "Tiene"}).assign(Necesita=0, Faltante=0, Sobrante=lambda d: d["Tiene"], **{"Cobertura_%": 100, "Estado": "🟢 Suficiente"}).drop(columns=["Categoria"], errors="ignore")
        df_s2_inv = df_s2_inv[~df_s2_inv["Insumo"].isin(df_s2_req["Insumo"].tolist())]  # SEMÁFORO 5 CATEGORÍAS - no duplicar si ya aparece en requirements
        df_s2 = pd.concat([df_s2_req, df_s2_inv], ignore_index=True)
        semaforo_seccion(df_s2, "Producto en Proceso / Semielaborado", "⚙️")
        st.caption("Stock disponible de semielaborados (Masa quebrada, Masa de empanada, Base blanca de helados) para usar en otras recetas.")

    with tab_s3:  # SEMÁFORO 5 CATEGORÍAS - Productos terminados
        df_s3_req = summary_cat[summary_cat["Categoria"].eq("Producto Terminado")].drop(columns=["Categoria"], errors="ignore")
        df_s3_inv = inv_extra_stock[inv_extra_stock["Categoria"].eq("Producto Terminado")].rename(columns={"Stock_lote": "Tiene"}).assign(Necesita=0, Faltante=0, Sobrante=lambda d: d["Tiene"], **{"Cobertura_%": 100, "Estado": "🟢 Suficiente"}).drop(columns=["Categoria"], errors="ignore")
        df_s3_inv = df_s3_inv[~df_s3_inv["Insumo"].isin(df_s3_req["Insumo"].tolist())]  # SEMÁFORO 5 CATEGORÍAS
        df_s3 = pd.concat([df_s3_req, df_s3_inv], ignore_index=True)
        semaforo_seccion(df_s3, "Producto Terminado", "🍰")
        st.caption("Stock disponible de productos terminados (Pie de queso, Empanada de carne, etc.) listos para venta.")

    with tab_s4:  # SEMÁFORO 5 CATEGORÍAS - Materiales Auxiliares
        df_s4 = summary_cat[summary_cat["Categoria"].eq("Materiales Auxiliares")].drop(columns=["Categoria"], errors="ignore")
        semaforo_seccion(df_s4, "Materiales Auxiliares", "🏷️")

    with tab_s5:  # SEMÁFORO 5 CATEGORÍAS - Suministros
        df_s5 = summary_cat[summary_cat["Categoria"].eq("Suministros")].drop(columns=["Categoria"], errors="ignore")
        semaforo_seccion(df_s5, "Suministros", "🧴")

with tabs[6]:
    st.header("6. Compras automáticas")
    lean_badge("Sistema Kanban / Just In Time", "green")

    # FIX BUG removeChild - Proveedores con data_editor es de solo lectura real (no edita fecha), se deja
    st.subheader("Proveedores sugeridos")
    st.session_state.providers = st.data_editor(st.session_state.providers, num_rows="dynamic", use_container_width=True, key="providers_editor", column_config={"Prioridad base": st.column_config.SelectboxColumn("Prioridad base", options=["Alta", "Media", "Baja"])})

    st.subheader("Solicitudes automáticas")
    st.dataframe(purchase_auto, use_container_width=True)

    st.markdown("---")
    st.subheader("➕ Registrar solicitud de compra manual")  # FIX BUG removeChild - reemplaza data_editor de compras manuales
    st.caption("Usa este formulario para añadir una compra manual adicional. Sin grid editable, sin doble digitación.")  # FIX BUG removeChild
    all_insumos_compra = sorted(set(inv_current["Insumo"].dropna().unique().tolist()) | set(st.session_state.providers["Insumo"].dropna().unique().tolist()))  # FIX BUG removeChild
    with st.form(key="form_compra_manual", clear_on_submit=True):  # FIX BUG removeChild
        col_c1, col_c2, col_c3 = st.columns(3)  # FIX BUG removeChild
        with col_c1:  # FIX BUG removeChild
            fecha_compra = st.date_input("Fecha", value=today(), key="cm_fecha")  # FIX BUG removeChild
            modo_insumo_c = st.radio("Insumo", ["Elegir de lista", "Escribir nuevo"], horizontal=True, key="cm_modo")  # FIX BUG removeChild
            if modo_insumo_c == "Elegir de lista":  # FIX BUG removeChild
                insumo_compra = st.selectbox("Insumo", all_insumos_compra, key="cm_insumo_sel")  # FIX BUG removeChild
            else:  # FIX BUG removeChild
                insumo_compra = st.text_input("Nombre insumo", key="cm_insumo_txt")  # FIX BUG removeChild
        with col_c2:  # FIX BUG removeChild
            unidad_compra = st.selectbox("Unidad", ["kg", "lt", "unidad", "g", "ml"], key="cm_unidad")  # FIX BUG removeChild
            cantidad_compra = st.number_input("Cantidad faltante", min_value=0.0, step=0.01, value=0.0, key="cm_cantidad")  # FIX BUG removeChild
        with col_c3:  # FIX BUG removeChild
            provs_disponibles = st.session_state.providers["Proveedor sugerido"].dropna().unique().tolist()  # FIX BUG removeChild
            prov_compra = st.selectbox("Proveedor sugerido", provs_disponibles + ["Otro"], key="cm_prov")  # FIX BUG removeChild
            prioridad_compra = st.selectbox("Prioridad", ["Alta", "Media", "Baja"], index=1, key="cm_prioridad")  # FIX BUG removeChild
            estado_compra = st.selectbox("Estado", ["Pendiente", "Cotizado", "Comprado", "Anulado"], key="cm_estado")  # FIX BUG removeChild
        enviado_compra = st.form_submit_button("✅ Registrar solicitud manual")  # FIX BUG removeChild
        if enviado_compra:  # FIX BUG removeChild
            if not insumo_compra or cantidad_compra <= 0:  # FIX BUG removeChild
                st.error("Indica el insumo y una cantidad mayor a 0.")  # FIX BUG removeChild
            else:  # FIX BUG removeChild
                nueva_compra = pd.DataFrame([[fecha_compra, insumo_compra, unidad_compra, cantidad_compra, prov_compra, prioridad_compra, estado_compra, "Manual"]], columns=["Fecha", "Insumo", "Unidad", "Cantidad faltante", "Proveedor sugerido", "Prioridad", "Estado", "Origen"])  # FIX BUG removeChild
                st.session_state.purchase_requests_manual = pd.concat([st.session_state.purchase_requests_manual, nueva_compra], ignore_index=True)  # FIX BUG removeChild
                st.success(f"Solicitud manual registrada: {insumo_compra} — {cantidad_compra:.2f} {unidad_compra}.")  # FIX BUG removeChild
                st.rerun()  # FIX BUG removeChild

    if not st.session_state.purchase_requests_manual.empty:  # FIX BUG removeChild
        st.subheader("✏️ Editar o anular solicitud manual")  # FIX BUG removeChild
        idx_compra = st.selectbox("Selecciona solicitud a editar (índice)", st.session_state.purchase_requests_manual.index.tolist(), format_func=lambda i: f"#{i} — {st.session_state.purchase_requests_manual.loc[i,'Insumo']} ({st.session_state.purchase_requests_manual.loc[i,'Cantidad faltante']:.2f} {st.session_state.purchase_requests_manual.loc[i,'Unidad']})", key="cm_sel_editar")  # FIX BUG removeChild
        fila_compra = st.session_state.purchase_requests_manual.loc[idx_compra]  # FIX BUG removeChild
        with st.form(key="form_editar_compra_manual"):  # FIX BUG removeChild
            col_ce1, col_ce2 = st.columns(2)  # FIX BUG removeChild
            with col_ce1:  # FIX BUG removeChild
                cant_edit = st.number_input("Cantidad faltante", min_value=0.0, step=0.01, value=safe_float(fila_compra["Cantidad faltante"]), key="cme_cantidad")  # FIX BUG removeChild
                prov_edit = st.text_input("Proveedor sugerido", value=str(fila_compra.get("Proveedor sugerido", "")), key="cme_prov")  # FIX BUG removeChild
            with col_ce2:  # FIX BUG removeChild
                prio_opts = ["Alta", "Media", "Baja"]  # FIX BUG removeChild
                idx_prio_c = prio_opts.index(fila_compra["Prioridad"]) if fila_compra["Prioridad"] in prio_opts else 1  # FIX BUG removeChild
                prio_edit = st.selectbox("Prioridad", prio_opts, index=idx_prio_c, key="cme_prio")  # FIX BUG removeChild
                est_opts = ["Pendiente", "Cotizado", "Comprado", "Anulado"]  # FIX BUG removeChild
                idx_est_c = est_opts.index(fila_compra["Estado"]) if fila_compra["Estado"] in est_opts else 0  # FIX BUG removeChild
                est_edit = st.selectbox("Estado", est_opts, index=idx_est_c, key="cme_estado")  # FIX BUG removeChild
            col_btn_c1, col_btn_c2 = st.columns(2)  # FIX BUG removeChild
            with col_btn_c1: guardar_compra = st.form_submit_button("💾 Guardar cambios")  # FIX BUG removeChild
            with col_btn_c2: eliminar_compra = st.form_submit_button("🗑️ Eliminar solicitud")  # FIX BUG removeChild
            if guardar_compra:  # FIX BUG removeChild
                st.session_state.purchase_requests_manual.loc[idx_compra, "Cantidad faltante"] = cant_edit  # FIX BUG removeChild
                st.session_state.purchase_requests_manual.loc[idx_compra, "Proveedor sugerido"] = prov_edit  # FIX BUG removeChild
                st.session_state.purchase_requests_manual.loc[idx_compra, "Prioridad"] = prio_edit  # FIX BUG removeChild
                st.session_state.purchase_requests_manual.loc[idx_compra, "Estado"] = est_edit  # FIX BUG removeChild
                st.success("Solicitud actualizada.")  # FIX BUG removeChild
                st.rerun()  # FIX BUG removeChild
            if eliminar_compra:  # FIX BUG removeChild
                st.session_state.purchase_requests_manual = st.session_state.purchase_requests_manual.drop(index=idx_compra).reset_index(drop=True)  # FIX BUG removeChild
                st.success("Solicitud eliminada.")  # FIX BUG removeChild
                st.rerun()  # FIX BUG removeChild

    st.subheader("📋 Solicitudes manuales registradas")  # FIX BUG removeChild
    st.dataframe(coerce_date_columns(st.session_state.purchase_requests_manual, ["Fecha"]), use_container_width=True)  # FIX BUG removeChild - solo lectura
    st.subheader("📋 Bandeja total de compras")
    st.dataframe(pd.concat([purchase_auto, st.session_state.purchase_requests_manual], ignore_index=True), use_container_width=True)

with tabs[7]:
    st.header("7. Picking inteligente PEPS/FIFO y descuento automático")
    lean_badge("Enfoque 5S / Trabajo Estándar", "blue")
    st.info("El picking prioriza lote más próximo a vencer y luego fecha de ingreso: lógica PEPS/FIFO estricta por vencimiento.")
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - picking usa OP con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]
    if ops.empty:
        st.info("No hay OP generadas.")
    else:
        selected_op = st.selectbox("Selecciona OP", ops["OP"].tolist())
        pick_op = picking[picking["OP"] == selected_op].copy()
        pick_op = normalize_picking_for_dispatch(pick_op)
        st.subheader(f"Hoja de picking - {selected_op}")
        pick_editado = st.data_editor(
            pick_op,
            use_container_width=True,
            key=f"picking_editor_{selected_op}",
            column_config={
                "Cantidad_a_entregar": st.column_config.NumberColumn("Cantidad requerida por receta", disabled=True, format="%.4f"),
                "Cantidad_despachar_real": st.column_config.NumberColumn("Cantidad a despachar real", min_value=0.0, step=0.01, format="%.4f"),
                "Diferencia_despacho": st.column_config.NumberColumn("Diferencia", disabled=True, format="%.4f"),
                "Alerta_despacho": st.column_config.TextColumn("Alerta despacho", disabled=True),
            },
        )
        pick_editado = normalize_picking_for_dispatch(pick_editado)
        st.dataframe(pick_editado[["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_vencimiento", "Cantidad_a_entregar", "Cantidad_despachar_real", "Diferencia_despacho", "Alerta_despacho", "Estado"]].style.map(style_status, subset=["Alerta_despacho", "Estado"]), use_container_width=True)
        responsable = st.text_input("Responsable almacén", "Almacenero")
        disabled_dispatch = pick_editado["Estado"].astype(str).str.contains("🔴").any() or pick_editado["Alerta_despacho"].astype(str).str.contains("🔴").any()
        if pick_editado["Alerta_despacho"].astype(str).str.contains("🔴").any():
            alert_rows = pick_editado[pick_editado["Alerta_despacho"].astype(str).str.contains("🔴")].copy()
            st.error("Hay diferencias entre la cantidad requerida por receta y la cantidad intentada. Corrige antes de despachar.")
            alert_log = alert_rows[["OP", "Producto", "Insumo", "Unidad", "Lote", "Cantidad_a_entregar", "Cantidad_despachar_real", "Diferencia_despacho", "Alerta_despacho"]].copy()
            alert_log.insert(0, "Fecha", today())
            alert_log["Responsable"] = responsable
            alert_log = alert_log.rename(columns={"Cantidad_a_entregar": "Cantidad_requerida", "Cantidad_despachar_real": "Cantidad_intentada", "Diferencia_despacho": "Diferencia", "Alerta_despacho": "Alerta"})
            st.session_state.dispatch_alerts = pd.concat([st.session_state.dispatch_alerts, alert_log], ignore_index=True).drop_duplicates()
        if st.button("✅ Despachar OP y descontar inventario", disabled=disabled_dispatch):
            pick_para_despacho = pick_editado.copy()
            pick_para_despacho["Cantidad_a_entregar"] = pick_para_despacho["Cantidad_despachar_real"]
            new_inv, log_df, msg = dispatch_inventory(st.session_state.inventory, pick_para_despacho, selected_op, responsable)
            if not log_df.empty:
                st.session_state.inventory = new_inv
                st.session_state.dispatched_log = pd.concat([st.session_state.dispatched_log, log_df], ignore_index=True)
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)
        if disabled_dispatch:
            st.warning("Despacho bloqueado hasta que la OP no tenga faltantes y el despacho coincida exactamente con la receta.")
        st.subheader("Histórico de despachos")
        st.dataframe(st.session_state.dispatched_log, use_container_width=True)
        st.subheader("Alertas de intento de despacho fuera de receta")
        st.dataframe(st.session_state.dispatch_alerts, use_container_width=True)

with tabs[8]:
    st.header("8. Inventario, saldo inicial y adquisiciones")
    lean_badge("Enfoque 5S / Trabajo Estándar", "blue")
    subtab1, subtab2, subtab3, subtab4 = st.tabs(["Saldo inicial / lotes", "Adquisiciones documentarias", "Inventario operativo valorizado", "Almacén por categoría"])  # MÓDULO CATEGORÍA ALMACÉN - nueva subpestaña
    with subtab1:
        # FIX BUG removeChild (DEFINITIVO) - se reemplaza st.data_editor por formulario estable, mismo patrón que en "1. Pedidos por tienda"
        st.markdown("""
        <div class="section-note">
        Registra aquí el <b>saldo inicial</b> de cualquier insumo: Materia Prima, Materiales Auxiliares, Suministros,
        y también <b>Productos en Proceso/Semielaborados</b> (Masa quebrada, Masa de empanada, Base blanca de helados)
        y <b>Productos Terminados</b> (Pie de queso, Empanada de carne, etc.). Puedes registrar, corregir o actualizar
        el saldo en cualquier momento; cada registro es un lote independiente con su propio costo y vencimiento.
        </div>
        """, unsafe_allow_html=True)  # FIX BUG removeChild (DEFINITIVO)

        productos_con_receta_si = sorted(st.session_state.recipes["Producto"].dropna().unique().tolist())  # FIX BUG removeChild (DEFINITIVO)
        insumos_existentes_si = sorted(st.session_state.inventory["Insumo"].dropna().unique().tolist()) if not st.session_state.inventory.empty else []  # FIX BUG removeChild (DEFINITIVO)
        opciones_insumo_si = sorted(set(productos_con_receta_si) | set(insumos_existentes_si))  # FIX BUG removeChild (DEFINITIVO) - incluye semielaborados/terminados + insumos ya usados

        st.subheader("➕ Registrar saldo inicial de un insumo o producto")  # FIX BUG removeChild (DEFINITIVO)
        with st.form(key="form_nuevo_saldo_inicial", clear_on_submit=True):  # FIX BUG removeChild (DEFINITIVO)
            col_s1, col_s2, col_s3 = st.columns(3)  # FIX BUG removeChild (DEFINITIVO)
            with col_s1:  # FIX BUG removeChild (DEFINITIVO)
                modo_insumo = st.radio("Insumo/Producto", ["Elegir de la lista", "Escribir nuevo"], horizontal=True, key="si_modo_insumo")  # FIX BUG removeChild (DEFINITIVO)
                if modo_insumo == "Elegir de la lista" and opciones_insumo_si:  # FIX BUG removeChild (DEFINITIVO)
                    insumo_in = st.selectbox("Insumo / Producto", opciones_insumo_si, key="si_insumo_select")  # FIX BUG removeChild (DEFINITIVO)
                else:  # FIX BUG removeChild (DEFINITIVO)
                    insumo_in = st.text_input("Nombre del insumo/producto", key="si_insumo_texto")  # FIX BUG removeChild (DEFINITIVO)
                unidad_in = st.selectbox("Unidad", ["kg", "lt", "unidad", "g", "ml"], key="si_unidad")  # FIX BUG removeChild (DEFINITIVO)
            with col_s2:  # FIX BUG removeChild (DEFINITIVO)
                stock_in = st.number_input("Stock del lote", min_value=0.0, step=0.01, value=0.0, key="si_stock")  # FIX BUG removeChild (DEFINITIVO)
                costo_in = st.number_input("Costo unitario (S/)", min_value=0.0, step=0.01, value=0.0, key="si_costo")  # FIX BUG removeChild (DEFINITIVO)
            with col_s3:  # FIX BUG removeChild (DEFINITIVO)
                fecha_ingreso_in = st.date_input("Fecha de ingreso", value=today(), key="si_fecha_ingreso")  # FIX BUG removeChild (DEFINITIVO)
                fecha_venc_in = st.date_input("Fecha de vencimiento", value=today() + timedelta(days=30), key="si_fecha_venc")  # FIX BUG removeChild (DEFINITIVO)
            col_s4, col_s5 = st.columns(2)  # FIX BUG removeChild (DEFINITIVO)
            with col_s4:  # FIX BUG removeChild (DEFINITIVO)
                ubicacion_in = st.text_input("Ubicación", value="Almacén general", key="si_ubicacion")  # FIX BUG removeChild (DEFINITIVO)
            with col_s5:  # FIX BUG removeChild (DEFINITIVO)
                estado_in = st.selectbox("Estado", ["Disponible", "Bloqueado", "Vencido", "Rechazado", "Cuarentena"], key="si_estado")  # FIX BUG removeChild (DEFINITIVO)
            lote_in = st.text_input("Código de lote (opcional, se genera uno si lo dejas vacío)", value="", key="si_lote")  # FIX BUG removeChild (DEFINITIVO)
            enviado_si = st.form_submit_button("✅ Registrar saldo inicial")  # FIX BUG removeChild (DEFINITIVO)
            if enviado_si:  # FIX BUG removeChild (DEFINITIVO)
                if not insumo_in or stock_in <= 0:  # FIX BUG removeChild (DEFINITIVO)
                    st.error("Indica el nombre del insumo/producto y un stock mayor a 0.")  # FIX BUG removeChild (DEFINITIVO)
                else:  # FIX BUG removeChild (DEFINITIVO)
                    lote_final = lote_in.strip() if lote_in.strip() else f"L-{re.sub(r'[^A-Za-z0-9]', '', insumo_in).upper()[:10]}-{today().strftime('%Y%m%d%H%M%S')}"  # FIX BUG removeChild (DEFINITIVO)
                    nueva_fila_inv = pd.DataFrame([[insumo_in, unidad_in, stock_in, costo_in, lote_final, fecha_ingreso_in, fecha_venc_in, ubicacion_in, estado_in, "Saldo inicial"]], columns=["Insumo", "Unidad", "Stock_lote", "Costo_unitario", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Ubicacion", "Estado", "Origen"])  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory = pd.concat([st.session_state.inventory, nueva_fila_inv], ignore_index=True)  # FIX BUG removeChild (DEFINITIVO)
                    st.success(f"Saldo inicial registrado: {insumo_in} — {stock_in:.3f} {unidad_in} (lote {lote_final}).")  # FIX BUG removeChild (DEFINITIVO)
                    st.rerun()  # FIX BUG removeChild (DEFINITIVO)

        st.markdown("---")  # FIX BUG removeChild (DEFINITIVO)
        st.subheader("✏️ Corregir o actualizar un lote existente")  # FIX BUG removeChild (DEFINITIVO)
        inv_si_actual = coerce_date_columns(st.session_state.inventory, ["Fecha_ingreso", "Fecha_vencimiento"]).reset_index(drop=True)  # FIX BUG removeChild (DEFINITIVO)
        if inv_si_actual.empty:  # FIX BUG removeChild (DEFINITIVO)
            st.info("Aún no hay lotes registrados.")  # FIX BUG removeChild (DEFINITIVO)
        else:  # FIX BUG removeChild (DEFINITIVO)
            lote_a_editar = st.selectbox("Selecciona el lote a corregir", inv_si_actual["Lote"].astype(str).tolist(), key="si_select_lote_editar")  # FIX BUG removeChild (DEFINITIVO)
            fila_lote = inv_si_actual[inv_si_actual["Lote"].astype(str).eq(lote_a_editar)].iloc[0]  # FIX BUG removeChild (DEFINITIVO)
            with st.form(key="form_editar_saldo_inicial"):  # FIX BUG removeChild (DEFINITIVO)
                col_se1, col_se2, col_se3 = st.columns(3)  # FIX BUG removeChild (DEFINITIVO)
                with col_se1:  # FIX BUG removeChild (DEFINITIVO)
                    stock_edit = st.number_input("Stock del lote", min_value=0.0, step=0.01, value=safe_float(fila_lote["Stock_lote"]), key="si_edit_stock")  # FIX BUG removeChild (DEFINITIVO)
                    costo_edit = st.number_input("Costo unitario (S/)", min_value=0.0, step=0.01, value=safe_float(fila_lote["Costo_unitario"]), key="si_edit_costo")  # FIX BUG removeChild (DEFINITIVO)
                with col_se2:  # FIX BUG removeChild (DEFINITIVO)
                    fecha_ingreso_edit = st.date_input("Fecha de ingreso", value=fila_lote["Fecha_ingreso"] if pd.notna(fila_lote["Fecha_ingreso"]) else today(), key="si_edit_fecha_ingreso")  # FIX BUG removeChild (DEFINITIVO)
                    fecha_venc_edit = st.date_input("Fecha de vencimiento", value=fila_lote["Fecha_vencimiento"] if pd.notna(fila_lote["Fecha_vencimiento"]) else today(), key="si_edit_fecha_venc")  # FIX BUG removeChild (DEFINITIVO)
                with col_se3:  # FIX BUG removeChild (DEFINITIVO)
                    opciones_estado_si = ["Disponible", "Bloqueado", "Vencido", "Rechazado", "Cuarentena"]  # FIX BUG removeChild (DEFINITIVO)
                    idx_estado_si = opciones_estado_si.index(fila_lote["Estado"]) if fila_lote["Estado"] in opciones_estado_si else 0  # FIX BUG removeChild (DEFINITIVO)
                    estado_edit = st.selectbox("Estado", opciones_estado_si, index=idx_estado_si, key="si_edit_estado")  # FIX BUG removeChild (DEFINITIVO)
                    ubicacion_edit = st.text_input("Ubicación", value=str(fila_lote.get("Ubicacion", "")), key="si_edit_ubicacion")  # FIX BUG removeChild (DEFINITIVO)
                col_btn_si1, col_btn_si2 = st.columns(2)  # FIX BUG removeChild (DEFINITIVO)
                with col_btn_si1:  # FIX BUG removeChild (DEFINITIVO)
                    guardar_si = st.form_submit_button("💾 Guardar cambios")  # FIX BUG removeChild (DEFINITIVO)
                with col_btn_si2:  # FIX BUG removeChild (DEFINITIVO)
                    eliminar_si = st.form_submit_button("🗑️ Eliminar lote")  # FIX BUG removeChild (DEFINITIVO)
                if guardar_si:  # FIX BUG removeChild (DEFINITIVO)
                    mask_si = st.session_state.inventory["Lote"].astype(str).eq(lote_a_editar)  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory.loc[mask_si, "Stock_lote"] = stock_edit  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory.loc[mask_si, "Costo_unitario"] = costo_edit  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory.loc[mask_si, "Fecha_ingreso"] = fecha_ingreso_edit  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory.loc[mask_si, "Fecha_vencimiento"] = fecha_venc_edit  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory.loc[mask_si, "Estado"] = estado_edit  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory.loc[mask_si, "Ubicacion"] = ubicacion_edit  # FIX BUG removeChild (DEFINITIVO)
                    st.success(f"Lote {lote_a_editar} actualizado.")  # FIX BUG removeChild (DEFINITIVO)
                    st.rerun()  # FIX BUG removeChild (DEFINITIVO)
                if eliminar_si:  # FIX BUG removeChild (DEFINITIVO)
                    st.session_state.inventory = st.session_state.inventory[~st.session_state.inventory["Lote"].astype(str).eq(lote_a_editar)].reset_index(drop=True)  # FIX BUG removeChild (DEFINITIVO)
                    st.success(f"Lote {lote_a_editar} eliminado.")  # FIX BUG removeChild (DEFINITIVO)
                    st.rerun()  # FIX BUG removeChild (DEFINITIVO)

        st.markdown("---")  # FIX BUG removeChild (DEFINITIVO)
        st.subheader("📋 Lotes de saldo inicial registrados")  # FIX BUG removeChild (DEFINITIVO)
        st.dataframe(inv_si_actual, use_container_width=True)  # FIX BUG removeChild (DEFINITIVO) - solo lectura, no dispara removeChild
    with subtab2:
        st.session_state.acquisitions = st.data_editor(coerce_date_columns(st.session_state.acquisitions, ["Fecha", "Fecha_vencimiento"]), num_rows="dynamic", use_container_width=True, key="acquisitions_editor", column_config={"Fecha": st.column_config.DateColumn("Fecha"), "Fecha_vencimiento": st.column_config.DateColumn("Fecha vencimiento"), "Tipo_documento": st.column_config.SelectboxColumn("Tipo documento", options=["Factura", "Boleta", "Guía remitente", "Guía transportista", "Liquidación de compra", "Nota de crédito", "Nota de débito", "Orden de compra", "Orden de venta", "Otro"]), "Cantidad_documento": st.column_config.NumberColumn("Cantidad documento", min_value=0.0, step=0.01), "Cantidad_aceptada": st.column_config.NumberColumn("Cantidad aceptada", min_value=0.0, step=0.01), "Cantidad_rechazada": st.column_config.NumberColumn("Cantidad rechazada", min_value=0.0, step=0.01), "Costo_unitario": st.column_config.NumberColumn("Costo unitario", min_value=0.0, step=0.01, format="S/ %.2f"), "Estado_documentario": st.column_config.SelectboxColumn("Estado", options=["Aceptado", "Aceptado parcial", "Pendiente revisión", "Observado", "Anulado"])})
        acq = st.session_state.acquisitions.copy()
        if not acq.empty:
            for c in ["Cantidad_documento", "Cantidad_aceptada", "Cantidad_rechazada", "Costo_unitario"]:
                acq[c] = coerce_num_series(acq[c])
            acq["Valor_aceptado"] = acq["Cantidad_aceptada"] * acq["Costo_unitario"]
            acq["Diferencia_doc_vs_almacen"] = acq["Cantidad_documento"] - acq["Cantidad_aceptada"] - acq["Cantidad_rechazada"]
            acq["Semaforo_documentario"] = np.where(acq["Diferencia_doc_vs_almacen"].abs() > 0.001, "🔴 Revisar diferencia", np.where(acq["Cantidad_rechazada"] > 0, "🟡 Nota crédito / reclamo", "🟢 Cuadrado"))
            st.dataframe(acq.style.map(style_status, subset=["Semaforo_documentario"]), use_container_width=True)
    with subtab3:
        inv_op = available_inventory()
        inv_op["Valor_lote"] = inv_op["Stock_lote"] * inv_op["Costo_unitario"]
        inv_op["Dias_vencimiento"] = (pd.to_datetime(inv_op["Fecha_vencimiento"], errors="coerce") - pd.Timestamp(today())).dt.days
        inv_op["Alerta_vencimiento"] = inv_op["Dias_vencimiento"].apply(exp_status)
        c1, c2, c3 = st.columns(3)
        with c1: kpi("Valor operativo almacén", money(inv_op["Valor_lote"].sum()), "Incluye adquisiciones aceptadas")
        with c2: kpi("Lotes disponibles", f"{(inv_op['Estado'].astype(str) == 'Disponible').sum()}", "Control por lote")
        with c3: kpi("Próximos a vencer", f"{inv_op['Alerta_vencimiento'].astype(str).str.contains('🔴|🟡', regex=True).sum()}", "Vencimiento ≤ 15 días")
        st.dataframe(inv_op.style.map(style_status, subset=["Alerta_vencimiento"]), use_container_width=True)
    with subtab4:  # CATEGORÍA AVANZADA - separación MP / Suministros / Auxiliares / Semielaborado / Terminado
        st.markdown("""
        <div class="section-note">
        <b>Clasificación automática del almacén</b> en 5 categorías contables:
        <b>Materia Prima</b> (insumo base sin receta propia), <b>Producto en Proceso/Semielaborado</b> (tiene receta propia
        Y se usa como insumo de otra receta — ej. Masa quebrada, Masa de empanada, Base blanca de helados),
        <b>Producto Terminado</b> (tiene receta propia y no se usa como insumo de otra receta — ej. Pie de queso),
        <b>Materiales Auxiliares</b> (empaque/embalaje) y <b>Suministros</b> (insumos no alimentarios).
        Puedes corregir manualmente la categoría de cualquier insumo en la tabla de abajo.
        </div>
        """, unsafe_allow_html=True)  # CATEGORÍA AVANZADA

        inv_cat = available_inventory()  # CATEGORÍA AVANZADA
        if not st.session_state.categoria_overrides.empty:  # MÓDULO CATEGORÍA ALMACÉN - aplica correcciones manuales sobre la clasificación automática
            overrides_map = st.session_state.categoria_overrides.drop_duplicates(subset=["Insumo"], keep="last").set_index("Insumo")["Categoria"].to_dict()  # MÓDULO CATEGORÍA ALMACÉN
            inv_cat["Categoria"] = inv_cat.apply(lambda r: overrides_map.get(r["Insumo"], r["Categoria"]), axis=1)  # MÓDULO CATEGORÍA ALMACÉN
        inv_cat["Valor_lote"] = inv_cat["Stock_lote"] * inv_cat["Costo_unitario"]  # MÓDULO CATEGORÍA ALMACÉN

        categorias_almacen = ["Materia Prima", "Producto en Proceso/Semielaborado", "Producto Terminado", "Materiales Auxiliares", "Suministros"]  # CATEGORÍA AVANZADA
        cols_cat = st.columns(5)  # CATEGORÍA AVANZADA
        for col_widget, categoria_nombre in zip(cols_cat, categorias_almacen):  # CATEGORÍA AVANZADA
            with col_widget:  # MÓDULO CATEGORÍA ALMACÉN
                subset_cat = inv_cat[inv_cat["Categoria"].eq(categoria_nombre)]  # MÓDULO CATEGORÍA ALMACÉN
                kpi(categoria_nombre, money(subset_cat["Valor_lote"].sum()), f"{subset_cat['Insumo'].nunique()} insumos")  # CATEGORÍA AVANZADA

        tab_mp, tab_proc, tab_term, tab_aux, tab_sum = st.tabs(["📦 Materia Prima", "⚙️ En Proceso/Semielaborado", "🍰 Producto Terminado", "🏷️ Materiales Auxiliares", "🧴 Suministros"])  # CATEGORÍA AVANZADA
        with tab_mp:  # MÓDULO CATEGORÍA ALMACÉN
            st.dataframe(inv_cat[inv_cat["Categoria"].eq("Materia Prima")].drop(columns=["Categoria"]), use_container_width=True)  # MÓDULO CATEGORÍA ALMACÉN
        with tab_proc:  # CATEGORÍA AVANZADA
            st.caption("Almacén automático de descarga: aquí se acumula el stock de producción intermedia (masas, bases) lista para usarse en otras recetas.")  # CATEGORÍA AVANZADA
            st.dataframe(inv_cat[inv_cat["Categoria"].eq("Producto en Proceso/Semielaborado")].drop(columns=["Categoria"]), use_container_width=True)  # CATEGORÍA AVANZADA
        with tab_term:  # CATEGORÍA AVANZADA
            st.dataframe(inv_cat[inv_cat["Categoria"].eq("Producto Terminado")].drop(columns=["Categoria"]), use_container_width=True)  # CATEGORÍA AVANZADA
        with tab_aux:  # MÓDULO CATEGORÍA ALMACÉN
            st.dataframe(inv_cat[inv_cat["Categoria"].eq("Materiales Auxiliares")].drop(columns=["Categoria"]), use_container_width=True)  # MÓDULO CATEGORÍA ALMACÉN
        with tab_sum:  # MÓDULO CATEGORÍA ALMACÉN
            st.dataframe(inv_cat[inv_cat["Categoria"].eq("Suministros")].drop(columns=["Categoria"]), use_container_width=True)  # MÓDULO CATEGORÍA ALMACÉN

        st.subheader("Corregir categoría de un insumo")  # MÓDULO CATEGORÍA ALMACÉN
        st.caption("La clasificación automática puede equivocarse en casos ambiguos. Agrega aquí la corrección manual; se aplicará a todos los lotes de ese insumo.")  # MÓDULO CATEGORÍA ALMACÉN
        st.session_state.categoria_overrides = st.data_editor(  # MÓDULO CATEGORÍA ALMACÉN
            st.session_state.categoria_overrides,  # MÓDULO CATEGORÍA ALMACÉN
            num_rows="dynamic",  # MÓDULO CATEGORÍA ALMACÉN
            use_container_width=True,  # MÓDULO CATEGORÍA ALMACÉN
            key="categoria_overrides_editor",  # MÓDULO CATEGORÍA ALMACÉN
            column_config={  # MÓDULO CATEGORÍA ALMACÉN
                "Insumo": st.column_config.SelectboxColumn("Insumo", options=sorted(inv_cat["Insumo"].dropna().unique().tolist())),  # MÓDULO CATEGORÍA ALMACÉN
                "Categoria": st.column_config.SelectboxColumn("Categoría corregida", options=categorias_almacen),  # CATEGORÍA AVANZADA
            },  # MÓDULO CATEGORÍA ALMACÉN
        )  # MÓDULO CATEGORÍA ALMACÉN

with tabs[9]:
    st.header("9. Control de producción")
    lean_badge("Optimización Six Sigma", "purple")
    if st.button("Generar control de producción desde OP actuales"):
        st.session_state.production_control = production_control_from_ops(ops)
        st.rerun()
    pc = st.session_state.production_control.copy()
    if not pc.empty:
        pc["Cantidad Programada"] = coerce_num_series(pc["Cantidad Programada"])
        pc["Cantidad Real"] = coerce_num_series(pc["Cantidad Real"])
        pc["Diferencia"] = pc["Cantidad Real"] - pc["Cantidad Programada"]
        pc["Rendimiento_%"] = np.where(pc["Cantidad Programada"] > 0, pc["Cantidad Real"] / pc["Cantidad Programada"] * 100, 0)
    st.session_state.production_control = st.data_editor(pc, num_rows="dynamic", use_container_width=True, key="production_editor", column_config={"Cantidad Programada": st.column_config.NumberColumn("Cantidad Programada", min_value=0.0, step=1.0), "Cantidad Real": st.column_config.NumberColumn("Cantidad Real", min_value=0.0, step=1.0), "Diferencia": st.column_config.NumberColumn("Diferencia", disabled=True), "Rendimiento_%": st.column_config.NumberColumn("Rendimiento %", disabled=True, format="%.2f")})

    st.markdown("---")  # CATEGORÍA AVANZADA
    st.subheader("Descarga automática a almacén")  # CATEGORÍA AVANZADA
    lean_badge("Producto en Proceso/Semielaborado → almacén disponible para otras recetas", "blue")  # CATEGORÍA AVANZADA
    st.markdown("""
    <div class="section-note">
    Al confirmar este paso, la <b>Cantidad Real</b> producida de cada OP cuyo producto sea
    <b>Semielaborado</b> (ej. Masa quebrada, Masa de empanada, Base blanca de helados) o <b>Producto Terminado</b>
    se registra como un lote nuevo en el almacén operativo, costeado según el costo unitario calculado por receta+OP.
    Así queda disponible automáticamente para ser consumido por otras recetas (caso semielaborado) o vendido (caso terminado).
    </div>
    """, unsafe_allow_html=True)  # CATEGORÍA AVANZADA
    if st.button("📥 Ingresar producción terminada/semielaborada a almacén", key="btn_ingresar_produccion_almacen"):  # CATEGORÍA AVANZADA
        inv_nuevo, log_ingreso = ingresar_produccion_a_almacen(st.session_state.production_control, recipes, costs, st.session_state.inventory)  # CATEGORÍA AVANZADA
        if log_ingreso.empty:  # CATEGORÍA AVANZADA
            st.warning("No hay producción con Cantidad Real > 0 de productos Semielaborados o Terminados para ingresar a almacén.")  # CATEGORÍA AVANZADA
        else:  # CATEGORÍA AVANZADA
            st.session_state.inventory = inv_nuevo  # CATEGORÍA AVANZADA
            st.session_state.produccion_almacen_log = pd.concat([st.session_state.produccion_almacen_log, log_ingreso], ignore_index=True)  # CATEGORÍA AVANZADA
            st.success(f"{len(log_ingreso)} lote(s) nuevo(s) ingresado(s) a almacén. Revísalos en '8. Inventario y adquisiciones → Almacén por categoría'.")  # CATEGORÍA AVANZADA
            st.rerun()  # CATEGORÍA AVANZADA
    st.subheader("Histórico de ingresos de producción a almacén")  # CATEGORÍA AVANZADA
    st.dataframe(st.session_state.produccion_almacen_log, use_container_width=True)  # CATEGORÍA AVANZADA

with tabs[10]:
    st.header("10. Mermas reales")
    lean_badge("Optimización Six Sigma", "purple")
    st.session_state.physical_count = st.data_editor(st.session_state.physical_count, num_rows="dynamic", use_container_width=True, key="physical_editor", column_config={"Stock_teorico": st.column_config.NumberColumn("Stock teórico", min_value=0.0, step=0.01, format="%.3f"), "Stock_fisico": st.column_config.NumberColumn("Stock físico", min_value=0.0, step=0.01, format="%.3f")})
    mermas = compute_mermas(st.session_state.physical_count, inv_current)
    st.dataframe(mermas.style.map(style_status, subset=["Estado"]), use_container_width=True)
    c1, c2, c3 = st.columns(3)
    with c1: kpi("Valor merma", money(mermas["Valor_merma"].sum() if not mermas.empty else 0), "Impacto económico")
    with c2: kpi("Insumos con merma", f"{(mermas['Merma_real'] > 0).sum() if not mermas.empty else 0}", "Diferencias físicas")
    with c3: kpi("Merma promedio", f"{mermas['Merma_%'].mean() if not mermas.empty else 0:.2f}%", "Sobre stock teórico")

with tabs[11]:
    st.header("11. Trazabilidad completa")
    lean_badge("Pedido → OP → Picking → Producción → Inventario → Costos → Rentabilidad", "dark")
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - trazabilidad incluye OP con nuevo formato de clave
    st.caption("Las claves de OP usan el formato: OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO]")  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    codigos_pedidos = st.session_state.store_orders["Código Pedido"].astype(str).unique().tolist() if "Código Pedido" in st.session_state.store_orders.columns else []
    codigos_ops = ops["OP"].astype(str).unique().tolist() if not ops.empty else []
    codigos_ops_tienda = ops_tienda["OP"].astype(str).unique().tolist() if not ops_tienda.empty else []  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    opciones_trazabilidad = [""] + codigos_pedidos + codigos_ops + codigos_ops_tienda  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    codigo_busqueda = st.selectbox("Selecciona o ingresa código de Pedido / OP", opciones_trazabilidad, key="trace_select")
    codigo_manual = st.text_input("Código manual de Pedido u OP", value=codigo_busqueda, key="trace_manual")
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - trazabilidad unifica ops globales y ops_tienda para búsqueda
    ops_unificadas = pd.concat([ops, ops_tienda.rename(columns={"Cantidad": "Cantidad", "Fecha_OP": "Fecha requerida", "Estado OP": "Estado OP"})], ignore_index=True).drop_duplicates(subset=["OP"])  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    trazabilidad = build_traceability(codigo_manual, st.session_state.store_orders, ops_unificadas, picking, st.session_state.dispatched_log, st.session_state.production_control, inv_current, costs)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    if not codigo_manual:
        st.info("Ingresa un código de pedido como PED-0001 o una OP como OP-SURCO-GALLEPECA-20250101-001.")
    elif not trazabilidad["found"]:
        st.error("No se encontró trazabilidad para el código ingresado.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1: kpi("Pedido(s)", str(trazabilidad["pedido"]), "Origen tienda")
        with c2: kpi("OP", str(trazabilidad["op"]), "Producción centralizada")
        with c3: kpi("Producto", str(trazabilidad["producto"]), "Producto trazado")
        st.subheader("Línea de tiempo operativa")
        for title, detail, status in trazabilidad["timeline"]:
            timeline_step(title, detail, status)
        st.subheader("Detalle Picking de Insumos")
        st.dataframe(trazabilidad["picking"], use_container_width=True)
        st.subheader("Despachos registrados")
        st.dataframe(trazabilidad["despachos"], use_container_width=True)
        st.subheader("Control de producción")
        st.dataframe(trazabilidad["produccion"], use_container_width=True)
        st.subheader("Costos y rentabilidad")
        st.dataframe(trazabilidad["costos"], use_container_width=True)

with tabs[12]:
    st.header("12. Reporte integral y guion para video demo")
    lean_badge("Filosofía Lean & Six Sigma", "dark")
    all_purchase = pd.concat([purchase_auto, st.session_state.purchase_requests_manual], ignore_index=True)
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - reporte incluye OP por tienda y explosión por OP tienda
    explosion_tienda_reporte = explode_recipes_por_op_tienda(ops_tienda, recipes, inv_current)  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
    rentabilidad_pos_reporte = rentabilidad_real_vs_op(st.session_state.pos_ventas, costs)  # MÓDULO VENTAS POS
    stock_pt_reporte = descontar_stock_por_ventas(st.session_state.pos_ventas, st.session_state.production_control)  # MÓDULO VENTAS POS
    report = {
        "Pedidos_Tienda": st.session_state.store_orders,
        "Consolidacion": consolidated,
        "Ordenes_Produccion": ops,
        "OP_Por_Tienda": ops_tienda,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        "Explosion_OP_Tienda": explosion_tienda_reporte,  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        "Recetas": st.session_state.recipes,
        "Explosion_Recetas": requirements,
        "Semaforo_Stock": summary,
        "Solicitudes_Compra": all_purchase,
        "Picking_PEPS_FIFO": picking,
        "Inventario_Operativo": inv_current,
        "Adquisiciones": st.session_state.acquisitions,
        "Despachos": st.session_state.dispatched_log,
        "Control_Produccion": st.session_state.production_control,
        "Mermas": mermas,
        "Costos": costs,
        "Alertas_Despacho": st.session_state.dispatch_alerts,
        "Ventas_POS": st.session_state.pos_ventas,  # MÓDULO VENTAS POS
        "Stock_Producto_Terminado": stock_pt_reporte,  # MÓDULO VENTAS POS
        "Rentabilidad_Real_vs_OP": rentabilidad_pos_reporte,  # MÓDULO VENTAS POS
    }
    st.download_button("📥 Descargar Excel integral del sistema", data=excel_download(report), file_name=f"ERP_Pasteleria_Industrial_PRO_{today_str()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.subheader("Filosofía Lean & Six Sigma")
    lean_route_panel()
    # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA - pasos de demo actualizados con nueva pestaña 2B / MÓDULO VENTAS POS - paso 13 agregado
    demo_steps = pd.DataFrame([
        [1, "Pedidos por tienda", "Mostrar cómo Surco, Miraflores y San Isidro cargan pedidos."],
        [2, "Consolidación", "Mostrar suma automática por producto."],
        [3, "2B. Generador OP por tienda", "Mostrar OP individuales con clave OP-[TIENDA]-[PRODUCTO]-[FECHA]-[CORRELATIVO], explosión y picking por OP."],  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        [4, "OP consolidadas", "Mostrar OP globales y semáforo liberado/faltante."],
        [5, "Recetas", "Mostrar explosión automática de insumos (incluye recetas del Excel)."],  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        [6, "Semáforo stock", "Mostrar necesita vs tiene."],
        [7, "Compras", "Mostrar solicitud automática."],
        [8, "Picking", "Seleccionar OP y mostrar PEPS/FIFO."],
        [9, "Descuento inventario", "Aplicar despacho y mostrar saldo actualizado."],
        [10, "Producción", "Registrar programado vs real."],
        [11, "Mermas", "Registrar conteo físico y valorizar diferencia."],
        [12, "Dashboard", "Cerrar con KPIs gerenciales y OP por tienda."],  # INTEGRACIÓN NUEVA LÓGICA DE OP POR TIENDA
        [13, "Ventas POS externo", "Cargar Excel de ventas, mostrar descuento de stock de producto terminado y rentabilidad real vs OP."],  # MÓDULO VENTAS POS
    ], columns=["Paso", "Pantalla", "Qué mostrar"])
    st.dataframe(demo_steps, use_container_width=True)

# MÓDULO VENTAS POS - pestaña 13: carga de Excel de ventas externas, descuento de stock y rentabilidad real
with tabs[13]:
    st.header("13. Ventas por POS externo")
    lean_badge("Carga Excel POS → Descuento stock producto terminado → Rentabilidad real vs OP", "dark")
    st.markdown("""
    <div class="section-note">
    Sube el archivo Excel exportado de tu sistema POS externo con las ventas realizadas. El sistema:
    <br>1) Normaliza columnas (Fecha, Tienda, Producto, Cantidad, Precio, Total).
    <br>2) Descuenta automáticamente el stock de <b>producto terminado</b> (Cantidad Real producida en OP − vendido acumulado).
    <br>3) Cruza la venta real contra el <b>costo unitario calculado desde la receta y la OP</b> para mostrar la rentabilidad real, no la teórica.
    </div>
    """, unsafe_allow_html=True)  # MÓDULO VENTAS POS

    pos_file = st.file_uploader("Cargar Excel de ventas POS", type=["xlsx", "xlsm", "xls"], key="pos_file_uploader")  # MÓDULO VENTAS POS
    pos_sheets = read_excel_sheets(pos_file)  # MÓDULO VENTAS POS

    if pos_sheets:  # MÓDULO VENTAS POS
        nombre_hoja_pos = st.selectbox("Selecciona la hoja con el detalle de ventas", list(pos_sheets.keys()), key="pos_sheet_select")  # MÓDULO VENTAS POS
        df_pos_preview = pos_sheets[nombre_hoja_pos]  # MÓDULO VENTAS POS
        st.caption("Vista previa del archivo cargado (primeras filas):")  # MÓDULO VENTAS POS
        st.dataframe(df_pos_preview.head(10), use_container_width=True)  # MÓDULO VENTAS POS
        df_pos_normalizado = normalize_pos_excel(df_pos_preview, pos_file.name if pos_file else nombre_hoja_pos)  # MÓDULO VENTAS POS
        st.caption(f"Filas normalizadas y listas para registrar: {len(df_pos_normalizado)}")  # MÓDULO VENTAS POS
        st.dataframe(df_pos_normalizado, use_container_width=True)  # MÓDULO VENTAS POS
        if st.button("✅ Registrar ventas en el sistema", key="btn_registrar_pos"):  # MÓDULO VENTAS POS
            if df_pos_normalizado.empty:  # MÓDULO VENTAS POS
                st.warning("No hay filas válidas para registrar. Verifica que el Excel tenga columna 'Producto' y 'Cantidad'.")  # MÓDULO VENTAS POS
            else:  # MÓDULO VENTAS POS
                st.session_state.pos_ventas = pd.concat([st.session_state.pos_ventas, df_pos_normalizado], ignore_index=True)  # MÓDULO VENTAS POS
                log_descuento = df_pos_normalizado[["Fecha", "Tienda", "Producto", "Cantidad_vendida"]].rename(columns={"Cantidad_vendida": "Cantidad_descontada"})  # MÓDULO VENTAS POS
                log_descuento["Origen"] = pos_file.name if pos_file else "POS Externo"  # MÓDULO VENTAS POS
                st.session_state.ventas_stock_log = pd.concat([st.session_state.ventas_stock_log, log_descuento], ignore_index=True)  # MÓDULO VENTAS POS
                st.success(f"{len(df_pos_normalizado)} ventas registradas. Stock de producto terminado actualizado.")  # MÓDULO VENTAS POS
                st.rerun()  # MÓDULO VENTAS POS
    else:  # MÓDULO VENTAS POS
        st.info("Carga un archivo Excel exportado del POS de tu tienda para iniciar el registro de ventas.")  # MÓDULO VENTAS POS

    st.markdown("---")  # MÓDULO VENTAS POS
    st.subheader("Histórico de ventas registradas")  # MÓDULO VENTAS POS
    st.dataframe(st.session_state.pos_ventas, use_container_width=True)  # MÓDULO VENTAS POS
    if not st.session_state.pos_ventas.empty and st.button("🗑️ Limpiar histórico de ventas POS", key="btn_clear_pos"):  # MÓDULO VENTAS POS
        st.session_state.pos_ventas = pd.DataFrame(columns=["Fecha", "Tienda", "Producto", "Cantidad_vendida", "Precio_unitario_venta", "Total_venta", "Canal", "Archivo_origen"])  # MÓDULO VENTAS POS
        st.session_state.ventas_stock_log = pd.DataFrame(columns=["Fecha", "Tienda", "Producto", "Cantidad_descontada", "Origen"])  # MÓDULO VENTAS POS
        st.rerun()  # MÓDULO VENTAS POS

    st.markdown("---")  # MÓDULO VENTAS POS
    st.subheader("Stock de producto terminado (Producido en OP − Vendido por POS)")  # MÓDULO VENTAS POS
    stock_pt = descontar_stock_por_ventas(st.session_state.pos_ventas, st.session_state.production_control)  # MÓDULO VENTAS POS
    if stock_pt.empty:  # MÓDULO VENTAS POS
        st.info("Aún no hay producción registrada (pestaña '9. Control producción') ni ventas cargadas para calcular el stock de producto terminado.")  # MÓDULO VENTAS POS
    else:  # MÓDULO VENTAS POS
        st.dataframe(stock_pt.style.map(style_status, subset=["Estado_stock_PT"]), use_container_width=True)  # MÓDULO VENTAS POS
        c_pt1, c_pt2, c_pt3 = st.columns(3)  # MÓDULO VENTAS POS
        with c_pt1: kpi("Productos con stock disponible", f"{(stock_pt['Estado_stock_PT'].astype(str).str.contains('🟢')).sum()}", "Listos para vender")  # MÓDULO VENTAS POS
        with c_pt2: kpi("Productos agotados", f"{(stock_pt['Estado_stock_PT'].astype(str).str.contains('🟡')).sum()}", "Producido = vendido")  # MÓDULO VENTAS POS
        with c_pt3: kpi("Productos en sobreventa", f"{(stock_pt['Estado_stock_PT'].astype(str).str.contains('🔴')).sum()}", "Se vendió más de lo producido en OP")  # MÓDULO VENTAS POS

    st.markdown("---")  # MÓDULO VENTAS POS
    st.subheader("Rentabilidad real: venta POS vs costo de producción (OP)")  # MÓDULO VENTAS POS
    lean_badge("Contabilidad Lean — margen real, no teórico", "purple")  # MÓDULO VENTAS POS
    rentabilidad_real = rentabilidad_real_vs_op(st.session_state.pos_ventas, costs)  # MÓDULO VENTAS POS
    if rentabilidad_real.empty:  # MÓDULO VENTAS POS
        st.info("Carga ventas POS y asegúrate de que existan costos calculados (pestaña '1. Dashboard gerencial' o '3. Consolidación y OP') para ver la rentabilidad real.")  # MÓDULO VENTAS POS
    else:  # MÓDULO VENTAS POS
        st.dataframe(rentabilidad_real.style.map(style_status, subset=["Estado_margen"]), use_container_width=True)  # MÓDULO VENTAS POS
        c_r1, c_r2, c_r3 = st.columns(3)  # MÓDULO VENTAS POS
        with c_r1: kpi("Venta total POS", money(rentabilidad_real["Total_venta"].sum()), "Acumulado de ventas cargadas")  # MÓDULO VENTAS POS
        with c_r2: kpi("Utilidad real total", money(rentabilidad_real["Utilidad_real"].sum()), "Venta real − costo de producción real")  # MÓDULO VENTAS POS
        with c_r3:
            margen_prom = safe_div(rentabilidad_real["Utilidad_real"].sum(), rentabilidad_real["Total_venta"].sum()) * 100  # MÓDULO VENTAS POS
            kpi("Margen real promedio", f"{margen_prom:.1f}%", "Sobre venta total POS")  # MÓDULO VENTAS POS
        if PLOTLY_OK:  # MÓDULO VENTAS POS
            fig_rent = px.bar(rentabilidad_real, x="Producto", y=["Total_venta", "Costo_total_estimado", "Utilidad_real"], barmode="group", title="Venta real vs costo de producción vs utilidad por producto")  # MÓDULO VENTAS POS
            st.plotly_chart(fig_rent, use_container_width=True)  # MÓDULO VENTAS POS

    st.markdown("---")  # MÓDULO VENTAS POS
    st.subheader("Log de descuentos de stock por venta")  # MÓDULO VENTAS POS
    st.dataframe(st.session_state.ventas_stock_log, use_container_width=True)  # MÓDULO VENTAS POS

    if not st.session_state.pos_ventas.empty:  # MÓDULO VENTAS POS
        reporte_pos = {  # MÓDULO VENTAS POS
            "Ventas_POS": st.session_state.pos_ventas,  # MÓDULO VENTAS POS
            "Stock_Producto_Terminado": stock_pt,  # MÓDULO VENTAS POS
            "Rentabilidad_Real_vs_OP": rentabilidad_real,  # MÓDULO VENTAS POS
        }  # MÓDULO VENTAS POS
        st.download_button(  # MÓDULO VENTAS POS
            "📥 Descargar Excel de Ventas POS y Rentabilidad",  # MÓDULO VENTAS POS
            data=excel_download(reporte_pos),  # MÓDULO VENTAS POS
            file_name=f"Ventas_POS_Rentabilidad_{today_str()}.xlsx",  # MÓDULO VENTAS POS
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # MÓDULO VENTAS POS
        )  # MÓDULO VENTAS POS


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
        tienda_login = st.selectbox("Tienda", list(TIENDAS_CREDENCIALES.keys()), key="login_tienda_select")
        password_login = st.text_input("Contraseña", type="password", key="login_password_input")
        if st.button("Ingresar al sistema", use_container_width=True):
            if password_login == TIENDAS_CREDENCIALES.get(tienda_login):
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
    ], columns=["Insumo", "Unidad", "Stock_lote", "Costo_unitario", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Ubicacion", "Estado", "Origen"])


def df_recipes_demo() -> pd.DataFrame:
    return pd.DataFrame([
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
    ], columns=["Insumo", "Proveedor sugerido", "Prioridad base"])


def df_physical_count_demo() -> pd.DataFrame:
    return pd.DataFrame([
        ["Huevos", "kg", 5.00, 4.00, "Conteo cierre producción", "Huevos rotos/no conformes"],
        ["Pecanas", "kg", 2.60, 2.40, "Conteo cierre producción", "Diferencia física menor"],
    ], columns=["Insumo", "Unidad", "Stock_teorico", "Stock_fisico", "Tipo_conteo", "Observación"])


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
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy()


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
    return inv


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


def generate_ops(consolidated: pd.DataFrame, requirements: pd.DataFrame, inv: pd.DataFrame) -> pd.DataFrame:
    if consolidated.empty:
        return pd.DataFrame(columns=["OP", "Producto", "Cantidad", "Estado OP", "Prioridad", "Fecha requerida"])
    rows = []
    for i, r in consolidated.reset_index(drop=True).iterrows():
        rows.append([f"OP-{i+1:03d}", r["Producto"], float(r["Cantidad Consolidada"]), op_status(r["Producto"], requirements, inv), r.get("Prioridad máxima", "Media"), r.get("Fecha requerida mínima", today())])
    return pd.DataFrame(rows, columns=["OP", "Producto", "Cantidad", "Estado OP", "Prioridad", "Fecha requerida"])


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


def fifo_picking(requirements: pd.DataFrame, inv: pd.DataFrame, ops: pd.DataFrame) -> pd.DataFrame:
    if requirements.empty:
        return pd.DataFrame(columns=["OP", "Producto", "Insumo", "Unidad", "Lote", "Fecha_ingreso", "Fecha_vencimiento", "Cantidad_a_entregar", "Costo_unitario", "Valor_salida", "Estado"])
    inv2 = inv.copy()
    inv2["Fecha_ingreso_dt"] = pd.to_datetime(inv2["Fecha_ingreso"], errors="coerce")
    inv2["Fecha_vencimiento_dt"] = pd.to_datetime(inv2["Fecha_vencimiento"], errors="coerce")
    inv2 = inv2[inv2["Estado"].astype(str).str.lower().eq("disponible")].sort_values(["Insumo", "Fecha_ingreso_dt", "Fecha_vencimiento_dt", "Lote"], na_position="last")
    req_prod = requirements.groupby(["Producto", "Insumo", "Unidad"], as_index=False)["Requerido_total"].sum()
    op_map = ops.set_index("Producto")["OP"].to_dict() if not ops.empty else {}
    rows = []
    for _, req in req_prod.iterrows():
        prod, ins, und = req["Producto"], req["Insumo"], req["Unidad"]
        need = float(req["Requerido_total"])
        op = op_map.get(prod, "OP-SIN")
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
        rows.append([r["OP"], r["Producto"], float(r["Cantidad"]), float(r["Cantidad"]), 0.0, 100.0, "Operario", ""])
    return pd.DataFrame(rows, columns=["OP", "Producto", "Cantidad Programada", "Cantidad Real", "Diferencia", "Rendimiento_%", "Responsable", "Observación"])


st.sidebar.title("⚙️ Parámetros")
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
    for key in ["inventory", "recipes", "store_orders", "acquisitions", "providers", "physical_count", "production_control", "dispatched_log", "purchase_requests_manual"]:
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

st.title("🥐 ERP Gastronómico Pastelería Industrial PRO")
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

tabs = st.tabs(["1. Dashboard gerencial", "2. Pedidos por tienda", "3. Consolidación y OP", "4. Recetas e insumos", "5. Semáforo stock", "6. Compras automáticas", "7. Picking PEPS/FIFO", "8. Inventario y adquisiciones", "9. Control producción", "10. Mermas reales", "11. Reporte y video demo"])

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
    st.subheader("Semáforo ejecutivo")
    st.dataframe(summary.style.map(style_status, subset=["Estado"]), use_container_width=True)
    c9, c10 = st.columns(2)
    with c9:
        st.subheader("Costo y rentabilidad")
        st.dataframe(costs, use_container_width=True)
    with c10:
        st.subheader("Compras automáticas")
        st.dataframe(purchase_auto, use_container_width=True)
    if PLOTLY_OK and not costs.empty:
        st.plotly_chart(px.bar(costs, x="Producto", y="Costo total", title="Costo total por producto"), use_container_width=True)
    st.subheader("Filosofía Lean & Six Sigma")
    lean_route_panel()

with tabs[1]:
    st.header("1. Pedidos por tienda")
    tienda_actual = st.session_state.tienda_actual
    st.success(f"Bienvenido, {tienda_actual}. En este módulo solo puedes registrar y ver pedidos de tu tienda.")
    pedidos_globales = coerce_date_columns(st.session_state.store_orders, ["Fecha Pedido", "Fecha Requerida"])
    pedidos_tienda = pedidos_globales[pedidos_globales["Tienda"].astype(str).eq(str(tienda_actual))].copy()
    pedidos_otras_tiendas = pedidos_globales[~pedidos_globales["Tienda"].astype(str).eq(str(tienda_actual))].copy()
    pedidos_editados = st.data_editor(
        pedidos_tienda,
        num_rows="dynamic",
        use_container_width=True,
        key=f"store_orders_editor_{tienda_actual}",
        column_config={
            "Fecha Pedido": st.column_config.DateColumn("Fecha Pedido"),
            "Fecha Requerida": st.column_config.DateColumn("Fecha Requerida"),
            "Tienda": st.column_config.SelectboxColumn("Tienda", options=[tienda_actual]),
            "Producto": st.column_config.SelectboxColumn("Producto", options=sorted(st.session_state.recipes["Producto"].dropna().unique().tolist())),
            "Cantidad Solicitada": st.column_config.NumberColumn("Cantidad Solicitada", min_value=0.0, step=1.0),
            "Prioridad": st.column_config.SelectboxColumn("Prioridad", options=["Alta", "Media", "Baja"]),
            "Estado": st.column_config.SelectboxColumn("Estado", options=["Pendiente", "Producción", "Entregado", "Anulado"]),
        },
    )
    if pedidos_editados is not None:
        pedidos_editados = pedidos_editados.copy()
        if "Tienda" in pedidos_editados.columns:
            pedidos_editados["Tienda"] = tienda_actual
        pedidos_editados = coerce_date_columns(pedidos_editados, ["Fecha Pedido", "Fecha Requerida"])
        st.session_state.store_orders = pd.concat([pedidos_otras_tiendas, pedidos_editados], ignore_index=True)
    if not pedidos_editados.empty:
        st.subheader(f"Vista consolidada de pedidos - {tienda_actual}")
        pivot = pedidos_editados.pivot_table(index="Tienda", columns="Producto", values="Cantidad Solicitada", aggfunc="sum", fill_value=0)
        st.dataframe(pivot, use_container_width=True)

with tabs[2]:
    st.header("2. Consolidación automática y 3. Generador de OP")
    lean_badge("Control Visual Andon / Jidoka", "red")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Consolidación")
        st.dataframe(consolidated, use_container_width=True)
    with c2:
        st.subheader("Órdenes de producción")
        st.dataframe(ops.style.map(style_status, subset=["Estado OP"]), use_container_width=True)

with tabs[3]:
    st.header("4. Explosión automática de recetas")
    lean_badge("Trabajo Estándar", "blue")
    st.session_state.recipes = st.data_editor(st.session_state.recipes, num_rows="dynamic", use_container_width=True, key="recipes_editor", column_config={"Rendimiento_lote": st.column_config.NumberColumn("Rendimiento lote", min_value=0.0001, step=1.0), "Cantidad_receta": st.column_config.NumberColumn("Cantidad receta", min_value=0.0, step=0.01, format="%.4f"), "Merma_tecnica_pct": st.column_config.NumberColumn("Merma técnica %", min_value=0.0, max_value=1.0, step=0.01, format="%.2f"), "Criticidad": st.column_config.SelectboxColumn("Criticidad", options=["Crítico", "Normal", "Bajo"])})
    st.subheader("Explosión calculada")
    st.dataframe(requirements, use_container_width=True)

with tabs[4]:
    st.header("5. Semáforo de disponibilidad de insumos")
    lean_badge("Control Visual Andon / Jidoka", "red")
    st.dataframe(summary.style.map(style_status, subset=["Estado"]), use_container_width=True)
    for _, r in summary.iterrows():
        if r["Faltante"] > 0:
            st.error(f"Falta comprar {r['Faltante']:.3f} {r['Unidad']} de {r['Insumo']}. Necesita {r['Necesita']:.3f}; tiene {r['Tiene']:.3f}.")
        elif "🟡" in str(r["Estado"]):
            st.warning(f"{r['Insumo']} está justo: tiene {r['Tiene']:.3f} {r['Unidad']} para requerimiento de {r['Necesita']:.3f}.")
        else:
            st.success(f"{r['Insumo']}: stock suficiente.")

with tabs[5]:
    st.header("6. Compras automáticas")
    lean_badge("Sistema Kanban / Just In Time", "green")
    st.subheader("Proveedores sugeridos")
    st.session_state.providers = st.data_editor(st.session_state.providers, num_rows="dynamic", use_container_width=True, key="providers_editor", column_config={"Prioridad base": st.column_config.SelectboxColumn("Prioridad base", options=["Alta", "Media", "Baja"])})
    st.subheader("Solicitudes automáticas")
    st.dataframe(purchase_auto, use_container_width=True)
    st.subheader("Solicitudes manuales adicionales")
    st.session_state.purchase_requests_manual = st.data_editor(coerce_date_columns(st.session_state.purchase_requests_manual, ["Fecha"]), num_rows="dynamic", use_container_width=True, key="purchase_manual_editor", column_config={"Fecha": st.column_config.DateColumn("Fecha"), "Cantidad faltante": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.01), "Prioridad": st.column_config.SelectboxColumn("Prioridad", options=["Alta", "Media", "Baja"]), "Estado": st.column_config.SelectboxColumn("Estado", options=["Pendiente", "Cotizado", "Comprado", "Anulado"])})
    st.subheader("Bandeja total de compras")
    st.dataframe(pd.concat([purchase_auto, st.session_state.purchase_requests_manual], ignore_index=True), use_container_width=True)

with tabs[6]:
    st.header("7. Picking inteligente PEPS/FIFO y descuento automático")
    lean_badge("Enfoque 5S / Trabajo Estándar", "blue")
    if ops.empty:
        st.info("No hay OP generadas.")
    else:
        selected_op = st.selectbox("Selecciona OP", ops["OP"].tolist())
        pick_op = picking[picking["OP"] == selected_op].copy()
        st.subheader(f"Hoja de picking - {selected_op}")
        st.dataframe(pick_op.style.map(style_status, subset=["Estado"]), use_container_width=True)
        responsable = st.text_input("Responsable almacén", "Almacenero")
        disabled_dispatch = pick_op["Estado"].astype(str).str.contains("🔴").any()
        if st.button("✅ Despachar OP y descontar inventario", disabled=disabled_dispatch):
            new_inv, log_df, msg = dispatch_inventory(st.session_state.inventory, pick_op, selected_op, responsable)
            if not log_df.empty:
                st.session_state.inventory = new_inv
                st.session_state.dispatched_log = pd.concat([st.session_state.dispatched_log, log_df], ignore_index=True)
                st.success(msg)
                st.rerun()
            else:
                st.warning(msg)
        if disabled_dispatch:
            st.error("No se puede despachar: existen faltantes.")
        st.subheader("Histórico de despachos")
        st.dataframe(st.session_state.dispatched_log, use_container_width=True)

with tabs[7]:
    st.header("8. Inventario, saldo inicial y adquisiciones")
    lean_badge("Enfoque 5S / Trabajo Estándar", "blue")
    subtab1, subtab2, subtab3 = st.tabs(["Saldo inicial / lotes", "Adquisiciones documentarias", "Inventario operativo valorizado"])
    with subtab1:
        st.session_state.inventory = st.data_editor(coerce_date_columns(st.session_state.inventory, ["Fecha_ingreso", "Fecha_vencimiento"]), num_rows="dynamic", use_container_width=True, key="inventory_editor", column_config={"Fecha_ingreso": st.column_config.DateColumn("Fecha ingreso"), "Fecha_vencimiento": st.column_config.DateColumn("Fecha vencimiento"), "Stock_lote": st.column_config.NumberColumn("Stock lote", min_value=0.0, step=0.01, format="%.3f"), "Costo_unitario": st.column_config.NumberColumn("Costo unitario", min_value=0.0, step=0.01, format="S/ %.2f"), "Estado": st.column_config.SelectboxColumn("Estado", options=["Disponible", "Bloqueado", "Vencido", "Rechazado", "Cuarentena"])})
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

with tabs[8]:
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

with tabs[9]:
    st.header("10. Mermas reales")
    lean_badge("Optimización Six Sigma", "purple")
    st.session_state.physical_count = st.data_editor(st.session_state.physical_count, num_rows="dynamic", use_container_width=True, key="physical_editor", column_config={"Stock_teorico": st.column_config.NumberColumn("Stock teórico", min_value=0.0, step=0.01, format="%.3f"), "Stock_fisico": st.column_config.NumberColumn("Stock físico", min_value=0.0, step=0.01, format="%.3f")})
    mermas = compute_mermas(st.session_state.physical_count, inv_current)
    st.dataframe(mermas.style.map(style_status, subset=["Estado"]), use_container_width=True)
    c1, c2, c3 = st.columns(3)
    with c1: kpi("Valor merma", money(mermas["Valor_merma"].sum() if not mermas.empty else 0), "Impacto económico")
    with c2: kpi("Insumos con merma", f"{(mermas['Merma_real'] > 0).sum() if not mermas.empty else 0}", "Diferencias físicas")
    with c3: kpi("Merma promedio", f"{mermas['Merma_%'].mean() if not mermas.empty else 0:.2f}%", "Sobre stock teórico")

with tabs[10]:
    st.header("11. Reporte integral y guion para video demo")
    lean_badge("Filosofía Lean & Six Sigma", "dark")
    all_purchase = pd.concat([purchase_auto, st.session_state.purchase_requests_manual], ignore_index=True)
    report = {"Pedidos_Tienda": st.session_state.store_orders, "Consolidacion": consolidated, "Ordenes_Produccion": ops, "Recetas": st.session_state.recipes, "Explosion_Recetas": requirements, "Semaforo_Stock": summary, "Solicitudes_Compra": all_purchase, "Picking_PEPS_FIFO": picking, "Inventario_Operativo": inv_current, "Adquisiciones": st.session_state.acquisitions, "Despachos": st.session_state.dispatched_log, "Control_Produccion": st.session_state.production_control, "Mermas": mermas, "Costos": costs}
    st.download_button("📥 Descargar Excel integral del sistema", data=excel_download(report), file_name=f"ERP_Pasteleria_Industrial_PRO_{today_str()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.subheader("Filosofía Lean & Six Sigma")
    lean_route_panel()
    demo_steps = pd.DataFrame([[1, "Pedidos por tienda", "Mostrar cómo Surco, Miraflores y San Isidro cargan pedidos."], [2, "Consolidación", "Mostrar suma automática por producto."], [3, "OP", "Mostrar OP y semáforo liberado/faltante."], [4, "Recetas", "Mostrar explosión automática de insumos."], [5, "Semáforo stock", "Mostrar necesita vs tiene."], [6, "Compras", "Mostrar solicitud automática."], [7, "Picking", "Seleccionar OP y mostrar PEPS/FIFO."], [8, "Descuento inventario", "Aplicar despacho y mostrar saldo actualizado."], [9, "Producción", "Registrar programado vs real."], [10, "Mermas", "Registrar conteo físico y valorizar diferencia."], [11, "Dashboard", "Cerrar con KPIs gerenciales."]], columns=["Paso", "Pantalla", "Qué mostrar"])
    st.dataframe(demo_steps, use_container_width=True)

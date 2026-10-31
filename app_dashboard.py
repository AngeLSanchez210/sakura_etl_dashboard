"""
Sakura Bookstore — Dashboard de Inteligencia de Negocios
========================================================

"""
import hashlib                           # para firmar el token de la sesión
import hmac                              # compara contraseñas de forma segura
import os                                # para leer variables del .env
import time                              # hora actual, para que la sesión expire
import pandas as pd                      # tablas de datos (DataFrame)
import plotly.express as px              # gráficas
import plotly.io as pio
import psycopg2                          # conexión a PostgreSQL
import streamlit as st                   # la página web del dashboard
from dotenv import load_dotenv           # lee el archivo .env
from pathlib import Path                 # para ubicar el archivo estilos.css

from etl import conectar_postgres, ejecutar_etl_completo   # importacion del etl.py

#Titulo de la pagina
st.set_page_config(page_title="Sakura Bookstore ST", layout="wide",
                   initial_sidebar_state="expanded")
pio.templates.default = "plotly_white"     


# ==============================================================================
# 1. COLORES Y ESTILO
# ==============================================================================
AZUL = "#1f2937"         # color principal: barra lateral, barras y líneas
NARANJA = "#0f9d8a"      # color de acento: lo que se quiere destacar
TINTA = "#111827"        # color del texto
FONDO = "#f3f4f6"        # fondo gris claro de la página
NEUTRO = "#d1d5db"       # barras que no se destacan
ESCALA = ["#e6f6f3", "#b8e6dd", "#7fd0c1", "#3fb3a0", "#0f9d8a", "#0b6e61"]   # escala de colores
VERDE, AMARILLO, ROJO = "#1b8a3a", "#d99100", "#c8322f"   # estado de clientes


#variables de  colores para utilizar en estilos.css
variables = f":root {{ --azul:{AZUL}; --naranja:{NARANJA}; --tinta:{TINTA}; --fondo:{FONDO}; }}"
estilos = (Path(__file__).parent / "estilos.css").read_text(encoding="utf-8")
lineas = [l.strip() for l in (variables + "\n" + estilos).splitlines() if l.strip()]   # sin líneas vacías
st.markdown("<style>\n" + "\n".join(lineas) + "\n</style>", unsafe_allow_html=True)


#conversion de los numeros decimles a float para graficar sin errores
DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values, "DEC2FLOAT",
    lambda valor, cursor: float(valor) if valor is not None else None)
psycopg2.extensions.register_type(DEC2FLOAT)


# ==============================================================================
# 2. Funciones generales
# ==============================================================================
@st.cache_data(ttl=600)                  # guarda el resultado 10 minutos para no repetir la consulta.
def consultar(sql, params=None):
    with conectar_postgres() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def grafica(fig, alto=360):
    fig.update_layout(
        height=alto,
        font=dict(family="Inter, sans-serif", size=13, color=TINTA), # estilo predifinido para todas las graficas
        title_font=dict(size=16),
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=10, r=20, t=55, b=10),
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False, automargin=True)               # sin líneas verticales
    fig.update_yaxes(gridcolor="#eef1f5", automargin=True)          # líneas horizontales suaves
    st.plotly_chart(fig, use_container_width=True, theme=None)

  #funcion de optimizacion del texto html
def html(texto):
    limpio = "\n".join(linea.strip() for linea in texto.splitlines() if linea.strip())
    st.markdown(limpio, unsafe_allow_html=True)


# genera las tarjetas segun la pregunta con su respectiva gráfica
def seccion(numero, pregunta, dato, dato_texto, interpretacion, recomendacion):
    izquierda, derecha = st.columns([1, 2], gap="medium")
    with izquierda:
        html(f"""
            <div class="tarjeta">
            <div class="numero">{numero}</div>
            <div class="pregunta">{pregunta}</div>
            <div class="dato"><div class="grande">{dato}</div>{dato_texto}</div>
            <div class="etiqueta">Interpretación</div><p>{interpretacion}</p>
            <div class="etiqueta">Recomendación</div><p>{recomendacion}</p>
            </div>""")
    return derecha

#verificación si los datos despues de un filtro vienen vacios
def revisar_datos(*tablas, mensaje="No hay datos para los filtros elegidos. Probá con otro año o departamento."):
    if any(tabla.empty for tabla in tablas):
        st.info(mensaje)
        st.stop()        # no sigue ejecutando el resto del código

#funcion para formato de dinero
def dinero(x):
    """12345.6 -> '$12,345.60'"""
    return f"${x:,.2f}"


# ==============================================================================
# 2.5 INICIO DE SESIÓN: credenciales previamente definidas
# ==============================================================================
load_dotenv()                                   # lee el .env de la carpeta
USUARIO = os.getenv("DASH_USER", "admin")       # usuario permitido
CLAVE = os.getenv("DASH_PASSWORD")              # contraseña definida en el env
HORAS_SESION = 8                                # se define un tiempo estimado de la sesión activa



# se crea un token al iniciar sesion ya que Streamlit borrra la sesion al recargar la página
def crear_token(usuario):
    expira = int(time.time()) + HORAS_SESION * 3600
    firma = hmac.new(CLAVE.encode(), f"{usuario}.{expira}".encode(), hashlib.sha256).hexdigest()
    return f"{usuario}.{expira}.{firma}"


#verificacion del token
def usuario_del_token(token):
    try:
        usuario, expira, firma = token.rsplit(".", 2)    # se parte en las 3 piezas
        expira = int(expira)
    except ValueError:                                   # token vacío o mal formado
        return None
    if CLAVE is None or expira < time.time():            # sin clave o ya venció
        return None
    esperada = hmac.new(CLAVE.encode(), f"{usuario}.{expira}".encode(), hashlib.sha256).hexdigest()
    return usuario if hmac.compare_digest(firma, esperada) else None


def pantalla_login():
    #crea la la tarjeta y ocultas los otros elementos
    st.markdown("""<style>[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
                   [data-testid="stExpandSidebarButton"] {display:none;}</style>""", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        html(f"""<div class="tarjeta" style="text-align:center; margin-top:10vh;">  
            <div style="font-size:2.4rem;"></div> 
            <h3 style="margin:.3rem 0; color:{TINTA};">Sakura Bookstore</h3>
            <p style="color:#667085;">Iniciá sesión para ver el dashboard</p></div>""")
            #estilos de la tarjeta
            #se agrupan los campos 
        with st.form("login"):  
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if entrar:
            # comparara los datos ingresados con los datos definidos en el env
            ok_usuario = hmac.compare_digest(usuario.encode(), USUARIO.encode())
            ok_clave = CLAVE is not None and hmac.compare_digest(clave.encode(), CLAVE.encode())

            if ok_usuario and ok_clave:
                st.session_state["autenticado"] = True       # si todo esta bien guarda quien entro
                st.session_state["usuario"] = usuario
                st.query_params["sesion"] = crear_token(usuario)   
                st.rerun()                                   # recarga y ya muestra el dashboard
            else:
                st.error("Usuario o contraseña incorrectos")


# verifica si ya se inicio sesión
if not st.session_state.get("autenticado"):
    usuario_url = usuario_del_token(st.query_params.get("sesion", ""))
    if usuario_url:
        st.session_state["autenticado"] = True
        st.session_state["usuario"] = usuario_url
    else:
        pantalla_login()
        st.stop()


# ==============================================================================
# 3. LAYOUT DE BARRA LATERAL LOGO, MENÚ, FILTROS Y BOTÓN DEL ETL
# ==============================================================================
# Fecha de la última venta guardada en el DW 
ultima = consultar("""SELECT MAX(t.fecha) AS ultima FROM dw.hechos_venta hv
                      JOIN dw.dim_tiempo t ON t.fecha_key = hv.fecha_key""")["ultima"][0]


#consulta sacada del dw para filtrar por año las ventas
anios = consultar("""SELECT DISTINCT t.anio FROM dw.hechos_venta hv
                     JOIN dw.dim_tiempo t ON t.fecha_key = hv.fecha_key ORDER BY 1 DESC""")
#consulta sacada del dw para filtrar por deparamento                
deptos = consultar("SELECT DISTINCT departamento FROM dw.dim_ubicacion ORDER BY 1")

# Páginas del menu
PAGINAS = {
    "  Inicio": "INICIO",
    "  Tendencia": "P1",
    "  Catálogo": "P2",
    "  Clientes": "P3",
    "  Geografía": "P4",
    "  Devoluciones": "P5",
    "  Retención": "P6",
    "  Preferencias": "P7",
    "  Ofertas": "P8",
}

#Elementos de la barra lateral
with st.sidebar:
    html(f"""
        <div class="perfil">
          <div class="nombre">SAKURA BOOKSTORE</div>
          <div class="sub">Datos al {ultima:%d/%m/%Y}</div>
        </div>""")
    eleccion = st.radio("Menú", list(PAGINAS), label_visibility="collapsed")
    elegida = PAGINAS[eleccion]   

    st.divider()
    anio = st.selectbox("Año", ["Todos"] + anios["anio"].astype(int).tolist())
    depto = st.selectbox("Departamento", ["Todos"] + deptos["departamento"].tolist())

    with st.popover("Sincronizar datos", use_container_width=True):   
        if st.button("Ejecutar ETL ahora", type="primary", use_container_width=True):
            ok, resultado = ejecutar_etl_completo()
            if ok:
                st.cache_data.clear()        # limpia lo anterior antes de cargar
                st.success("ETL completado")
                st.json(resultado)           # muestra los resultados de las tablas que han cargado
            else:
                st.error(f"Error en el ETL: {resultado}")

    st.caption(f"Sesión: {st.session_state['usuario']}")  
    if st.button("Cerrar sesión", use_container_width=True): #verificacion al cerrar sesion
        st.session_state.clear()        # borra la sesión de la pestaña
        st.query_params.clear()         # borra el token de la URL
        st.rerun()                      # vuelve al login




PARAMS = {}  #guarda el valor elegido en los filtros 
FILTRO_ANIO = ""
FILTRO_DEPTO = ""
if anio != "Todos":
    FILTRO_ANIO = "AND t.anio = %(anio)s"              # filtra por año y guarda en params el año elegido
    PARAMS["anio"] = int(anio)
if depto != "Todos":
    FILTRO_DEPTO = "AND u.departamento = %(depto)s"     # filtra por departamento y guarda en params el dep elegido
    PARAMS["depto"] = depto  

# ==============================================================================
# 4. CONSULTAS BASE 
# ==============================================================================
def cte_ventas(con_filtro_anio=True):
    filtro_anio = FILTRO_ANIO if con_filtro_anio else ""  #se verifica si se aplica el filtro del año 
    return f"""
    totales AS (                 
        SELECT id_venta, SUM(subtotal) AS total_venta   --totales de cada venta
        FROM dw.hechos_venta GROUP BY id_venta
    ),
    ventas AS (
        SELECT hv.id_venta, hv.cliente_key, hv.libro_key, hv.autor_key, hv.categoria_key, -- se manda a traer la fila de la ventas realizadas
               hv.oferta_key, hv.cantidad, hv.descuento_item, hv.descuento_global_venta,
               t.fecha, u.departamento, u.municipio,
               hv.subtotal - COALESCE(hv.descuento_global_venta * hv.subtotal / NULLIF(tt.total_venta, 0), 0) AS ingreso, -- ingreso = subtotal de la línea - su parte del cupón global
                                                                              -- (el cupón se reparte según lo que pesa la línea en la venta: subtotal ÷ total)
               hv.cantidad * hv.costo_unitario AS costo                  -- cantidad de costo por libro
        FROM dw.hechos_venta hv                                          
        JOIN totales tt          ON tt.id_venta = hv.id_venta            
        JOIN dw.dim_tiempo t     ON t.fecha_key = hv.fecha_key           
        JOIN dw.dim_ubicacion u  ON u.ubicacion_key = hv.ubicacion_key   
        WHERE hv.estado_venta = 'COMPLETADA' {filtro_anio} {FILTRO_DEPTO} --solo se toma en cuenta las ventas completadas
    )"""


# Tabla temporal devoluciones
# Trae la cantidad, el reembolso, el nombre del libro y el motivo.
CTE_DEVOLUCIONES = f"""
    devoluciones AS (
        SELECT hd.libro_key, hd.cantidad, hd.monto_reembolso,
               l.nombre AS libro, m.nombre AS motivo
        FROM dw.hechos_devolucion hd                                     
        JOIN dw.dim_tiempo t            ON t.fecha_key = hd.fecha_key    
        JOIN dw.dim_ubicacion u         ON u.ubicacion_key = hd.ubicacion_key
        JOIN dw.dim_libro l             ON l.libro_key = hd.libro_key    
        JOIN dw.dim_motivo_devolucion m ON m.motivo_key = hd.motivo_key  
        WHERE hd.estado_devolucion = 'APROBADA' {FILTRO_ANIO} {FILTRO_DEPTO}
    )"""




# ==============================================================================
# 5. KPIS
# ==============================================================================
html(f"""<div class="titulo" style="justify-content:center; text-align:center;">
         <h2>Análisis de ventas y comportamiento de clientes </h2></div>""") #titulo del encabezado


k = consultar(f"""  
WITH {cte_ventas()}, {CTE_DEVOLUCIONES},  --juntamos los totales de venta
resumen AS (
    SELECT COUNT(DISTINCT id_venta)    AS transacciones,   -- se cuenta las ventas distintas
           COALESCE(SUM(cantidad), 0)  AS unidades,        -- sumatoria de libros vendidos
           COALESCE(SUM(ingreso), 0)   AS ingreso,         -- se suma el ingreso real
           COALESCE(SUM(costo), 0)     AS costo,           -- la sumatoria del costo
           COUNT(DISTINCT cliente_key) AS clientes         -- cuenta cuantos clientes distintos han comprado
    FROM ventas
),
recurrentes AS (                                           -- se agrupa por cliente y solamente los que tienen dos o más compras
    SELECT COUNT(*) AS recurrentes FROM (
        SELECT cliente_key FROM ventas
        GROUP BY cliente_key HAVING COUNT(DISTINCT id_venta) >= 2) x
),
devueltos AS (
    SELECT COALESCE(SUM(cantidad), 0)        AS unidades_devueltas,  --totales de las devoluciones y la cantidad rembolsada
           COALESCE(SUM(monto_reembolso), 0) AS reembolsos
    FROM devoluciones
)
SELECT * FROM resumen, recurrentes, devueltos""", PARAMS).iloc[0]   # se junta todo

# Fórmulas de las fichas de los KPI establecidad en l sección 9.7 del documento.
# if para evitar divisiones entre cero
ventas_netas = k["ingreso"] - k["reembolsos"]
venta_promedio = k["ingreso"] / k["transacciones"] if k["transacciones"] else 0
margen = (k["ingreso"] - k["costo"]) / k["ingreso"] * 100 if k["ingreso"] else 0
recurrencia = k["recurrentes"] / k["clientes"] * 100 if k["clientes"] else 0
devolucion = k["unidades_devueltas"] / k["unidades"] * 100 if k["unidades"] else 0

# Tarjetas con icono
tarjetas = [
    ("$", "Ventas netas", dinero(ventas_netas), "Ingreso − reembolsos aprobados"),
    ("🛒", "Venta promedio", dinero(venta_promedio), "Ingreso ÷ número de ventas"),
    ("%", "Margen bruto", f"{margen:.1f}%", "(Ingreso − costo) ÷ ingreso"),
    ("↻", "Clientes recurrentes", f"{recurrencia:.1f}%", "Clientes con 2+ compras ÷ clientes"),
    ("↩", "Tasa de devolución", f"{devolucion:.2f}%", "Unidades devueltas ÷ vendidas"),
]
tarjetas_html = ""
for i, (icono, titulo, valor, formula) in enumerate(tarjetas):
    clase = "kpi principal" if i == 0 else "kpi"          
    tarjetas_html += (f'<div class="{clase}"><span class="icono">{icono}</span>'
                      f'<div class="titulo-kpi">{titulo}</div><div class="valor">{valor}</div>'
                      f'<div class="formula">{formula}</div></div>')
html(f'<div class="kpis">{tarjetas_html}</div>')


# ==============================================================================
# 6. Paginas
# ==============================================================================
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# ------------------------------------------------------------------------------
# INICIO: vista general (como la pantalla principal del diseño)
# ------------------------------------------------------------------------------
if elegida == "INICIO":
    por_mes = consultar(f"""
        WITH {cte_ventas()}
        SELECT EXTRACT(YEAR FROM fecha)::int  AS anio,
               EXTRACT(MONTH FROM fecha)::int AS num_mes,
               SUM(ingreso) AS ingreso, SUM(costo) AS costo
        FROM ventas GROUP BY 1, 2 ORDER BY 1, 2""", PARAMS)

    # Top 4 categorías:  categoria | ingreso
    top_cat = consultar(f"""
        WITH {cte_ventas()}      --se agrupa las ventas por año y por mes
        SELECT c.nombre AS categoria, SUM(v.ingreso) AS ingreso
        FROM ventas v JOIN dw.dim_categoria c ON c.categoria_key = v.categoria_key
        GROUP BY 1 ORDER BY 2 DESC LIMIT 4""", PARAMS)
    revisar_datos(por_mes, top_cat)

    por_mes["mes"] = por_mes["num_mes"].map(lambda m: MESES[m - 1])   # prepara los datos
    por_mes["año"] = por_mes["anio"].astype(str)                      

    # barras por mes
    izquierda, derecha = st.columns([3, 1.1], gap="medium")
    with izquierda:
        años = sorted(por_mes["año"].unique())                # ["2025", "2026"]
        colores = {a: NEUTRO for a in años}
        colores[años[-1]] = NARANJA
        if len(años) > 1:
            colores[años[-2]] = AZUL
        fig = px.bar(por_mes, x="mes", y="ingreso", color="año", barmode="group",
                     title="Resultado · ingreso por mes (US$)",
                     category_orders={"mes": MESES, "año": años},
                     color_discrete_map=colores,
                     labels={"mes": "", "ingreso": "", "año": ""})
        fig.update_traces(marker_line_width=0)
        fig.update_layout(bargap=.35, bargroupgap=.12,
                          legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
        fig.update_yaxes(tickprefix="$")
        grafica(fig, alto=380)
    with derecha:
        dona = pd.DataFrame({"tipo": ["Recurrentes", "Una sola compra"],  #arma un tabla con los clientes recurrente y los que tienen una compra
                             "clientes": [k["recurrentes"], k["clientes"] - k["recurrentes"]]})
        fig = px.pie(dona, names="tipo", values="clientes", hole=.68,
                     title="Clientes", color="tipo",
                     color_discrete_map={"Recurrentes": AZUL, "Una sola compra": NARANJA})
        fig.update_traces(textinfo="none", sort=False)
        fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.05),
                          annotations=[dict(text=f"<b>{recurrencia:.0f}%</b>", x=.5, y=.5,
                                            font_size=26, showarrow=False)])
        grafica(fig, alto=380)

    # Gráfica de costo por mes
    izquierda, derecha = st.columns([3, 1.1], gap="medium")
    with izquierda:
        por_mes["fecha"] = pd.to_datetime(dict(year=por_mes["anio"], month=por_mes["num_mes"], day=1))
        largo = por_mes.melt(id_vars="fecha", value_vars=["ingreso", "costo"],
                             var_name="medida", value_name="monto")
        largo["medida"] = largo["medida"].map({"ingreso": "Ingreso", "costo": "Costo"})
        fig = px.area(largo, x="fecha", y="monto", color="medida",
                      title="Ingreso vs costo por mes (US$)",
                      color_discrete_map={"Ingreso": AZUL, "Costo": NARANJA},
                      labels={"fecha": "", "monto": "", "medida": ""})
        fig.update_traces(stackgroup=None, fill="tozeroy", line_width=2)   
        fig.update_traces(fillcolor="rgba(31,41,55,.15)", selector=dict(name="Ingreso"))    
        fig.update_traces(fillcolor="rgba(15,157,138,.25)", selector=dict(name="Costo"))   
        fig.update_layout(legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
        fig.update_xaxes(tickformat="%m/%Y")
        fig.update_yaxes(tickprefix="$")
        grafica(fig, alto=340)
    with derecha:
        filas = "".join(f'<div class="lista-item"><span>{fila.categoria}</span>'
                        f'<b>{dinero(fila.ingreso)}</b></div>' for fila in top_cat.itertuples())  #lista 4 categorias con mayor ingreso 
        html(f"""<div class="tarjeta"><h4>Top 4 categorías</h4>{filas}</div>""")
        html(f"""<div class="tarjeta"><h4>Resumen ejecutivo</h4> 
            <p>{anio} · {depto}: <b>{int(k['transacciones']):,}</b> ventas de
            <b>{int(k['clientes']):,}</b> clientes por <b>{dinero(ventas_netas)}</b> netos,
            con margen de <b>{margen:.1f}%</b>. Se devolvió el {devolucion:.2f}% de los libros.</p>
            <span class="boton-naranja">Ver preguntas en el menú</span></div>""")

# ------------------------------------------------------------------------------
# P1. ¿Cómo evolucionan las ventas y en qué meses y días hay picos o caídas?
# ------------------------------------------------------------------------------
elif elegida == "P1": # pregunta elegida
    por_mes = consultar(f"""
        WITH {cte_ventas()} --se obtiene las ventas por mes y el ingreso
        SELECT date_trunc('month', fecha)::date AS mes, SUM(ingreso) AS ingreso
        FROM ventas GROUP BY 1 ORDER BY 1""", PARAMS)
#se obtiene ventas por dia de la semana
    por_dia = consultar(f"""
        WITH {cte_ventas()}
        SELECT EXTRACT(ISODOW FROM fecha)::int AS num_dia, SUM(ingreso) AS ingreso
        FROM ventas GROUP BY 1 ORDER BY 1""", PARAMS)
    por_dia["dia"] = por_dia["num_dia"].map({1: "Lun", 2: "Mar", 3: "Mié", 4: "Jue",
                                             5: "Vie", 6: "Sáb", 7: "Dom"})
    revisar_datos(por_mes, por_dia)                           # si no hay ventas se para aca

    pico = por_mes.loc[por_mes["ingreso"].idxmax()]          # obtiene el mes con más ingresos
    dia_alto = por_dia.loc[por_dia["ingreso"].idxmax(), "dia"]   # dia más alto
    dia_bajo = por_dia.loc[por_dia["ingreso"].idxmin(), "dia"]   # dia más bajo
    completo = {"Lun": "lunes", "Mar": "martes", "Mié": "miércoles", "Jue": "jueves",
                "Vie": "viernes", "Sáb": "sábados", "Dom": "domingos"}
    nombre_alto, nombre_bajo = completo[dia_alto], completo[dia_bajo]

    #titulo de la pregunta más resultado de el mes con mas ingreso y cuanto fue más interpretacion
    derecha = seccion(
        "01", "¿Cómo evolucionan las ventas y en qué meses y días hay picos o caídas?",
        f"{pico['mes']:%m/%Y}", f"mes con más ingreso ({dinero(pico['ingreso'])})",
        f"Los <b>{nombre_alto}</b> se vende más y los <b>{nombre_bajo}</b> se vende menos. "
        "El último mes puede verse bajo porque todavía no termina.",
        f"Preparar inventario antes de los meses pico y lanzar promociones los {nombre_bajo}.")
    #graficas de ingreso por mes y ingreso por dia a la semana
    with derecha:
        fig = px.area(por_mes, x="mes", y="ingreso", title="Ingreso por mes (US$)",
                      labels={"mes": "", "ingreso": ""})
        fig.update_traces(line_color=AZUL, fillcolor="rgba(31,41,55,.10)")
        fig.update_xaxes(tickformat="%m/%Y")       
        fig.update_yaxes(tickprefix="$")
        grafica(fig)
        fig = px.bar(por_dia, x="dia", y="ingreso", title="Ingreso por día de la semana (US$)",
                     labels={"dia": "", "ingreso": ""})
        # Se resalta el mejor dia
        fig.update_traces(marker_color=[NARANJA if d == dia_alto else AZUL for d in por_dia["dia"]])
        grafica(fig, alto=300)

# ------------------------------------------------------------------------------
# P2. ¿Qué libros, autores, editoriales y categorías generan más ingreso y margen?
# ------------------------------------------------------------------------------
elif elegida == "P2":
    opcion = st.radio("Agrupar por", ["Libro", "Autor", "Editorial", "Categoría"], horizontal=True)
    columna = {"Libro": "l.nombre", "Autor": "a.nombre",                 #crea los botones para los respectivos filtros y se guarda en opcion
               "Editorial": "l.editorial", "Categoría": "c.nombre"}[opcion]


# Por cada libro, autor, editorial o categoría segun lo que se elija calcula las unidades
# vendidas, el ingreso, la ganancia y el margen, ordenado de mayor a menor ingreso.
    df = consultar(f"""
        WITH {cte_ventas()}
        SELECT {columna} AS elemento,
               SUM(v.cantidad)          AS unidades,
               SUM(v.ingreso)           AS ingreso,
               SUM(v.ingreso - v.costo) AS ganancia,
               SUM(v.ingreso - v.costo) / NULLIF(SUM(v.ingreso), 0) * 100 AS margen
        FROM ventas v
        JOIN dw.dim_libro l     ON l.libro_key = v.libro_key             -- nombre y editorial
        JOIN dw.dim_autor a     ON a.autor_key = v.autor_key             -- autor
        JOIN dw.dim_categoria c ON c.categoria_key = v.categoria_key     -- categoría
        GROUP BY 1 ORDER BY ingreso DESC""", PARAMS)

#revisa que la eleccion seleccionada tenga datos
    revisar_datos(df) 
    lider = df.iloc[0]                        # mayor ingreso
    candidatos = df[df["unidades"] >= 5]      #solo los que vendieron 5 o más
    if candidatos.empty:                      # con pocos datos se usan todos
        candidatos = df
    mejor = candidatos.sort_values("margen", ascending=False).iloc[0]

#titulo de pregunta y grafica
    derecha = seccion(
        "02", "¿Qué libros, autores, editoriales y categorías generan más ingreso y margen?",
        lider["elemento"], f"lidera con {dinero(lider['ingreso'])}",
        f"El mejor margen (con 5 o más unidades) es <b>{mejor['elemento']}</b> con {mejor['margen']:.1f}%.",
        "Dar más visibilidad a lo que vende mucho con buen margen y revisar el precio o costo "
        "de lo que deja poco.")
    with derecha:
        # Gráfica de puntos que representa un elemento ,  más a la derecha más ingresos representa
        # más arriba esten más margen representa y el tamaño de los elementos representa las unidades vendidas
        fig = px.scatter(df, x="ingreso", y="margen", size="unidades", hover_name="elemento",
                         title=f"Ingreso vs. margen por {opcion.lower()}",
                         labels={"ingreso": "Ingreso (US$)", "margen": "Margen (%)"})
        fig.update_traces(marker=dict(color=AZUL, opacity=.7, line=dict(color="white", width=1)))
        grafica(fig)
        with st.expander("Ver tabla completa"): #tabla despegable que muestra los datos completos
            st.dataframe(df, hide_index=True, use_container_width=True)

# ------------------------------------------------------------------------------
# P3. ¿Quiénes son los clientes más valiosos y cuáles están en riesgo?
# ------------------------------------------------------------------------------
elif elegida == "P3":
    # Por cada cliente calcula cuántas compras hizo, cuánto gastó, cuándo fue su última y los dias que lleva sin comprar
    # se cuenta desde la ultima venta y se filtra Activo (menos de 45 días), En alerta (45 a 90) o En riesgo (más de 90).
    # se ordena de mayor a menor en gasto
    df = consultar(f"""
        WITH {cte_ventas()},
        corte AS (SELECT MAX(fecha) AS ultima_fecha FROM ventas)       
        SELECT c.nombre                               AS cliente,
               COUNT(DISTINCT v.id_venta)             AS compras,
               SUM(v.ingreso)                         AS gasto,
               MAX(v.fecha)                           AS ultima_compra,
               MAX(corte.ultima_fecha) - MAX(v.fecha) AS dias_sin_comprar,
               CASE WHEN MAX(corte.ultima_fecha) - MAX(v.fecha) > 90  THEN 'En riesgo'
                    WHEN MAX(corte.ultima_fecha) - MAX(v.fecha) >= 45 THEN 'En alerta'
                    ELSE 'Activo' END                 AS estado
        FROM ventas v
        JOIN dw.dim_cliente c ON c.cliente_key = v.cliente_key
        CROSS JOIN corte
        GROUP BY c.cliente_key, c.nombre
        ORDER BY gasto DESC""", PARAMS)
    revisar_datos(df)

    riesgo = df[df["estado"] == "En riesgo"]                  # Se queda solo con los que llevan más de 90 días sin comprar
    #titulo de la pregunta más interpretcion 
    derecha = seccion(
        "03", "¿Quiénes son los clientes más valiosos y cuáles están en riesgo?",
        f"{len(riesgo) / len(df) * 100:.0f}%", f"de los clientes ({len(riesgo)}) lleva más de 90 días sin comprar",
        f"El cliente más valioso es <b>{df.iloc[0]['cliente']}</b> con {dinero(df.iloc[0]['gasto'])}. "
        "Activo: menos de 45 días · Alerta: 45 a 90 · Riesgo: más de 90.",
        "Enviar un cupón de reactivación a los clientes valiosos en riesgo y crear un programa "
        "de lealtad para los 10 mejores.")
    with derecha:
        #Gráfica de puntos donde cada punto es un cliente y más a la derecha = más días sin comprar, más arriba = más gasto.
        fig = px.scatter(df, x="dias_sin_comprar", y="gasto", color="estado", symbol="estado",
                         hover_name="cliente", title="Gasto de cada cliente vs. días sin comprar",
                         color_discrete_map={"Activo": VERDE, "En alerta": AMARILLO, "En riesgo": ROJO},
                         labels={"dias_sin_comprar": "Días sin comprar", "gasto": "Gasto (US$)"})
        grafica(fig)
        st.markdown("**Clientes valiosos en riesgo**")
        st.dataframe(riesgo.head(10), hide_index=True, use_container_width=True)

# ------------------------------------------------------------------------------
# P4. ¿Desde qué departamentos y municipios compran más y dónde hay oportunidades?
# ------------------------------------------------------------------------------
elif elegida == "P4":
    # Toma la lista de TODOS los municipios del país aunque no haya ventas y las coloca
    # Por cada municipio calcula cuántos clientes compraron y cuánto ingreso dejó.
    # Los municipios sin ventas quedan con vacios y permite detectar como oportunidad de negocio.
    df = consultar(f"""
        WITH {cte_ventas()}
        SELECT u.departamento, u.municipio,
               COUNT(DISTINCT v.cliente_key) AS clientes,
               COALESCE(SUM(v.ingreso), 0)   AS ingreso
        FROM (SELECT DISTINCT departamento, municipio FROM dw.dim_ubicacion u
              WHERE TRUE {FILTRO_DEPTO}) u                               -- lista de municipios
        LEFT JOIN ventas v ON v.departamento = u.departamento AND v.municipio = u.municipio
        GROUP BY 1, 2""", PARAMS)

    revisar_datos(df[df["ingreso"] > 0])                                 # se verifica que por lo menos un municipio venda
    sin_ventas = df[df["ingreso"] == 0]                                  # los que no tienen compra
    por_depto = df.groupby("departamento", as_index=False)["ingreso"].sum()   # sumatoria por departamentos
    lider = por_depto.loc[por_depto["ingreso"].idxmax()]  #el que más ingresos tuvo

    #seccion que responde a la pregunta con la interpretación
    derecha = seccion(
        "04", "¿Desde qué departamentos y municipios compran más y dónde hay oportunidades?",
        lider["departamento"], f"concentra el {lider['ingreso'] / por_depto['ingreso'].sum() * 100:.0f}% del ingreso",
        f"Hay <b>{len(sin_ventas)}</b> municipios donde todavía no se vende: son el mercado por conquistar.",
        "Probar envío gratis o publicidad local en los municipios sin ventas.")
    with derecha:
        # Treemap que cada rectángulo es un municipio dentro de su departamento en una jerarquia que si es más grande y más oscuro = más ingreso.
        fig = px.treemap(df[df["ingreso"] > 0], path=["departamento", "municipio"], values="ingreso",
                         color="ingreso", color_continuous_scale=ESCALA,
                         title="Ingreso por departamento y municipio")
        grafica(fig, alto=420)
        with st.expander(f"Ver los {len(sin_ventas)} municipios sin ventas"):
            st.dataframe(sin_ventas[["departamento", "municipio"]], hide_index=True,
                         use_container_width=True)

# ------------------------------------------------------------------------------
# P5. ¿Qué libros se devuelven más y por qué motivos?
# ------------------------------------------------------------------------------
elif elegida == "P5":
    # Suma las unidades devueltas y el dinero reembolsado de cada motivo (NO_DESEADO, DANADO, ERROR_PEDIDO, OTRO)
    por_motivo = consultar(f"""
        WITH {CTE_DEVOLUCIONES}
        SELECT motivo, SUM(cantidad) AS unidades, SUM(monto_reembolso) AS reembolso
        FROM devoluciones GROUP BY 1 ORDER BY unidades""", PARAMS)

    # Suma las unidades y el reembolso de cada libro con su motivo y se queda con los 10 que más se devolvieron
    por_libro = consultar(f"""
        WITH {CTE_DEVOLUCIONES}
        SELECT libro, motivo, SUM(cantidad) AS unidades, SUM(monto_reembolso) AS reembolso
        FROM devoluciones GROUP BY 1, 2 ORDER BY unidades DESC, reembolso DESC LIMIT 10""", PARAMS)

    revisar_datos(por_motivo, mensaje="No hubo devoluciones aprobadas con estos filtros. ") #revisa los datos para verificar si hay devoluciones
    principal = por_motivo.iloc[-1]                     # última fila = motivo con más unidades
    
    #muestra el motivo con más devoluciones y su porcentaje más interpretación
    derecha = seccion(
        "05", "¿Qué libros se devuelven más y por qué motivos?",
        principal["motivo"],
        f"es el motivo más común ({principal['unidades'] / por_motivo['unidades'].sum() * 100:.0f}% de lo devuelto)",
        f"Se reembolsaron {dinero(por_motivo['reembolso'].sum())} en devoluciones aprobadas.",
        "Atacar primero ese motivo (empaque, proveedor o descripción) y vigilar los libros de la tabla.")
    with derecha:
        #grafica con barras horizontales que representa el motivo mayor por que se devuelven
        fig = px.bar(por_motivo, x="unidades", y="motivo", orientation="h",
                     title="Unidades devueltas por motivo", labels={"unidades": "", "motivo": ""})
        fig.update_traces(marker_color=AZUL)
        grafica(fig, alto=300)
        st.markdown("**Los 10 libros más devueltos**")
        st.dataframe(por_libro, hide_index=True, use_container_width=True)

# ------------------------------------------------------------------------------
# P6. ¿Cuántos clientes nuevos siguen comprando a los 3, 6 y 12 meses?
# ------------------------------------------------------------------------------
elif elegida == "P6":
    filtro_cohorte = "WHERE EXTRACT(YEAR FROM s.primera) = %(anio)s" if anio != "Todos" else "" #Aquí el año no filtra las ventas filtra a los clientes según el año
                                                                                                #de su primera compra
    # 1) Busca la fecha de la última venta del DW y la fecha de compra de cada cliente.
    # Por cada cliente marca con 1 o 0 si volvió a comprar en cada ventana de tiempo establecido
    # que son entre el mes 0 y 3, entre el 3 y 6, y entre el 6 y 12 después de su primera compra.
    #Cuenta cuántos clientes se pueden evaluar en cada plazo (a los que ya les pasó ese tiempo) y cuántos de ellos siguieron comprando.
    r = consultar(f"""
        WITH {cte_ventas(con_filtro_anio=False)},  
        corte AS (SELECT MAX(fecha) AS ultima_fecha FROM ventas),
        primera AS (SELECT cliente_key, MIN(fecha) AS primera         
                    FROM ventas GROUP BY cliente_key),
        seguimiento AS (     -- por cliente: 1 si volvió a comprar en esa ventana, 0 si no
            SELECT p.cliente_key, p.primera,
                MAX(CASE WHEN v.fecha >  p.primera
                          AND v.fecha <= p.primera + INTERVAL '3 months'  THEN 1 ELSE 0 END) AS m3,
                MAX(CASE WHEN v.fecha >  p.primera + INTERVAL '3 months'
                          AND v.fecha <= p.primera + INTERVAL '6 months'  THEN 1 ELSE 0 END) AS m6,
                MAX(CASE WHEN v.fecha >  p.primera + INTERVAL '6 months'
                          AND v.fecha <= p.primera + INTERVAL '12 months' THEN 1 ELSE 0 END) AS m12
            FROM primera p JOIN ventas v ON v.cliente_key = p.cliente_key
            GROUP BY p.cliente_key, p.primera
        )
        SELECT
          COUNT(*)   FILTER (WHERE s.primera + INTERVAL '3 months'  <= c.ultima_fecha) AS evaluados_3,
          SUM(s.m3)  FILTER (WHERE s.primera + INTERVAL '3 months'  <= c.ultima_fecha) AS siguen_3,
          COUNT(*)   FILTER (WHERE s.primera + INTERVAL '6 months'  <= c.ultima_fecha) AS evaluados_6,
          SUM(s.m6)  FILTER (WHERE s.primera + INTERVAL '6 months'  <= c.ultima_fecha) AS siguen_6,
          COUNT(*)   FILTER (WHERE s.primera + INTERVAL '12 months' <= c.ultima_fecha) AS evaluados_12,
          SUM(s.m12) FILTER (WHERE s.primera + INTERVAL '12 months' <= c.ultima_fecha) AS siguen_12
        FROM seguimiento s CROSS JOIN corte c
        {filtro_cohorte}""", PARAMS).fillna(0).iloc[0]

    #Pasa la fila de resultados a una tabla de 3 filas (una por plazo) y calcula
    tabla = pd.DataFrame({
        "Plazo": ["3 meses", "6 meses", "12 meses"],
        "Evaluados": [r["evaluados_3"], r["evaluados_6"], r["evaluados_12"]],
        "Siguen comprando": [r["siguen_3"], r["siguen_6"], r["siguen_12"]],
    })
    # % = siguen ÷ evaluados × 100  (si no hay evaluados queda en 0)
    tabla["% retención"] = [round(s / e * 100, 1) if e else 0
                            for s, e in zip(tabla["Siguen comprando"], tabla["Evaluados"])]

    derecha = seccion(

        # Muestra el % de clientes que vuelve en sus primeros 3 meses y los porcentajes de los otros plazos y la recomendación.
        "06", "¿Cuántos clientes nuevos siguen comprando a los 3, 6 y 12 meses?",
        f"{tabla['% retención'][0]}%", "vuelve a comprar en sus primeros 3 meses",
        f"Entre los meses 3 y 6 sigue activo el {tabla['% retención'][1]}% y entre 6 y 12 el "
        f"{tabla['% retención'][2]}%. Con un año elegido se analizan los clientes que compraron "
        "por primera vez ese año.",
        "Enviar una recomendación personalizada antes de que se cumplan 3 meses de la primera compra.")
    with derecha:
        #grafica el resultado con el % de retención de cada plazo
        fig = px.bar(tabla, x="Plazo", y="% retención", text="% retención",
                     title="% de clientes nuevos que siguen comprando", labels={"Plazo": ""})
        fig.update_traces(marker_color=[ESCALA[2], ESCALA[3], ESCALA[5]],
                          texttemplate="%{text}%", textposition="outside")
        fig.update_yaxes(range=[0, 105])
        grafica(fig, alto=320)
        st.dataframe(tabla, hide_index=True, use_container_width=True)

# ------------------------------------------------------------------------------
# P7. ¿Qué géneros y autores prefiere cada segmento y zona? ¿Exploran otros géneros?
# ------------------------------------------------------------------------------
elif elegida == "P7":
    #Suma las unidades vendidas de cada género en cada departamento 
    por_zona = consultar(f"""
        WITH {cte_ventas()}
        SELECT v.departamento, c.nombre AS genero, SUM(v.cantidad) AS unidades
        FROM ventas v JOIN dw.dim_categoria c ON c.categoria_key = v.categoria_key
        GROUP BY 1, 2""", PARAMS)
    
    #Se agrega en una matriz (filas = departamentos, columnas = géneros) 
    # y convierte cada fila a porcentaje, para comparar departamentos aunque unos vendan más que otros.
    matriz = por_zona.pivot_table(index="departamento", columns="genero", values="unidades", fill_value=0)
    matriz = matriz.div(matriz.sum(axis=1), axis=0) * 100      # cada fila suma 100%

    #Ordena a los clientes por lo que han gastado y los divide en 3 grupos del mismo tamaño: Alto valor, Valor medio y Bajo valor.
    por_segmento = consultar(f"""
        WITH {cte_ventas()},
        segmentos AS (                       -- cliente_key | segmento
            SELECT cliente_key,
                   CASE NTILE(3) OVER (ORDER BY SUM(ingreso) DESC)
                        WHEN 1 THEN 'Alto valor' WHEN 2 THEN 'Valor medio'
                        ELSE 'Bajo valor' END AS segmento
            FROM ventas GROUP BY cliente_key
        )
        SELECT s.segmento, c.nombre AS genero, SUM(v.cantidad) AS unidades
        FROM ventas v
        JOIN segmentos s        ON s.cliente_key = v.cliente_key
        JOIN dw.dim_categoria c ON c.categoria_key = v.categoria_key
        GROUP BY 1, 2""", PARAMS)
    #se detiene la pagina si no hay datos
    revisar_datos(por_zona, por_segmento)
    favorito_alto = (por_segmento[por_segmento["segmento"] == "Alto valor"]
                     .sort_values("unidades").iloc[-1]["genero"])   # toma género con más unidades

    #Cuenta cuántos géneros distintos compró cada cliente 
    exploracion = consultar(f"""
        WITH {cte_ventas()},
        por_cliente AS (SELECT cliente_key, COUNT(DISTINCT categoria_key) AS generos
                        FROM ventas GROUP BY cliente_key)
        SELECT CASE WHEN generos = 1 THEN '1 género'
                    WHEN generos = 2 THEN '2 géneros' ELSE '3 o más' END AS perfil,
               COUNT(*) AS clientes
        FROM por_cliente GROUP BY 1 ORDER BY 1""", PARAMS)
    exploran = exploracion[exploracion["perfil"] != "1 género"]["clientes"].sum() / exploracion["clientes"].sum() * 100 #se saca el porcentaje 

    #Se suma las unidades vendidas de cada autor y se queda con los 10 primeros
    autores = consultar(f"""
        WITH {cte_ventas()}
        SELECT a.nombre AS autor, SUM(v.cantidad) AS unidades
        FROM ventas v JOIN dw.dim_autor a ON a.autor_key = v.autor_key
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10""", PARAMS)

    #titulo de la pregunta más interpretacion
    derecha = seccion(
        "07", "¿Qué géneros y autores prefiere cada segmento y zona? ¿Exploran otros géneros?",
        f"{exploran:.0f}%", "de los clientes compra más de un género",
        f"El segmento de alto valor prefiere <b>{favorito_alto}</b> y el autor más vendido es "
        f"<b>{autores.iloc[0]['autor']}</b>. Usá el filtro de departamento para ver cada zona.",
        "Recomendar por zona su género favorito y ofrecer a los clientes de un solo género un "
        "descuento para probar otro.")
    
    # se grfica el mapa de calor: cada cuadro es el % de un género en un departamento donde más oscuro = más preferido.
    with derecha:
        fig = px.imshow(matriz, color_continuous_scale=ESCALA, aspect="auto",
                        title="% de unidades por género en cada departamento",
                        labels={"color": "%", "x": "", "y": ""})
        grafica(fig, alto=380)
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(exploracion, x="perfil", y="clientes", title="¿Exploran otros géneros?",
                         labels={"perfil": "", "clientes": ""})
            fig.update_traces(marker_color=NARANJA)
            grafica(fig, alto=300)
        with c2:
            st.markdown("**Top 10 autores**")
            st.dataframe(autores, hide_index=True, use_container_width=True, height=300)

# ------------------------------------------------------------------------------
# P8. ¿Qué tan sensibles a los descuentos son los clientes?
# ------------------------------------------------------------------------------
elif elegida == "P8":
    #Marca cada línea de venta con 1 si tuvo algún descuento (una oferta, un descuento en el libro o un cupón en la venta) y con 0 si se pagó a precio normal.
    df = consultar(f"""
        WITH {cte_ventas()},
        lineas AS (                          -- cliente_key | ingreso | con_descuento (1 o 0)
            SELECT v.cliente_key, v.ingreso,
                   CASE WHEN o.id_oferta_pk <> 0 OR v.descuento_item > 0
                             OR v.descuento_global_venta > 0 THEN 1 ELSE 0 END AS con_descuento
            FROM ventas v JOIN dw.dim_oferta o ON o.oferta_key = v.oferta_key
        ),
        clientes AS (                        -- AVG de unos y ceros x 100 = porcentaje
            SELECT cliente_key, SUM(ingreso) AS gasto, AVG(con_descuento) * 100 AS pct_con_descuento  
            FROM lineas GROUP BY cliente_key
        )
        SELECT c.nombre AS cliente, x.gasto, x.pct_con_descuento,
               CASE WHEN x.pct_con_descuento >= 80 THEN 'Cazador de ofertas'
                    WHEN x.pct_con_descuento >= 30 THEN 'Sensibilidad media'
                    ELSE 'Precio regular' END AS segmento
        FROM clientes x JOIN dw.dim_cliente c ON c.cliente_key = x.cliente_key
        ORDER BY x.pct_con_descuento DESC""", PARAMS)

    # Suma el ingreso de las ventas de cada oferta, sin contar el registro comodín "SIN OFERTA" (id 0), que representa las ventas a precio normal.
    ofertas = consultar(f"""
        WITH {cte_ventas()}
        SELECT o.nombre_oferta AS oferta, SUM(v.ingreso) AS ingreso
        FROM ventas v JOIN dw.dim_oferta o ON o.oferta_key = v.oferta_key
        WHERE o.id_oferta_pk <> 0
        GROUP BY 1 ORDER BY 2""", PARAMS)

    # Cuenta cuántos clientes quedaron en cada segmento (siempre en el mismo orden y con 0 si alguno no tiene clientes) y cuántos son cazadores de ofertas.
    revisar_datos(df)
    conteo = df["segmento"].value_counts().reindex(
        ["Precio regular", "Sensibilidad media", "Cazador de ofertas"]).fillna(0).reset_index()
    conteo.columns = ["segmento", "clientes"]
    cazadores = (df["segmento"] == "Cazador de ofertas").sum()

    #titulo de la pregunta mas interpretcion general 
    derecha = seccion(
        "08", "¿Qué tan sensibles a los descuentos son los clientes?",
        f"{cazadores / len(df) * 100:.0f}%", f"de los clientes ({cazadores}) compra casi solo con oferta",
        (f"La oferta que más ingreso trajo fue <b>{ofertas.iloc[-1]['oferta']}</b>. "
         if not ofertas.empty else "No se usaron ofertas en este periodo. ") +
        "Cazador: 80% o más de sus libros con descuento · Media: 30% a 79% · Regular: menos de 30%.",
        "Dirigir las ofertas a los cazadores y no regalar margen a quienes compran a precio regular.")
    
    #barras con cuántos clientes hay en cada segmento y barras
    # horizontales con el ingreso de cada oferta. Debajo, una tabla desplegable con cada cliente, su gasto, su % de compras con descuento y su segmento.
    with derecha:
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(conteo, x="segmento", y="clientes", title="Clientes por segmento",
                         labels={"segmento": "", "clientes": ""})
            fig.update_traces(marker_color=[ESCALA[2], ESCALA[3], ESCALA[5]])
            grafica(fig, alto=320)
        with c2:
            fig = px.bar(ofertas, x="ingreso", y="oferta", orientation="h",   # vacía si no hubo ofertas
                         title="Ingreso por oferta (US$)", labels={"ingreso": "", "oferta": ""})
            fig.update_traces(marker_color=NARANJA)
            grafica(fig, alto=320)
        with st.expander("Ver clientes y su % de compras con descuento"):
            st.dataframe(df, hide_index=True, use_container_width=True)
#de donde salen los datos
st.caption("Fuente: Data Warehouse sakura_dw ") 
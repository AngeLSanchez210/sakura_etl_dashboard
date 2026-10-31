import os
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values #ubica los archivos necesarios y psycopg2 se comunica a postgres
from neo4j import GraphDatabase
from dotenv import load_dotenv

# se lee las credenciales del archivo .env 
CARPETA = Path(__file__).resolve().parent
load_dotenv(CARPETA / ".env")

#funiones para abrir las conexiones
def conectar_postgres(): #conexion al datawarehouse sakura_dw
    return psycopg2.connect(
        host=os.getenv("PG_HOST"),
        port=os.getenv("PG_PORT", "5432"),
        dbname=os.getenv("PG_DATABASE", "sakura_dw"),
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
    )

#conexion a Neo4j
def conectar_neo4j():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")),
    )

# Extracciones
#provenientes de Neo4j
EXTRACCIONES = [
    ("Departamentos",
     "MATCH (dep:Departamento) RETURN dep.id_departamento, dep.nombre",
     "INSERT INTO stg.departamento VALUES %s"),

#consta de 3 partes nombre para la bitacora, consulta cypher y el insert en la tabla stg
    ("Municipios",
     "MATCH (m:Municipio)-[:PERTENECE_A]->(dep:Departamento) "
     "RETURN m.id_municipio, m.nombre, dep.id_departamento",
     "INSERT INTO stg.municipio VALUES %s"),

    ("Distritos",
     "MATCH (d:Distrito)-[:PERTENECE_A]->(m:Municipio) "
     "RETURN d.id_distrito, d.nombre, m.id_municipio",
     "INSERT INTO stg.distrito VALUES %s"),

    ("Clientes",
     "MATCH (c:Cliente)-[:RESIDE_EN]->(d:Distrito) "
     "RETURN c.id_cliente, c.nombre, c.email, toString(c.fecha_registro), d.id_distrito",
     "INSERT INTO stg.cliente VALUES %s"),

    ("Editoriales",
     "MATCH (e:Editorial) RETURN e.id_editorial, e.nombre, e.pais",
     "INSERT INTO stg.editorial VALUES %s"),

    ("Autores",
     "MATCH (a:Autor) RETURN a.id_autor, a.nombre, a.nacionalidad",
     "INSERT INTO stg.autor VALUES %s"),

    ("Categorias",
     "MATCH (cat:Categoria) RETURN cat.id_categoria, cat.nombre",
     "INSERT INTO stg.categoria VALUES %s"),

    #libros con su respectivo editorial, autor y la categoria
    ("Libros",
     """
     MATCH (l:Libro)
     OPTIONAL MATCH (l)-[:PUBLICADO_POR]->(e:Editorial)
     OPTIONAL MATCH (l)-[:ESCRITO_POR]->(a:Autor)
     OPTIONAL MATCH (l)-[:PERTENECE_A]->(cat:Categoria)
     WITH l, min(e.id_editorial) AS id_editorial,
             min(a.id_autor) AS id_autor,
             min(cat.id_categoria) AS id_categoria
     RETURN l.id_producto, l.isbn, l.nombre, l.precio_unitario, l.costo_promedio,
            l.formato, l.idioma, id_editorial, id_autor, id_categoria
     """,
     "INSERT INTO stg.libro VALUES %s"),

    ("Ofertas",
     "MATCH (o:Oferta) RETURN o.id_oferta, o.nombre_oferta, o.tipo_descuento, "
     "o.valor_descuento, toString(o.fecha_inicio), toString(o.fecha_fin)",
     "INSERT INTO stg.oferta VALUES %s"),

    ("Motivos devolucion",
     "MATCH (m:MotivoDevolucion) RETURN m.id_motivo_devolucion, m.nombre",
     "INSERT INTO stg.motivo_devolucion VALUES %s"),

    ("Ventas",
     """
     MATCH (c:Cliente)-[:REALIZO]->(v:Venta)
     OPTIONAL MATCH (v)-[:APLICO_OFERTA]->(o:Oferta)
     WITH v, min(c.id_cliente) AS id_cliente, min(o.id_oferta) AS id_oferta
     RETURN v.id_venta, id_cliente, id_oferta, toString(v.fecha),
            v.subtotal_general, v.descuento_global, v.total, v.estado
     """,
     "INSERT INTO stg.venta VALUES %s"),

    ("Detalle ventas",
     """
     MATCH (v:Venta)-[r:INCLUYE_LIBRO]->(l:Libro)
     RETURN DISTINCT r.id_detalle_venta, v.id_venta, l.id_producto, r.id_oferta,
            r.cantidad, r.precio_unitario, r.descuento_aplicado, r.subtotal
     """,
     "INSERT INTO stg.detalle_venta VALUES %s"),

    ("Devoluciones",
     """
     MATCH (v:Venta)-[:TIENE_DEVOLUCION]->(d:Devolucion)-[:POR_MOTIVO]->(m:MotivoDevolucion)
     RETURN d.id_devolucion, v.id_venta, m.id_motivo_devolucion,
            toString(coalesce(d.fecha_devolucion, v.fecha)), d.tipo_reembolso, d.estado
     """,
     "INSERT INTO stg.devolucion VALUES %s"),

    ("Detalle devoluciones",
     """
     MATCH (d:Devolucion)-[r:DEVOLVIO_ITEM]->(l:Libro)
     RETURN DISTINCT r.id_detalle_devolucion, d.id_devolucion, r.id_detalle_venta,
            l.id_producto, r.cantidad, r.monto_reembolso, r.reingresa_stock
     """,
     "INSERT INTO stg.detalle_devolucion VALUES %s"),
]


#ejecuta la consulta cypher y carga al stg una entidad
def extraer_y_cargar(sesion_neo, cursor_pg, cypher, insert_sql):
    filas = {} # se guarda en un diccionario y se usa el id como llave
    for registro in sesion_neo.run(cypher): # se consulta a neo4j y se recorren los resultados uno x uno 
        fila = tuple(registro.values())
        filas.setdefault(fila[0], fila)  #se convierte el resultado a tupla y guarda el valor si todavia no existe          
    if filas:
        execute_values(cursor_pg, insert_sql, list(filas.values())) # si no hay nada  el diccionario queda vacio
    return len(filas) #devuelve cuantas filas se cargaron

#funcion que corre todo el etl
def ejecutar_etl_completo():
    #se definen variables con las conexiones 
    neo = conectar_neo4j()
    pg = conectar_postgres()
    cur = pg.cursor() #el mensajero que manda las consultas sql a postgres
    conteo = {} # se define diccionario vacio donde contara cuantas filas cargan de cada identidad

    try:
        with neo.session() as sesion: #se abre una sesion a neo4j
            #se borra la info de los stg ya que por cad ejecucion los datos se recarga todo desde cero
            cur.execute("""
                TRUNCATE stg.departamento, stg.municipio, stg.distrito, stg.cliente,
                         stg.editorial, stg.autor, stg.categoria, stg.libro,
                         stg.oferta, stg.motivo_devolucion, stg.venta, stg.detalle_venta,
                         stg.devolucion, stg.detalle_devolucion""")

            #se reccoren las 14 entidades con los 3 elementos
            for nombre, cypher, insert_sql in EXTRACCIONES:
                #se llama a extraer y cargar para que guarde en cada uno de los stg y anote cuantas filas se cargaron
                conteo[nombre] = extraer_y_cargar(sesion, cur, cypher, insert_sql)

        # se llama a poblar_dw.sql lee todo el texto sql y lo ejecuta
        cur.execute((CARPETA / "poblar_dw.sql").read_text(encoding="utf-8"))
        #pasa los datos del stg a las dimensiones y hechos del dw


        # lineas de venta que están en stg pero no llegaron al dw
        cur.execute("""SELECT COUNT(*) FROM stg.detalle_venta s
                       WHERE NOT EXISTS (SELECT 1 FROM dw.hechos_venta h
                                         WHERE h.id_detalle_venta = s.id_detalle_venta)""")
        conteo["Lineas de venta descartadas"] = cur.fetchone()[0]

        #lineas de devolución que están en stg pero no llegaron al dw
        cur.execute("""SELECT COUNT(*) FROM stg.detalle_devolucion s
                       WHERE NOT EXISTS (SELECT 1 FROM dw.hechos_devolucion h
                                         WHERE h.id_detalle_devolucion = s.id_detalle_devolucion)""")
        conteo["Lineas de devolucion descartadas"] = cur.fetchone()[0]

        # Todo salió bien se confirma y se anota en la bitácora
        cur.execute("INSERT INTO dw.etl_bitacora (estado, detalle) VALUES ('OK', %s)",
                    (json.dumps(conteo),))
        pg.commit() #se confirma todo de una vez 
        return True, conteo

    except Exception as error:
        # si algo falla en la bitacora se especifica
        pg.rollback() # deshace todo lo que se hizo en la ejecucion
        cur.execute("INSERT INTO dw.etl_bitacora (estado, detalle) VALUES ('ERROR', %s)",
                    (str(error),))
        pg.commit()
        return False, str(error)

    finally:
        cur.close() # cierre las conexiones y cursor
        pg.close()
        neo.close()


# Permite correr el ETL desde la terminal:  python etl.py
if __name__ == "__main__":
    ok, resultado = ejecutar_etl_completo()
    print("ETL completado:" if ok else "ETL con error:", resultado)

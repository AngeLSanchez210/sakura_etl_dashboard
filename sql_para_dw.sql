create schema stg;
create schema dw;

CREATE TABLE stg.departamento (
    id_departamento integer PRIMARY KEY,
    nombre text NOT NULL
);

CREATE TABLE stg.municipio (
    id_municipio integer PRIMARY KEY,
    nombre text NOT NULL,
    id_departamento integer NOT NULL
);

CREATE TABLE stg.distrito (
    id_distrito integer PRIMARY KEY,
    nombre text NOT NULL,
    id_municipio integer NOT NULL
);

CREATE TABLE stg.cliente (
    id_cliente integer PRIMARY KEY,
    nombre text NOT NULL,
    email text,
    fecha_registro date,
    id_distrito integer NOT NULL
);

-- B. Dominio del Catálogo Literario
CREATE TABLE stg.editorial (
    id_editorial integer PRIMARY KEY,
    nombre text NOT NULL,
    pais text
);

CREATE TABLE stg.autor (
    id_autor integer PRIMARY KEY,
    nombre text NOT NULL,
    nacionalidad text
);

CREATE TABLE stg.categoria (
    id_categoria integer PRIMARY KEY,
    nombre text NOT NULL
);

CREATE TABLE stg.libro (
    id_producto integer PRIMARY KEY,
    isbn text,
    nombre text NOT NULL,
    precio_unitario numeric(10,2),
    costo_promedio numeric(10,2),
    formato text,
    idioma text,
    id_editorial integer,
    id_autor integer,     -- Relación [:ESCRITO_POR]
    id_categoria integer  -- Relación [:PERTENECE_A]
);

-- C. Dominio Transaccional (Ventas, Ofertas y Devoluciones)
CREATE TABLE stg.oferta (
    id_oferta integer PRIMARY KEY,
    nombre_oferta text NOT NULL,
    tipo_descuento text,
    valor_descuento numeric(10,2),
    fecha_inicio date,
    fecha_fin date
);

CREATE TABLE stg.motivo_devolucion (
    id_motivo_devolucion integer PRIMARY KEY,
    nombre text NOT NULL
);

CREATE TABLE stg.venta (
    id_venta integer PRIMARY KEY,
    id_cliente integer NOT NULL,
    id_oferta integer,
    fecha timestamptz NOT NULL,
    subtotal_general numeric(10,2),
    descuento_global numeric(10,2),
    total numeric(10,2),
    estado text NOT NULL
);

CREATE TABLE stg.detalle_venta (
    id_detalle_venta integer PRIMARY KEY,
    id_venta integer NOT NULL,
    id_producto integer NOT NULL,
    id_oferta integer,
    cantidad integer NOT NULL,
    precio_unitario numeric(10,2) NOT NULL,
    descuento_aplicado numeric(10,2) NOT NULL,
    subtotal numeric(10,2) NOT NULL
);

CREATE TABLE stg.devolucion (
    id_devolucion integer PRIMARY KEY,
    id_venta integer NOT NULL,
    id_motivo_devolucion integer NOT NULL,
    fecha_devolucion timestamptz NOT NULL,
    tipo_reembolso text,
    estado text NOT NULL
);

CREATE TABLE stg.detalle_devolucion (
    id_detalle_devolucion integer PRIMARY KEY,
    id_devolucion integer NOT NULL,
    id_detalle_venta integer NOT NULL,
    id_producto integer NOT NULL,
    cantidad integer NOT NULL,
    monto_reembolso numeric(10,2) NOT NULL,
    reingresa_stock boolean NOT NULL
);

-- Dimensión 1: Tiempo
CREATE TABLE dw.dim_tiempo (
    fecha_key integer PRIMARY KEY,
    fecha date NOT NULL UNIQUE,
    anio smallint NOT NULL,
    trimestre smallint NOT NULL,
    mes smallint NOT NULL,
    nombre_mes text NOT NULL,
    anio_mes char(7) NOT NULL,
    dia smallint NOT NULL,
    nombre_dia text NOT NULL
);

-- Dimensión 2: Ubicación / Lugar (Independiente del cliente)
CREATE TABLE dw.dim_ubicacion (
    ubicacion_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_distrito_pk integer NOT NULL UNIQUE,
    distrito text NOT NULL,
    id_municipio integer NOT NULL,
    municipio text NOT NULL,
    id_departamento integer NOT NULL,
    departamento text NOT NULL
);

-- Dimensión 3: Cliente (Limpia, enfocada solo en el cliente)
CREATE TABLE dw.dim_cliente (
    cliente_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_cliente_pk integer NOT NULL UNIQUE,
    nombre text NOT NULL,
    email text,
    fecha_registro date
);

-- Dimensión 4: Autor (Independiente para consultas rápidas en Preguntas P2 y P7)
CREATE TABLE dw.dim_autor (
    autor_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_autor_pk integer NOT NULL UNIQUE,
    nombre text NOT NULL,
    nacionalidad text
);

-- Dimensión 5: Categoría (Independiente para Preguntas P2 y P7)
CREATE TABLE dw.dim_categoria (
    categoria_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_categoria_pk integer NOT NULL UNIQUE,
    nombre text NOT NULL
);

-- Dimensión 6: Libro (Incluye su editorial)
CREATE TABLE dw.dim_libro (
    libro_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_producto_pk integer NOT NULL UNIQUE,
    isbn text,
    nombre text NOT NULL,
    precio_lista numeric(10,2),
    costo_promedio numeric(10,2),
    formato text,
    idioma text,
    editorial text,
    pais_editorial text
);

-- Dimensión 7: Oferta
CREATE TABLE dw.dim_oferta (
    oferta_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_oferta_pk integer NOT NULL UNIQUE,
    nombre_oferta text NOT NULL,
    tipo_descuento text,
    valor_descuento numeric(10,2),
    fecha_inicio date,
    fecha_fin date
);

-- Registro comodín para cuando una venta NO tiene oferta (id_oferta_pk = 0)
INSERT INTO dw.dim_oferta (id_oferta_pk, nombre_oferta, tipo_descuento, valor_descuento)
VALUES (0, 'SIN OFERTA', 'NINGUNO', 0) ON CONFLICT (id_oferta_pk) DO NOTHING;

-- Dimensión 8: Motivo de Devolución
CREATE TABLE dw.dim_motivo_devolucion (
    motivo_key integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_motivo_pk integer NOT NULL UNIQUE,
    nombre text NOT NULL
);

-- HECHOS DE VENTA (Conecta Tiempo, Cliente, Ubicación, Libro, Autor, Categoría y Oferta)
CREATE TABLE dw.hechos_venta (
    id_detalle_venta integer PRIMARY KEY,
    fecha_key integer NOT NULL REFERENCES dw.dim_tiempo(fecha_key),
    cliente_key integer NOT NULL REFERENCES dw.dim_cliente(cliente_key),
    ubicacion_key integer NOT NULL REFERENCES dw.dim_ubicacion(ubicacion_key),
    libro_key integer NOT NULL REFERENCES dw.dim_libro(libro_key),
    autor_key integer NOT NULL REFERENCES dw.dim_autor(autor_key),
    categoria_key integer NOT NULL REFERENCES dw.dim_categoria(categoria_key),
    oferta_key integer NOT NULL REFERENCES dw.dim_oferta(oferta_key),
    id_venta integer NOT NULL,
    estado_venta text NOT NULL,
    cantidad integer NOT NULL,
    precio_unitario numeric(10,2) NOT NULL,
    costo_unitario numeric(10,2) NOT NULL,
    descuento_item numeric(10,2) NOT NULL,
    descuento_global_venta numeric(10,2) NOT NULL,
    subtotal numeric(10,2) NOT NULL
);

-- HECHOS DE DEVOLUCIÓN (Conecta Tiempo, Cliente, Ubicación, Libro y Motivo)
CREATE TABLE dw.hechos_devolucion (
    id_detalle_devolucion integer PRIMARY KEY,
    fecha_key integer NOT NULL REFERENCES dw.dim_tiempo(fecha_key),
    cliente_key integer NOT NULL REFERENCES dw.dim_cliente(cliente_key),
    ubicacion_key integer NOT NULL REFERENCES dw.dim_ubicacion(ubicacion_key),
    libro_key integer NOT NULL REFERENCES dw.dim_libro(libro_key),
    motivo_key integer NOT NULL REFERENCES dw.dim_motivo_devolucion(motivo_key),
    id_devolucion integer NOT NULL,
    id_venta integer NOT NULL,
    estado_devolucion text NOT NULL,
    tipo_reembolso text,
    cantidad integer NOT NULL,
    monto_reembolso numeric(10,2) NOT NULL,
    reingresa_stock boolean NOT NULL
);

-- AUDITORÍA DEL ETL
CREATE TABLE dw.etl_bitacora (
    id_ejecucion serial PRIMARY KEY,           -- número de ejecución
    fecha        timestamptz DEFAULT clock_timestamp(),    -- cuándo se registró la ejecución
    estado       text,                         -- OK o ERROR
    detalle      text                          -- filas cargadas por tabla o mensaje de error
);

INSERT INTO dw.dim_tiempo
SELECT 
    to_char(d, 'YYYYMMDD')::integer,
    d::date,
    extract(year FROM d)::smallint,
    extract(quarter FROM d)::smallint,
    extract(month FROM d)::smallint,
    (array['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'])[extract(month FROM d)],
    to_char(d, 'YYYY-MM'),
    extract(day FROM d)::smallint,
    (array['LUNES', 'MARTES', 'MIERCOLES', 'JUEVES', 'VIERNES', 'SABADO', 'DOMINGO'])[extract(isodow FROM d)]
FROM generate_series('2020-01-01'::date, '2027-12-31'::date, interval '1 day') AS d
ON CONFLICT (fecha_key) DO NOTHING;
-- 1. Cargar Dimensión Ubicación (Uniendo Distrito, Municipio y Departamento desde STG)
INSERT INTO dw.dim_ubicacion (id_distrito_pk, distrito, id_municipio, municipio, id_departamento, departamento)
SELECT 
    d.id_distrito, 
    d.nombre, 
    m.id_municipio, 
    m.nombre, 
    dep.id_departamento, 
    dep.nombre
FROM stg.distrito d
JOIN stg.municipio m ON d.id_municipio = m.id_municipio
JOIN stg.departamento dep ON m.id_departamento = dep.id_departamento
ON CONFLICT (id_distrito_pk) DO UPDATE SET
    distrito = EXCLUDED.distrito,
    municipio = EXCLUDED.municipio,
    departamento = EXCLUDED.departamento;

-- 2. Cargar Dimensión Cliente (Independiente de la ubicación)
INSERT INTO dw.dim_cliente (id_cliente_pk, nombre, email, fecha_registro)
SELECT id_cliente, nombre, email, fecha_registro
FROM stg.cliente
ON CONFLICT (id_cliente_pk) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    email = EXCLUDED.email;

-- 3. Cargar Dimensión Autor
INSERT INTO dw.dim_autor (id_autor_pk, nombre, nacionalidad)
SELECT id_autor, nombre, nacionalidad
FROM stg.autor
ON CONFLICT (id_autor_pk) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    nacionalidad = EXCLUDED.nacionalidad;

-- 4. Cargar Dimensión Categoría
INSERT INTO dw.dim_categoria (id_categoria_pk, nombre)
SELECT id_categoria, nombre
FROM stg.categoria
ON CONFLICT (id_categoria_pk) DO UPDATE SET
    nombre = EXCLUDED.nombre;

-- 5. Cargar Dimensión Libro (Con su Editorial)
INSERT INTO dw.dim_libro (id_producto_pk, isbn, nombre, precio_lista, costo_promedio, formato, idioma, editorial, pais_editorial)
SELECT 
    l.id_producto, l.isbn, l.nombre, l.precio_unitario, l.costo_promedio, 
    l.formato, l.idioma, COALESCE(e.nombre, 'SIN EDITORIAL'), COALESCE(e.pais, 'N/A')
FROM stg.libro l
LEFT JOIN stg.editorial e ON l.id_editorial = e.id_editorial
ON CONFLICT (id_producto_pk) DO UPDATE SET
    nombre = EXCLUDED.nombre,
    precio_lista = EXCLUDED.precio_lista,
    costo_promedio = EXCLUDED.costo_promedio,
    editorial = EXCLUDED.editorial;

-- 6. Cargar Dimensión Oferta
INSERT INTO dw.dim_oferta (id_oferta_pk, nombre_oferta, tipo_descuento, valor_descuento, fecha_inicio, fecha_fin)
SELECT id_oferta, nombre_oferta, tipo_descuento, valor_descuento, fecha_inicio, fecha_fin
FROM stg.oferta
ON CONFLICT (id_oferta_pk) DO UPDATE SET
    nombre_oferta = EXCLUDED.nombre_oferta,
    valor_descuento = EXCLUDED.valor_descuento;

-- 7. Cargar Dimensión Motivo Devolución
INSERT INTO dw.dim_motivo_devolucion (id_motivo_pk, nombre)
SELECT id_motivo_devolucion, nombre
FROM stg.motivo_devolucion
ON CONFLICT (id_motivo_pk) DO UPDATE SET
    nombre = EXCLUDED.nombre;

-- 8. Cargar HECHOS DE VENTA (Aquí se unen todas las llaves de las dimensiones)
INSERT INTO dw.hechos_venta (
    id_detalle_venta, fecha_key, cliente_key, ubicacion_key, libro_key, 
    autor_key, categoria_key, oferta_key, id_venta, estado_venta, 
    cantidad, precio_unitario, costo_unitario, descuento_item, descuento_global_venta, subtotal
)
SELECT 
    dv.id_detalle_venta,
    -- La fecha se convierte a hora de El Salvador antes de sacar el día (evita que
    -- una venta de las 7 p. m. quede registrada el día siguiente por estar en UTC)
    to_char(v.fecha AT TIME ZONE 'America/El_Salvador', 'YYYYMMDD')::integer AS fecha_key,
    dc.cliente_key,
    du.ubicacion_key,
    dl.libro_key,
    da.autor_key,
    dcat.categoria_key,
    COALESCE(dof.oferta_key, (SELECT oferta_key FROM dw.dim_oferta WHERE id_oferta_pk = 0)),
    v.id_venta,
    v.estado,
    dv.cantidad,
    dv.precio_unitario,
    sl.costo_promedio,
    dv.descuento_aplicado,
    COALESCE(v.descuento_global, 0),
    dv.subtotal
FROM stg.detalle_venta dv
JOIN stg.venta v ON dv.id_venta = v.id_venta
JOIN stg.cliente sc ON v.id_cliente = sc.id_cliente
JOIN stg.libro sl ON dv.id_producto = sl.id_producto
-- Cruce con las Dimensiones de DW para obtener sus *_key:
JOIN dw.dim_cliente dc ON dc.id_cliente_pk = sc.id_cliente
JOIN dw.dim_ubicacion du ON du.id_distrito_pk = sc.id_distrito
JOIN dw.dim_libro dl ON dl.id_producto_pk = sl.id_producto
JOIN dw.dim_autor da ON da.id_autor_pk = sl.id_autor
JOIN dw.dim_categoria dcat ON dcat.id_categoria_pk = sl.id_categoria
LEFT JOIN dw.dim_oferta dof ON dof.id_oferta_pk = COALESCE(dv.id_oferta, v.id_oferta, 0)
ON CONFLICT (id_detalle_venta) DO UPDATE SET
    fecha_key = EXCLUDED.fecha_key,
    estado_venta = EXCLUDED.estado_venta,
    cantidad = EXCLUDED.cantidad,
    precio_unitario = EXCLUDED.precio_unitario,
    descuento_item = EXCLUDED.descuento_item,
    descuento_global_venta = EXCLUDED.descuento_global_venta,
    subtotal = EXCLUDED.subtotal;

-- 9. Cargar HECHOS DE DEVOLUCIÓN
INSERT INTO dw.hechos_devolucion (
    id_detalle_devolucion, fecha_key, cliente_key, ubicacion_key, libro_key, 
    motivo_key, id_devolucion, id_venta, estado_devolucion, tipo_reembolso, 
    cantidad, monto_reembolso, reingresa_stock
)
SELECT 
    dd.id_detalle_devolucion,
    to_char(d.fecha_devolucion AT TIME ZONE 'America/El_Salvador', 'YYYYMMDD')::integer AS fecha_key,
    dc.cliente_key,
    du.ubicacion_key,
    dl.libro_key,
    dm.motivo_key,
    d.id_devolucion,
    d.id_venta,
    d.estado,
    d.tipo_reembolso,
    dd.cantidad,
    dd.monto_reembolso,
    dd.reingresa_stock
FROM stg.detalle_devolucion dd
JOIN stg.devolucion d ON dd.id_devolucion = d.id_devolucion
JOIN stg.venta v ON d.id_venta = v.id_venta
JOIN stg.cliente sc ON v.id_cliente = sc.id_cliente
-- Cruce con las Dimensiones de DW:
JOIN dw.dim_cliente dc ON dc.id_cliente_pk = sc.id_cliente
JOIN dw.dim_ubicacion du ON du.id_distrito_pk = sc.id_distrito
JOIN dw.dim_libro dl ON dl.id_producto_pk = dd.id_producto
JOIN dw.dim_motivo_devolucion dm ON dm.id_motivo_pk = d.id_motivo_devolucion
ON CONFLICT (id_detalle_devolucion) DO UPDATE SET
    fecha_key = EXCLUDED.fecha_key,
    estado_devolucion = EXCLUDED.estado_devolucion,
    monto_reembolso = EXCLUDED.monto_reembolso;
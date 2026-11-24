-- Esquema de la base de datos de tarimas (PostgreSQL).
-- Se ejecuta con:  python init_db.py   (no borra datos si ya existe)

-- Líneas de producción
CREATE TABLE IF NOT EXISTS lineas (
    id            SERIAL PRIMARY KEY,
    codigo        TEXT NOT NULL UNIQUE,          -- "L4" (prefijo del folio)
    nombre        TEXT NOT NULL,                 -- "Línea 4"
    impresora_ip  TEXT,                          -- impresora de etiquetas de esa línea
    lote_actual   TEXT NOT NULL DEFAULT '',      -- lo captura el operador
    ultimo_folio  INTEGER NOT NULL DEFAULT 0,    -- consecutivo de la línea
    activa        BOOLEAN NOT NULL DEFAULT TRUE
);

-- Presentaciones (productos)
CREATE TABLE IF NOT EXISTS presentaciones (
    id                 SERIAL PRIMARY KEY,
    clave              TEXT NOT NULL UNIQUE,     -- "4LB-F10"
    nombre             TEXT NOT NULL,            -- "4 lb"
    descripcion        TEXT NOT NULL DEFAULT '', -- "Fardo de 10 bolsas"
    libras_por_bolsa   NUMERIC(10, 3) NOT NULL CHECK (libras_por_bolsa > 0),
    bolsas_por_fardo   INTEGER NOT NULL CHECK (bolsas_por_fardo > 0),
    fardos_por_tarima  INTEGER NOT NULL CHECK (fardos_por_tarima > 0),
    activa             BOOLEAN NOT NULL DEFAULT TRUE
);

-- Qué presentaciones se pueden producir en cada línea
CREATE TABLE IF NOT EXISTS linea_presentacion (
    linea_id        INTEGER NOT NULL REFERENCES lineas(id) ON DELETE CASCADE,
    presentacion_id INTEGER NOT NULL REFERENCES presentaciones(id) ON DELETE CASCADE,
    PRIMARY KEY (linea_id, presentacion_id)
);

-- Cada tarima registrada. Se guardan también el nombre y los datos de la
-- presentación tal como estaban ese día, por si después se modifica.
CREATE TABLE IF NOT EXISTS tarimas (
    id               BIGSERIAL PRIMARY KEY,
    folio            TEXT NOT NULL UNIQUE,       -- "L4-000123"
    linea_id         INTEGER NOT NULL REFERENCES lineas(id),
    numero           INTEGER NOT NULL,           -- 123
    presentacion_id  INTEGER NOT NULL REFERENCES presentaciones(id),
    presentacion     TEXT NOT NULL,
    descripcion      TEXT NOT NULL,
    fecha_hora       TIMESTAMP NOT NULL,         -- hora local de la planta
    turno            SMALLINT NOT NULL,
    lote             TEXT NOT NULL,
    fardos           INTEGER NOT NULL CHECK (fardos > 0),
    bolsas           INTEGER NOT NULL,
    libras           NUMERIC(12, 3) NOT NULL,
    completa         BOOLEAN NOT NULL,
    estado           TEXT NOT NULL DEFAULT 'OK' CHECK (estado IN ('OK', 'ANULADA')),
    anulada_en       TIMESTAMP,
    registro_por     TEXT NOT NULL DEFAULT 'Montacargas',
    UNIQUE (linea_id, numero)
);

CREATE INDEX IF NOT EXISTS tarimas_fecha_idx ON tarimas (fecha_hora);
CREATE INDEX IF NOT EXISTS tarimas_linea_fecha_idx ON tarimas (linea_id, fecha_hora);

-- Cola de envíos a Google Sheets. Se escribe en la misma transacción que la
-- tarima, así nunca hay una tarima sin su envío pendiente.
CREATE TABLE IF NOT EXISTS sheets_pendientes (
    id        BIGSERIAL PRIMARY KEY,
    mensaje   JSONB NOT NULL,
    creado    TIMESTAMP NOT NULL DEFAULT now(),
    intentos  INTEGER NOT NULL DEFAULT 0
);

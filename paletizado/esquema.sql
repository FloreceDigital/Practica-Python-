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

-- ---------------------------------------------------------------------------
-- Versión 2: campos del formulario de producción (Línea 4, 10/4 lb)
-- Se pueden correr sobre una base que ya existe: solo agregan lo que falta.
-- ---------------------------------------------------------------------------

-- Código de material de SAP de cada presentación (ej. 25000307)
ALTER TABLE presentaciones ADD COLUMN IF NOT EXISTS codigo_sap TEXT NOT NULL DEFAULT '';

-- Datos de la corrida que captura el operador una vez (no por tarima).
-- lineas.lote_actual queda como lote MANUAL: vacío = se calcula solo.
ALTER TABLE lineas ADD COLUMN IF NOT EXISTS color_actual        TEXT NOT NULL DEFAULT '';
ALTER TABLE lineas ADD COLUMN IF NOT EXISTS lote_film           TEXT NOT NULL DEFAULT '';
ALTER TABLE lineas ADD COLUMN IF NOT EXISTS lote_bale           TEXT NOT NULL DEFAULT '';
ALTER TABLE lineas ADD COLUMN IF NOT EXISTS operador_produccion TEXT NOT NULL DEFAULT '';
ALTER TABLE lineas ADD COLUMN IF NOT EXISTS supervisor          TEXT NOT NULL DEFAULT '';
ALTER TABLE lineas ADD COLUMN IF NOT EXISTS estibadores         TEXT NOT NULL DEFAULT '';

-- Personal que aparece en las listas (montacargas, operadores, supervisores, estibadores)
CREATE TABLE IF NOT EXISTS personas (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT NOT NULL,
    rol     TEXT NOT NULL CHECK (rol IN ('montacargas', 'operador', 'supervisor', 'estibador')),
    activa  BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (nombre, rol)
);

-- Datos de cada tarima tal como pide el formulario
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS fecha_turno         DATE;      -- día en que empezó el turno
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS numero_pallet       INTEGER;   -- Finished Pallet No. (1, 2, 3… por turno)
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS codigo_sap          TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS color               TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS lote_film           TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS lote_bale           TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS operador_produccion TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS montacarguista      TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS supervisor          TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS estibadores         TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS comentarios         TEXT NOT NULL DEFAULT '';

-- Un número de tarima no se repite dentro del mismo turno de la misma línea
CREATE UNIQUE INDEX IF NOT EXISTS tarimas_pallet_turno_idx
    ON tarimas (linea_id, fecha_turno, turno, numero_pallet)
    WHERE numero_pallet IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Versión 3: correcciones de tarimas (mismo número, dato corregido)
-- ---------------------------------------------------------------------------
-- Resumen legible de las correcciones (va al Excel y a Google Sheets)
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS correcciones TEXT NOT NULL DEFAULT '';

-- Historial completo: cada dato que se cambió, de qué valor a cuál y por qué
CREATE TABLE IF NOT EXISTS correcciones (
    id          BIGSERIAL PRIMARY KEY,
    tarima_id   BIGINT NOT NULL REFERENCES tarimas(id),
    campo       TEXT NOT NULL,
    antes       TEXT NOT NULL,
    despues     TEXT NOT NULL,
    motivo      TEXT NOT NULL,
    fecha_hora  TIMESTAMP NOT NULL DEFAULT now(),
    usuario     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS correcciones_tarima_idx ON correcciones (tarima_id);

-- ---------------------------------------------------------------------------
-- Versión 4: presentaciones en bin y lote de caja
-- ---------------------------------------------------------------------------
-- unidad 'fardo': la tarima lleva fardos_por_tarima fardos de bolsas_por_fardo bolsas
-- unidad 'caja' : igual que fardo pero en cajas (usa lote de caja en vez de bale)
-- unidad 'bin'  : un bin por etiqueta, con bolsas_por_fardo bolsas (fardos_por_tarima = 1)
ALTER TABLE presentaciones ADD COLUMN IF NOT EXISTS unidad TEXT NOT NULL DEFAULT 'fardo';
ALTER TABLE lineas  ADD COLUMN IF NOT EXISTS lote_caja TEXT NOT NULL DEFAULT '';
ALTER TABLE tarimas ADD COLUMN IF NOT EXISTS lote_caja TEXT NOT NULL DEFAULT '';

"""Conexión a PostgreSQL."""

import psycopg
from psycopg.rows import dict_row

import config


def conectar():
    """Abre una conexión. Usar con `with db.conectar() as con:`.
    Al salir del `with` se guarda (commit) o se deshace si hubo error."""
    return psycopg.connect(config.DATABASE_URL, row_factory=dict_row)

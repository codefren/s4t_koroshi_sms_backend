"""
ERP database queries for fetching packing/client data needed by XPO.

Connects to the external ERP MSSQL database (separate from the local S4T_SMS DB).
Connection is configured via ERP_DB_* environment variables.
"""
import os
import logging
import urllib
from typing import Optional
from dataclasses import dataclass

import pyodbc

logger = logging.getLogger(__name__)

ERP_SERVER   = os.getenv("DB_SERVER_KOROSHI", "LWWTEST")
ERP_DATABASE = os.getenv("DB_NAME_KOROSHI",   "S4T_ERP")
ERP_USER     = os.getenv("DB_USER_KOROSHI",   "sa")
ERP_PASSWORD = os.getenv("DB_PASSWORD_KOROSHI", "")
ERP_DRIVER   = os.getenv("ERP_DB_DRIVER",    "ODBC Driver 18 for SQL Server")


@dataclass
class PackingInfo:
    cliente:      str = ""
    documento:    str = ""
    nombre:       str = ""
    direccion:    str = ""
    cp:           str = ""
    poblacion:    str = ""
    provincia:    str = ""
    pais:         str = "ES"
    email:        str = ""
    telefono:     str = ""
    volumen:      float = 0.0
    peso_neto:    float = 0.0
    peso_bruto:   float = 0.0
    fecha:        Optional[object] = None
    cantidad:     int = 0
    ped_cli:      str = ""   # client's own purchase order number → nro_su_pedido in XPO
    cod_tienda:   str = ""   # store/branch code → DestinoCodTienda in XPO


_SQL = """
    SELECT
        a.fldIdCliente   AS Cliente,
        a.fldIdPacking   AS Documento,
        b.fldNombreSocial AS Nombre,
        b.fldDireccion   AS Direccion,
        b.fldCodPostal   AS CPostal,
        b.fldPoblacion   AS Poblacion,
        b.fldProvincia   AS Provincia,
        b.fldPais        AS Pais,
        b.fldEmail       AS Email,
        b.fldTelf1       AS Telefono,
        3                             AS NumCajas,
        d.fldVolumen   * 3            AS Volumen,
        d.fldPesoNeto  * 3            AS PesoNeto,
        d.fldPesoBruto * 3            AS PesoBruto,
        a.fldFechaPacking             AS Fecha,
        a.fldCanPack                  AS Cantidad,
        a.fldIdPedCli                 AS PedCli,
        ISNULL(e.fldSucursal, '')     AS CodTienda
    FROM tbdPacking a
        LEFT JOIN tbdClientes      b ON a.fldIdCliente = b.fldIdCliente
        LEFT JOIN tbdClientesEnvio e ON a.fldIdCliente = e.fldIdCliente,
        tbdLogisEmbalajes d
    WHERE d.fldIdEmbalaje = 'B'
      AND a.fldIdPacking  = ?
    GROUP BY
        a.fldIdCliente, a.fldIdPacking,
        b.fldNombreSocial, b.fldDireccion, b.fldCodPostal, b.fldPoblacion,
        b.fldProvincia, b.fldPais, b.fldEmail, b.fldTelf1,
        d.fldTipoEmbalaje,
        a.fldFechaPacking, a.fldCanPack, a.fldIdPedCli, e.fldSucursal,
        d.fldVolumen, d.fldPesoNeto, d.fldPesoBruto
"""


def _get_erp_connection() -> pyodbc.Connection:
    conn_str = (
        f"DRIVER={{{ERP_DRIVER}}};"
        f"SERVER={ERP_SERVER};"
        f"DATABASE={ERP_DATABASE};"
        f"UID={ERP_USER};"
        f"PWD={ERP_PASSWORD};"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=10)


def get_packing_info(packing_id: str) -> Optional[PackingInfo]:
    """
    Fetch packing + client data from the ERP database for a given packing_id.

    Returns None if the record is not found or the ERP is unreachable
    (caller should fall back to order-level data in that case).
    """
    if not ERP_DATABASE:
        logger.warning("ERP_DB_NAME not configured — skipping ERP lookup")
        return None

    try:
        conn = _get_erp_connection()
        cursor = conn.cursor()
        cursor.execute(_SQL, packing_id)
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.warning(f"No ERP packing record found for packing_id={packing_id}")
            return None

        return PackingInfo(
            cliente    = str(row.Cliente   or ""),
            documento  = str(row.Documento or ""),
            nombre     = str(row.Nombre    or ""),
            direccion  = str(row.Direccion or ""),
            cp         = str(row.CPostal   or ""),
            poblacion  = str(row.Poblacion or ""),
            provincia  = str(row.Provincia or ""),
            pais       = str(row.Pais      or "ES"),
            email      = str(row.Email     or ""),
            telefono   = str(row.Telefono  or ""),
            volumen    = float(row.Volumen   or 0),
            peso_neto  = float(row.PesoNeto  or 0),
            peso_bruto = float(row.PesoBruto or 0),
            fecha      = row.Fecha,
            cantidad   = int(row.Cantidad or 0),
            ped_cli    = str(row.PedCli    or ""),
            cod_tienda = str(row.CodTienda or ""),
        )

    except pyodbc.Error as exc:
        logger.error(f"ERP DB error fetching packing_id={packing_id}: {exc}")
        return None

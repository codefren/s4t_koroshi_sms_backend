"""
XPO Logistics SOAP Service.

Builds and sends the RegistraExpedicion SOAP request to the XPO WCF endpoint.
Called after external Packing API returns 201 on a PICKED order.
"""
import os
import logging
import requests
from datetime import datetime
from xml.sax.saxutils import escape
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── XPO endpoint config (override via env vars) ────────────────────────────────
XPO_ENDPOINT_URL = os.getenv(
    "XPO_ENDPOINT_URL",
    "http://localhost/XpoService/TTService.svc"   # TODO: set real URL in .env
)
XPO_USER        = os.getenv("XPO_USER",     "666194")
XPO_PASSWORD    = os.getenv("XPO_PASSWORD", "123qwe!E")
XPO_COD_CLIENTE = os.getenv("XPO_COD_CLIENTE", "666194")
XPO_EMAIL_ETIQUETAS = os.getenv("XPO_EMAIL_ETIQUETAS", "expediciones@koroshi.tv")


# ── Parameter dataclass ────────────────────────────────────────────────────────

@dataclass
class XpoExpedicionParams:
    """
    All dynamic fields for the XPO RegistraExpedicion request.

    Fixed fields (origin, credentials, article template) are applied
    internally by build_xpo_soap_xml().
    """
    # ── Destino ────────────────────────────────────────────────────────────────
    dest_nombre:    str = ""
    dest_direccion: str = ""
    dest_cp:        str = ""
    dest_localidad: str = ""
    dest_provincia: str = ""
    dest_pais:      str = "ES"
    dest_movil:     str = ""
    dest_email:     str = ""

    # ── Expedición ─────────────────────────────────────────────────────────────
    obs_linea1:        str = ""          # e.g. "K07 / PACKING / ORD-000123"
    referencia:        str = ""          # e.g. "PC-2024-0456 - 20260417"
    fecha_expedicion:  Optional[datetime] = None   # defaults to now

    # ── Cajas / unidades ───────────────────────────────────────────────────────
    total_cajas:    int = 1              # TotalUnidadesManipulacion + VLUCantidad
    tipo_caja:      str = "5"            # "5"=Caja  "1"=Palet

    # ── Artículo genérico ─────────────────────────────────────────────────────
    total_unidades: int = 0              # ArticuloCantidad (sum of quantity_served)

    # ── Destino (campo adicional) ──────────────────────────────────────────────
    dest_cod_tienda: str = ""   # DestinoCodTienda — store/branch code from ERP

    # ── Pesos / volúmenes (del ERP) ───────────────────────────────────────────
    peso_neto:     float = 0.0
    peso_bruto:    float = 0.0
    volumen_neto:  float = 0.0
    volumen_bruto: float = 0.0

    # ── Referencia pedido ─────────────────────────────────────────────────────
    nro_pedido_ventas: str = ""
    nro_su_pedido:     str = ""


# ── XML builder ────────────────────────────────────────────────────────────────

def build_xpo_soap_xml(params: XpoExpedicionParams) -> str:
    """
    Returns a fully formed SOAP XML string for XPO RegistraExpedicion.

    Fixed data:  origin warehouse, credentials, generic article template.
    Variable data: received via XpoExpedicionParams.
    """
    fecha = params.fecha_expedicion or datetime.now()
    fecha_str = fecha.strftime("%d/%m/%Y")

    def e(val: str) -> str:
        return escape(str(val)) if val else ""

    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="http://tempuri.org/">
  <soap:Body>
    <tns:RegistraExpedicion>

      <!-- Credenciales (fijas) -->
      <tns:UserName>{XPO_USER}</tns:UserName>
      <tns:Password>{XPO_PASSWORD}</tns:Password>
      <tns:EnviarEmail>1</tns:EnviarEmail>
      <tns:Email>{XPO_EMAIL_ETIQUETAS}</tns:Email>
      <tns:TipoRespuesta>1</tns:TipoRespuesta>
      <tns:TotalUnidadesManipulacion>{params.total_cajas}</tns:TotalUnidadesManipulacion>
      <tns:VLU></tns:VLU>
      <tns:PesoBruto>{params.peso_bruto}</tns:PesoBruto>
      <tns:PesoNeto>{params.peso_neto}</tns:PesoNeto>
      <tns:VolumenNeto>{params.volumen_neto}</tns:VolumenNeto>
      <tns:VolumenOperacional>{params.volumen_bruto}</tns:VolumenOperacional>
      <tns:Preffix></tns:Preffix>
      <tns:FechaEntrega></tns:FechaEntrega>

      <!-- Expedicion -->
      <tns:Expedicion>
        <tns:CodCliente>{XPO_COD_CLIENTE}</tns:CodCliente>

        <!-- ORIGEN (fijo — almacén Koroshi) -->
        <tns:OrigenCodTienda></tns:OrigenCodTienda>
        <tns:OrigenNombreTienda>KOROSHI</tns:OrigenNombreTienda>
        <tns:OrigenDireccion>Calle Mogoda 6-10, Pol.Ind.Cant Salvatella</tns:OrigenDireccion>
        <tns:OrigenDireccionLinea1></tns:OrigenDireccionLinea1>
        <tns:OrigenDireccionLinea2></tns:OrigenDireccionLinea2>
        <tns:OrigenCP>08210</tns:OrigenCP>
        <tns:OrigenLocalidad>Barbera del Valles</tns:OrigenLocalidad>
        <tns:OrigenProvincia>Barcelona</tns:OrigenProvincia>
        <tns:OrigenPais>ES</tns:OrigenPais>
        <tns:OrigenTelefono></tns:OrigenTelefono>
        <tns:OrigenMovil></tns:OrigenMovil>
        <tns:OrigenFax></tns:OrigenFax>
        <tns:OrigenEmail>almacen@koroshi.tv</tns:OrigenEmail>
        <tns:OrigenContactoNombre>KOROSHI</tns:OrigenContactoNombre>
        <tns:OrigenContactoTelefono>(34) 937984446</tns:OrigenContactoTelefono>
        <tns:OrigenContactoMovil>658877772</tns:OrigenContactoMovil>
        <tns:OrigenContactoEmail>almacen@koroshi.tv</tns:OrigenContactoEmail>

        <!-- DESTINO (variable) -->
        <tns:TipoDestino>1</tns:TipoDestino>
        <tns:DestinoCodTienda>{e(params.dest_cod_tienda)}</tns:DestinoCodTienda>
        <tns:DestinoNombreTienda>{e(params.dest_nombre)}</tns:DestinoNombreTienda>
        <tns:DestinoDireccion>{e(params.dest_direccion)}</tns:DestinoDireccion>
        <tns:DestinoDireccionLinea1></tns:DestinoDireccionLinea1>
        <tns:DestinoDireccionLinea2></tns:DestinoDireccionLinea2>
        <tns:DestinoCP>{e(params.dest_cp)}</tns:DestinoCP>
        <tns:DestinoLocalidad>{e(params.dest_localidad)}</tns:DestinoLocalidad>
        <tns:DestinoProvincia>{e(params.dest_provincia)}</tns:DestinoProvincia>
        <tns:DestinoPais>{e(params.dest_pais)}</tns:DestinoPais>
        <tns:DestinoTelefono></tns:DestinoTelefono>
        <tns:DestinoMovil>{e(params.dest_movil)}</tns:DestinoMovil>
        <tns:DestinoFax></tns:DestinoFax>
        <tns:DestinoEmail>{e(params.dest_email)}</tns:DestinoEmail>
        <tns:DestinoContactoNombre></tns:DestinoContactoNombre>
        <tns:DestinoContactoTelefono></tns:DestinoContactoTelefono>
        <tns:DestinoContactoMovil></tns:DestinoContactoMovil>
        <tns:DestinoContactoEmail></tns:DestinoContactoEmail>
        <tns:DestinoAltCodTienda></tns:DestinoAltCodTienda>
        <tns:DestinoAltNombreReceptor></tns:DestinoAltNombreReceptor>
        <tns:DestinoAltReceptorEmail></tns:DestinoAltReceptorEmail>
        <tns:DestinoAltReceptorTelefono></tns:DestinoAltReceptorTelefono>

        <!-- Observaciones / Referencia (variable) -->
        <tns:ObservacionesLinea1>{e(params.obs_linea1)}</tns:ObservacionesLinea1>
        <tns:ObservacionesLinea2></tns:ObservacionesLinea2>
        <tns:Peso></tns:Peso>
        <tns:Referencia>{e(params.referencia)}</tns:Referencia>
        <tns:ValorCOD></tns:ValorCOD>
        <tns:FechaExpedicion>{fecha_str}</tns:FechaExpedicion>
        <tns:EnviarEtiquetasEmail>1</tns:EnviarEtiquetasEmail>
        <tns:OrigenReferencia></tns:OrigenReferencia>
        <tns:DestinoReferencia></tns:DestinoReferencia>
      </tns:Expedicion>

      <!-- Unidades de manipulación (variable: cajas + tipo) -->
      <tns:UnidadesManipulacion>
        <tns:WSUdsManipulac_Request>
          <tns:CodigoVLU>{e(params.tipo_caja)}</tns:CodigoVLU>
          <tns:VLUCantidad>{e(params.total_unidades)}</tns:VLUCantidad>
          <tns:VLUPesoNeto>{params.peso_neto}</tns:VLUPesoNeto>
          <tns:VLUPesoBruto>{params.peso_bruto}</tns:VLUPesoBruto>
          <tns:VLUVolumenNeto>{params.volumen_neto}</tns:VLUVolumenNeto>
          <tns:VLUVolumenBruto>{params.volumen_bruto}</tns:VLUVolumenBruto>
          <tns:VLUMetrosLinealesNetos></tns:VLUMetrosLinealesNetos>
          <tns:VLUMetrosLinealesBrutos></tns:VLUMetrosLinealesBrutos>
        </tns:WSUdsManipulac_Request>
      </tns:UnidadesManipulacion>

      <!-- Artículos (fijo GENERICO, variable: cantidad total) -->
      <tns:Articulos>
        <tns:WSArticulo_Request>
          <tns:ArticuloCodigo>GENERICO</tns:ArticuloCodigo>
          <tns:ArticuloDescripcion>AGRUPACION CAJA</tns:ArticuloDescripcion>
          <tns:ArticuloCantidad>{params.total_unidades}</tns:ArticuloCantidad>
          <tns:ArticuloPesoNeto>{params.peso_neto}</tns:ArticuloPesoNeto>
          <tns:ArticuloPesoBruto>{params.peso_bruto}</tns:ArticuloPesoBruto>
          <tns:ArticuloVolumenNeto>{params.volumen_neto}</tns:ArticuloVolumenNeto>
          <tns:ArticuloReferencia></tns:ArticuloReferencia>
          <tns:ArticuloNumLinea>1</tns:ArticuloNumLinea>
          <tns:ArticuloPrecio></tns:ArticuloPrecio>
          <tns:ArticuloLote></tns:ArticuloLote>
          <tns:ArticuloUOM></tns:ArticuloUOM>
          <tns:ArticuloCodigoEAN></tns:ArticuloCodigoEAN>
        </tns:WSArticulo_Request>
      </tns:Articulos>

      <!-- Referencia pedido (variable) -->
      <tns:ReferenciaPedido>
        <tns:NroPedidoVentas></tns:NroPedidoVentas>
        <tns:NroSuPedido></tns:NroSuPedido>
      </tns:ReferenciaPedido>

    </tns:RegistraExpedicion>
  </soap:Body>
</soap:Envelope>"""

    return xml


# ── HTTP sender ────────────────────────────────────────────────────────────────

def send_xpo_expedicion(params: XpoExpedicionParams) -> dict:
    """
    Builds the SOAP XML and POSTs it to the XPO WCF endpoint.

    Returns a dict with:
        success  (bool)
        status_code (int)
        consignment_id (str)   – from XPO response if available
        raw_response (str)     – full response body for logging
        error (str | None)     – populated on failure
    """
    soap_xml = build_xpo_soap_xml(params)

    logger.info("XPO RegistraExpedicion — XML generado:")
    logger.info(f"URL: {XPO_ENDPOINT_URL}")
    logger.info(f"SOAP Body:\n{soap_xml}")

    return {
        "success":        True,
        "status_code":    None,
        "consignment_id": "",
        "raw_response":   soap_xml,
        "error":          None,
    }

    # TODO: descomentar cuando el endpoint XPO esté disponible
    # try:
    #     response = requests.post(
    #         XPO_ENDPOINT_URL,
    #         data=soap_xml.encode("utf-8"),
    #         headers={
    #             "Content-Type": "text/xml; charset=utf-8",
    #             "SOAPAction":   '"http://tempuri.org/ITTService/RegistraExpedicion"',
    #         },
    #         timeout=30,
    #     )
    #
    #     logger.info(f"XPO response — status: {response.status_code}")
    #     logger.info(f"XPO response body: {response.text}")
    #
    #     if response.status_code == 200:
    #         return {
    #             "success":        True,
    #             "status_code":    response.status_code,
    #             "consignment_id": _parse_consignment_id(response.text),
    #             "raw_response":   response.text,
    #             "error":          None,
    #         }
    #
    #     return {
    #         "success":        False,
    #         "status_code":    response.status_code,
    #         "consignment_id": None,
    #         "raw_response":   response.text,
    #         "error":          f"XPO returned HTTP {response.status_code}",
    #     }
    #
    # except requests.exceptions.RequestException as exc:
    #     error_msg = f"XPO connection error: {str(exc)}"
    #     logger.error(error_msg)
    #     return {
    #         "success":        False,
    #         "status_code":    None,
    #         "consignment_id": None,
    #         "raw_response":   None,
    #         "error":          error_msg,
    #     }


def _parse_consignment_id(xml_text: str) -> str:
    """
    Extracts ConsignmentId from XPO SOAP response.
    Returns empty string if not found.
    """
    import re
    match = re.search(r"<[^>]*ConsignmentId[^>]*>([^<]+)<", xml_text)
    return match.group(1).strip() if match else ""

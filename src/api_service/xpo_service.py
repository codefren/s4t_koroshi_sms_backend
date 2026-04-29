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
    "https://openservices-pre.fieldeas.com/apps/xpows/TTService.svc"
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

    def e(val) -> str:
        """Escape string values; numbers are formatted directly."""
        if isinstance(val, (int, float)):
            return str(val)
        return escape(str(val)) if val else ""

    # tns = http://tempuri.org/ (operation wrapper + top-level fields)
    # mc  = http://schemas.datacontract.org/2004/07/XPOTrackAndTrace.MessageContracts
    #       (children of expedicion, articulos, referenciaPedido, unidadesManipulacion)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns="http://tempuri.org/"
               xmlns:mc="http://schemas.datacontract.org/2004/07/XPOTrackAndTrace.MessageContracts">
  <soap:Header/>
  <soap:Body>
    <tns:RegistraExpedicionRequest>
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

      <tns:expedicion>
        <mc:CodCliente>{XPO_COD_CLIENTE}</mc:CodCliente>
        <mc:OrigenCodTienda></mc:OrigenCodTienda>
        <mc:OrigenNombreTienda>KOROSHI</mc:OrigenNombreTienda>
        <mc:OrigenDireccion>Calle Mogoda 6-10, Pol.Ind.Cant Salvatella</mc:OrigenDireccion>
        <mc:OrigenDireccionLinea1></mc:OrigenDireccionLinea1>
        <mc:OrigenDireccionLinea2></mc:OrigenDireccionLinea2>
        <mc:OrigenCP>08210</mc:OrigenCP>
        <mc:OrigenLocalidad>Barbera del Valles</mc:OrigenLocalidad>
        <mc:OrigenProvincia>Barcelona</mc:OrigenProvincia>
        <mc:OrigenPais>ES</mc:OrigenPais>
        <mc:OrigenTelefono></mc:OrigenTelefono>
        <mc:OrigenMovil></mc:OrigenMovil>
        <mc:OrigenFax></mc:OrigenFax>
        <mc:OrigenEmail>almacen@koroshi.tv</mc:OrigenEmail>
        <mc:OrigenContactoNombre>KOROSHI</mc:OrigenContactoNombre>
        <mc:OrigenContactoTelefono>(34) 937984446</mc:OrigenContactoTelefono>
        <mc:OrigenContactoMovil>658877772</mc:OrigenContactoMovil>
        <mc:OrigenContactoEmail>almacen@koroshi.tv</mc:OrigenContactoEmail>
        <mc:TipoDestino>1</mc:TipoDestino>
        <mc:DestinoCodTienda>{e(params.dest_cod_tienda)}</mc:DestinoCodTienda>
        <mc:DestinoNombreTienda>{e(params.dest_nombre)}</mc:DestinoNombreTienda>
        <mc:DestinoDireccion>{e(params.dest_direccion)}</mc:DestinoDireccion>
        <mc:DestinoDireccionLinea1></mc:DestinoDireccionLinea1>
        <mc:DestinoDireccionLinea2></mc:DestinoDireccionLinea2>
        <mc:DestinoCP>{e(params.dest_cp)}</mc:DestinoCP>
        <mc:DestinoLocalidad>{e(params.dest_localidad)}</mc:DestinoLocalidad>
        <mc:DestinoProvincia>{e(params.dest_provincia)}</mc:DestinoProvincia>
        <mc:DestinoPais>{e(params.dest_pais)}</mc:DestinoPais>
        <mc:DestinoTelefono></mc:DestinoTelefono>
        <mc:DestinoMovil>{e(params.dest_movil)}</mc:DestinoMovil>
        <mc:DestinoFax></mc:DestinoFax>
        <mc:DestinoEmail>{e(params.dest_email)}</mc:DestinoEmail>
        <mc:DestinoContactoNombre></mc:DestinoContactoNombre>
        <mc:DestinoContactoTelefono></mc:DestinoContactoTelefono>
        <mc:DestinoContactoMovil></mc:DestinoContactoMovil>
        <mc:DestinoContactoEmail></mc:DestinoContactoEmail>
        <mc:DestinoAltCodTienda></mc:DestinoAltCodTienda>
        <mc:DestinoAltNombreReceptor></mc:DestinoAltNombreReceptor>
        <mc:DestinoAltReceptorEmail></mc:DestinoAltReceptorEmail>
        <mc:DestinoAltReceptorTelefono></mc:DestinoAltReceptorTelefono>
        <mc:ObservacionesLinea1>{e(params.obs_linea1)}</mc:ObservacionesLinea1>
        <mc:ObservacionesLinea2></mc:ObservacionesLinea2>
        <mc:Peso></mc:Peso>
        <mc:Referencia>{e(params.referencia)}</mc:Referencia>
        <mc:ValorCOD></mc:ValorCOD>
        <mc:FechaExpedicion>{fecha_str}</mc:FechaExpedicion>
        <mc:EnviarEtiquetasEmail>1</mc:EnviarEtiquetasEmail>
        <mc:OrigenReferencia></mc:OrigenReferencia>
        <mc:DestinoReferencia></mc:DestinoReferencia>
      </tns:expedicion>

      <tns:articulos>
        <mc:WSArticulo_Request>
          <mc:ArticuloCodigo>GENERICO</mc:ArticuloCodigo>
          <mc:ArticuloDescripcion>AGRUPACION CAJA</mc:ArticuloDescripcion>
          <mc:ArticuloCantidad>{params.total_unidades}</mc:ArticuloCantidad>
          <mc:ArticuloPesoNeto>{params.peso_neto}</mc:ArticuloPesoNeto>
          <mc:ArticuloPesoBruto>{params.peso_bruto}</mc:ArticuloPesoBruto>
          <mc:ArticuloVolumenNeto>{params.volumen_neto}</mc:ArticuloVolumenNeto>
          <mc:ArticuloVolumenBruto>{params.volumen_bruto}</mc:ArticuloVolumenBruto>
          <mc:ArticuloReferencia></mc:ArticuloReferencia>
          <mc:ArticuloNumLinea>1</mc:ArticuloNumLinea>
          <mc:ArticuloPrecio></mc:ArticuloPrecio>
          <mc:ArticuloLote></mc:ArticuloLote>
          <mc:ArticuloUOM></mc:ArticuloUOM>
          <mc:ArticuloCodigoEAN></mc:ArticuloCodigoEAN>
        </mc:WSArticulo_Request>
      </tns:articulos>

      <tns:referenciaPedido>
        <mc:NroPedidoVentas>{e(params.nro_pedido_ventas)}</mc:NroPedidoVentas>
        <mc:NroSuPedido>{e(params.nro_su_pedido)}</mc:NroSuPedido>
      </tns:referenciaPedido>

      <tns:unidadesManipulacion>
        <mc:WSUdsManipulac_Request>
          <mc:CodigoVLU>{e(params.tipo_caja)}</mc:CodigoVLU>
          <mc:VLUCantidad>{params.total_cajas}</mc:VLUCantidad>
          <mc:VLUPesoNeto>{params.peso_neto}</mc:VLUPesoNeto>
          <mc:VLUPesoBruto>{params.peso_bruto}</mc:VLUPesoBruto>
          <mc:VLUVolumenNeto>{params.volumen_neto}</mc:VLUVolumenNeto>
          <mc:VLUVolumenBruto>{params.volumen_bruto}</mc:VLUVolumenBruto>
          <mc:VLUMetrosLinealesNetos></mc:VLUMetrosLinealesNetos>
          <mc:VLUMetrosLinealesBrutos></mc:VLUMetrosLinealesBrutos>
        </mc:WSUdsManipulac_Request>
      </tns:unidadesManipulacion>

    </tns:RegistraExpedicionRequest>
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

    try:
        response = requests.post(
            XPO_ENDPOINT_URL,
            data=soap_xml.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction":   '"http://tempuri.org/ITTService/RegistraExpedicion"',
            },
            timeout=30,
        )

        logger.info(f"XPO response — status: {response.status_code}")
        logger.info(f"XPO response body: {response.text}")

        if response.status_code == 200:
            return {
                "success":        True,
                "status_code":    response.status_code,
                "consignment_id": _parse_consignment_id(response.text),
                "raw_response":   response.text,
                "error":          None,
            }

        return {
            "success":        False,
            "status_code":    response.status_code,
            "consignment_id": None,
            "raw_response":   response.text,
            "error":          f"XPO returned HTTP {response.status_code}",
        }

    except requests.exceptions.RequestException as exc:
        error_msg = f"XPO connection error: {str(exc)}"
        logger.error(error_msg)
        return {
            "success":        False,
            "status_code":    None,
            "consignment_id": None,
            "raw_response":   None,
            "error":          error_msg,
        }


def _parse_consignment_id(xml_text: str) -> str:
    """
    Extracts ConsignmentId from XPO SOAP response.
    Returns empty string if not found.
    """
    import re
    match = re.search(r"<[^>]*ConsignmentID[^>]*>([^<]+)<", xml_text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

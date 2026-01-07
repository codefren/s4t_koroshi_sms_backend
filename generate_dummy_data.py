import random
from datetime import datetime, timedelta

# Configuración de productos
productos = [
    ("HA", "GORRA", ["BLACK", "NAVY", "CRUDO / OFF-WHITE"], ["UNI"]),
    ("SU", "SUDADERA", ["BLACK", "NAVY", "ROJO / RED", "PETROLEO / DARK GREEN", "CRUDO / OFF-WHITE"], ["S", "M", "L", "XL", "XXL"]),
    ("PT", "JEANS", ["AZUL OSC / DARK BLUE", "AZUL CL / LIGHT BLUE", "BLACK DENIM", "AZUL MED / MEDIUM BL"], ["28", "30", "32", "34", "36", "38", "40", "42", "44"]),
    ("JA", "CAZADORA", ["BLACK", "NAVY", "MARRON / BROWN", "KAKI / KHAKI", "VERDE / GREEN", "VINO / WINE RED"], ["S", "M", "L", "XL", "XXL", "3XL"]),
    ("TR", "JERSEY", ["BLACK", "NAVY", "ROJO / RED", "MULTICOLOR / MULTI-C", "CRUDO / OFF-WHITE"], ["S", "M", "L", "XL"]),
    ("VS", "VESTIDO", ["BLACK", "NAVY", "VERDE / GREEN", "VINO / WINE RED"], ["S", "M", "L", "XL"]),
    ("ML", "CAMISETA MANGA LARGA", ["BLACK", "NAVY", "CRUDO / OFF-WHITE", "AZUL / BLUE"], ["S", "M", "L", "XL", "XXL"]),
    ("BI", "BISUTERIA", ["ORO / GOLD", "PLATA / SILVER"], ["UNI"]),
    ("PL", "POLO", ["BLACK", "NAVY", "AZUL / BLUE", "CRUDO / OFF-WHITE"], ["S", "M", "L", "XL"]),
]

descripciones = {
    "HA": ["GORRA UNISEX", "COMPLEMENTO UNISEX GORRA", "CAP BASIC"],
    "SU": ["SUDADERA CAPUCHA", "SUDADERA OVERSIZE", "SUDADERA CREWNECK", "SUDADERA HIGH NECK", "SUDADERA ZIP"],
    "PT": ["JEANS SLIM FIT", "JEANS REGULAR FIT", "JEANS SKINNY", "JEANS BOYFRIEND", "JEANS CARGO", "JEANS WIDE LEG"],
    "JA": ["CAZADORA EFECTO PIEL", "CAZADORA ACOLCHADA", "CHAQUETA ACOLCHADA CAPUCHA", "BOMBER", "CHAQUETA DENIM"],
    "TR": ["JERSEY PUNTO", "JERSEY CUELLO ALTO", "CARDIGAN PUNTO", "JERSEY JACQUARD", "JERSEY RAYAS"],
    "VS": ["VESTIDO CORTO", "VESTIDO MIDI", "VESTIDO LARGO", "VESTIDO CAMISERO"],
    "ML": ["CAMISETA MANGA LARGA", "CAMISETA MANGA LARGA BASICA", "POLO MANGA LARGA"],
    "BI": ["PENDIENTES LARGOS", "COLLAR COLGANTE", "PULSERA", "ANILLO", "PENDIENTES ARO"],
    "PL": ["POLO MANGA LARGA", "POLO BASICO", "POLO BORDADO"],
}

# Órdenes existentes
ordenes = [
    (1111087089, "00000042", "K42 - MADRID", "000053", "20251216"),
    (1111087090, "00000043", "K43 - BARCELONA", "000054", "20251216"),
    (1111087091, "00000044", "K44 - VALENCIA", "000055", "20251216"),
    (1111087092, "00000045", "K45 - SEVILLA", "000056", "20251216"),
    (1111087093, "00000046", "K46 - BILBAO", "000057", "20251216"),
    (1111087094, "00000047", "K47 - ZARAGOZA", "000058", "20251216"),
    (1111087095, "00000048", "K48 - MALAGA", "000059", "20251217"),
    (1111087096, "00000049", "K49 - MURCIA", "000060", "20251217"),
    (1111087097, "00000050", "K50 - ALICANTE", "000061", "20251217"),
    (1111087098, "00000051", "K51 - CORDOBA", "000062", "20251217"),
]

talla_posicion = {
    "UNI": 1, "S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5, "3XL": 6,
    "28": 1, "30": 2, "32": 3, "34": 4, "36": 5, "38": 6, "40": 7, "42": 8, "44": 9
}

color_codes = {
    "BLACK": "000003",
    "NAVY": "000039",
    "ROJO / RED": "000015",
    "PETROLEO / DARK GREEN": "000073",
    "CRUDO / OFF-WHITE": "000030",
    "AZUL OSC / DARK BLUE": "000302",
    "AZUL CL / LIGHT BLUE": "000300",
    "BLACK DENIM": "000306",
    "AZUL MED / MEDIUM BL": "000301",
    "MARRON / BROWN": "000019",
    "KAKI / KHAKI": "000014",
    "VERDE / GREEN": "000010",
    "VINO / WINE RED": "000158",
    "MULTICOLOR / MULTI-C": "000323",
    "AZUL / BLUE": "000006",
    "ORO / GOLD": "000046",
    "PLATA / SILVER": "000047",
    "MARRON OSCURO / DARK": "000181",
    "GRIS PERLA / PEARL G": "000130",
}

# Generar ubicaciones
ubicaciones = [f"{str(i).zfill(2)}-{str(j).zfill(3)}" for i in range(1, 21) for j in range(1, 61)]

def generar_ean():
    """Genera un EAN-13 realista"""
    return f"8445962{random.randint(700000, 999999)}"

def generar_articulo(tipo, num):
    """Genera un código de artículo"""
    return f"26{random.randint(11, 23)}{tipo}{str(num).zfill(2)}"

def generar_item(orden_info, item_num):
    """Genera un item completo"""
    orden, cliente, nombre_cliente, operario, fecha = orden_info
    
    # Seleccionar producto aleatorio
    tipo, cat, colores, tallas = random.choice(productos)
    color = random.choice(colores)
    talla = random.choice(tallas)
    descripcion = random.choice(descripciones[tipo])
    
    ean = generar_ean()
    ubicacion = random.choice(ubicaciones)
    articulo = generar_articulo(tipo, random.randint(1, 50))
    color_code = color_codes.get(color, "000003")
    posicion_talla = talla_posicion.get(talla, 1)
    temporada = "V26"
    cantidad = random.randint(1, 3)
    servida = cantidad if random.random() > 0.15 else random.randint(0, cantidad)
    status = "S" if servida == cantidad else "D"
    
    # Generar hora aleatoria
    hora_base = random.randint(8, 17)
    minuto = random.randint(0, 59)
    hora = f"{str(hora_base).zfill(2)}:{str(minuto).zfill(2)}"
    
    caja = f"CJ{random.randint(304450, 304500):09d}"
    
    return f"{ean};{ubicacion};{articulo};{color_code};{talla};{posicion_talla};{descripcion};{color};{temporada};;{orden};{cliente};{nombre_cliente};{cantidad};{servida};{operario};{status};{fecha};{hora};{caja}"

# Generar 150 items distribuidos entre las 10 órdenes
items_por_orden = 15  # 15 items por orden = 150 total
print("ean;ubicación;articulo;color;talla;posiciontalla;descripcion producto;descripcion color;temporada;;no.orden;cliente;nombre cliente;cantidad;servida;operario;status;fecha;hora;caja")

for orden_info in ordenes:
    for i in range(items_por_orden):
        print(generar_item(orden_info, i))

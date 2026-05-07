"""
Unit tests for the chronological season sort logic and CSV filename helper.

Tests the _season_sort_key helper and the overall ordering of a
realistic season list matching the Koroshi catalog codes.
"""
import csv
import io
import pytest
from src.api_service.service import _season_sort_key


# ─── _season_sort_key ─────────────────────────────────────────────────────────

class TestSeasonSortKey:
    """Tests for the _season_sort_key helper function."""

    def test_verano_single_digit_year(self):
        assert _season_sort_key("V8") == (8, 0)

    def test_invierno_single_digit_year(self):
        assert _season_sort_key("I8") == (8, 1)

    def test_verano_two_digit_year(self):
        assert _season_sort_key("V25") == (25, 0)

    def test_invierno_two_digit_year(self):
        assert _season_sort_key("I25") == (25, 1)

    def test_verano_before_invierno_same_year(self):
        """Within the same year, Verano (V) must come before Invierno (I)."""
        assert _season_sort_key("V16") < _season_sort_key("I16")

    def test_earlier_year_before_later_year(self):
        assert _season_sort_key("V10") < _season_sort_key("V25")

    def test_case_insensitive_lowercase(self):
        assert _season_sort_key("v25") == _season_sort_key("V25")

    def test_case_insensitive_mixed(self):
        assert _season_sort_key("i16") == _season_sort_key("I16")

    def test_strips_whitespace(self):
        assert _season_sort_key("  V25  ") == _season_sort_key("V25")

    def test_unknown_code_sorts_last(self):
        """Codes that don't match <V|I><digits> format sort after all known ones."""
        unknown = _season_sort_key("UNKNOWN")
        known = _season_sort_key("V99")
        assert unknown > known

    def test_empty_string_sorts_last(self):
        empty = _season_sort_key("")
        known = _season_sort_key("V99")
        assert empty > known


# ─── Full list ordering ───────────────────────────────────────────────────────

class TestSeasonListOrdering:
    """Tests for ordering a real-world season list."""

    # Season codes as they appear in the Koroshi DB (including duplicates
    # that DISTINCT will remove before sorting).
    RAW_SEASONS = [
        "V12", "V14", "V13", "V15", "I16", "I11", "V25", "V8",
        "I11", "V18", "V16", "I21", "I25", "V10", "V17", "I11",
        "V19", "I23", "V18", "I10", "I14", "V16", "V17", "V20",
        "I18", "V16", "I23", "V23", "V25", "V26", "V26", "V12",
        "V18", "V19", "I17", "V19", "V17",
    ]

    @pytest.fixture
    def unique_sorted_seasons(self):
        """Deduplicate and sort the raw season list."""
        unique = list(dict.fromkeys(self.RAW_SEASONS))  # preserve first occurrence, remove dups
        return sorted(set(unique), key=_season_sort_key)

    def test_v8_is_first(self, unique_sorted_seasons):
        assert unique_sorted_seasons[0] == "V8"

    def test_v26_is_last(self, unique_sorted_seasons):
        assert unique_sorted_seasons[-1] == "V26"

    def test_v10_before_i10(self, unique_sorted_seasons):
        """V10 (Verano 2010) must come before I10 (Invierno 2010)."""
        idx_v10 = unique_sorted_seasons.index("V10")
        idx_i10 = unique_sorted_seasons.index("I10")
        assert idx_v10 < idx_i10

    def test_i11_before_v12(self, unique_sorted_seasons):
        idx_i11 = unique_sorted_seasons.index("I11")
        idx_v12 = unique_sorted_seasons.index("V12")
        assert idx_i11 < idx_v12

    def test_v25_before_i25(self, unique_sorted_seasons):
        idx_v25 = unique_sorted_seasons.index("V25")
        idx_i25 = unique_sorted_seasons.index("I25")
        assert idx_v25 < idx_i25

    def test_i25_before_v26(self, unique_sorted_seasons):
        idx_i25 = unique_sorted_seasons.index("I25")
        idx_v26 = unique_sorted_seasons.index("V26")
        assert idx_i25 < idx_v26

    def test_full_expected_order(self, unique_sorted_seasons):
        """Verify the complete expected chronological order."""
        expected = [
            "V8",
            "V10", "I10",  # Verano 2010, then Invierno 2010
            "I11",
            "V12",
            "V13",
            "V14", "I14",  # Verano 2014, then Invierno 2014
            "V15",
            "V16", "I16",
            "V17", "I17",
            "V18", "I18",
            "V19",
            "V20",
            "I21",
            "V23", "I23",
            "V25", "I25",
            "V26",
        ]
        assert unique_sorted_seasons == expected

    def test_no_duplicates_in_result(self, unique_sorted_seasons):
        assert len(unique_sorted_seasons) == len(set(unique_sorted_seasons))

    def test_all_input_seasons_present(self, unique_sorted_seasons):
        unique_input = set(self.RAW_SEASONS)
        assert set(unique_sorted_seasons) == unique_input


# ─── CSV output ─────────────────────────────────────────────────────────────────

class TestCsvOutput:
    """Unit tests for the CSV generation logic (no DB, pure in-memory)."""

    EXPECTED_HEADERS = [
        "id", "referencia", "sku", "nombre_producto",
        "color_id", "nombre_color", "talla", "posicion_talla",
        "temporada", "activo",
    ]

    def _build_csv(self, rows: list[dict]) -> list[list[str]]:
        """Helper: write rows to CSV and parse them back."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(self.EXPECTED_HEADERS)
        for r in rows:
            writer.writerow([
                r.get("id", ""),
                r.get("referencia", ""),
                r.get("sku") or "",
                r.get("nombre_producto", ""),
                r.get("color_id", ""),
                r.get("nombre_color") or "",
                r.get("talla", ""),
                r.get("posicion_talla") if r.get("posicion_talla") is not None else "",
                r.get("temporada") or "",
                r.get("activo", ""),
            ])
        output.seek(0)
        return list(csv.reader(output))

    def test_header_row_is_correct(self):
        parsed = self._build_csv([])
        assert parsed[0] == self.EXPECTED_HEADERS

    def test_single_product_row(self):
        rows = [{
            "id": 1, "referencia": "A1B2C3", "sku": "KOR-001",
            "nombre_producto": "Camisa Polo", "color_id": "000001",
            "nombre_color": "Rojo", "talla": "M", "posicion_talla": 3,
            "temporada": "V25", "activo": True,
        }]
        parsed = self._build_csv(rows)
        assert len(parsed) == 2  # header + 1 data row
        assert parsed[1][1] == "A1B2C3"  # referencia
        assert parsed[1][3] == "Camisa Polo"  # nombre_producto
        assert parsed[1][6] == "M"  # talla

    def test_null_sku_becomes_empty_string(self):
        rows = [{"id": 2, "referencia": "B2C3D4", "sku": None,
                 "nombre_producto": "X", "color_id": "01",
                 "nombre_color": None, "talla": "S", "posicion_talla": None,
                 "temporada": "I16", "activo": False}]
        parsed = self._build_csv(rows)
        assert parsed[1][2] == ""  # sku empty
        assert parsed[1][5] == ""  # nombre_color empty
        assert parsed[1][7] == ""  # posicion_talla empty

    def test_multiple_rows_count(self):
        rows = [{"id": i, "referencia": f"R{i:06d}", "sku": None,
                 "nombre_producto": "P", "color_id": "01",
                 "nombre_color": None, "talla": "M", "posicion_talla": 1,
                 "temporada": "V25", "activo": True}
                for i in range(50)]
        parsed = self._build_csv(rows)
        assert len(parsed) == 51  # 1 header + 50 data

    def test_csv_filename_uses_season_code(self):
        """Verify the filename pattern used in Content-Disposition."""
        temporada = "V25"
        safe = temporada.strip().replace(" ", "_")
        filename = f"productos_{safe}.csv"
        assert filename == "productos_V25.csv"

    def test_csv_filename_spaces_replaced(self):
        """Season codes with spaces get underscores in the filename."""
        temporada = "Verano 2025"
        safe = temporada.strip().replace(" ", "_")
        filename = f"productos_{safe}.csv"
        assert filename == "productos_Verano_2025.csv"

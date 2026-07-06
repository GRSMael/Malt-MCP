from malt_mcp_server.scraping.profile import _parse_int, _parse_rate


class TestParseRate:
    def test_euro_per_day(self):
        assert _parse_rate("500 EUR/jour") == 500

    def test_euro_symbol(self):
        assert _parse_rate("750€/j") == 750

    def test_with_spaces(self):
        assert _parse_rate("1 200 EUR/jour") == 1200

    def test_no_number(self):
        assert _parse_rate("TBD") is None

    def test_with_decimals(self):
        assert _parse_rate("500.00 EUR/jour") == 500

    def test_with_comma_decimal(self):
        assert _parse_rate("750,00€/j") == 750

    def test_empty(self):
        assert _parse_rate("") is None


class TestParseInt:
    def test_simple(self):
        assert _parse_int("42") == 42

    def test_in_text(self):
        assert _parse_int("12 missions") == 12

    def test_no_number(self):
        assert _parse_int("none") is None

    def test_empty(self):
        assert _parse_int("") is None

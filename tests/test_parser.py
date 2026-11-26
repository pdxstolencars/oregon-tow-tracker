import unittest
from pathlib import Path
from towtracker.parser import parse_vehicle_html, ParseError
from towtracker.normalize import classify_reason, normalize_agency, oregon_scope, vin_info
BASE = Path(__file__).parent / "fixtures"

class ParserTests(unittest.TestCase):
    def test_table_fixture(self):
        record = parse_vehicle_html((BASE / "oregon_table.html").read_text(), 9994704)
        self.assertEqual(record["geo_scope"], "include")
        self.assertEqual(record["reason_category"], "stolen_recovery")
        self.assertEqual(record["agency"], "PPB")
        self.assertEqual(record["license_plate"], "DEMO123")
        self.assertEqual(record["license_state"], "OR")
        self.assertEqual(record["vin_last4"], "4567")
        self.assertFalse(record["vin"])
        self.assertEqual(record["tow_company_address"], "100 Example Street, Portland, OR 97214")
        self.assertEqual(record["tow_company_phone"], "+15030000000")
        self.assertEqual(record["fee_details"], [{"label": "Impound Fee Standard", "amount": "$120.00"}, {"label": "Storage Daily Rate", "amount": "$35.50"}])
        self.assertTrue(record["towed_at"].startswith("2026-11-25T10:42"))
    def test_string_fixture(self):
        record = parse_vehicle_html((BASE / "oregon_strings.html").read_text(), 9994705)
        self.assertEqual(record["geo_scope"], "include")
        self.assertEqual(record["license_state"], "WA")
        self.assertEqual(record["reason_category"], "impound")
        self.assertEqual(record["agency"], "MCSO")
    def test_actual_field_pattern_from_screenshot(self):
        record = parse_vehicle_html((BASE / "oregon_private_property.html").read_text(), 9994715)
        self.assertEqual(record["tr_number"], "P3889871")
        self.assertEqual(record["license_plate"], "066CTX")
        self.assertEqual(record["license_state"], "OR")
        self.assertEqual(record["vin_masked"], "************3759")
        self.assertEqual(record["vin_last4"], "3759")
        self.assertEqual(record["reason_category"], "private_property")
        self.assertEqual(record["agency"], "OTHER")
        self.assertEqual(record["geo_evidence"], "oregon_yard_only")
        self.assertEqual(record["tow_company"], "21ST CENTURY TOWING")
        self.assertEqual(record["tow_company_address"], "8510 N Kerby Ave, Portland, OR")
        self.assertEqual(record["status"], "Please call +15032837788")
        self.assertTrue(record["towed_at"].startswith("2026-11-25T16:29"))
    def test_non_oregon(self):
        self.assertEqual(oregon_scope("360 Hooker St", "5160 York Street, Denver, CO")[0], "exclude")
        self.assertEqual(oregon_scope("Portland, OR", "Seattle, WA")[0], "include")
        self.assertEqual(oregon_scope("Seattle, WA", "Portland, OR")[0], "exclude")
        self.assertEqual(oregon_scope("Dallas, TX", "Portland, OR")[0], "exclude")
        self.assertEqual(oregon_scope("Chicago, Illinois", "Portland, OR")[0], "exclude")
        self.assertEqual(oregon_scope("Unknown Street", "Unknown Lot")[0], "unconfirmed")
        self.assertEqual(oregon_scope("Unknown Street", "Unknown Lot", "MCSO"), ("include", "oregon_agency_only"))
        self.assertEqual(oregon_scope("Seattle, WA", "Portland, OR", "PPB")[0], "exclude")
    def test_stolen_is_explicit(self):
        self.assertEqual(classify_reason("IMPOUND Impounded Vehicle"), "impound")
        self.assertEqual(classify_reason("STOLEN AUTO"), "stolen_recovery")
        self.assertEqual(classify_reason("TRC 7.2.46 CONSTRUCTION ZONE"), "parking")
        self.assertEqual(classify_reason("PPI PRVT PROP IMPOUND"), "private_property")
    def test_agencies(self):
        self.assertEqual(normalize_agency("TriMet Transit Police"), "TRIMET")
        self.assertEqual(normalize_agency("Port of Portland Police"), "PORT_POLICE")
    def test_vin(self):
        self.assertEqual(vin_info("**********5595"), ("", "5595"))
        self.assertEqual(vin_info("1HGCM82633A004352"), ("1HGCM82633A004352", "4352"))
    def test_unexpected_html_fails_closed(self):
        with self.assertRaises(ParseError):
            parse_vehicle_html("<html><body><h1>Blocked</h1></body></html>" * 5, 123)
if __name__ == "__main__":
    unittest.main()

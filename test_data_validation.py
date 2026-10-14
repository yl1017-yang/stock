import unittest

from data_validation import validate_snapshot


class SnapshotValidationTests(unittest.TestCase):
    def test_missing_tab_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'us_ndq'):
            validate_snapshot([{'category': 'market_status'}], [{'category': 'us_ndq'}])

    def test_failed_domestic_candles_are_rejected(self):
        with self.assertRaisesRegex(ValueError, '일봉'):
            validate_snapshot([{'category': 'domestic_theme', 'change_1m': 'N/A'}])

    def test_optional_missing_metrics_are_allowed(self):
        validate_snapshot([
            {'category': 'domestic_theme', 'change_1m': '+2%', 'per': 'N/A'},
            {'category': 'yang_stock', 'change_1m': 'N/A'},
        ], [{'category': 'yang_stock'}])

    def test_empty_snapshot_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_snapshot([])


if __name__ == '__main__':
    unittest.main()

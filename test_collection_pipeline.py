import ast
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from data_validation import collect_tab


class CollectionPipelineTests(unittest.TestCase):
    def test_failure_preserves_rows_and_original_timestamp_across_retries(self):
        old = {'category': 'domestic_value', 'time': '2026-10-23 15:40', 'change_1m': '+3%'}
        rows, status = collect_tab('domestic_value', lambda: [], [old], '2026-10-26 15:40')
        self.assertEqual(rows, [old])
        self.assertEqual(status['state'], 'stale')
        previous = rows + [{'category': 'collection_status', 'tabs': {'domestic_value': status}}]
        _, retried = collect_tab('domestic_value', lambda: [], previous, '2026-10-27 15:40')
        self.assertEqual(retried['last_success'], old['time'])
        self.assertEqual(retried['attempted_at'], '2026-10-27 15:40')

    def test_failed_candles_keep_old_data_and_recovery_clears_error(self):
        old = {'category': 'domestic_theme', 'change_1m': '+1%'}
        rows, status = collect_tab('domestic_theme', lambda: [
            {'category': 'domestic_theme', 'change_1m': 'N/A'}], [old], 'now')
        self.assertEqual(rows, [old])
        self.assertEqual(status['state'], 'stale')
        new = {'category': 'domestic_theme', 'change_1m': '+5%'}
        rows, status = collect_tab('domestic_theme', lambda: [new], [old], 'later')
        self.assertEqual(rows, [new])
        self.assertEqual(status['state'], 'ok')
        self.assertEqual(status['error'], '')
        self.assertEqual(status['last_success'], 'later')

    def test_first_failure_without_previous_data(self):
        rows, status = collect_tab('us_sp', Mock(side_effect=RuntimeError('offline')), [], 'now')
        self.assertEqual(rows, [])
        self.assertEqual(status['state'], 'unavailable')
        self.assertEqual(status['last_success'], '')

    def test_market_failure_keeps_old_market_status(self):
        old = {'category': 'market_status', 'market_status': [{'flags': []}]}
        rows, status = collect_tab('market_status', lambda: [
            {'category': 'market_status', 'market_status': [{'flags': ['수집실패']}]}], [old], 'now')
        self.assertEqual(rows, [old])
        self.assertEqual(status['state'], 'stale')

    def test_main_saves_successful_tabs_despite_other_failures(self):
        # Execute only main to avoid network/login side effects during imports.
        source = Path(__file__).with_name('main.py').read_text(encoding='utf-8')
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'main')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            snapshot = Path(directory) / 'data.json'
            old = [{'category': category, 'code': 'OLD', 'time': '2026-10-23 15:40',
                    'change_1m': '+1%'}
                   for category in ('domestic_theme', 'domestic_value', 'us_sp', 'us_ndq', 'us_rsl')]
            snapshot.write_text(json.dumps(old), encoding='utf-8')
            scan = Mock(side_effect=lambda tickers, label, sectors: [
                {'category': 'us_sp', 'code': 'NEW'}] if label == 'S&P 500' else [])
            namespace = dict(
                __file__=str(Path(directory) / 'main.py'), os=os, Path=Path,
                datetime=datetime, timedelta=timedelta, collect_tab=collect_tab,
                DOMESTIC_OHLCV_CACHE={},
                get_us_hot_theme_stocks=Mock(side_effect=RuntimeError('offline')),
                get_index_tickers=Mock(return_value=['TEST']),
                scan_us_tickers=scan, get_us_leading_sectors=Mock(return_value=[]),
                get_market_status_item=Mock(side_effect=RuntimeError('offline')))
            exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
            with patch.dict(os.environ, {'KRX_ID': '', 'KRX_PW': ''}):
                namespace['main']()
                saved = json.loads(snapshot.read_text(encoding='utf-8'))
                self.assertEqual(next(row for row in saved if row['category'] == 'us_sp')['code'], 'NEW')
                self.assertEqual(next(row for row in saved if row['category'] == 'domestic_value')['code'], 'OLD')
                statuses = saved[-1]['tabs']
                self.assertEqual(statuses['us_sp']['state'], 'ok')
                self.assertEqual(statuses['us_theme']['state'], 'unavailable')
                # A following run where everything fails still persists old rows and failure status.
                scan.side_effect = RuntimeError('offline')
                namespace['main']()
            retried = json.loads(snapshot.read_text(encoding='utf-8'))
            self.assertEqual(retried[:-1], saved[:-1])
            self.assertEqual(retried[-1]['tabs']['us_sp']['last_success'], statuses['us_sp']['last_success'])
            self.assertTrue(all(tab['state'] != 'ok' for tab in retried[-1]['tabs'].values()))
            self.assertFalse(snapshot.with_suffix('.json.tmp').exists())


if __name__ == '__main__':
    unittest.main()

import ast
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd


class DomesticOhlcvTests(unittest.TestCase):
    def setUp(self):
        # Load the lookup alone so unit tests never trigger pykrx login on import.
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'get_domestic_ohlcv')
        self.stock = SimpleNamespace(get_market_ohlcv=Mock())
        self.cache = {}
        namespace = dict(os=os, pd=pd, datetime=datetime, timedelta=timedelta,
                         stock=self.stock, DOMESTIC_OHLCV_CACHE=self.cache)
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'main.py', 'exec'), namespace)
        self.lookup = namespace['get_domestic_ohlcv']
        self.env = patch.dict(os.environ, {'KRX_ID': 'test', 'KRX_PW': 'test'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def candles(self):
        return pd.DataFrame({'시가': [1, 2], '고가': [2, 3], '저가': [1, 1],
                             '종가': [2, 2], '거래량': [10, 20]},
                            index=pd.to_datetime(['2026-10-23', '2026-10-22']))

    def test_adjusted_sorted_and_isolated_cache(self):
        self.stock.get_market_ohlcv.return_value = self.candles()
        result = self.lookup('005930')
        self.assertTrue(result.index.is_monotonic_increasing)
        self.assertTrue(self.stock.get_market_ohlcv.call_args.kwargs['adjusted'])
        result.iloc[0, 0] = 999
        self.assertNotEqual(self.lookup('005930').iloc[0, 0], 999)
        self.stock.get_market_ohlcv.assert_called_once()

    def test_failed_request_can_be_retried(self):
        self.stock.get_market_ohlcv.side_effect = [RuntimeError('offline'), self.candles()]
        self.assertTrue(self.lookup('005930').empty)
        self.assertNotIn('005930', self.cache)
        self.assertFalse(self.lookup('005930').empty)

    def test_empty_or_malformed_data_not_cached(self):
        for response in (pd.DataFrame(), pd.DataFrame({'종가': [1]})):
            self.stock.get_market_ohlcv.return_value = response
            self.assertTrue(self.lookup('005930').empty)
            self.assertNotIn('005930', self.cache)

    def test_missing_credentials_do_not_request(self):
        with patch.dict(os.environ, {'KRX_PW': ''}):
            with self.assertRaisesRegex(RuntimeError, 'KRX_ID'):
                self.lookup('005930')
        self.stock.get_market_ohlcv.assert_not_called()


if __name__ == '__main__':
    unittest.main()

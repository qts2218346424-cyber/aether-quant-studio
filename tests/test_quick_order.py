from src.paths import load_frontend_bundle_text
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from trader import Trader
import app as main_app
from fastapi.testclient import TestClient

class QuickOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_rank_order_preview_custom_leverage_and_margin(self):
        trader = Trader()
        trader.client = MagicMock()
        trader.client.get_account = AsyncMock(return_value={'totalWalletBalance': '250.0'})
        trader.client.clamp_leverage = AsyncMock(return_value=(10, 50))
        trader.client.quantity_for_notional = AsyncMock(return_value=5.0)

        with patch.object(trader, '_one_click_analysis', new=AsyncMock()) as mock_analysis:
            mock_analysis.return_value = {
                'signal': 1,
                'score': 85,
                'reason': 'Strong momentum',
                'indicators': {'price': 100.0, 'atr': 2.5},
                'factors': ['突破均线'],
            }

            preview = await trader.rank_order_preview('BTCUSDT', leverage=10, margin=50.0, side='SHORT')

            self.assertTrue(preview['ok'])
            self.assertEqual(preview['symbol'], 'BTCUSDT')
            self.assertEqual(preview['side'], 'SHORT')
            self.assertEqual(preview['side_cn'], '做空')
            self.assertEqual(preview['leverage'], 10)
            self.assertEqual(preview['margin'], 50.0)
            self.assertEqual(preview['notional'], 500.0)
            self.assertEqual(preview['qty'], 5.0)

    async def test_rank_order_preview_account_401_graceful_fallback(self):
        trader = Trader()
        trader.client = MagicMock()
        trader.client.get_account = AsyncMock(side_effect=Exception("Binance API Error 401: {'code': -2015, 'msg': 'Invalid API-key'}"))
        trader.client.clamp_leverage = AsyncMock(return_value=(5, 20))
        trader.client.quantity_for_notional = AsyncMock(return_value=2.0)

        with patch.object(trader, '_one_click_analysis', new=AsyncMock()) as mock_analysis:
            mock_analysis.return_value = {
                'signal': 1,
                'score': 80,
                'reason': 'Breakout',
                'indicators': {'price': 50.0, 'atr': 1.0},
                'factors': ['多头放量'],
            }

            # Should not throw exception despite 401
            preview = await trader.rank_order_preview('SOLUSDT', leverage=5, margin=20.0)
            self.assertTrue(preview['ok'])
            self.assertEqual(preview['symbol'], 'SOLUSDT')
            self.assertEqual(preview['leverage'], 5)
            self.assertEqual(preview['margin'], 20.0)
            self.assertEqual(preview['notional'], 100.0)

    async def test_rank_one_click_open_custom_parameters(self):
        trader = Trader()
        with patch.object(trader, 'rank_order_preview', new=AsyncMock()) as mock_prev, \
             patch.object(trader, '_execute_signal', new=AsyncMock()) as mock_exec:

            mock_prev.return_value = {
                'ok': True,
                'symbol': 'ETHUSDT',
                'side': 'SHORT',
                'price': 3000.0,
                'leverage': 8,
                'margin': 40.0,
                'notional': 320.0,
                'qty': 0.106,
                'sl': 3150.0,
                'tp1': 2800.0,
                'tp2': 2700.0,
                'score': 90,
                'reason': 'Bearish divergence',
                'action': 'SELL',
            }

            mock_exec.return_value = {
                'ok': True,
                'symbol': 'ETHUSDT',
                'side': 'SHORT',
                'leverage': 8,
                'notional': 320.0,
                'sl': 3120.0,
                'tp': 2850.0,
                'order_id': 987654,
                'status': 'FILLED',
            }

            res = await trader.rank_one_click_open(
                symbol='ETHUSDT',
                leverage=8,
                margin=40.0,
                side='SHORT',
                sl=3120.0,
                tp=2850.0
            )

            self.assertNotIn('error', res)
            self.assertEqual(res['symbol'], 'ETHUSDT')
            self.assertEqual(res['side'], 'SHORT')
            self.assertEqual(res['leverage'], 8)
            self.assertEqual(res['notional'], 320.0)
            self.assertEqual(res['sl'], 3120.0)
            self.assertEqual(res['tp'], 2850.0)

            mock_exec.assert_called_once()
            args, kwargs = mock_exec.call_args
            candidate = kwargs.get('candidate_context', {})
            self.assertEqual(candidate.get('custom_leverage'), 8)
            self.assertEqual(candidate.get('custom_notional'), 320.0)
            self.assertEqual(candidate.get('recommendation', {}).get('sl'), 3120.0)
            self.assertEqual(candidate.get('recommendation', {}).get('tp1'), 2850.0)

    def test_api_rank_preview_and_one_click_routes(self):
        client = TestClient(main_app.app)
        with patch.object(main_app.trader, 'rank_order_preview', new=AsyncMock()) as mock_preview, \
             patch.object(main_app.trader, 'rank_one_click_open', new=AsyncMock()) as mock_open:

            mock_preview.return_value = {
                'ok': True,
                'symbol': 'BTCUSDT',
                'side': 'LONG',
                'price': 60000.0,
                'leverage': 10,
                'margin': 100.0,
                'notional': 1000.0,
                'qty': 0.016
            }

            resp = client.get('/api/rank_preview?symbol=BTCUSDT&leverage=10&margin=100&side=LONG')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['leverage'], 10)
            self.assertEqual(data['margin'], 100.0)

            mock_open.return_value = {
                'symbol': 'BTCUSDT',
                'side': 'LONG',
                'leverage': 10,
                'qty': '0.016',
                'notional': 1000.0,
                'sl': 58000.0,
                'tp': 64000.0
            }
            post_resp = client.post('/api/rank_one_click', json={
                'symbol': 'BTCUSDT',
                'leverage': 10,
                'margin': 100,
                'side': 'LONG',
                'sl': 58000.0,
                'tp': 64000.0
            })
            self.assertEqual(post_resp.status_code, 200)
            res_data = post_resp.json()
            self.assertEqual(res_data['symbol'], 'BTCUSDT')
            self.assertEqual(res_data['leverage'], 10)
            self.assertEqual(res_data['sl'], 58000.0)

    def test_index_html_contains_resizable_workspace_splitters(self):
        html = load_frontend_bundle_text()

        # Verify Splitter DOM elements exist
        self.assertIn('id="splitter-side"', html)
        self.assertIn('id="splitter-bottom"', html)
        self.assertIn('id="splitter-top"', html)

        # Verify CSS variables for resizable panels
        self.assertIn('--side-panel-width', html)
        self.assertIn('--bottom-panel-height', html)
        self.assertIn('--splitter-size', html)

        # Verify JS resizing and collapse engine
        self.assertIn('toggleSidePanelCollapse', html)
        self.assertIn('toggleBottomPanelCollapse', html)
        self.assertIn('toggleMetricStripCollapse', html)
        self.assertIn('triggerAllChartsResize', html)


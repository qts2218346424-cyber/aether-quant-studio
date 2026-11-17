"""Unit tests for TypeSafe Jev (System One) Decision Engine."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from typesafe_engine import TypeSafeDecisionEngine, TypeSafeStateBuilder


class TestTypeSafeEngine(unittest.TestCase):
    def test_state_builder(self):
        candidate_context = {
            "base_score": 62.5,
            "pattern": "连续阳线(强势上攻)",
            "strategy_factors": ["EMA ribbon bullish stack", "Volume expansion > 2x"],
            "htf_aligned": True,
            "indicators": {"rsi": 62.0, "macd_hist": 2.5, "atr": 1.2},
            "smart_money": {"intent": "拉升", "score": 25.0},
            "liquidity": {"quote_volume_24h": 50000000.0, "spread_bps": 1.5},
        }
        state = TypeSafeStateBuilder.build_state(
            symbol="BTCUSDT",
            candidate_signal=1,
            price=90000.0,
            candidate_context=candidate_context,
            recent_closes=[88000.0, 88500.0, 89000.0, 89500.0, 90000.0],
            funding_rate=0.0001,
        )

        self.assertEqual(state["asset"]["symbol"], "BTCUSDT")
        self.assertEqual(state["candidate_setup"]["proposed_direction"], "LONG")
        self.assertEqual(state["candidate_setup"]["quantitative_base_score"], 62.5)
        self.assertIn("Consecutive green candles", state["candidate_setup"]["candle_pattern"])
        self.assertEqual(state["technical_indicators"]["smart_money_intent"], "Markup (active push into higher prices)")
        self.assertEqual(state["technical_indicators"]["rsi_14"], 62.0)
        self.assertEqual(state["asset"]["funding_rate_pct"], 0.01)

    def test_build_questions(self):
        engine = TypeSafeDecisionEngine({"api_key": "test_key"})
        questions = engine._build_questions()

        self.assertIn("market_regime", questions)
        self.assertIn("signal_action", questions)
        self.assertIn("breakout_quality", questions)
        self.assertIn("risk_level", questions)
        self.assertIn("trend_continuation", questions)

        self.assertEqual(questions["signal_action"].type, "choice")
        self.assertEqual(questions["breakout_quality"].type, "score")
        self.assertEqual(questions["trend_continuation"].type, "noul")

    def test_missing_api_key(self):
        engine = TypeSafeDecisionEngine({"api_key": ""})
        # Clear env var if set during test
        with patch.dict("os.environ", {"TYPESAFE_API_KEY": ""}):
            loop = unittest.mock.MagicMock()
            result = loop.run_until_complete = unittest.IsolatedAsyncioTestCase()

            async def _run():
                return await engine.evaluate_entry(
                    symbol="BTCUSDT",
                    candidate_signal=1,
                    price=90000.0,
                )

            res = unittest.IsolatedAsyncioTestCase()._callSetUp = None
            import asyncio
            res = asyncio.run(_run())
            self.assertFalse(res["approved"])
            self.assertEqual(res["status"], "missing_api_key")

    def test_evaluation_gating_approved(self):
        engine = TypeSafeDecisionEngine({
            "api_key": "ts-dummy-key",
            "min_confidence": 0.65,
            "max_risk_score": 2.5,
            "min_breakout_score": 1.8,
        })

        mock_resp = MagicMock()
        mock_resp.model = "jev-latest"
        mock_resp.usage = {"input_tokens": 120, "output_tokens": 20}
        mock_resp.choices = {
            "signal_action": MagicMock(choice="LONG", confidence=0.85, probabilities={"LONG": 0.88, "SHORT": 0.04, "HOLD": 0.08}),
            "market_regime": MagicMock(choice="strong_trend", confidence=0.80),
        }
        mock_resp.scores = {
            "breakout_quality": MagicMock(score=3.2, confidence=0.75),
            "risk_level": MagicMock(score=1.2, confidence=0.70),
        }
        mock_resp.nouls = {
            "trend_continuation": MagicMock(noul=0.82),
        }

        async def _run():
            with patch("typesafe_engine.AsyncTypeSafeClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.system_one.return_value = mock_resp
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                return await engine.evaluate_entry(
                    symbol="BTCUSDT",
                    candidate_signal=1,
                    price=90000.0,
                )

        import asyncio
        res = asyncio.run(_run())
        self.assertTrue(res["approved"])
        self.assertEqual(res["jev_action"], "LONG")
        self.assertGreaterEqual(res["confidence"], 0.65)
        self.assertLessEqual(res["risk_level_score"], 2.5)
        self.assertGreaterEqual(res["composite_score"], 70.0)

    def test_evaluation_gating_rejected_on_risk(self):
        engine = TypeSafeDecisionEngine({
            "api_key": "ts-dummy-key",
            "min_confidence": 0.65,
            "max_risk_score": 2.5,
            "min_breakout_score": 1.8,
        })

        mock_resp = MagicMock()
        mock_resp.choices = {
            "signal_action": MagicMock(choice="LONG", confidence=0.80, probabilities={"LONG": 0.70, "HOLD": 0.30}),
            "market_regime": MagicMock(choice="choppy_noise"),
        }
        mock_resp.scores = {
            "breakout_quality": MagicMock(score=2.0, confidence=0.60),
            "risk_level": MagicMock(score=3.8, confidence=0.85),  # High hazard!
        }
        mock_resp.nouls = {
            "trend_continuation": MagicMock(noul=0.30),
        }

        async def _run():
            with patch("typesafe_engine.AsyncTypeSafeClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.system_one.return_value = mock_resp
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                return await engine.evaluate_entry(
                    symbol="BTCUSDT",
                    candidate_signal=1,
                    price=90000.0,
                )

        import asyncio
        res = asyncio.run(_run())
        self.assertFalse(res["approved"])
        self.assertIn("high_risk_score", str(res["risk_flags"]))

    def test_state_builder_with_obsidian_playbook(self):
        mock_bridge = MagicMock()
        mock_bridge.match_strategies_for_symbol.return_value = {
            "ok": True,
            "best_match": {
                "title": "SMC聪明钱概念剥头皮",
                "type": "smart_money_concepts",
                "match_score": 88.0,
                "direction": "LONG",
                "entry_rules": "Liquidity sweep + MSS + FVG retest",
                "risk_rules": "Stop loss at extreme wick + 0.2%",
                "checklist": [{"name": "EMA均线结构", "status": "pass", "detail": "Bullish stack"}],
            }
        }
        mock_bridge.analyze_habits.return_value = {
            "overall_score": 85.0,
            "warnings": ["Recent chase warning"],
            "strengths": ["Strong stop loss execution"],
        }

        playbook = TypeSafeStateBuilder.extract_obsidian_playbook(
            symbol="BTCUSDT",
            price=90000.0,
            candidate_signal=1,
            candidate_context={"indicators": {"rsi": 55.0}},
            bridge=mock_bridge,
        )
        self.assertIsNotNone(playbook)
        self.assertEqual(playbook["strategy_title"], "SMC聪明钱概念剥头皮")
        self.assertEqual(playbook["discipline_status"]["overall_score"], 85.0)

        state = TypeSafeStateBuilder.build_state(
            symbol="BTCUSDT",
            candidate_signal=1,
            price=90000.0,
            obsidian_playbook=playbook,
        )
        self.assertIn("user_obsidian_playbook", state)
        self.assertEqual(state["user_obsidian_playbook"]["matched_strategy"]["title"], "SMC聪明钱概念剥头皮")

    def test_build_questions_with_obsidian(self):
        engine = TypeSafeDecisionEngine({"api_key": "test_key"})
        q_no_obs = engine._build_questions(include_obsidian=False)
        self.assertNotIn("playbook_adherence", q_no_obs)
        self.assertNotIn("discipline_violation", q_no_obs)

        q_obs = engine._build_questions(include_obsidian=True)
        self.assertIn("playbook_adherence", q_obs)
        self.assertIn("discipline_violation", q_obs)
        self.assertEqual(q_obs["playbook_adherence"].type, "score")
        self.assertEqual(q_obs["discipline_violation"].type, "noul")

    def test_evaluation_gating_approved_with_obsidian(self):
        mock_bridge = MagicMock()
        mock_bridge.match_strategies_for_symbol.return_value = {
            "ok": True,
            "best_match": {
                "title": "SMC聪明钱概念剥头皮",
                "type": "smart_money_concepts",
                "match_score": 90.0,
                "direction": "LONG",
                "entry_rules": "Liquidity sweep + MSS + FVG retest",
                "risk_rules": "Stop loss at extreme wick",
                "checklist": [],
            }
        }
        mock_bridge.analyze_habits.return_value = {
            "overall_score": 88.0,
            "warnings": [],
            "strengths": ["Disciplined"],
        }

        engine = TypeSafeDecisionEngine(
            {
                "api_key": "ts-dummy-key",
                "min_confidence": 0.65,
                "max_risk_score": 2.5,
                "min_breakout_score": 1.8,
                "use_obsidian_playbook": True,
                "min_playbook_score": 1.5,
                "max_violation_prob": 0.45,
            },
            obsidian_bridge=mock_bridge,
        )

        mock_resp = MagicMock()
        mock_resp.model = "jev-latest"
        mock_resp.usage = {"input_tokens": 150, "output_tokens": 30}
        mock_resp.choices = {
            "signal_action": MagicMock(choice="LONG", confidence=0.88, probabilities={"LONG": 0.90, "HOLD": 0.10}),
            "market_regime": MagicMock(choice="strong_trend"),
        }
        mock_resp.scores = {
            "breakout_quality": MagicMock(score=3.5, confidence=0.80),
            "risk_level": MagicMock(score=1.0, confidence=0.75),
            "playbook_adherence": MagicMock(score=3.8, confidence=0.85),
        }
        mock_resp.nouls = {
            "trend_continuation": MagicMock(noul=0.85),
            "discipline_violation": MagicMock(noul=0.08),
        }

        async def _run():
            with patch("typesafe_engine.AsyncTypeSafeClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.system_one.return_value = mock_resp
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                return await engine.evaluate_entry(
                    symbol="BTCUSDT",
                    candidate_signal=1,
                    price=90000.0,
                )

        import asyncio
        res = asyncio.run(_run())
        self.assertTrue(res["approved"])
        self.assertIn("obsidian_playbook", res)
        self.assertEqual(res["obsidian_playbook"]["matched_strategy"], "SMC聪明钱概念剥头皮")
        self.assertEqual(res["playbook_score"], 3.8)
        self.assertEqual(res["discipline_violation_prob"], 0.08)
        self.assertIn("playbook=3.8", res["reason"])

    def test_evaluation_gating_rejected_on_playbook_mismatch(self):
        mock_bridge = MagicMock()
        mock_bridge.match_strategies_for_symbol.return_value = {
            "ok": True,
            "best_match": {
                "title": "SMC聪明钱概念剥头皮",
                "type": "smart_money_concepts",
                "match_score": 60.0,
                "direction": "LONG",
                "entry_rules": "MSS required",
                "risk_rules": "Tight stop",
            }
        }
        mock_bridge.analyze_habits.return_value = {"overall_score": 80.0, "warnings": []}

        engine = TypeSafeDecisionEngine(
            {
                "api_key": "ts-dummy-key",
                "min_confidence": 0.65,
                "use_obsidian_playbook": True,
                "min_playbook_score": 2.0,  # Strict threshold
            },
            obsidian_bridge=mock_bridge,
        )

        mock_resp = MagicMock()
        mock_resp.choices = {
            "signal_action": MagicMock(choice="LONG", confidence=0.85, probabilities={"LONG": 0.85}),
            "market_regime": MagicMock(choice="strong_trend"),
        }
        mock_resp.scores = {
            "breakout_quality": MagicMock(score=3.0),
            "risk_level": MagicMock(score=1.5),
            "playbook_adherence": MagicMock(score=1.0),  # FAILS playbook check
        }
        mock_resp.nouls = {
            "trend_continuation": MagicMock(noul=0.80),
            "discipline_violation": MagicMock(noul=0.10),
        }

        async def _run():
            with patch("typesafe_engine.AsyncTypeSafeClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.system_one.return_value = mock_resp
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                return await engine.evaluate_entry(
                    symbol="BTCUSDT",
                    candidate_signal=1,
                    price=90000.0,
                )

        import asyncio
        res = asyncio.run(_run())
        self.assertFalse(res["approved"])
        self.assertIn("obsidian_playbook_mismatch", str(res["risk_flags"]))

    def test_autonomous_hunter_approved(self):
        engine = TypeSafeDecisionEngine({
            "api_key": "ts-dummy-key",
            "autonomous_hunter": {
                "enabled": True,
                "min_confidence": 0.68,
                "min_playbook_score": 2.5,
                "max_risk_score": 2.3,
                "min_breakout_score": 2.0,
                "max_violation_prob": 0.28,
            },
        })

        mock_resp = MagicMock()
        mock_resp.choices = {
            "signal_action": MagicMock(choice="LONG", confidence=0.88),
            "market_regime": MagicMock(choice="strong_trend"),
        }
        mock_resp.scores = {
            "breakout_quality": MagicMock(score=3.2),
            "risk_level": MagicMock(score=1.2),
            "playbook_adherence": MagicMock(score=3.6),
        }
        mock_resp.nouls = {
            "trend_continuation": MagicMock(noul=0.90),
            "discipline_violation": MagicMock(noul=0.08),
        }

        async def _run():
            with patch("typesafe_engine.AsyncTypeSafeClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.system_one.return_value = mock_resp
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                return await engine.scan_autonomous_hunter(
                    symbol="SOLUSDT",
                    price=240.0,
                    recent_closes=[230.0, 232.0, 235.0, 238.0, 240.0],
                )

        import asyncio
        res = asyncio.run(_run())
        self.assertTrue(res["approved"])
        self.assertEqual(res["action"], "LONG")
        self.assertGreaterEqual(res["confidence"], 0.68)
        self.assertIn("S-tier", res["reason"])

    def test_autonomous_hunter_rejected_due_to_low_playbook(self):
        engine = TypeSafeDecisionEngine({
            "api_key": "ts-dummy-key",
            "autonomous_hunter": {
                "enabled": True,
                "min_confidence": 0.68,
                "min_playbook_score": 2.5,
            },
        })

        mock_resp = MagicMock()
        mock_resp.choices = {
            "signal_action": MagicMock(choice="LONG", confidence=0.75),
        }
        mock_resp.scores = {
            "breakout_quality": MagicMock(score=2.2),
            "risk_level": MagicMock(score=2.0),
            "playbook_adherence": MagicMock(score=1.8),  # below 2.5
        }
        mock_resp.nouls = {
            "discipline_violation": MagicMock(noul=0.10),
        }

        async def _run():
            with patch("typesafe_engine.AsyncTypeSafeClient") as MockClient:
                mock_client_instance = AsyncMock()
                mock_client_instance.system_one.return_value = mock_resp
                MockClient.return_value.__aenter__.return_value = mock_client_instance

                return await engine.scan_autonomous_hunter(
                    symbol="ETHUSDT",
                    price=3500.0,
                )

        import asyncio
        res = asyncio.run(_run())
        self.assertFalse(res["approved"])


if __name__ == "__main__":
    unittest.main()


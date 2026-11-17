"""市场情绪数据模块 - 恐贪指数/多空比/持仓量/聪明钱综合评分"""
import asyncio
import math
import time

import aiohttp


class MarketSentiment:
    """聚合链上+衍生品市场情绪数据"""

    def __init__(self, proxy: str = None, base_url: str = "https://fapi.binance.com"):
        self.proxy = proxy or None
        self.base_url = base_url
        self.cache: dict = {}
        self.cache_times: dict[str, float] = {}
        self.derivatives_cache: dict[str, dict] = {}
        self.derivatives_cache_times: dict[str, float] = {}
        self.cache_ttl = 120  # 2分钟缓存
        self._fear_cache: dict | None = None
        self._fear_cache_time = 0.0
        self._fear_lock = asyncio.Lock()
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _get_json(self, url):
        session = await self._get_session()
        kwargs = {}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        last_error = None
        for attempt in range(2):
            try:
                async with session.get(url, **kwargs) as resp:
                    data = await resp.json(content_type=None)
                    if resp.status == 200:
                        return data
                    raise RuntimeError(f"HTTP {resp.status}: {data}")
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.35)
        raise last_error

    # ===== 恐惧贪婪指数 (alternative.me) =====
    async def get_fear_greed(self) -> dict:
        now = time.time()
        if self._fear_cache and now - self._fear_cache_time < 600:
            return self._fear_cache
        async with self._fear_lock:
            now = time.time()
            if self._fear_cache and now - self._fear_cache_time < 600:
                return self._fear_cache
            result = await self._fetch_fear_greed()
            self._fear_cache = result
            self._fear_cache_time = now
            return result

    async def _fetch_fear_greed(self) -> dict:
        try:
            data = await self._get_json("https://api.alternative.me/fng/?limit=1")
            d = data["data"][0]
            value = int(d["value"])
            label = d["value_classification"]
            # 映射中文
            cn_map = {
                "Extreme Fear": "极度恐慌", "Fear": "恐慌", "Neutral": "中性",
                "Greed": "贪婪", "Extreme Greed": "极度贪婪"
            }
            return {
                "value": value,
                "label": cn_map.get(label, label),
                "interpretation": self._fg_interpret(value),
                "available": True,
            }
        except Exception as e:
            print(f"[Sentiment] 恐贪指数失败: {e}")
            return {"value": 50, "label": "未知", "interpretation": "", "available": False}

    def _fg_interpret(self, value: int) -> str:
        if value <= 20:
            return "极度恐慌,历史上常是底部区域,逆向看多机会"
        elif value <= 40:
            return "市场恐慌,情绪偏悲观"
        elif value <= 60:
            return "情绪中性"
        elif value <= 80:
            return "市场贪婪,注意过热风险"
        else:
            return "极度贪婪,历史上常是顶部区域,逆向看空风险"

    # ===== 多空比 (币安合约) =====
    async def get_long_short_ratio(self, symbol: str) -> dict:
        try:
            url = f"{self.base_url}/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=24"
            data = await self._get_json(url)
            if data:
                current = data[-1]
                ratio = float(current["longShortRatio"])
                long_pct = float(current["longAccount"]) * 100
                short_pct = float(current["shortAccount"]) * 100
                first_ratio = float(data[0]["longShortRatio"])
                ratio_change = (ratio - first_ratio) / first_ratio * 100 if first_ratio else 0
                return {
                    "ratio": round(ratio, 3),
                    "long_pct": round(long_pct, 1),
                    "short_pct": round(short_pct, 1),
                    "change_24h_pct": round(ratio_change, 2),
                    "interpretation": self._ls_interpret(ratio),
                    "available": True,
                }
        except Exception as e:
            print(f"[Sentiment] 多空比失败: {e}")
        return {
            "ratio": 1.0, "long_pct": 50, "short_pct": 50,
            "change_24h_pct": 0, "interpretation": "", "available": False,
        }

    def _ls_interpret(self, ratio: float) -> str:
        if ratio > 2.0:
            return "散户极度偏多,警惕多头挤压(反向指标偏空)"
        elif ratio > 1.3:
            return "账户偏多"
        elif ratio < 0.5:
            return "散户极度偏空,警惕空头挤压(反向指标偏多)"
        elif ratio < 0.77:
            return "账户偏空"
        return "多空均衡"

    # ===== 大户账户比 (Top Trader Account) =====
    async def get_top_trader_account_ratio(self, symbol: str) -> dict:
        try:
            url = f"{self.base_url}/futures/data/topLongShortAccountRatio?symbol={symbol}&period=1h&limit=24"
            data = await self._get_json(url)
            if data:
                current = data[-1]
                ratio = float(current["longShortRatio"])
                first_ratio = float(data[0]["longShortRatio"])
                ratio_change = (ratio - first_ratio) / first_ratio * 100 if first_ratio else 0
                return {
                    "ratio": round(ratio, 3),
                    "long_pct": round(float(current["longAccount"]) * 100, 1),
                    "short_pct": round(float(current["shortAccount"]) * 100, 1),
                    "change_24h_pct": round(ratio_change, 2),
                    "interpretation": "大户账户偏多" if ratio > 1.2 else "大户账户偏空" if ratio < 0.83 else "大户账户均衡",
                    "available": True,
                }
        except Exception as e:
            print(f"[Sentiment] 大户账户比失败: {e}")
        return {
            "ratio": 1.0, "long_pct": 50, "short_pct": 50,
            "change_24h_pct": 0, "interpretation": "", "available": False,
        }

    # ===== 大户持仓比 (Top Trader Position) =====
    async def get_top_trader_ratio(self, symbol: str) -> dict:
        try:
            url = f"{self.base_url}/futures/data/topLongShortPositionRatio?symbol={symbol}&period=1h&limit=24"
            data = await self._get_json(url)
            if data:
                current = data[-1]
                ratio = float(current["longShortRatio"])
                first_ratio = float(data[0]["longShortRatio"])
                ratio_change = (ratio - first_ratio) / first_ratio * 100 if first_ratio else 0
                return {
                    "ratio": round(ratio, 3),
                    "long_pct": round(float(current["longAccount"]) * 100, 1),
                    "short_pct": round(float(current["shortAccount"]) * 100, 1),
                    "change_24h_pct": round(ratio_change, 2),
                    "interpretation": "大户偏多" if ratio > 1.2 else "大户偏空" if ratio < 0.83 else "大户均衡",
                    "available": True,
                }
        except Exception as e:
            print(f"[Sentiment] 大户比失败: {e}")
        return {
            "ratio": 1.0, "long_pct": 50, "short_pct": 50,
            "change_24h_pct": 0, "interpretation": "", "available": False,
        }

    # ===== 持仓量 Open Interest =====
    async def get_open_interest(self, symbol: str) -> dict:
        try:
            url = f"{self.base_url}/futures/data/openInterestHist?symbol={symbol}&period=1h&limit=24"
            data = await self._get_json(url)
            if data and len(data) >= 2:
                current = float(data[-1]["sumOpenInterestValue"])
                prev_1h = float(data[-2]["sumOpenInterestValue"])
                prev_4h = float(data[-5]["sumOpenInterestValue"]) if len(data) >= 5 else float(data[0]["sumOpenInterestValue"])
                prev_24h = float(data[0]["sumOpenInterestValue"])
                change_1h = (current - prev_1h) / prev_1h * 100 if prev_1h else 0
                change_4h = (current - prev_4h) / prev_4h * 100 if prev_4h else 0
                change_pct = (current - prev_24h) / prev_24h * 100 if prev_24h else 0
                return {
                    "value_usd": round(current, 0),
                    "change_1h_pct": round(change_1h, 2),
                    "change_4h_pct": round(change_4h, 2),
                    "change_24h_pct": round(change_pct, 2),
                    "interpretation": self._oi_interpret(change_pct),
                    "available": True,
                }
        except Exception as e:
            print(f"[Sentiment] 持仓量失败: {e}")
        return {
            "value_usd": 0, "change_1h_pct": 0, "change_4h_pct": 0,
            "change_24h_pct": 0, "interpretation": "", "available": False,
        }

    def _oi_interpret(self, change_pct: float) -> str:
        if change_pct > 10:
            return "持仓量大幅增加,资金涌入,波动可能加剧"
        elif change_pct > 3:
            return "持仓量温和增加"
        elif change_pct < -10:
            return "持仓量大幅减少,资金撤离,可能在去杠杆"
        elif change_pct < -3:
            return "持仓量温和减少"
        return "持仓量平稳"

    # ===== 衍生品聚合 =====
    async def get_derivatives(self, symbol: str = "BTCUSDT", force: bool = False) -> dict:
        now = time.time()
        if (
            not force
            and symbol in self.derivatives_cache
            and now - self.derivatives_cache_times.get(symbol, 0) < self.cache_ttl
        ):
            return self.derivatives_cache[symbol]

        ls, top_account, top_position, oi = await asyncio.gather(
            self.get_long_short_ratio(symbol),
            self.get_top_trader_account_ratio(symbol),
            self.get_top_trader_ratio(symbol),
            self.get_open_interest(symbol),
            return_exceptions=True,
        )
        result = {
            "long_short": ls if isinstance(ls, dict) else {
                "ratio": 1.0, "long_pct": 50, "short_pct": 50,
                "change_24h_pct": 0, "interpretation": "", "available": False,
            },
            "top_trader_account": top_account if isinstance(top_account, dict) else {
                "ratio": 1.0, "long_pct": 50, "short_pct": 50,
                "change_24h_pct": 0, "interpretation": "", "available": False,
            },
            "top_trader": top_position if isinstance(top_position, dict) else {
                "ratio": 1.0, "long_pct": 50, "short_pct": 50,
                "change_24h_pct": 0, "interpretation": "", "available": False,
            },
            "open_interest": oi if isinstance(oi, dict) else {
                "value_usd": 0, "change_1h_pct": 0, "change_4h_pct": 0,
                "change_24h_pct": 0, "interpretation": "", "available": False,
            },
        }
        self.derivatives_cache[symbol] = result
        self.derivatives_cache_times[symbol] = now
        return result

    @staticmethod
    def _ratio_bias(ratio: float) -> float:
        """把多空比映射为 -1~1；2.0约等于+1，0.5约等于-1。"""
        if ratio <= 0:
            return 0.0
        return max(-1.0, min(1.0, math.log(ratio) / math.log(2)))

    @classmethod
    def score_smart_money(
        cls,
        sentiment: dict,
        price_change_1h: float = 0.0,
        price_change_24h: float = 0.0,
        volume_surge: float = 1.0,
        funding_rate: float | None = None,
    ) -> dict:
        """综合大户仓位、账户、OI、价格、成交量与拥挤度推断资金倾向。"""
        top_position = sentiment.get("top_trader", {})
        top_account = sentiment.get("top_trader_account", {})
        retail = sentiment.get("long_short", {})
        oi = sentiment.get("open_interest", {})
        components = []
        score = 0.0
        available_count = sum(bool(x.get("available")) for x in (top_position, top_account, retail, oi))

        top_position_bias = cls._ratio_bias(float(top_position.get("ratio", 1.0)))
        top_account_bias = cls._ratio_bias(float(top_account.get("ratio", 1.0)))
        retail_bias = cls._ratio_bias(float(retail.get("ratio", 1.0)))

        if top_position.get("available"):
            points = top_position_bias * 38
            score += points
            components.append({
                "name": "大户持仓", "points": round(points, 1),
                "text": f"持仓多空比 {top_position.get('ratio', 1.0)}",
            })
            position_change = float(top_position.get("change_24h_pct", 0))
            if abs(top_position_bias) >= 0.15 and position_change * top_position_bias > 0:
                trend_points = math.copysign(min(8.0, abs(position_change) * 0.8), top_position_bias)
                score += trend_points
                components.append({
                    "name": "大户仓位趋势", "points": round(trend_points, 1),
                    "text": f"24h 比值变化 {position_change:+.1f}%",
                })

        if top_account.get("available"):
            points = top_account_bias * 22
            score += points
            components.append({
                "name": "大户账户", "points": round(points, 1),
                "text": f"账户多空比 {top_account.get('ratio', 1.0)}",
            })

        if retail.get("available") and abs(top_position_bias) >= 0.15:
            if top_position_bias * retail_bias < 0:
                points = math.copysign(12.0, top_position_bias)
                score += points
                components.append({
                    "name": "大户散户背离", "points": round(points, 1),
                    "text": "大户与全市场账户方向相反，背离增强",
                })
            elif abs(retail_bias) >= 0.7 and top_position_bias * retail_bias > 0:
                points = -math.copysign(8.0, top_position_bias)
                score += points
                components.append({
                    "name": "同向拥挤", "points": round(points, 1),
                    "text": "大户与散户同向且过度拥挤，降低追单权重",
                })

        oi_1h = float(oi.get("change_1h_pct", 0))
        oi_24h = float(oi.get("change_24h_pct", 0))
        price_dir_1h = 1 if price_change_1h > 0.15 else -1 if price_change_1h < -0.15 else 0
        price_dir_24h = 1 if price_change_24h > 1.0 else -1 if price_change_24h < -1.0 else 0
        if oi.get("available") and oi_1h > 0.35 and price_dir_1h:
            points = price_dir_1h * min(18.0, 10.0 + oi_1h * 2.0)
            score += points
            components.append({
                "name": "价格/OI 1h共振", "points": round(points, 1),
                "text": f"价格 {price_change_1h:+.2f}% · OI {oi_1h:+.2f}%",
            })
        elif oi.get("available") and oi_1h < -0.5:
            components.append({
                "name": "去杠杆", "points": 0.0,
                "text": f"OI 1h {oi_1h:+.2f}%，资金撤离，方向可信度下降",
            })

        if oi.get("available") and oi_24h > 3 and price_dir_24h:
            points = price_dir_24h * min(10.0, 5.0 + oi_24h * 0.35)
            score += points
            components.append({
                "name": "价格/OI 24h共振", "points": round(points, 1),
                "text": f"价格 {price_change_24h:+.2f}% · OI {oi_24h:+.2f}%",
            })

        if volume_surge >= 1.5 and price_dir_1h:
            points = price_dir_1h * min(7.0, 3.0 + (volume_surge - 1.5) * 2.0)
            score += points
            components.append({
                "name": "成交量确认", "points": round(points, 1),
                "text": f"近端成交量 {volume_surge:.2f}x",
            })

        if funding_rate is not None:
            if funding_rate >= 0.0005:
                score -= 12
                components.append({"name": "多头费率拥挤", "points": -12.0, "text": f"资金费率 {funding_rate*100:.4f}%"})
            elif funding_rate >= 0.0002:
                score -= 6
                components.append({"name": "多头费率偏热", "points": -6.0, "text": f"资金费率 {funding_rate*100:.4f}%"})
            elif funding_rate <= -0.0005:
                score += 12
                components.append({"name": "空头费率拥挤", "points": 12.0, "text": f"资金费率 {funding_rate*100:.4f}%"})
            elif funding_rate <= -0.0002:
                score += 6
                components.append({"name": "空头费率偏热", "points": 6.0, "text": f"资金费率 {funding_rate*100:.4f}%"})

        score = round(max(-100.0, min(100.0, score)), 1)
        quality = round(available_count / 4, 2)
        if score >= 15:
            direction, label = "LONG", "聪明钱偏多"
        elif score <= -15:
            direction, label = "SHORT", "聪明钱偏空"
        else:
            direction, label = "NEUTRAL", "聪明钱观望"
        confidence = round(min(95.0, abs(score) * 0.75 + quality * 25), 1)
        return {
            "score": score,
            "direction": direction,
            "label": label,
            "confidence": confidence,
            "data_quality": quality,
            "price_change_1h": round(float(price_change_1h), 2),
            "price_change_24h": round(float(price_change_24h), 2),
            "volume_surge": round(float(volume_surge), 2),
            "components": components,
            "interpretation": (
                f"{label}，综合分 {score:+.1f}。"
                "该分数代表公开衍生品数据推断的资金倾向，不代表已知庄家目标价。"
            ),
        }

    # ===== 完整聚合 =====
    async def get_all(self, symbol: str = "BTCUSDT", force: bool = False) -> dict:
        now = time.time()
        cache_key = symbol
        if (
            not force
            and cache_key in self.cache
            and now - self.cache_times.get(cache_key, 0) < self.cache_ttl
        ):
            return self.cache[cache_key]

        fg, derivatives = await asyncio.gather(
            self.get_fear_greed(),
            self.get_derivatives(symbol, force=force),
            return_exceptions=True,
        )

        derivatives = derivatives if isinstance(derivatives, dict) else {}
        result = {
            "fear_greed": fg if isinstance(fg, dict) else {
                "value": 50, "label": "未知", "interpretation": "", "available": False,
            },
            **derivatives,
        }
        self.cache[cache_key] = result
        self.cache_times[cache_key] = now
        return result

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

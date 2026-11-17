"""币安USDT-M合约 API客户端 (REST + WebSocket)"""
import asyncio
import hashlib
import hmac
import json
import math
import time
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
from urllib.parse import urlencode

import aiohttp
import websockets

from config import load_config


class BinanceFuturesClient:
    def __init__(self, cfg: dict = None):
        self.cfg = cfg or load_config()
        self.api_key = self.cfg["api_key"]
        self.api_secret = self.cfg["api_secret"]
        self.base_url = self.cfg.get("base_url", "https://fapi.binance.com")
        self.ws_url = self.cfg.get("ws_url", "wss://fstream.binance.com")
        self.proxy = self.cfg.get("proxy") or None
        self.live_trading_enabled = bool(self.cfg.get("live_trading_enabled", False))
        self.paper_trading = bool(self.cfg.get("paper_trading", True))
        self._session: aiohttp.ClientSession | None = None
        self.time_offset: int = 0  # 本地与币安服务器时间差(ms)
        self.hedge_mode: bool | None = None  # 双向持仓(对冲)模式标记, 延迟检测
        self._quantity_rules: dict[str, tuple[Decimal, Decimal, Decimal, Decimal]] = {}
        self._leverage_caps: dict[str, int] = {}
        self._price_ticks: dict[str, Decimal] = {}
        self._exchange_info_by_symbol: dict[str, dict] = {}
        self._exchange_info_ts: float = 0.0
        self._exchange_info_lock = asyncio.Lock()

    async def sync_time(self):
        """同步本地时间与币安服务器时间"""
        try:
            data = await self._request("GET", "/fapi/v1/time")
            server_time = data["serverTime"]
            local_time = int(time.time() * 1000)
            self.time_offset = server_time - local_time
            print(f"[Client] 时间同步完成，偏差: {self.time_offset}ms")
        except Exception as e:
            print(f"[Client] 时间同步失败: {e}")

    async def _get_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000) + self.time_offset
        params["recvWindow"] = 10000
        query = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        params["signature"] = signature
        return params

    def _headers(self):
        return {"X-MBX-APIKEY": self.api_key}

    async def _request(self, method, path, params=None, signed=False):
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        base_params = dict(params or {})

        # Signed requests occasionally fail with -1021 after Windows clock
        # adjustments or a long sleep. Re-sync once and retry transparently.
        for attempt in range(2):
            request_params = dict(base_params)
            if signed:
                request_params = self._sign(request_params)
            kwargs = {
                "headers": self._headers(),
                "params": request_params,
            }
            if self.proxy:
                kwargs["proxy"] = self.proxy

            async with session.request(method, url, **kwargs) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200:
                    return data

                is_timestamp_error = (
                    signed
                    and attempt == 0
                    and isinstance(data, dict)
                    and data.get("code") == -1021
                )
                if is_timestamp_error:
                    await self.sync_time()
                    continue

                raise Exception(f"Binance API Error {resp.status}: {data}")

        raise Exception("Binance API timestamp retry exhausted")

    # ========== 行情 ==========
    async def get_klines(self, symbol, interval="5m", limit=200,
                         start_time=None, end_time=None):
        params = {"symbol": symbol, "interval": interval, "limit": min(int(limit), 1500)}
        if start_time:
            params["startTime"] = int(start_time)
        if end_time:
            params["endTime"] = int(end_time)
        return await self._request("GET", "/fapi/v1/klines", params)

    async def get_ticker(self, symbol):
        return await self._request("GET", "/fapi/v1/ticker/24hr", {"symbol": symbol})

    async def get_all_ticker_prices(self):
        """全市场最新价(weight≈2), 用于高频价格监控, 远轻于24hr全量"""
        return await self._request("GET", "/fapi/v1/ticker/price")

    async def get_all_tickers(self):
        """全市场24h行情(不传symbol返回所有交易对), 用于成交量排名筛选"""
        return await self._request("GET", "/fapi/v1/ticker/24hr")

    async def get_funding_rate(self, symbol):
        return await self._request("GET", "/fapi/v1/fundingRate", {"symbol": symbol, "limit": 1})

    async def get_mark_price(self, symbol):
        return await self._request("GET", "/fapi/v1/premiumIndex", {"symbol": symbol})

    # ========== 账户 ==========
    async def _symbol_exchange_info(self, symbol: str) -> dict:
        """Return the matching contract entry instead of assuming symbols[0]."""
        symbol = symbol.upper()
        if self._exchange_info_by_symbol and time.time() - self._exchange_info_ts < 300:
            info = self._exchange_info_by_symbol.get(symbol)
            if info:
                return info
        async with self._exchange_info_lock:
            if not self._exchange_info_by_symbol or time.time() - self._exchange_info_ts >= 300:
                data = await self._request("GET", "/fapi/v1/exchangeInfo")
                symbols = data.get("symbols", []) if isinstance(data, dict) else []
                self._exchange_info_by_symbol = {
                    str(item.get("symbol", "")).upper(): item
                    for item in symbols
                    if item.get("symbol")
                }
                self._exchange_info_ts = time.time()
            info = self._exchange_info_by_symbol.get(symbol)
            if not info:
                raise ValueError(f"exchange rules missing for {symbol}")
            return info

    async def _quantity_rule(self, symbol: str) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        symbol = symbol.upper()
        cached = self._quantity_rules.get(symbol)
        if cached:
            return cached
        info = await self._symbol_exchange_info(symbol)
        filters = {item.get("filterType"): item for item in info.get("filters", [])}
        lot = filters.get("MARKET_LOT_SIZE") or filters.get("LOT_SIZE") or {}
        notional_filter = filters.get("MIN_NOTIONAL") or filters.get("NOTIONAL") or {}
        step = Decimal(str(lot.get("stepSize", "1")))
        min_qty = Decimal(str(lot.get("minQty", "0")))
        max_qty = Decimal(str(lot.get("maxQty", "0")))
        min_notional = Decimal(str(
            notional_filter.get("notional", notional_filter.get("minNotional", "5"))
        ))
        if step <= 0:
            raise ValueError(f"invalid quantity step for {symbol}")
        if min_notional < 0:
            min_notional = Decimal("0")
        if max_qty < 0:
            max_qty = Decimal("0")
        self._quantity_rules[symbol] = (step, min_qty, max_qty, min_notional)
        return step, min_qty, max_qty, min_notional

    async def _price_tick(self, symbol: str) -> Decimal:
        """PRICE_FILTER tickSize, 用于保护单价格取整"""
        symbol = symbol.upper()
        cached = self._price_ticks.get(symbol)
        if cached:
            return cached
        info = await self._symbol_exchange_info(symbol)
        filters = {item.get("filterType"): item for item in info.get("filters", [])}
        tick = Decimal(str((filters.get("PRICE_FILTER") or {}).get("tickSize", "0.01")))
        if tick <= 0:
            tick = Decimal("0.01")
        self._price_ticks[symbol] = tick
        return tick

    @staticmethod
    def _round_price(price: float, tick: Decimal) -> str:
        """价格按tickSize向下取整并格式化为合法字符串"""
        d = (Decimal(str(price)) / tick).quantize(Decimal("1"), rounding=ROUND_DOWN) * tick
        return format(d.normalize(), "f")

    async def cancel_all_orders(self, symbol: str):
        """清空该合约所有挂单(含Algo条件单), 平仓后防止残留保护单误触发"""
        if not self.live_trading_enabled or self.paper_trading:
            return {"symbol": symbol.upper(), "msg": "Paper all orders cancelled", "_is_paper": True}
        try:
            await self._request(
                "DELETE", "/fapi/v1/allOpenOrders", {"symbol": symbol.upper()}, signed=True)
        except Exception as exc:
            print(f"[client] {symbol} 清空挂单失败: {exc}")
        # 2025-12起部分币种条件单走Algo端点, 需单独清理
        try:
            open_algos = await self._request(
                "GET", "/fapi/v1/openAlgoOrders", {"symbol": symbol.upper()}, signed=True)
            for algo in open_algos or []:
                algo_id = algo.get("algoId")
                if not algo_id:
                    continue
                try:
                    await self._request("DELETE", "/fapi/v1/algoOrder", {
                        "symbol": symbol.upper(), "algotype": algo.get("algoType", "CONDITIONAL"),
                        "algoId": str(algo_id)}, signed=True)
                except Exception as exc:
                    print(f"[client] {symbol} 取消Algo单{algo_id}失败: {exc}")
        except Exception:
            pass

    async def place_protective_stop(self, symbol: str, position_side: str, kind: str,
                                    stop_price: float, close_side: str) -> dict:
        """交易所侧保护单: STOP_MARKET/TAKE_PROFIT_MARKET + closePosition, 标记价格触发。
        服务宕机/断网时仓位仍有硬性止盈止损。
        2025-12起新上市币条件单被迁移到Algo Order API(-4120), 自动降级走/fapi/v1/algoOrder。"""
        if not self.live_trading_enabled or self.paper_trading:
            print(f"[PAPER-GUARD 模拟防护] 拦截交易所保护单: {symbol} {position_side} {kind} stop={stop_price}")
            mock_id = int(time.time() * 1000)
            return {
                "orderId": mock_id,
                "symbol": symbol.upper(),
                "status": "NEW",
                "clientOrderId": f"paper_stop_{mock_id}",
                "stopPrice": str(stop_price),
                "side": close_side,
                "positionSide": position_side,
                "_is_paper": True,
            }
        tick = await self._price_tick(symbol)
        stop = self._round_price(stop_price, tick)
        params = {
            "symbol": symbol.upper(),
            "type": kind,
            "side": close_side,
            "positionSide": position_side,
            "stopPrice": stop,
            "closePosition": "true",
            "workingType": "MARK_PRICE",
            "priceProtect": "TRUE",
        }
        try:
            return await self._request("POST", "/fapi/v1/order", params, signed=True)
        except Exception as exc:
            if "-4120" not in str(exc):
                raise
            algo_params = {
                "symbol": symbol.upper(),
                "algotype": "CONDITIONAL",
                "type": kind,
                "side": close_side,
                "positionSide": position_side,
                "triggerprice": stop,
                "closePosition": "true",
            }
            return await self._request("POST", "/fapi/v1/algoOrder", algo_params, signed=True)

    async def get_open_orders(self, symbol: str = None) -> list:
        params = {"symbol": symbol.upper()} if symbol else {}
        return await self._request("GET", "/fapi/v1/openOrders", params, signed=True)

    async def get_order(self, symbol: str, order_id=None, client_order_id: str = None) -> dict:
        """查询单笔订单状态(FILLED时含avgPrice/executedQty), 用于限价单成交轮询"""
        params = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = int(order_id)
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._request("GET", "/fapi/v1/order", params, signed=True)

    async def place_limit_order(self, symbol: str, side: str, position_side: str,
                                qty: float, price: float, client_order_id: str = None) -> dict:
        """GTC限价单: 价格按tickSize取整, 数量精度错误自动截断重试(网格挂单用)"""
        if not self.live_trading_enabled or self.paper_trading:
            print(f"[PAPER-GUARD 模拟防护] 拦截限价挂单: {symbol} {side} {position_side} qty={qty} price={price}")
            mock_id = int(time.time() * 1000)
            return {
                "orderId": mock_id,
                "symbol": symbol.upper(),
                "status": "NEW",
                "clientOrderId": client_order_id or f"paper_limit_{mock_id}",
                "price": str(price),
                "origQty": str(qty),
                "executedQty": "0",
                "side": side,
                "positionSide": position_side,
                "_is_paper": True,
            }
        tick = await self._price_tick(symbol)
        price_d = (Decimal(str(price)) / tick).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * tick
        price_str = format(price_d.normalize(), "f")
        normalized = await self.normalize_quantity(symbol, qty)
        if normalized <= 0:
            raise ValueError(f"quantity is below exchange minimum for {symbol}")
        decimals = self._qty_decimals(normalized)
        for attempt in range(decimals + 1):
            params = {
                "symbol": symbol.upper(), "type": "LIMIT", "timeInForce": "GTC",
                "side": side, "positionSide": position_side,
                "quantity": self._floor_qty(normalized, decimals - attempt),
                "price": price_str,
                "newOrderRespType": "RESULT",
            }
            if client_order_id:
                params["newClientOrderId"] = client_order_id[:36]
            try:
                return await self._request("POST", "/fapi/v1/order", params, signed=True)
            except Exception as exc:
                if "-1111" in str(exc) and attempt < decimals:
                    continue
                raise
        raise ValueError(f"unable to place limit order for {symbol}")

    async def cancel_order(self, symbol: str, order_id=None, client_order_id: str = None):
        if not self.live_trading_enabled or self.paper_trading:
            return {"symbol": symbol.upper(), "status": "CANCELED", "_is_paper": True}
        params = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = int(order_id)
        elif client_order_id:
            params["origClientOrderId"] = client_order_id
        return await self._request("DELETE", "/fapi/v1/order", params, signed=True)

    async def normalize_quantity(self, symbol: str, quantity) -> float:
        """Floor an order quantity to the exchange market-order step size."""
        step, min_qty, _, _ = await self._quantity_rule(symbol)
        qty = Decimal(str(quantity))
        normalized = (qty / step).to_integral_value(rounding=ROUND_DOWN) * step
        if normalized <= 0 or (min_qty > 0 and normalized < min_qty):
            return 0.0
        return float(normalized)

    async def quantity_for_notional(self, symbol: str, price, target_notional) -> float:
        """Round strategy sizing up just enough to satisfy the market-order notional floor."""
        step, min_qty, max_qty, min_notional = await self._quantity_rule(symbol)
        mark_price = Decimal(str(price))
        target = max(Decimal(str(target_notional)), min_notional)
        # 最低名义为约束项时留6%余量: 下单精度截断可能小幅拉低名义, 避免跌破门槛被拒
        if target == min_notional and min_notional > 0:
            target = min_notional * Decimal("1.06")
        if mark_price <= 0 or target <= 0:
            raise ValueError(f"invalid price or notional for {symbol}")
        normalized = (target / mark_price / step).to_integral_value(rounding=ROUND_UP) * step
        if normalized < min_qty:
            normalized = (min_qty / step).to_integral_value(rounding=ROUND_UP) * step
        if max_qty > 0 and normalized > max_qty:
            raise ValueError(
                f"minimum notional {min_notional} for {symbol} requires quantity "
                f"{normalized}, above market maximum {max_qty}"
            )
        return float(normalized)

    async def validate_market_open_quantity(self, symbol: str, price, quantity) -> tuple[float, float, float]:
        """Validate a proposed opening quantity against live market-order quantity and notional limits."""
        step, min_qty, max_qty, min_notional = await self._quantity_rule(symbol)
        normalized = (Decimal(str(quantity)) / step).to_integral_value(
            rounding=ROUND_DOWN) * step
        if normalized <= 0 or (min_qty > 0 and normalized < min_qty):
            raise ValueError(f"quantity is below the market minimum for {symbol}")
        if max_qty > 0 and normalized > max_qty:
            raise ValueError(
                f"quantity {normalized} exceeds market maximum {max_qty} for {symbol}"
            )
        mark_price = Decimal(str(price))
        if mark_price <= 0:
            raise ValueError(f"invalid market price for {symbol}")
        notional = normalized * mark_price
        if min_notional > 0 and notional < min_notional:
            raise ValueError(
                f"notional {notional} is below the market minimum {min_notional} for {symbol}"
            )
        return float(normalized), float(notional), float(min_notional)

    async def get_account(self):
        return await self._request("GET", "/fapi/v2/account", signed=True)

    async def get_positions(self):
        return await self._request("GET", "/fapi/v2/positionRisk", signed=True)

    async def set_leverage(self, symbol, leverage):
        return await self._request("POST", "/fapi/v1/leverage", {
            "symbol": symbol, "leverage": leverage
        }, signed=True)

    async def get_max_leverage(self, symbol: str) -> int:
        """Return the account-specific highest initial leverage available for a symbol."""
        symbol = symbol.upper()
        cached = self._leverage_caps.get(symbol)
        if cached:
            return cached
        data = await self._request(
            "GET", "/fapi/v1/leverageBracket", {"symbol": symbol}, signed=True)
        rows = data if isinstance(data, list) else [data]
        brackets = rows[0].get("brackets", []) if rows and isinstance(rows[0], dict) else []
        maximum = max(
            (int(float(item.get("initialLeverage", 0) or 0)) for item in brackets),
            default=0,
        )
        if maximum < 1:
            raise ValueError(f"leverage bracket missing for {symbol}")
        self._leverage_caps[symbol] = maximum
        return maximum

    async def clamp_leverage(self, symbol: str, requested_leverage) -> tuple[int, int]:
        """Clamp a requested leverage to the symbol's current account-specific cap."""
        maximum = await self.get_max_leverage(symbol)
        requested = max(1, int(float(requested_leverage)))
        return min(requested, maximum), maximum

    async def set_margin_type(self, symbol, margin_type="ISOLATED"):
        """Set margin mode before opening a new futures position."""
        return await self._request("POST", "/fapi/v1/marginType", {
            "symbol": symbol, "marginType": str(margin_type).upper()
        }, signed=True)

    # ========== 交易 ==========
    async def _position_side(self, direction: str):
        """双向持仓(对冲)模式下单必须带positionSide; 单向模式返回None"""
        if self.hedge_mode is None:
            try:
                mode = await self._request("GET", "/fapi/v1/positionSide/dual", signed=True)
                self.hedge_mode = bool(mode.get("dualSidePosition"))
                print(f"[Client] 持仓模式: {'双向(对冲)' if self.hedge_mode else '单向'}")
            except Exception as e:
                print(f"[Client] 查询持仓模式失败: {e}")
                self.hedge_mode = False
        return direction if self.hedge_mode else None

    async def place_order(self, symbol, side, order_type="MARKET", quantity=None,
                           price=None, stop_price=None, reduce_only=False,
                           time_in_force=None, position_side=None,
                           close_position=False):
        requested_quantity = None
        normalized_quantity = None
        qty = None
        if quantity:
            requested_quantity = float(quantity)
            try:
                qty = await self.normalize_quantity(symbol, quantity)
            except Exception:
                qty = float(quantity)
            if qty <= 0:
                raise ValueError(f"quantity is below exchange minimum for {symbol}")
            normalized_quantity = qty

        if not self.live_trading_enabled or self.paper_trading:
            print(f"[PAPER-GUARD 模拟防护] 拦截市价/条件实盘下单: {symbol} {side} {order_type} qty={quantity} (严禁开实盘)")
            mock_id = int(time.time() * 1000)
            mock_price = float(price) if price else 100.0
            return {
                "orderId": mock_id,
                "symbol": symbol.upper(),
                "status": "FILLED",
                "clientOrderId": f"paper_{mock_id}",
                "price": str(mock_price),
                "avgPrice": str(mock_price),
                "origQty": str(quantity or 0),
                "executedQty": str(quantity or 0),
                "cumQuote": str((quantity or 0) * mock_price),
                "timeInForce": "GTC",
                "type": order_type,
                "reduceOnly": reduce_only,
                "side": side,
                "positionSide": position_side or "BOTH",
                "_local_execution": {
                    "requested_qty": requested_quantity or 0,
                    "normalized_qty": normalized_quantity or 0,
                    "is_paper": True,
                }
            }

        # 币安部分低价币实际下单精度低于exchangeInfo声称值(如声称3位实际只收1位),
        # 遇到-1111精度错误时逐位截断小数重试, 全市场通用无需逐币硬编码。
        decimals = self._qty_decimals(qty) if qty else 0
        for attempt in range(decimals + 1):
            params = {"symbol": symbol, "side": side, "type": order_type}
            if qty:
                params["quantity"] = self._floor_qty(qty, decimals - attempt)
            if price:
                params["price"] = price
            if stop_price:
                params["stopPrice"] = stop_price
            if reduce_only:
                params["reduceOnly"] = "true"
            if close_position:
                params["closePosition"] = "true"
            if time_in_force:
                params["timeInForce"] = time_in_force
            elif order_type == "LIMIT":
                params["timeInForce"] = "GTC"
            if position_side:
                params["positionSide"] = position_side
            # RESULT returns status, executedQty and avgPrice for market orders, which the
            # trader uses to advance its take-profit state only after a real fill.
            params["newOrderRespType"] = "RESULT"
            try:
                response = await self._request("POST", "/fapi/v1/order", params, signed=True)
                if isinstance(response, dict):
                    response["_local_execution"] = {
                        "requested_qty": requested_quantity,
                        "normalized_qty": normalized_quantity,
                    }
                return response
            except Exception as exc:
                msg = str(exc)
                if "-1111" in msg and qty and attempt < decimals:
                    continue  # 截断一位小数重试
                raise
        raise ValueError(f"unable to place order for {symbol} after precision truncation")

    @staticmethod
    def _qty_decimals(qty) -> int:
        s = f"{qty:.10f}".rstrip("0")
        return len(s.split(".")[1]) if "." in s else 0

    @staticmethod
    def _floor_qty(qty, decimals: int) -> float:
        decimals = max(0, int(decimals))
        factor = 10 ** decimals
        return math.floor(float(qty) * factor) / factor

    async def market_open_long(self, symbol, quantity):
        return await self.place_order(symbol, "BUY", "MARKET", quantity=quantity,
                                      position_side=await self._position_side("LONG"))

    async def market_open_short(self, symbol, quantity):
        return await self.place_order(symbol, "SELL", "MARKET", quantity=quantity,
                                      position_side=await self._position_side("SHORT"))

    async def market_close_long(self, symbol, quantity):
        ps = await self._position_side("LONG")
        # 对冲模式带positionSide时不能再传reduceOnly(币安-1106); 仅单向模式需要reduceOnly
        return await self.place_order(symbol, "SELL", "MARKET", quantity=quantity,
                                      reduce_only=(ps is None), position_side=ps)

    async def market_close_short(self, symbol, quantity):
        ps = await self._position_side("SHORT")
        return await self.place_order(symbol, "BUY", "MARKET", quantity=quantity,
                                      reduce_only=(ps is None), position_side=ps)
    async def cancel_all_orders_globally(self, symbols: list[str] | None = None) -> dict:
        """全局紧急撤单: 并发清理指定或全部持仓币种的所有挂单及Algo条件单"""
        if not self.live_trading_enabled or self.paper_trading:
            return {"ok": True, "cancelled_count": len(symbols or []), "_is_paper": True}
        target_symbols = list(symbols or [])
        if not target_symbols:
            try:
                positions = await self.get_positions()
                target_symbols = list({p["symbol"] for p in positions if float(p.get("positionAmt", 0)) != 0})
            except Exception as exc:
                print(f"[client] 获取持仓币种失败: {exc}")
        if not target_symbols:
            # 如果没有明确持仓，尝试从当前挂单列表获取币种
            try:
                orders = await self.get_open_orders()
                target_symbols = list({o.get("symbol") for o in orders if o.get("symbol")})
            except Exception:
                pass
        results = {}
        for sym in set(target_symbols):
            try:
                await self.cancel_all_orders(sym)
                results[sym] = "OK"
            except Exception as e:
                results[sym] = str(e)
        return {"ok": True, "results": results}

    # ========== 历史查询 ==========
    async def get_user_trades(self, symbol, limit=1000,
                              start_time=None, end_time=None, from_id=None):
        """成交流水(含realizedPnl/side/positionSide), 用于单笔胜率与方向统计"""
        params = {"symbol": symbol, "limit": limit}
        if start_time is not None:
            params["startTime"] = int(start_time)
        if end_time is not None:
            params["endTime"] = int(end_time)
        if from_id is not None:
            params["fromId"] = int(from_id)
        return await self._request("GET", "/fapi/v1/userTrades", params, signed=True)

    async def get_user_trades_time_range(self, symbol, start_time, end_time,
                                         limit=1000, window_ms=None):
        """Fetch account trades over a long period as API-valid <=7-day requests.

        Returns (rows, truncated_windows). A non-empty truncated_windows value
        means at least one API request reached its row limit and the
        fill-level statistics may be incomplete for that interval.
        """
        start = int(start_time)
        end = int(end_time)
        if start > end:
            return [], []
        max_window = int(window_ms or (7 * 86400 * 1000))
        if max_window <= 0:
            raise ValueError("window_ms must be positive")

        rows_by_id = {}
        rows_without_id = []
        truncated_windows = []
        window_start = start
        while window_start <= end:
            window_end = min(end, window_start + max_window - 1)
            rows = await self.get_user_trades(
                symbol, limit=limit, start_time=window_start, end_time=window_end)
            if len(rows) >= limit:
                truncated_windows.append({
                    "start_time": window_start,
                    "end_time": window_end,
                    "row_count": len(rows),
                })
            for row in rows:
                trade_id = row.get("id")
                if trade_id is None:
                    rows_without_id.append(row)
                else:
                    rows_by_id[str(trade_id)] = row
            window_start = window_end + 1

        rows = list(rows_by_id.values()) + rows_without_id
        rows.sort(key=lambda item: (int(item.get("time", 0) or 0), int(item.get("id", 0) or 0)))
        return rows, truncated_windows

    async def get_income_history(self, income_type=None, limit=1000, days=30,
                                 start_time=None, end_time=None):
        """账户收益流水, 分页拉取。income_type如 REALIZED_PNL/COMMISSION/FUNDING_FEE"""
        import time as _t
        end = int(end_time) if end_time is not None else int(_t.time() * 1000)
        start = int(start_time) if start_time is not None else end - days * 86400 * 1000
        all_rows, page = [], 1
        while True:
            params = {"limit": limit, "startTime": start, "endTime": end, "page": page}
            if income_type:
                params["incomeType"] = income_type
            rows = await self._request("GET", "/fapi/v1/income", params, signed=True)
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < limit:
                break
            page += 1
            if page > 20:  # 安全上限
                break
        return all_rows

    # ========== WebSocket ==========
    async def ws_klines(self, symbols: list, interval: str, callback):
        """订阅K线流(走代理)，callback(kline_dict)"""
        streams = "/".join(f"{s.lower()}@kline_{interval}" for s in symbols)
        url = f"{self.ws_url}/stream?streams={streams}"
        while True:
            try:
                session = await self._get_session()
                async with session.ws_connect(url, proxy=self.proxy, timeout=30) as ws:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        data = json.loads(msg.data)
                        if "data" in data:
                            k = data["data"]["k"]
                            kline = {
                                "symbol": data["data"]["s"],
                                "open_time": k["t"],
                                "open": float(k["o"]),
                                "high": float(k["h"]),
                                "low": float(k["l"]),
                                "close": float(k["c"]),
                                "volume": float(k["v"]),
                                "close_time": k["T"],
                                "is_closed": k["x"],
                            }
                            await callback(kline)
            except Exception as e:
                print(f"[WS] 断线重连: {e}")
                await asyncio.sleep(3)

    async def ws_mark_price(self, symbols: list, callback):
        """订阅标记价格(走代理)"""
        streams = "/".join(f"{s.lower()}@markPrice@1s" for s in symbols)
        url = f"{self.ws_url}/stream?streams={streams}"
        while True:
            try:
                session = await self._get_session()
                async with session.ws_connect(url, proxy=self.proxy, timeout=30) as ws:
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        data = json.loads(msg.data)
                        if "data" in data:
                            d = data["data"]
                            await callback({
                                "symbol": d["s"],
                                "mark_price": float(d["p"]),
                                "funding_rate": float(d["r"]),
                            })
            except Exception as e:
                print(f"[WS markPrice] 断线重连: {e}")
                await asyncio.sleep(3)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

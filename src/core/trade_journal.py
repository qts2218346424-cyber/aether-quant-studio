"""交易日志持久化 + 每日报告 + AI总结学习"""
import json
import os
from datetime import datetime, date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class TradeJournal:
    def __init__(self):
        self._cache: dict[str, list] = {}  # date_str -> records

    def _file(self, date_str: str) -> Path:
        return DATA_DIR / f"trades_{date_str}.json"

    def _load(self, date_str: str) -> list:
        if date_str in self._cache:
            return self._cache[date_str]
        f = self._file(date_str)
        if f.exists():
            records = json.loads(f.read_text(encoding="utf-8"))
        else:
            records = []
        self._cache[date_str] = records
        return records

    def _save(self, date_str: str):
        records = self._cache.get(date_str, [])
        self._file(date_str).write_text(
            json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    def record_open(self, symbol: str, side: str, qty: float, price: float,
                    leverage: int = 10, margin: float = 0, score: float = 0,
                    order_id=None, entry_context: dict = None):
        """记录开仓"""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        records = self._load(date_str)
        record = {
            "type": "open",
            "time": now.strftime("%H:%M:%S"),
            "timestamp": int(now.timestamp()),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "leverage": leverage,
            "margin": margin,
            "score": score,
        }
        if order_id is not None:
            record["order_id"] = order_id
        if entry_context:
            record["entry_context"] = entry_context
        records.append(record)
        self._save(date_str)

    def record_close(self, symbol: str, side: str, qty: float,
                     entry_price: float, exit_price: float, reason: str,
                     pnl: float = 0, pnl_pct: float = 0, order_id=None):
        """记录平仓(含盈亏)"""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        records = self._load(date_str)
        record = {
            "type": "close",
            "time": now.strftime("%H:%M:%S"),
            "timestamp": int(now.timestamp()),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "reason": reason,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl_pct, 2),
        }
        if order_id is not None:
            record["order_id"] = order_id
        records.append(record)
        self._save(date_str)

    def merge_external_records(self, date_str: str, external_records: list) -> dict:
        """Merge Binance fills into the local journal without duplicating local orders."""
        records = self._load(date_str)
        known_ids = {
            r.get("external_id") for r in records if r.get("external_id")
        }
        imported = enriched = skipped = 0

        def close_enough(a, b) -> bool:
            a, b = float(a or 0), float(b or 0)
            return abs(a - b) <= max(1e-8, max(abs(a), abs(b)) * 0.03)

        def find_local_match(ext):
            for record in records:
                if record.get("external_id"):
                    continue
                if record.get("type") != ext.get("type"):
                    continue
                if record.get("symbol") != ext.get("symbol"):
                    continue
                if record.get("side") != ext.get("side"):
                    continue
                if abs(int(record.get("timestamp", 0)) - int(ext.get("timestamp", 0))) > 180:
                    continue
                if not close_enough(record.get("qty"), ext.get("qty")):
                    continue
                return record
            return None

        for ext in external_records:
            external_id = ext.get("external_id")
            if external_id in known_ids:
                skipped += 1
                continue

            local = find_local_match(ext)
            if local is not None:
                local_reason = local.get("reason")
                local_score = local.get("score")
                local_leverage = local.get("leverage")
                local.update(ext)
                local["source"] = "local+binance"
                if local_reason and local_reason != "币安成交同步":
                    local["reason"] = local_reason
                if local_score is not None:
                    local["score"] = local_score
                if local_leverage:
                    local["leverage"] = local_leverage
                enriched += 1
            else:
                records.append(ext)
                imported += 1
            if external_id:
                known_ids.add(external_id)

        records.sort(key=lambda r: (int(r.get("timestamp", 0)), r.get("type", "")))
        self._save(date_str)
        return {
            "imported": imported,
            "enriched": enriched,
            "skipped": skipped,
            "total_external": len(external_records),
        }

    def get_day_records(self, date_str: str = None) -> list:
        """获取某日全部记录"""
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
        return self._load(date_str)

    def daily_report(self, date_str: str = None) -> dict:
        """生成每日交易报告: 统计 + 明细"""
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
        records = self._load(date_str)

        def source_bucket(record: dict) -> str:
            source = str(record.get("source", "local") or "local").lower()
            return "bot" if source == "local" or source.startswith("local+") else "external"

        def source_summary(source_records: list) -> dict:
            source_opens = [r for r in source_records if r.get("type") == "open"]
            source_closes = [r for r in source_records if r.get("type") == "close"]
            source_wins = [r for r in source_closes if float(r.get("pnl", 0) or 0) > 0]
            source_losses = [r for r in source_closes if float(r.get("pnl", 0) or 0) < 0]
            source_pnl = sum(float(r.get("pnl", 0) or 0) for r in source_closes)
            source_commission = sum(
                abs(float(r.get("commission", 0) or 0)) for r in source_records)
            return {
                "open_count": len(source_opens),
                "close_count": len(source_closes),
                "total_pnl": round(source_pnl, 4),
                "commission": round(source_commission, 4),
                "net_pnl": round(source_pnl - source_commission, 4),
                "wins": len(source_wins),
                "losses": len(source_losses),
                "win_rate": round(
                    len(source_wins) / len(source_closes) * 100, 1
                ) if source_closes else 0,
            }

        opens = [r for r in records if r["type"] == "open"]
        closes = [r for r in records if r["type"] == "close"]
        by_source = {
            "bot": source_summary([r for r in records if source_bucket(r) == "bot"]),
            "external": source_summary([
                r for r in records if source_bucket(r) == "external"
            ]),
        }

        total_pnl = sum(r.get("pnl", 0) for r in closes)
        total_commission = sum(abs(float(r.get("commission", 0) or 0)) for r in records)
        net_pnl = total_pnl - total_commission
        wins = [r for r in closes if r.get("pnl", 0) > 0]
        losses = [r for r in closes if r.get("pnl", 0) < 0]
        win_rate = len(wins) / len(closes) * 100 if closes else 0

        # 按币种汇总
        by_symbol = {}
        for r in closes:
            sym = r["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = {"pnl": 0, "count": 0, "wins": 0}
            by_symbol[sym]["pnl"] += r.get("pnl", 0)
            by_symbol[sym]["count"] += 1
            if r.get("pnl", 0) > 0:
                by_symbol[sym]["wins"] += 1

        # 止盈/止损统计
        tp_count = len([r for r in closes if "止盈" in r.get("reason", "")])
        sl_count = len([r for r in closes if "止损" in r.get("reason", "")])

        avg_win = sum(r["pnl"] for r in wins) / len(wins) if wins else 0
        avg_loss = sum(r["pnl"] for r in losses) / len(losses) if losses else 0
        profit_factor = abs(sum(r["pnl"] for r in wins) / sum(r["pnl"] for r in losses)) if losses and sum(r["pnl"] for r in losses) != 0 else float("inf")

        return {
            "date": date_str,
            "summary": {
                "total_trades": len(opens),
                "total_closes": len(closes),
                "total_pnl": round(total_pnl, 4),
                "commission": round(total_commission, 4),
                "net_pnl": round(net_pnl, 4),
                "win_rate": round(win_rate, 1),
                "wins": len(wins),
                "losses": len(losses),
                "avg_win": round(avg_win, 4),
                "avg_loss": round(avg_loss, 4),
                "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999,
                "tp_count": tp_count,
                "sl_count": sl_count,
                "synced_records": len([
                    r for r in records if "binance" in str(r.get("source", ""))
                ]),
            },
            "by_symbol": by_symbol,
            "by_source": by_source,
            "records": records,
        }

    def ai_summary(self, date_str: str = None) -> str:
        """AI自动总结当日交易表现 + 学习要点"""
        rpt = self.daily_report(date_str)
        s = rpt["summary"]
        date_str = rpt["date"]

        lines = [f"📊 {date_str} 交易日报", ""]

        # 基本统计
        lines.append(f"开仓 {s['total_trades']} 笔 | 平仓 {s['total_closes']} 笔")
        net_value = s.get("net_pnl", s["total_pnl"])
        pnl_emoji = "✅" if net_value >= 0 else "❌"
        lines.append(f"{pnl_emoji} 净盈亏: {net_value:+.4f} U")
        lines.append(
            f"已实现盈亏: {s['total_pnl']:+.4f}U | "
            f"手续费: -{s.get('commission', 0):.4f}U")
        lines.append(f"胜率: {s['win_rate']}% ({s['wins']}胜/{s['losses']}负)")
        lines.append(f"平均盈利: +{s['avg_win']:.4f}U | 平均亏损: {s['avg_loss']:.4f}U")
        lines.append(f"盈亏比: {s['profit_factor']}")
        lines.append(f"止盈触发: {s['tp_count']}次 | 止损触发: {s['sl_count']}次")
        lines.append("")

        # 按币种分析
        if rpt["by_symbol"]:
            lines.append("【币种表现】")
            sorted_syms = sorted(rpt["by_symbol"].items(), key=lambda x: x[1]["pnl"], reverse=True)
            for sym, info in sorted_syms:
                emoji = "🟢" if info["pnl"] >= 0 else "🔴"
                lines.append(f"  {emoji} {sym}: {info['pnl']:+.4f}U ({info['count']}笔, 胜{info['wins']})")
            lines.append("")

        # AI学习要点
        lines.append("【AI学习总结】")
        insights = []

        if s["total_closes"] > 0:
            if s["win_rate"] < 40:
                insights.append("⚠️ 胜率偏低(<40%), 建议提高开仓评分阈值或减少逆势交易")
            elif s["win_rate"] > 65:
                insights.append("✅ 胜率良好, 当前策略方向正确")

            if s["profit_factor"] < 1.0:
                insights.append("⚠️ 盈亏比<1, 亏损大于盈利, 需检查止损是否过宽或止盈过早")
            elif s["profit_factor"] > 2.0:
                insights.append("✅ 盈亏比优秀(>2), 风险回报合理")

            if s["sl_count"] > s["tp_count"] * 2:
                insights.append("⚠️ 止损远多于止盈, 可能入场时机偏晚或趋势判断有误")

            # 检查是否频繁交易
            if s["total_trades"] > 10:
                insights.append("⚠️ 交易过于频繁, 注意手续费侵蚀, 建议提高信号阈值")

            # 检查单币种集中度
            if rpt["by_symbol"]:
                worst = min(rpt["by_symbol"].items(), key=lambda x: x[1]["pnl"])
                if worst[1]["pnl"] < 0 and abs(worst[1]["pnl"]) > abs(s["total_pnl"]) * 0.5:
                    insights.append(f"⚠️ {worst[0]} 贡献了大部分亏损, 注意该币种波动风险")

        if not insights:
            insights.append("今日交易数据不足, 继续观察")

        lines.extend(insights)
        return "\n".join(lines)

    def export_csv(self, date_str: str = None) -> str:
        """导出CSV格式字符串"""
        if not date_str:
            date_str = date.today().strftime("%Y-%m-%d")
        records = self._load(date_str)

        header = "时间,类型,币种,方向,数量,价格/入场价,出场价,杠杆,盈亏U,手续费U,盈亏%,原因/评分,来源"
        rows = [header]
        for r in records:
            if r["type"] == "open":
                rows.append(f"{r['time']},开仓,{r['symbol']},{r['side']},{r['qty']},{r['price']},,{r.get('leverage','')},,{r.get('commission','')},,评分{r.get('score','')},{r.get('source','local')}")
            else:
                rows.append(f"{r['time']},平仓,{r['symbol']},{r['side']},{r['qty']},{r.get('entry_price','')},{r.get('exit_price','')},,{r.get('pnl','')},{r.get('commission','')},{r.get('pnl_pct','')},{r.get('reason','')},{r.get('source','local')}")
        return "\n".join(rows)


# 全局单例
journal = TradeJournal()

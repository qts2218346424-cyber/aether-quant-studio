"""新闻爬取模块 - 多源聚合 + 关键词情绪打分"""
import asyncio
import re
import time
from datetime import datetime

import aiohttp

# 情绪关键词库
BULLISH_WORDS = [
    # 英文
    "surge", "rally", "bullish", "breakout", "all-time high", "ath", "soar",
    "pump", "adoption", "approval", "etf inflow", "buy", "upgrade", "record",
    "rebound", "recover", "accumulate", "institutional", "partnership", "launch",
    "mainnet", "listing", "halving", "boost", "gain", "jump", "climb", "rise",
    "optimism", "breakthrough", "milestone", "inflow", "support", "bottom",
    # 中文
    "暴涨", "大涨", "上涨", "反弹", "突破", "新高", "利好", "增持", "买入",
    "获批", "通过", "上线", "合作", "里程碑", "创纪录", "回暖", "复苏", "看涨",
    "多头", "资金流入", "机构买入", "减半", "升级", "主网", "挂牌", "上市",
]
BEARISH_WORDS = [
    # 英文
    "crash", "dump", "bearish", "plunge", "sell-off", "selloff", "hack", "exploit",
    "ban", "lawsuit", "sec", "regulation", "crackdown", "liquidation", "fear",
    "outflow", "decline", "drop", "fall", "loss", "warning", "risk", "fraud",
    "investigation", "delisting", "suspension", "bankrupt", "collapse", "downgrade",
    # 中文
    "暴跌", "大跌", "下跌", "跳水", "崩盘", "利空", "抛售", "卖出", "被盗",
    "黑客", "攻击", "监管", "禁止", "诉讼", "调查", "清算", "爆仓", "恐慌",
    "资金流出", "退市", "停牌", "破产", "倒闭", "看跌", "空头", "腰斩", "割肉",
]


def score_sentiment(text: str) -> int:
    """关键词情绪打分: 正=看多, 负=看空"""
    text = text.lower()
    score = 0
    for w in BULLISH_WORDS:
        if w in text:
            score += 1
    for w in BEARISH_WORDS:
        if w in text:
            score -= 1
    return score


class NewsFetcher:
    """多源新闻聚合，带缓存和降级"""

    def __init__(self, proxy: str = None):
        self.proxy = proxy or None
        self.cache: dict[str, list] = {}   # source -> [news items]
        self.all_news: list[dict] = []
        self.last_fetch = 0
        self.cache_ttl = 300  # 5分钟缓存
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _get(self, url, headers=None):
        session = await self._get_session()
        kwargs = {}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        if headers:
            kwargs["headers"] = headers
        async with session.get(url, **kwargs) as resp:
            return await resp.text(), resp.status

    # ===== 源1: 币安官方公告(影响力最大) =====
    async def fetch_binance_announcements(self) -> list:
        try:
            url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=48&pageNo=1&pageSize=15"
            text, status = await self._get(url, headers={"User-Agent": "Mozilla/5.0"})
            if status != 200:
                return []
            import json
            data = json.loads(text)
            items = []
            articles = data.get("data", {}).get("catalogs", [{}])[0].get("articles", [])
            if not articles:
                articles = data.get("data", {}).get("articles", [])
            for a in articles[:15]:
                title = a.get("title", "")
                items.append({
                    "source": "币安公告",
                    "title": title,
                    "time": a.get("releaseDate", ""),
                    "sentiment": score_sentiment(title),
                    "url": f"https://www.binance.com/en/support/announcement/{a.get('code','')}",
                })
            return items
        except Exception as e:
            print(f"[News] 币安公告失败: {e}")
            return []

    # ===== 源2: CoinDesk RSS =====
    async def fetch_coindesk_rss(self) -> list:
        try:
            url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
            text, status = await self._get(url, headers={"User-Agent": "Mozilla/5.0"})
            if status != 200:
                return []
            return self._parse_rss(text, "CoinDesk")
        except Exception as e:
            print(f"[News] CoinDesk失败: {e}")
            return []

    # ===== 源3: CoinTelegraph RSS =====
    async def fetch_cointelegraph_rss(self) -> list:
        try:
            url = "https://cointelegraph.com/rss"
            text, status = await self._get(url, headers={"User-Agent": "Mozilla/5.0"})
            if status != 200:
                return []
            return self._parse_rss(text, "CoinTelegraph")
        except Exception as e:
            print(f"[News] CoinTelegraph失败: {e}")
            return []

    # ===== 源4: TheBlock RSS =====
    async def fetch_theblock_rss(self) -> list:
        try:
            url = "https://www.theblock.co/rss.xml"
            text, status = await self._get(url, headers={"User-Agent": "Mozilla/5.0"})
            if status != 200:
                return []
            return self._parse_rss(text, "TheBlock")
        except Exception as e:
            print(f"[News] TheBlock失败: {e}")
            return []

    def _parse_rss(self, xml_text: str, source: str) -> list:
        items = []
        # 简单正则解析RSS,避免引入额外依赖
        titles = re.findall(r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>", xml_text)
        links = re.findall(r"<link>(.*?)</link>", xml_text)
        pubs = re.findall(r"<pubDate>(.*?)</pubDate>", xml_text)
        for i, t in enumerate(titles[:12]):
            title = t[0] or t[1]
            if not title or title.strip().lower() in ("rss", source.lower()):
                continue
            items.append({
                "source": source,
                "title": title.strip(),
                "time": pubs[i-1] if i-1 < len(pubs) else "",
                "sentiment": score_sentiment(title),
                "url": links[i] if i < len(links) else "",
            })
        return items[:10]

    # ===== 聚合 =====
    async def fetch_all(self, force: bool = False) -> list:
        now = time.time()
        if not force and self.all_news and (now - self.last_fetch) < self.cache_ttl:
            return self.all_news

        # 并发抓取所有源
        results = await asyncio.gather(
            self.fetch_binance_announcements(),
            self.fetch_coindesk_rss(),
            self.fetch_cointelegraph_rss(),
            self.fetch_theblock_rss(),
            return_exceptions=True,
        )

        all_items = []
        for r in results:
            if isinstance(r, list):
                all_items.extend(r)

        # 按情绪绝对值+时间排序,去重
        seen = set()
        unique = []
        for item in all_items:
            key = item["title"][:50]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        # 强情绪新闻优先
        unique.sort(key=lambda x: -abs(x["sentiment"]))
        self.all_news = unique[:30]
        self.last_fetch = now
        return self.all_news

    def get_sentiment_summary(self) -> dict:
        """新闻整体情绪统计"""
        if not self.all_news:
            return {"total": 0, "bullish": 0, "bearish": 0, "neutral": 0, "score": 0, "bias": "中性"}
        bullish = sum(1 for n in self.all_news if n["sentiment"] > 0)
        bearish = sum(1 for n in self.all_news if n["sentiment"] < 0)
        neutral = len(self.all_news) - bullish - bearish
        total_score = sum(n["sentiment"] for n in self.all_news)
        if bullish > bearish * 1.5:
            bias = "偏多"
        elif bearish > bullish * 1.5:
            bias = "偏空"
        else:
            bias = "中性"
        return {
            "total": len(self.all_news),
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "score": total_score,
            "bias": bias,
        }

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

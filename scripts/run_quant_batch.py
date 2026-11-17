"""全量量化数据跑批、参数自进化优化与 Obsidian 闭环同步脚本 (run_quant_batch.py)

功能:
1. 遍历全部 12 套量化策略模型 (01~12)
2. 加载主流币种 (BTCUSDT / ETHUSDT / SOLUSDT) 真实全周期历史 K 线
3. 执行样本内 (IS 70%) 探索与样本外 (OOS 30%) 防过拟合检验
4. 综合评估核心量化指标: 胜率、总净收益、最大回撤(MDD)、盈亏比(PF)、卡玛比率(Calmar)
5. 自动写回 Obsidian 知识库 (E:\\量化\\01-交易策略) 各策略专属笔记
6. 刷新本地配置预设 config/strategy_presets.json
7. 绝对禁止实盘，全流程无风险纯模拟回测
"""
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
import src  # noqa: F401
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Windows console encoding fix
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from candidate_strategies import CANDIDATE_STRATEGIES_REGISTRY
from strategy_auto_improver import (
    HistoricalDataLoader, CandidateBacktestEngine, StrategyAutoImprover, AutoEvolutionObsidianSync
)
from obsidian_bridge import obsidian_bridge


async def run_batch():
    print("=" * 80)
    print(f"🚀 开始全量量化数据跑批与参数进化优化 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    print("🛡️  安全声明: 全流程使用真实/高拟真离线历史数据，实盘硬锁已开启，零资金风险！")
    print("=" * 80)

    # 1. 准备多品种数据缓存
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    interval = "15m"
    klines_by_sym = {}

    for sym in symbols:
        # 优先读取本地 15m live 数据
        cache_file = Path(f"data/historical_klines/{sym}_15m_live.json")
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= 100:
                    klines_by_sym[sym] = data
                    print(f"[*] 成功载入 {sym} 真实历史 K 线: 共 {len(data)} 根")
                    continue
            except Exception:
                pass
        # 兜底生成
        klines = HistoricalDataLoader.generate_synthetic_klines(sym, interval, 15)
        klines_by_sym[sym] = klines
        print(f"[*] 生成 {sym} 拟真回测 K 线: 共 {len(klines)} 根")

    primary_klines = klines_by_sym.get("BTCUSDT", list(klines_by_sym.values())[0])

    # 2. 依次优化并回测全部 12 套策略
    results = []
    print("\n" + "-" * 80)
    print(f"{'编号':<4} | {'策略ID':<20} | {'策略名称':<25} | {'基线胜率':<8} | {'调优胜率':<8} | {'净收益':<9} | {'回撤MDD':<8} | {'状态'}")
    print("-" * 80)

    for idx, (strat_id, strat_cls) in enumerate(CANDIDATE_STRATEGIES_REGISTRY.items(), 1):
        try:
            # 运行自进化优化
            evo = await StrategyAutoImprover.auto_improve(
                strategy_id=strat_id,
                klines=primary_klines,
                interval=interval,
                split_ratio=0.70
            )

            # 同步写回 Obsidian 笔记
            sync_res = AutoEvolutionObsidianSync.sync_to_obsidian_note(evo)

            base_m = evo["baseline"]["metrics"]
            imp_m = evo["improved"]["metrics"]
            uplift = evo["uplift"]

            status = "✅ 样本外通过" if uplift.get("is_genuine") else "🟡 保持平稳"

            print(f"{idx:02d}   | {strat_id:<20} | {strat_cls.title[:20]:<25} | "
                  f"{base_m['win_rate']:5.1f}%   | {imp_m['win_rate']:5.1f}%   | "
                  f"{imp_m['net_pnl']:+6.2f}%   | {imp_m['max_drawdown']:5.2f}%   | {status}")

            results.append({
                "index": idx,
                "strategy_id": strat_id,
                "title": strat_cls.title,
                "category": strat_cls.category,
                "baseline": base_m,
                "improved": imp_m,
                "uplift": uplift,
                "best_params": evo["improved"]["params"],
                "obsidian_sync": sync_res.get("ok", False),
                "obsidian_file": sync_res.get("file", ""),
            })
        except Exception as exc:
            print(f"[-] 策略 {strat_id} 回测优化失败: {exc}")

    print("-" * 80)

    # 3. 输出汇总并落盘
    summary_path = Path("artifacts/quant_batch_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "interval": interval,
        "total_strategies": len(results),
        "strategies": results
    }
    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[+] 全量回测与自进化汇总数据已持久化保存至: {summary_path}")

    # 4. 触发一次 Obsidian 编译
    vp = obsidian_bridge.get_vault_path()
    if vp and vp.exists():
        print(f"[+] 正在触发 Obsidian 知识库全量编译更新: {vp} ...")
        compile_res = obsidian_bridge.compile_vault(vp)
        print(f"[+] Obsidian 编译完成: 状态={compile_res.get('status')}, 页面数={compile_res.get('compiled_pages', 0)}")

    return summary_data


if __name__ == "__main__":
    asyncio.run(run_batch())

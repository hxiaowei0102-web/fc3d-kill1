# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 暴力穷举（双窗口：200期/300期，三位置独立，v3 大池）
=============================================
公式池：59特征 × 单/双/三特征线性组合 ≈ 905万规格。
numpy 向量化计算窗口期输出，流式更新三位置最优（不存池、不去重、内存O(1)）。
并列裁决：命中率 → 公式更短 → 字典序。

产物：
  best_formula.json       最近 200 期窗口（默认/主窗口，预测跟踪沿用）
  best_formula_300.json   最近 300 期窗口（新增，页面按钮切换展示）
"""
import json
import numpy as np
from engine import load_data
from formulas import feat_list, iter_specs, formula_name

CSV = 'data/fc3d-history.csv'
WINDOW = 200          # 主窗口（线上沿用，跟踪/predictions_log 基准）
WINDOW_300 = 300      # 副窗口（切换展示）
JSON_MAIN = 'best_formula.json'
JSON_300 = 'best_formula_300.json'


def search_best(hh, tt, oo, window=WINDOW, verbose=True):
    N = len(hh)
    if N < window + 1:
        raise ValueError(
            f"数据量不足：仅 {N} 期，至少需要 {window+1} 期（{window}期被预测 + 1期上期）。"
            f"请检查 data/fc3d-history.csv 是否被截断或损坏。")
    start = N - window
    if verbose:
        print(f"穷举窗口: 第 {start+1}..{N} 条数据，共 {window} 期")

    # 特征矩阵 (window, NF)
    rows = [
        feat_list(
            hh[start + k - 1], tt[start + k - 1], oo[start + k - 1],
            prev=(hh[start + k - 2], tt[start + k - 2], oo[start + k - 2]) if start + k - 2 >= 0 else None
        )
        for k in range(window)
    ]
    F = np.array(rows, dtype=np.int64)
    ah = np.array(hh[start:start + window], dtype=np.int64)
    at = np.array(tt[start:start + window], dtype=np.int64)
    ao = np.array(oo[start:start + window], dtype=np.int64)

    # 流式维护三位置最优 (hits, name)
    best = {'h': (-1, ''), 't': (-1, ''), 'o': (-1, '')}
    total = 0
    for terms, const in iter_specs():
        cols = np.array([idx for _, idx in terms], dtype=np.int64)
        coeffs = np.array([c for c, _ in terms], dtype=np.int64)
        out = (F[:, cols] * coeffs).sum(axis=1) + const
        out %= 10
        hh_hits = int((out != ah).sum())
        tt_hits = int((out != at).sum())
        oo_hits = int((out != ao).sum())
        # 惰性生成 name：仅当可能刷新最优时才拼串
        for pos, hits in (('h', hh_hits), ('t', tt_hits), ('o', oo_hits)):
            b_hits, b_name = best[pos]
            if hits >= b_hits:
                name = formula_name(terms, const)
                if hits > b_hits or (len(name), name) < (len(b_name), b_name):
                    best[pos] = (hits, name)
        total += 1

    if verbose:
        print(f"  遍历公式规格: {total:,} 条")
    out = {}
    for pos in ['h', 't', 'o']:
        hits, name = best[pos]
        out[pos] = (name, hits / window, hits)
        if verbose:
            print(f"  {pos} 最优: {name}  命中 {hits}/{window} = {hits/window*100:.2f}%")
    return out, total


def build_result(best, pool_size, issues, window):
    """组装 best_formula*.json 结构"""
    combo = {pos: best[pos][0] for pos in ['h', 't', 'o']}
    return {
        'window': window,
        'data_info': {'n_issues': len(issues), 'first': issues[0], 'last': issues[-1]},
        'pool_size': pool_size,
        'combo': combo,
        'rates': {pos: round(best[pos][1] * 100, 2) for pos in ['h', 't', 'o']},
    }


def run_multi(verbose=True):
    """双窗口穷举：200→best_formula.json(主)，300→best_formula_300.json(副)。
    返回 (results_200, results_300)；任一窗口数据不足则对应为 None 且不写文件。"""
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    if verbose:
        print(f"数据 {N} 期：{issues[0]} ~ {issues[-1]}")

    r200 = r300 = None
    # 主窗口 200（必须，跟踪依赖）
    if N >= WINDOW + 1:
        best, pool = search_best(hh, tt, oo, WINDOW, verbose)
        r200 = build_result(best, pool, issues, WINDOW)
        with open(JSON_MAIN, 'w', encoding='utf-8') as f:
            json.dump(r200, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"已写入 {JSON_MAIN}")

    # 副窗口 300（数据够才跑，失败不阻塞主流程）
    if N >= WINDOW_300 + 1:
        best, pool = search_best(hh, tt, oo, WINDOW_300, verbose)
        r300 = build_result(best, pool, issues, WINDOW_300)
        with open(JSON_300, 'w', encoding='utf-8') as f:
            json.dump(r300, f, ensure_ascii=False, indent=2)
        if verbose:
            print(f"已写入 {JSON_300}")
    else:
        if verbose:
            print(f"数据 {N} 期 < {WINDOW_300}+1，跳过300期窗口（仅生成200期）")
    return r200, r300


def _combo_str(r, pos):
    return f"{r['combo'][pos]}  ({r['rates'][pos]}%)"


def main():
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    r200, r300 = run_multi()
    if r200:
        print(f"\n200期: 百{_combo_str(r200,'h')} 十{_combo_str(r200,'t')} 个{_combo_str(r200,'o')}")
    if r300:
        print(f"300期: 百{_combo_str(r300,'h')} 十{_combo_str(r300,'t')} 个{_combo_str(r300,'o')}")


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 暴力穷举（最新200期，三位置独立，v3 大池）
=============================================
公式池：59特征 × 单/双/三特征线性组合 ≈ 905万规格。
numpy 向量化计算 200期输出，流式更新三位置最优（不存池、不去重、内存O(1)）。
并列裁决：命中率 → 公式更短 → 字典序。
"""
import json
import numpy as np
from engine import load_data
from formulas import feat_list, iter_specs, formula_name

CSV = 'data/fc3d-history.csv'
WINDOW = 200


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


def main():
    issues, hh, tt, oo = load_data(CSV)
    N = len(issues)
    print(f"数据 {N} 期：{issues[0]} ~ {issues[-1]}")
    best, pool_size = search_best(hh, tt, oo, WINDOW)

    combo = {pos: best[pos][0] for pos in ['h', 't', 'o']}
    result = {
        'window': WINDOW,
        'data_info': {'n_issues': N, 'first': issues[0], 'last': issues[-1]},
        'pool_size': pool_size,
        'combo': combo,
        'rates': {pos: round(best[pos][1] * 100, 2) for pos in ['h', 't', 'o']},
    }
    with open('best_formula.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n已写入 best_formula.json")
    print(f"百位: {combo['h']}  ({result['rates']['h']}%)")
    print(f"十位: {combo['t']}  ({result['rates']['t']}%)")
    print(f"个位: {combo['o']}  ({result['rates']['o']}%)")


if __name__ == '__main__':
    main()

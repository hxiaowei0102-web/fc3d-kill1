# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 暴力穷举（最新200期，三位置独立）
=============================================
只参考最新200期，为百/十/个位各穷举出一条命中率最高的杀一码公式。
三位置独立评估（杀一码无需联合搜索），特征矩阵预计算提速。
并列裁决：命中率 → 公式更短 → 全量命中率更高 → 字典序。
"""
import json
from engine import load_data
from formulas import build_pool

CSV = 'data/fc3d-history.csv'
WINDOW = 200


def _hit_count(out, actual_pos):
    return sum(1 for k in range(len(out)) if out[k] != actual_pos[k])


def search_best(hh, tt, oo, window=WINDOW, verbose=True):
    """
    用最新 window 期穷举，返回 {pos: (name, rate, hits)}，pos in h/t/o。
    """
    N = len(hh)
    start = N - window
    if verbose:
        print(f"穷举窗口: 第 {start+1}..{N} 条数据（下标 {start}..{N-1}），共 {window} 期")
    pool = build_pool(hh, tt, oo, start, window, include_pair=True, verbose=verbose)

    actual = {'h': hh[start:], 't': tt[start:], 'o': oo[start:]}
    best = {}
    for pos in ['h', 't', 'o']:
        ap = actual[pos]
        scored = [(_hit_count(out, ap), name) for name, out in pool]
        maxhits = max(c for c, _ in scored)
        tied = [name for c, name in scored if c == maxhits]
        # 并列裁决：公式更短 → 字典序
        tied.sort(key=lambda n: (len(n), n))
        name = tied[0]
        best[pos] = (name, maxhits / window, maxhits)
        if verbose:
            print(f"  {pos} 最优: {name}  命中 {maxhits}/{window} = {maxhits/window*100:.2f}%  (并列{len(tied)}条取最短)")
    return best, len(pool)


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

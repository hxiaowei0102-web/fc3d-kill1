# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 暴力穷举（双窗口：200期/300期，三位置独立，v3 大池）
=============================================
公式池：59特征 × 单/双/三特征线性组合 ≈ 905万规格。
【v3.1 提速版】把 905万次 Python 循环按「特征组合」分组：
  单特征 236 组 + 双特征 1711 组 + 三特征 32509 组 ≈ 3.4万组，
  组内全部系数×常数一次性矩阵化 + bincount 直方图统计命中数。
  数学等价（模10环同态）：out=(base+const)%10≠T  ⟺ diff=(base-T)%10 ≠ (10-const)%10
  即 miss = hist[(10-const)%10]，一次 bincount 同时得到 10 个常数的命中数。
  结果与原逐条版本**完全一致**（含 tie-break 顺序），仅耗时降低约 10 倍。
并列裁决：命中率 → 公式更短 → 字典序。

产物：
  best_formula.json       最近 200 期窗口（默认/主窗口，预测跟踪沿用）
  best_formula_300.json   最近 300 期窗口（新增，页面按钮切换展示）
"""
import json
import numpy as np
from itertools import product
from engine import load_data
from formulas import FEAT_NAMES, COEFFS, TRIPLE_COEFFS

CSV = 'data/fc3d-history.csv'
WINDOW = 200          # 主窗口（线上沿用，跟踪/predictions_log 基准）
WINDOW_300 = 300      # 副窗口（切换展示）
JSON_MAIN = 'best_formula.json'
JSON_300 = 'best_formula_300.json'

# 常数→diff 命中判定查表：miss[c] = count(diff == (10-c)%10)
_CONST_LOOKUP = np.array([(10 - c) % 10 for c in range(10)], dtype=np.int64)
# 双特征系数网格 (16,2)：与原 iter_specs 中 (c1,c2) product(COEFFS) 顺序一致
_PAIR_C = np.array(list(product(COEFFS, COEFFS)), dtype=np.int64)
# 三特征系数网格 (27,3)：product(TRIPLE_COEFFS) 顺序一致
_TRIPLE_C = np.array(list(product(TRIPLE_COEFFS, TRIPLE_COEFFS, TRIPLE_COEFFS)), dtype=np.int64)


def _update_best(best, hits_grid, name_fn):
    """按原逐条 spec 顺序的语义更新最优（hits→公式更短→字典序）。
    hits_grid: (Ncoeff, 10) 第(r,c)格=第r个系数组合×常数c 的命中数，
    行优先顺序 == 原 iter_specs 逐条顺序，组内公式名按该顺序字典序非减，
    因此只需检查：①最大命中首现位置（>当前最优则更新）
    ②最大命中==当前最优时组内第一个同命中者的公式名是否更小。
    """
    b_hits, b_name = best
    maxh = int(hits_grid.max())
    if maxh < b_hits:
        return
    if maxh > b_hits:
        r, cc = divmod(int(np.argmax(hits_grid)), 10)  # 第一个最大值
        name = name_fn(r, cc)
        best[0] = maxh
        best[1] = name
        return
    # maxh == b_hits：组内第一个同命中（名字组内最小），更小才替换
    r, cc = np.argwhere(hits_grid == maxh)[0]
    name = name_fn(int(r), int(cc))
    if (len(name), name) < (len(b_name), b_name):
        best[1] = name


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
    from formulas import feat_list
    rows = [
        feat_list(
            hh[start + k - 1], tt[start + k - 1], oo[start + k - 1],
            prev=(hh[start + k - 2], tt[start + k - 2], oo[start + k - 2]) if start + k - 2 >= 0 else None
        )
        for k in range(window)
    ]
    F = np.array(rows, dtype=np.int64)              # (W, NF)
    T = np.stack([np.array(hh[start:start + window], dtype=np.int64),
                  np.array(tt[start:start + window], dtype=np.int64),
                  np.array(oo[start:start + window], dtype=np.int64)], axis=1)  # (W, 3)

    # 流式维护三位置最优 (hits, name)
    best = {'h': [-1, ''], 't': [-1, ''], 'o': [-1, '']}
    total = 0

    # ===== 单特征 (59×4 组，每组10常数) =====
    for idx in range(len(FEAT_NAMES)):
        fi = F[:, idx]
        feat = FEAT_NAMES[idx]
        for c in COEFFS:
            base = c * fi                                    # (W,)
            total += 10                                      # 该 (idx,c) 的10个常数
            for j, pos in enumerate(('h', 't', 'o')):
                diff = (base - T[:, j]) % 10
                hist = np.bincount(diff, minlength=10)       # 10 bins
                miss = hist[_CONST_LOOKUP]                   # 每常数 miss 数
                b = best[pos]
                for const in range(10):
                    hits = window - int(miss[const])
                    if hits >= b[0]:
                        name = f'{c}*{feat}+{const}'
                        if hits > b[0] or (len(name), name) < (len(b[1]), b[1]):
                            b[0] = hits
                            b[1] = name

    # ===== 双特征 (C(59,2)=1711 组，组内16系数×10常数矩阵化) =====
    for i in range(len(FEAT_NAMES)):
        fi = F[:, i]
        na = FEAT_NAMES[i]
        for j in range(i + 1, len(FEAT_NAMES)):
            fj = F[:, j]
            nb = FEAT_NAMES[j]
            base_grid = (_PAIR_C[:, 0:1] * fi[None, :] + _PAIR_C[:, 1:2] * fj[None, :])  # (16,W)
            for pj, pos in enumerate(('h', 't', 'o')):
                diff = (base_grid - T[None, :, pj]) % 10     # (16,W)
                off = np.arange(_PAIR_C.shape[0])[:, None] * 10
                h = np.bincount((diff + off).ravel(), minlength=_PAIR_C.shape[0] * 10)
                h = h.reshape(_PAIR_C.shape[0], 10)
                miss = h[:, _CONST_LOOKUP]                   # (16,10) miss[r,const]
                hits_grid = window - miss

                def name_fn(r, cc, na=na, nb=nb, pc=_PAIR_C):
                    c1, c2 = int(pc[r, 0]), int(pc[r, 1])
                    return f'{c1}*{na}+{c2}*{nb}+{cc}'
                _update_best(best[pos], hits_grid, name_fn)
            total += _PAIR_C.shape[0] * 10

    # ===== 三特征 (C(59,3)=32509 组，组内27系数×10常数矩阵化) =====
    for i in range(len(FEAT_NAMES)):
        fi = F[:, i]
        na = FEAT_NAMES[i]
        for j in range(i + 1, len(FEAT_NAMES)):
            fj = F[:, j]
            nb = FEAT_NAMES[j]
            for k in range(j + 1, len(FEAT_NAMES)):
                fk = F[:, k]
                nc = FEAT_NAMES[k]
                base_grid = (_TRIPLE_C[:, 0:1] * fi[None, :]
                             + _TRIPLE_C[:, 1:2] * fj[None, :]
                             + _TRIPLE_C[:, 2:3] * fk[None, :])  # (27,W)
                for pj, pos in enumerate(('h', 't', 'o')):
                    diff = (base_grid - T[None, :, pj]) % 10   # (27,W)
                    off = np.arange(_TRIPLE_C.shape[0])[:, None] * 10
                    h = np.bincount((diff + off).ravel(), minlength=_TRIPLE_C.shape[0] * 10)
                    h = h.reshape(_TRIPLE_C.shape[0], 10)
                    miss = h[:, _CONST_LOOKUP]                 # (27,10)
                    hits_grid = window - miss

                    def name_fn(r, cc, na=na, nb=nb, nc=nc, tc=_TRIPLE_C):
                        c1, c2, c3 = int(tc[r, 0]), int(tc[r, 1]), int(tc[r, 2])
                        return f'{c1}*{na}+{c2}*{nb}+{c3}*{nc}+{cc}'
                    _update_best(best[pos], hits_grid, name_fn)
                total += _TRIPLE_C.shape[0] * 10

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

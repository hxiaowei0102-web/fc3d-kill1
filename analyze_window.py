# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 最优窗口期数测算（样本外 walk-forward）
=============================================
问题：线上用「最新200期」穷举905万条选公式，200期是否最优？
方法：不同窗口 N ∈ {100,150,200,250,300,350}，最近300期切3段各100期：
     每段用「段前 N 期」选公式 → 固定公式预测「段内100期」（样本外，未参与选公式）
     统计 3杀全中率 / 三位置命中率。样本外表现最好的 N 即最优窗口。
用法：python analyze_window.py 100    # 只跑 N=100（3段顺序跑，约5-7分钟）
     汇总由 sum_window_results.py 完成
"""
import sys, json, os, time
import numpy as np
from engine import load_data
from formulas import feat_list, iter_specs, formula_name

CSV = 'data/fc3d-history.csv'
SEG_LEN = 100          # 每段样本外评估期数
N_SEG = 3              # 段数（最近 3*100=300 期）

# 段起点由数据量计算：seg0 = [end-300, end-201], seg1=[end-200,end-101], seg2=[end-100,end-1]


def select_best_on_range(hh, tt, oo, pred_start, n_pred):
    """用被预测期 [pred_start, pred_start+n_pred) 选三位置最优公式（905万条全池）
    特征：第 i 期预测用 i-1、i-2 期数据。返回 {pos:(name,hits)} 和 窗口内3杀全中数"""
    rows = [
        feat_list(
            hh[k], tt[k], oo[k],
            prev=(hh[k-1], tt[k-1], oo[k-1]) if k >= 1 else None
        )
        for k in range(pred_start - 1, pred_start + n_pred - 1)
    ]
    F = np.array(rows, dtype=np.int64)
    ah = np.array(hh[pred_start:pred_start + n_pred], dtype=np.int64)
    at = np.array(tt[pred_start:pred_start + n_pred], dtype=np.int64)
    ao = np.array(oo[pred_start:pred_start + n_pred], dtype=np.int64)

    best = {'h': (-1, ''), 't': (-1, ''), 'o': (-1, '')}
    win_all3_best = -1
    win_all3_name = ''
    for terms, const in iter_specs():
        cols = np.array([idx for _, idx in terms], dtype=np.int64)
        coeffs = np.array([c for c, _ in terms], dtype=np.int64)
        out = (F[:, cols] * coeffs).sum(axis=1) + const
        out %= 10
        hh_hits = int((out != ah).sum())
        tt_hits = int((out != at).sum())
        oo_hits = int((out != ao).sum())
        for pos, hits in (('h', hh_hits), ('t', tt_hits), ('o', oo_hits)):
            b_hits, b_name = best[pos]
            if hits >= b_hits:
                name = formula_name(terms, const)
                if hits > b_hits or (len(name), name) < (len(b_name), b_name):
                    best[pos] = (hits, name)
        # 窗口内 3杀全中（选公式时顺带统计，作为自洽参照）
        all3 = int(((out != ah) & (out != at) & (out != ao)).sum())
        if all3 > win_all3_best:
            win_all3_best = all3
            win_all3_name = formula_name(terms, const)
    return best, win_all3_best, win_all3_name


def eval_out_of_sample(hh, tt, oo, best, ev_start, ev_end):
    """固定公式评估样本外 [ev_start, ev_end]（含），统计三位置命中与3杀全中
    第 i 期预测：上期=i-1，前2期=i-2（与 backtest.py 一致，不偷看未来）"""
    from formulas import make_predictor
    fns = {pos: make_predictor(best[pos][1]) for pos in ['h', 't', 'o']}
    n = ev_end - ev_start + 1
    hh_hit = tt_hit = oo_hit = all3 = 0
    for i in range(ev_start, ev_end + 1):
        pb, ps, pg = hh[i-1], tt[i-1], oo[i-1]
        prev = (hh[i-2], tt[i-2], oo[i-2]) if i >= 2 else None
        kh = fns['h'](pb, ps, pg, prev)
        kt = fns['t'](pb, ps, pg, prev)
        ko = fns['o'](pb, ps, pg, prev)
        if kh != hh[i]: hh_hit += 1
        if kt != tt[i]: tt_hit += 1
        if ko != oo[i]: oo_hit += 1
        if kh != hh[i] and kt != tt[i] and ko != oo[i]: all3 += 1
    return {
        'h': round(hh_hit / n * 100, 2), 't': round(tt_hit / n * 100, 2),
        'o': round(oo_hit / n * 100, 2), 'all3': round(all3 / n * 100, 2),
        'all3_hits': all3, 'n': n,
    }


def main():
    N = int(sys.argv[1])
    issues, hh, tt, oo = load_data(CSV)
    n_total = len(hh)
    end = n_total - 1
    # 段划分：seg2 最靠近末端
    seg_starts = [end - N_SEG * SEG_LEN + 1, end - 2 * SEG_LEN + 1, end - SEG_LEN + 1]
    result = {'N': N, 'n_total': n_total, 'segs': {}, 'avg': None}
    print(f"=== 窗口 N={N} 测算开始 {time.strftime('%H:%M:%S')} ===")
    for si, seg_start in enumerate(seg_starts):
        seg_end = seg_start + SEG_LEN - 1
        pred_start = seg_start - N  # 选公式窗口（被预测期）
        if pred_start - 2 < 0:
            print(f"  段{si+1} 数据不足（pred_start={pred_start}），跳过")
            continue
        t0 = time.time()
        best, win_all3, win_name = select_best_on_range(hh, tt, oo, pred_start, N)
        sel = {'h': best['h'][1], 't': best['t'][1], 'o': best['o'][1]}
        oos = eval_out_of_sample(hh, tt, oo, best, seg_start, seg_end)
        result['segs'][f'seg{si+1}'] = {
            'range': f"{issues[seg_start]}~{issues[seg_end]}",
            'selected_formulas': sel,
            'in_window_all3': round(win_all3 / N * 100, 2),
            'oos': oos,
        }
        print(f"  段{si+1} [{issues[seg_start]}~{issues[seg_end]}] 样本外3杀全中 {oos['all3']}% "
              f"(百{oos['h']}% 十{oos['t']}% 个{oos['o']}%) 耗时{time.time()-t0:.0f}s")
    segs = result['segs']
    if segs:
        result['avg'] = {
            'all3': round(sum(s['oos']['all3'] for s in segs.values()) / len(segs), 2),
            'h': round(sum(s['oos']['h'] for s in segs.values()) / len(segs), 2),
            't': round(sum(s['oos']['t'] for s in segs.values()) / len(segs), 2),
            'o': round(sum(s['oos']['o'] for s in segs.values()) / len(segs), 2),
        }
        print(f"  N={N} 样本外平均: 3杀全中 {result['avg']['all3']}% (百{result['avg']['h']}% 十{result['avg']['t']}% 个{result['avg']['o']}%)")
    os.makedirs('results', exist_ok=True)
    with open(f'results/window_N{N}.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 已写 results/window_N{N}.json")


if __name__ == '__main__':
    main()

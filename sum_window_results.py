# -*- coding: utf-8 -*-
"""汇总 results/window_N*.json 为窗口期数对比表"""
import json, glob, os, sys

sys.stdout.reconfigure(encoding='utf-8')

rows = []
for p in sorted(glob.glob('results/window_N*.json'), key=lambda x: int(x.split('N')[1].split('.')[0])):
    d = json.load(open(p, encoding='utf-8'))
    N = d['N']
    if not d.get('avg'):
        continue
    a = d['avg']
    segs = d['segs']
    seg_rates = {k: v['oos']['all3'] for k, v in segs.items()}
    rows.append((N, a['all3'], a['h'], a['t'], a['o'], seg_rates))

print("=" * 78)
print(f"{'窗口N':>6} | {'样本外3杀全中':>10} | {'百':>6} {'十':>6} {'个':>6} | {'段1':>5} {'段2':>5} {'段3':>5}")
print("-" * 78)
for N, all3, h, t, o, segs in rows:
    print(f"{N:>6} | {all3:>9.2f}% | {h:>5.2f}% {t:>5.2f}% {o:>5.2f}% | {segs.get('seg1','-'):>5} {segs.get('seg2','-'):>5} {segs.get('seg3','-'):>5}")
print("=" * 78)
print(f"随机基线: 单码90% / 3杀全中72.9%")
if rows:
    best = max(rows, key=lambda r: r[1])
    print(f"\n样本外最优窗口: N={best[0]} (3杀全中 {best[1]}%)")
    print(f"线上当前: N=200 (样本外 {[r[1] for r in rows if r[0]==200][0]}%)")

# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 公式体系导出（AI可读）
=============================================
自动提取项目全部公式体系信息，输出：
  - 杀一码公式体系_AI版.md   人机可读文档
  - formulas_data.json       AI结构化数据
所有数据从 formulas.py / best_formula.json / backtest 实时提取，保证与代码一致。
"""
import json, os, math, itertools
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

from engine import load_data
from formulas import FEAT_NAMES, NF, COEFFS, TRIPLE_COEFFS, make_predictor, iter_specs, formula_name
import gen_site
import backtest

# ============ 特征表达式定义（与 formulas.feat_list 严格一致） ============
FEAT_EXPR = {
    'b': 'b', 's': 's', 'g': 'g',
    'b2': 'b*b%10', 's2': 's*s%10', 'g2': 'g*g%10',
    'b3': 'b*b*b%10', 's3': 's*s*s%10', 'g3': 'g*g*g%10',
    'S': 'b+s+g', 'S10': '(b+s+g)%10', 'P': 'max(b,s,g)-min(b,s,g)',
    'mx': 'max(b,s,g)', 'mn': 'min(b,s,g)', 'md': '中位数(b,s,g)',
    'd1': '|b-s|', 'd2': '|b-g|', 'd3': '|s-g|',
    'bs': '(b*s)%10', 'bg': '(b*g)%10', 'sg': '(s*g)%10', 'bsg': '(b*s*g)%10',
    'S2': 'S*S%10', 'P2': 'P*P%10',
    'sum2': '(b+s)%10', 'sum3': '(s+g)%10', 'sum4': '(b+g)%10',
    'bp': '(b**g)%10,g=0时=1', 'gp': '(g**b)%10,b=0时=1', 'sp': '(s**g)%10,g=0时=1',
    'bo': 'b%2', 'so': 's%2', 'go': 'g%2', 'So': 'S%2',
    'd12': '(d1*d2)%10', 'd13': '(d1*d3)%10', 'd23': '(d2*d3)%10',
    'mxmn': '(mx*mn)%10', 'mxmd': '(mx+md)%10', 'mnmd': '(mn+md)%10',
    'S3': '(S*S*S)%10',
    'dsum': '(d1+d2+d3)%10',
    'bsg2': '(b*s+s*g+g*b)%10',
    'bL': '前2期百位', 'sL': '前2期十位', 'gL': '前2期个位',
    'SL': 'bL+sL+gL', 'S10L': '(bL+sL+gL)%10',
    'PL': 'max(bL,sL,gL)-min(bL,sL,gL)',
    'db': '(b-bL)%10', 'ds': '(s-sL)%10', 'dg': '(g-gL)%10',
    'dS': '(S-SL)%10',
    'bh': '(b+bL)%10', 'sh': '(s+sL)%10', 'gh': '(g+gL)%10',
    'bpr': '(b*bL)%10', 'spr': '(s*sL)%10', 'gpr': '(g*gL)%10',
}

FEAT_GROUP = {
    'v1_single': '上期单期基础(34个)',
    'v2_single': '单期派生(9个)',
    'v2_cross': '跨期·前2期(16个)',
}


def _feat_group(name):
    idx = FEAT_NAMES.index(name)
    if idx < 34:
        return 'v1_single'
    if idx < 43:
        return 'v2_single'
    return 'v2_cross'


def build_data():
    issues, hh, tt, oo = load_data('data/fc3d-history.csv')
    with open('best_formula.json', 'r', encoding='utf-8') as f:
        bf = json.load(f)
    combo = bf['combo']
    rates = bf['rates']
    pool_size = bf['pool_size']

    bt = backtest.run_backtest('data/fc3d-history.csv', combo, n=200)
    sm = bt['summary']
    pred = backtest.predict_next('data/fc3d-history.csv', combo)

    # 手算示例：上期 2026221=2,9,6，前2期 2026220=3,7,3 → 预测 2026222
    ex_b, ex_s, ex_g = 2, 9, 6
    ex_prev = (3, 7, 3)
    example = {}
    for pos in ['h', 't', 'o']:
        fn = make_predictor(combo[pos])
        kill = fn(ex_b, ex_s, ex_g, ex_prev)
        example[pos] = {
            'formula': combo[pos],
            'input': f"上期({ex_b},{ex_s},{ex_g}) 前2期{ex_prev}",
            'kill': kill,
        }

    # 特征表
    features = []
    for name in FEAT_NAMES:
        features.append({
            'name': name,
            'group': FEAT_GROUP[_feat_group(name)],
            'zh': gen_site.FEAT_ZH.get(name, name),
            'expr': FEAT_EXPR[name],
        })

    # 公式池分层统计
    n_single = NF * len(COEFFS) * 10
    n_pair = (NF * (NF - 1) // 2) * len(COEFFS) * len(COEFFS) * 10
    n_triple = (NF * (NF - 1) * (NF - 2) // 6) * len(TRIPLE_COEFFS) ** 3 * 10
    n_total = n_single + n_pair + n_triple

    return {
        'meta': {
            'project': '福彩3D 百十个位各杀一码',
            'export_time': datetime.now(BJT).strftime('%Y-%m-%d %H:%M'),
            'data_periods': len(issues),
            'data_range': f"{issues[0]}~{issues[-1]}",
            'latest_draw': f"{hh[-1]}{tt[-1]}{oo[-1]}",
            'window': 200,
        },
        'features': features,
        'generation': {
            'type': '线性组合公式（暴力穷举）',
            'feature_count': NF,
            'coefficients_single_pair': list(COEFFS),
            'coefficients_triple': list(TRIPLE_COEFFS),
            'constants': list(range(10)),
            'mod': 10,
            'pool_stats': {
                'single': n_single, 'pair': n_pair, 'triple': n_triple, 'total': n_total,
            },
        },
        'selection': {
            'window': 200,
            'hit_definition': '预测杀码 ≠ 该期该位开奖号（杀对=命中）',
            'evaluate_input': '第i期预测只用第i-1期(上期)及第i-2期(前2期)数据，不偷看未来',
            'tie_break': ['命中率最高', '公式字符串更短', '字典序'],
        },
        'current_best': {
            pos: {
                'formula': combo[pos],
                'rate': rates[pos],
                'hits': int(rates[pos] / 100 * 200 + 0.5),
                'window': 200,
                'explain_zh': gen_site.explain(combo[pos]),
            } for pos in ['h', 't', 'o']
        },
        'example_predict': {
            'next_issue': pred['next_issue'],
            'last_issue': pred['last_issue'],
            'last_draw': pred['last_draw'],
            'kills': {'h': pred['kh'], 't': pred['kt'], 'o': pred['ko']},
            'hand_calc': example,
        },
        'backtest': {
            'hundreds': sm['hundreds_hit_rate'],
            'tens': sm['tens_hit_rate'],
            'ones': sm['ones_hit_rate'],
            'all3': sm['all_hit_rate'],
            'total_periods': sm['total_periods'],
            'max_miss_streak': sm['max_streak'],
            'random_baseline_all3': 72.9,
        },
        'reproduce': {
            'desc': '全部905万条公式可由 formulas.iter_specs() 流式重新生成（见 formulas.py），无需存储',
            'files': ['formulas.py', 'bruteforce.py', 'backtest.py', 'best_formula.json'],
        },
        'pool_samples': [
            formula_name(terms, const)
            for terms, const in itertools.islice(iter_specs(), 20)
        ],
    }


def gen_md(d):
    md = []
    md.append('# 福彩3D 百十个位各杀一码 — 公式体系（AI可读版）')
    md.append('')
    md.append(f"> 导出时间：{d['meta']['export_time']}（北京时间）  ")
    md.append(f"> 数据：{d['meta']['data_periods']}期（{d['meta']['data_range']}），最新开奖 {d['meta']['latest_draw']}  ")
    md.append(f"> 窗口：最新 {d['meta']['window']} 期")
    md.append('')
    md.append('---')
    md.append('')
    md.append('## 1. 系统概述')
    md.append('')
    md.append('对福彩3D开奖号码（百位/十位/个位各 0-9 一个数字），为**每个位置各杀1个码**。')
    md.append('算法：暴力穷举公式池（最新200期上命中率最高者胜出），每位置选1条公式，公式固定应用于后续预测与回测。')
    md.append('')
    md.append('- 预测规则：第 i 期预测只用第 i-1 期（上期）与第 i-2 期（前2期）数据，**不偷看未来**')
    md.append('- 命中定义：**预测杀码 ≠ 该期该位开奖号** 即杀对（随机基线 90%）')
    md.append('- 3杀全中基线：0.9³ = **72.9%**')
    md.append('')
    md.append('## 2. 特征体系（59个）')
    md.append('')
    md.append('输入：`b`=上期百位, `s`=上期十位, `g`=上期个位；`bL/sL/gL`=前2期三码。特征输出均为 0-9 整数（个别为 0-27）。')
    md.append('')
    md.append('| # | 名称 | 分组 | 中文含义 | 计算式 |')
    md.append('|---|---|---|---|---|')
    for i, f in enumerate(d['features'], 1):
        md.append(f"| {i} | `{f['name']}` | {f['group']} | {f['zh']} | `{f['expr']}` |")
    md.append('')
    md.append('## 3. 公式生成规则（可复现全部公式）')
    md.append('')
    md.append('公式为**线性组合取个位**：')
    md.append('')
    md.append('```')
    md.append(f"公式 = ( c1*特征A + c2*特征B [+ c3*特征C] + 常数 ) mod 10")
    md.append(f"单特征：c ∈ {d['generation']['coefficients_single_pair']}，常数 ∈ {d['generation']['constants']}")
    md.append(f"双特征：两个特征不同，c1,c2 ∈ {d['generation']['coefficients_single_pair']}")
    md.append(f"三特征：三个特征互异，c1,c2,c3 ∈ {d['generation']['coefficients_triple']}")
    md.append(f"组合方式：全部单特征 + 全部双特征组合 + 全部三特征组合")
    md.append('```')
    md.append('')
    p = d['generation']['pool_stats']
    md.append('| 层 | 公式条数 |')
    md.append('|---|---|')
    md.append(f"| 单特征 | {p['single']:,} |")
    md.append(f"| 双特征 | {p['pair']:,} |")
    md.append(f"| 三特征 | {p['triple']:,} |")
    md.append(f"| **合计** | **{p['total']:,}** |")
    md.append('')
    md.append('> 全部公式无需存储：`formulas.py` 中 `iter_specs()` 生成器可按此规则流式重现（numpy 向量化评估约 140 秒/轮）。')
    md.append('')
    md.append('### 公式池示例样本（前20条）')
    md.append('')
    md.append('```')
    for s in d['pool_samples']:
        md.append(s)
    md.append('```')
    md.append('')
    md.append('## 4. 选择逻辑（如何选最优公式）')
    md.append('')
    md.append(f"1. 用最新 {d['selection']['window']} 期逐条评估全部公式（每期用上期/前2期数据算杀码，对比该期开奖）")
    md.append(f"2. 统计命中率 = 杀对数 / {d['selection']['window']}")
    md.append(f"3. 三位置（百/十/个）**独立**选最优，互不影响")
    md.append(f"4. 并列裁决：{' → '.join(d['selection']['tie_break'])}")
    md.append('')
    md.append('## 5. 当前最优公式（2026222期在用）')
    md.append('')
    md.append('| 位置 | 公式 | 近200期命中率 | 白话解释 |')
    md.append('|---|---|---|---|')
    for pos, zh in [('h', '百位'), ('t', '十位'), ('o', '个位')]:
        v = d['current_best'][pos]
        md.append(f"| {zh} | `{v['formula']}` | {v['rate']}% ({v['hits']}/{v['window']}) | {v['explain_zh']} |")
    md.append('')
    md.append('### 手算验证示例')
    md.append('')
    for pos, zh in [('h', '百位'), ('t', '十位'), ('o', '个位')]:
        v = d['example_predict']['hand_calc'][pos]
        md.append(f"**{zh}** `{v['formula']}`，{v['input']} → 杀 **{v['kill']}**")
    md.append('')
    md.append(f"**预测 {d['example_predict']['next_issue']} 期**（上期 {d['example_predict']['last_issue']}={''.join(map(str, d['example_predict']['last_draw']))}）："
              f"百位杀 **{d['example_predict']['kills']['h']}**、十位杀 **{d['example_predict']['kills']['t']}**、个位杀 **{d['example_predict']['kills']['o']}**")
    md.append('')
    md.append('## 6. 200期回测结果（固定公式回看）')
    md.append('')
    b = d['backtest']
    md.append('| 指标 | 值 |')
    md.append('|---|---|')
    md.append(f"| 百位命中率 | {b['hundreds']}% |")
    md.append(f"| 十位命中率 | {b['tens']}% |")
    md.append(f"| 个位命中率 | {b['ones']}% |")
    md.append(f"| **★3杀全中率** | **{b['all3']}%**（随机基线 {b['random_baseline_all3']}%） |")
    md.append(f"| 最大连错 | {b['max_miss_streak']}期 |")
    md.append(f"| 回测期数 | {b['total_periods']}期 |")
    md.append('')
    md.append('> ⚠ 公式由最近200期穷举选出，属历史拟合；样本外命中率会回落，仅供研究参考。')
    md.append('')
    md.append('## 7. 复现指引')
    md.append('')
    md.append('| 文件 | 职责 |')
    md.append('|---|---|')
    md.append('| `formulas.py` | 59特征定义 + 公式生成器 `iter_specs()` |')
    md.append('| `bruteforce.py` | numpy向量化穷举评估（905万条约140秒） |')
    md.append('| `backtest.py` | 固定公式200期回测 + 下期预测 |')
    md.append('| `best_formula.json` | 当前最优3条公式 |')
    md.append('| `fetch.py` | 多源降级抓取最新开奖（云端自动） |')
    md.append('')
    md.append('`python update.py` 一键：抓数据→穷举→回测→生成网页。')
    return '\n'.join(md)


def main():
    d = build_data()
    os.makedirs('docs', exist_ok=True)
    with open('docs/formulas_data.json', 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    md = gen_md(d)
    with open('docs/杀一码公式体系_AI版.md', 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"✅ 已生成 docs/杀一码公式体系_AI版.md（{len(md)} 字符）")
    print(f"✅ 已生成 docs/formulas_data.json")
    print(f"   特征 {d['generation']['feature_count']} 个 | 公式池 {d['generation']['pool_stats']['total']:,} 条")
    print(f"   最优: 百{d['current_best']['h']['rate']}% 十{d['current_best']['t']['rate']}% 个{d['current_best']['o']['rate']}% | 3杀全中{d['backtest']['all3']}%")


if __name__ == '__main__':
    main()

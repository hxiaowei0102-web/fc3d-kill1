# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 特征引擎 + 公式库
=============================================
所有特征均由「上期」三码 b=百位, s=十位, g=个位 计算，输出落到 0-9 单数字。
穷举池 = 海量线性公式（特征×系数+常数、双特征组合），4-bit打包去重。
"""
from engine import load_data

# 34 个单期特征（与参考项目 feat_list 完全一致，保证可验证）
FEAT_NAMES = [
    'b', 's', 'g',
    'b2', 's2', 'g2',
    'b3', 's3', 'g3',
    'S', 'S10', 'P', 'mx', 'mn', 'md',
    'd1', 'd2', 'd3',
    'bs', 'bg', 'sg', 'bsg',
    'S2', 'P2',
    'sum2', 'sum3', 'sum4',
    'bp', 'gp', 'sp',
    'bo', 'so', 'go', 'So',
]
_IDX = {n: i for i, n in enumerate(FEAT_NAMES)}
NF = len(FEAT_NAMES)


def feat_list(b, s, g):
    mx = max(b, s, g); mn = min(b, s, g); md = b + s + g - mx - mn
    S = b + s + g; P = mx - mn
    return [
        b, s, g,
        b * b % 10, s * s % 10, g * g % 10,
        b * b * b % 10, s * s * s % 10, g * g * g % 10,
        S, S % 10, P, mx, mn, md,
        abs(b - s), abs(b - g), abs(s - g),
        b * s % 10, b * g % 10, s * g % 10, b * s * g % 10,
        S * S % 10, P * P % 10,
        (b + s) % 10, (s + g) % 10, (b + g) % 10,
        (1 if g == 0 else b ** g) % 10, (1 if b == 0 else g ** b) % 10, (1 if g == 0 else s ** g) % 10,
        b % 2, s % 2, g % 2, S % 2,
    ]


def eval_linear(feats, terms, const):
    v = const
    for c, idx in terms:
        v += c * feats[idx]
    return v % 10


def formula_name(terms, const):
    return '+'.join(f'{c}*{FEAT_NAMES[idx]}' for c, idx in terms) + f'+{const}'


# ============ 穷举池构建 ============
def build_linear_specs(include_pair=True, include_single=True):
    """生成 (terms, const) 规格列表（未去重）"""
    specs = []
    if include_single:
        for idx in range(NF):
            for c in (1, 2, 3):
                for const in range(10):
                    specs.append((((c, idx),), const))
    if include_pair:
        for i in range(NF):
            for j in range(i + 1, NF):
                for c1 in (1, 2, 3):
                    for c2 in (1, 2, 3):
                        for const in range(10):
                            specs.append((((c1, i), (c2, j)), const))
    return specs


def build_pool(hh, tt, oo, start, window, include_pair=True, verbose=True):
    """
    在近 window 期（start..start+window-1 为被预测期，用上期 start+k-1 的特征）上构建算法池。
    返回 [(name, [window outputs]), ...]，已按 4-bit 打包去重。
    """
    feats = [feat_list(hh[start + k - 1], tt[start + k - 1], oo[start + k - 1]) for k in range(window)]
    specs = build_linear_specs(include_pair=include_pair)
    if verbose:
        print(f"  线性公式数(去重前): {len(specs)}")

    pool = []
    seen = set()
    for terms, const in specs:
        out = []
        for k in range(window):
            v = const
            for c, idx in terms:
                v += c * feats[k][idx]
            out.append(v % 10)
        packed = 0
        for k, v in enumerate(out):
            packed |= v << (4 * k)
        if packed in seen:
            continue
        seen.add(packed)
        pool.append((formula_name(terms, const), out))
    if verbose:
        print(f"  算法池(去重后): {len(pool)} 个")
    return pool


def make_predictor(name):
    """把公式名编译为 (b,s,g)->int 的可调用函数，用于回测与预测"""
    terms, const = parse_linear(name)
    def fn(b, s, g, terms=terms, const=const):
        return eval_linear(feat_list(b, s, g), terms, const)
    return fn


def parse_linear(name):
    terms = []
    const = 0
    for part in name.split('+'):
        part = part.strip()
        if '*' in part:
            c_str, feat = part.split('*', 1)
            terms.append((int(c_str), _IDX[feat]))
        elif part.isdigit():
            const += int(part)
        else:
            terms.append((1, _IDX[part]))
    return terms, const


if __name__ == '__main__':
    issues, h, t, o = load_data()
    N = len(issues)
    pool = build_pool(h, t, o, N - 200, 200)
    print(f"示例公式: {pool[0][0]}")

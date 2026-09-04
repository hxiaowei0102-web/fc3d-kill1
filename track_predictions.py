# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 每日预测跟踪（真正的每日预测留痕+自动验证）
=============================================
职责：
1. **验证历史预测**：predictions_log.csv 中 status=pending 的预测，
   若对应期号已开奖（CSV中已出现），自动回填实际开奖并判定命中/失误。
2. **追加今日新预测**：把当天系统报出的预测（百/十/个杀码+公式）写入日志，
   供次日开奖后自动验证。
3. **累计统计**：输出真实累计命中率（全部验证过的预测）。

设计要点：
- 幂等：同一期号不重复记录（upsert by issue）；已验证不重复验证。
- 预测依据：第i期预测只用第i-1期(上期)及第i-2期(前2期)数据，不偷看未来。
- 回填历史：首次启用时，用固定公式把最近 N 期历史预测全部回填验证，
  让跟踪从第一天就有真实样本，而不是从今天才从零开始。
"""
import csv, json, os
from datetime import datetime, timezone, timedelta
from engine import load_data, get_next_issue
from formulas import make_predictor

CSV_PATH = 'data/fc3d-history.csv'
LOG_PATH = 'predictions_log.csv'          # 200期窗口 跟踪日志（唯一）
HEADER = ['issue', 'kh', 'kt', 'ko', 'prev_issue', 'prev_draw',
          'formula_h', 'formula_t', 'formula_o',
          'draw', 'h_hit', 't_hit', 'o_hit', 'all_hit', 'status', 'source',
          'predicted_at', 'verified_at']
STATUS = {'PENDING': 'pending', 'ALL_HIT': 'hit', 'PARTIAL': 'partial', 'MISS': 'miss'}
BJT = timezone(timedelta(hours=8))


def _now_bjt():
    """当前北京时间，格式 2026-08-28 22:00"""
    return datetime.now(BJT).strftime('%Y-%m-%d %H:%M')


def _load_log(path=LOG_PATH):
    """读日志，返回 {issue: row}。旧行缺新列时补默认值（向前兼容）"""
    rows = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r.get('issue'):
                    for k in ('predicted_at', 'verified_at'):
                        if k not in r or r[k] is None:
                            r[k] = ''
                    rows[r['issue']] = r
    return rows


def _save_log(rows, path=LOG_PATH):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for iss in sorted(rows.keys(), key=int):
            w.writerow({k: rows[iss].get(k, '') for k in HEADER})


def _compute_kills(combo, prev_draw, prev2_draw):
    """用公式计算预测杀码。prev_draw=(b,s,g)上期, prev2_draw=(bL,sL,gL)前2期"""
    pb, ps, pg = prev_draw
    fns = {pos: make_predictor(combo[pos]) for pos in ['h', 't', 'o']}
    return {
        'kh': fns['h'](pb, ps, pg, prev2_draw),
        'kt': fns['t'](pb, ps, pg, prev2_draw),
        'ko': fns['o'](pb, ps, pg, prev2_draw),
    }


def backfill_history(combo, n=60, path=LOG_PATH):
    """用固定公式回填最近n期历史预测并验证（第i期预测只用i-1期数据）。
    source=backfill 标记历史回填（区分真实每日跟踪）。
    返回新增的已验证记录数。"""
    issues, hh, tt, oo = load_data(CSV_PATH)
    N = len(issues)
    rows = _load_log(path)
    added = 0
    start = max(2, N - n)  # 需要前2期数据，从第2期起
    for i in range(start, N):
        target = issues[i]          # 被预测期（=开奖已出）
        prev_issue = issues[i-1]    # 上期
        prev_draw = (hh[i-1], tt[i-1], oo[i-1])
        prev2 = (hh[i-2], tt[i-2], oo[i-2])
        if target in rows:
            continue
        kills = _compute_kills(combo, prev_draw, prev2)
        draw = (hh[i], tt[i], oo[i])
        h_hit = kills['kh'] != draw[0]
        t_hit = kills['kt'] != draw[1]
        o_hit = kills['ko'] != draw[2]
        all_hit = h_hit and t_hit and o_hit
        status = STATUS['ALL_HIT'] if all_hit else (STATUS['MISS'] if not (h_hit or t_hit or o_hit) else STATUS['PARTIAL'])
        rows[target] = {
            'issue': target, 'kh': kills['kh'], 'kt': kills['kt'], 'ko': kills['ko'],
            'prev_issue': prev_issue, 'prev_draw': ''.join(map(str, prev_draw)),
            'formula_h': combo['h'], 'formula_t': combo['t'], 'formula_o': combo['o'],
            'draw': ''.join(map(str, draw)),
            'h_hit': '1' if h_hit else '0', 't_hit': '1' if t_hit else '0',
            'o_hit': '1' if o_hit else '0', 'all_hit': '1' if all_hit else '0',
            'status': status, 'source': 'backfill',
            'predicted_at': '回填', 'verified_at': '回填',
        }
        added += 1
    _save_log(rows, path)
    return added


def verify_pending(combo, path=LOG_PATH):
    """验证所有 pending 预测：对应期号已开奖 → 回填判定。
    返回 (验证条数, 全中条数, 失误条数)"""
    issues, hh, tt, oo = load_data(CSV_PATH)
    draw_map = {iss: (h, t, o) for iss, h, t, o in zip(issues, hh, tt, oo)}
    rows = _load_log(path)
    verified = hit = miss = 0
    for iss, row in rows.items():
        if row.get('status') != STATUS['PENDING']:
            continue
        if iss not in draw_map:
            continue  # 还没开奖
        draw = draw_map[iss]
        kh, kt, ko = int(row['kh']), int(row['kt']), int(row['ko'])
        h_hit = kh != draw[0]
        t_hit = kt != draw[1]
        o_hit = ko != draw[2]
        all_hit = h_hit and t_hit and o_hit
        row['draw'] = ''.join(map(str, draw))
        row['h_hit'] = '1' if h_hit else '0'
        row['t_hit'] = '1' if t_hit else '0'
        row['o_hit'] = '1' if o_hit else '0'
        row['all_hit'] = '1' if all_hit else '0'
        row['status'] = STATUS['ALL_HIT'] if all_hit else (STATUS['MISS'] if not (h_hit or t_hit or o_hit) else STATUS['PARTIAL'])
        row['verified_at'] = _now_bjt()
        verified += 1
        if all_hit:
            hit += 1
        else:
            miss += 1
    _save_log(rows, path)
    return verified, hit, miss


def add_prediction(combo, issue=None, path=LOG_PATH):
    """追加今日新预测（系统当前对下一期的预测）。幂等：该期已记录则跳过。"""
    rows = _load_log(path)
    issues, hh, tt, oo = load_data(CSV_PATH)
    latest = issues[-1]
    if issue is None:
        issue = get_next_issue(latest)
    if issue in rows:
        return 0
    prev_draw = (hh[-1], tt[-1], oo[-1])
    prev2 = (hh[-2], tt[-2], oo[-2])
    kills = _compute_kills(combo, prev_draw, prev2)
    rows[issue] = {
        'issue': issue, 'kh': kills['kh'], 'kt': kills['kt'], 'ko': kills['ko'],
        'prev_issue': latest, 'prev_draw': ''.join(map(str, prev_draw)),
        'formula_h': combo['h'], 'formula_t': combo['t'], 'formula_o': combo['o'],
        'draw': '', 'h_hit': '', 't_hit': '', 'o_hit': '', 'all_hit': '',
        'status': STATUS['PENDING'], 'source': 'live',
        'predicted_at': _now_bjt(), 'verified_at': '',
    }
    _save_log(rows, path)
    return 1


def summarize(combo=None, path=LOG_PATH):
    """统计真实累计命中率（仅已验证预测）。
    区分 source=live（真实每日跟踪）与 source=backfill（历史回填基准）。"""
    rows = _load_log(path)
    verified = [r for r in rows.values() if r.get('status') in (STATUS['ALL_HIT'], STATUS['PARTIAL'], STATUS['MISS'])]
    pending = [r for r in rows.values() if r.get('status') == STATUS['PENDING']]
    n = len(verified)
    if n == 0:
        return {'total': 0, 'pending': len(pending), 'verified': 0,
                'all_hit_rate': 0, 'h_rate': 0, 't_rate': 0, 'o_rate': 0,
                'all_hits': 0, 'max_miss_streak': 0, 'recent30_all': 0,
                'live': {'verified': 0, 'all_hit_rate': 0, 'all_hits': 0},
                'backfill': {'verified': 0, 'all_hit_rate': 0, 'all_hits': 0}}
    all_hits = sum(1 for r in verified if r['all_hit'] == '1')
    h_hits = sum(1 for r in verified if r['h_hit'] == '1')
    t_hits = sum(1 for r in verified if r['t_hit'] == '1')
    o_hits = sum(1 for r in verified if r['o_hit'] == '1')
    # 最大连错（all_hit=0 连续期数）
    mx = cur = 0
    for r in sorted(verified, key=lambda x: int(x['issue'])):
        if r['all_hit'] == '1':
            cur = 0
        else:
            cur += 1
            mx = max(mx, cur)
    # 最近30期
    recent = sorted(verified, key=lambda x: int(x['issue']))[-30:]
    recent_all = sum(1 for r in recent if r['all_hit'] == '1')
    # 分来源统计
    live = [r for r in verified if r.get('source') == 'live']
    backfill = [r for r in verified if r.get('source') != 'live']
    def _seg(seg):
        if not seg:
            return {'verified': 0, 'all_hit_rate': 0, 'all_hits': 0}
        hits = sum(1 for r in seg if r['all_hit'] == '1')
        return {'verified': len(seg), 'all_hit_rate': round(hits / len(seg) * 100, 2), 'all_hits': hits}
    return {
        'total': len(rows), 'pending': len(pending), 'verified': n,
        'all_hit_rate': round(all_hits / n * 100, 2),
        'h_rate': round(h_hits / n * 100, 2),
        't_rate': round(t_hits / n * 100, 2),
        'o_rate': round(o_hits / n * 100, 2),
        'all_hits': all_hits, 'max_miss_streak': mx,
        'recent30_all': round(recent_all / len(recent) * 100, 2) if recent else 0,
        'recent30_n': len(recent),
        'live': _seg(live),
        'backfill': _seg(backfill),
    }


def main(combo_path='best_formula.json', log_path=LOG_PATH, label=''):
    """对指定窗口跑完整跟踪：回填初始化→验证pending→追加今日→汇总。
    combo_path: 该窗口的公式 json；log_path: 该窗口跟踪日志。
    返回 track_changed:bool。"""
    import sys, io
    # 若 stdout 已被外层包装(如 auto_update.py)，则不再重复包装
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    with open(combo_path, 'r', encoding='utf-8') as f:
        combo = json.load(f)['combo']
    tag = f'[{label}] ' if label else ''
    print("=" * 50)
    print(f"{tag}每日预测跟踪 · 更新 ({combo_path})")
    print("=" * 50)

    track_changed = False

    # 1. 首次启用时回填历史基准（500期，含拟合窗内外，诚实呈现真实水平）
    #    之后不再回填，只做「验证 pending + 追加新预测」的真实每日跟踪
    if not os.path.exists(log_path):
        backfilled = backfill_history(combo, n=500, path=log_path)
        print(f"{tag}[初始化] 首次启用，回填 {backfilled} 条历史预测作为基准（最近500期）")
        if backfilled:
            track_changed = True
    else:
        print(f"{tag}[初始化] 日志已存在，跳过历史回填（只做真实每日跟踪）")

    # 2. 验证 pending
    verified, hit, miss = verify_pending(combo, path=log_path)
    if verified:
        print(f"{tag}[验证] 验证 {verified} 条预测: 全中 {hit} | 失误 {miss}")
        track_changed = True
    else:
        print(f"{tag}[验证] 无待验证预测")

    # 3. 追加今日新预测
    added = add_prediction(combo, path=log_path)
    if added:
        print(f"{tag}[新增] 已记录今日新预测（开奖前落盘）")
        track_changed = True
    else:
        print(f"{tag}[新增] 今日预测已存在，跳过")

    # 4. 汇总
    s = summarize(combo, path=log_path)
    print("-" * 50)
    print(f"{tag}累计已验证: {s['verified']} 期 | 待开奖: {s['pending']} 期")
    print(f"{tag}3杀全中率: {s['all_hit_rate']}% ({s['all_hits']}/{s['verified']})")
    print(f"{tag}百位 {s['h_rate']}% | 十位 {s['t_rate']}% | 个位 {s['o_rate']}%")
    print(f"{tag}最大连错: {s['max_miss_streak']} 期 | 近30期3杀全中 {s['recent30_all']}%")
    lv, bk = s['live'], s['backfill']
    print(f"{tag}[真实跟踪] {lv['verified']}期 3杀全中 {lv['all_hit_rate']}% | [历史回填] {bk['verified']}期 3杀全中 {bk['all_hit_rate']}%")
    return track_changed


def run_both():
    """200期窗口每日预测跟踪（唯一窗口）。返回是否有变化。"""
    return main('best_formula.json', LOG_PATH, '200')


if __name__ == '__main__':
    run_both()

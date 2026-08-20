# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV（自动补新期） → 暴力穷举选3条最优公式
      → 200期回测 → 生成 static/index.html（部署到 GitHub Pages）
幂等设计：数据与公式均无变化时**不重写页面**（含时间戳），
         workflow 的 git diff 检测不到任何变化即跳过提交与部署，零无效更新。
"""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)  # 保证 data/ static/ 相对路径正确

OUT_HTML = 'static/index.html'
COMBO_JSON = 'best_formula.json'


def main():
    t0 = time.time()
    print("=" * 46)
    print("  福彩3D 百十个位各杀一码 · 云端全自动更新")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 46)

    print("\n[1/4] 多源降级抓取 + 追加CSV")
    added = 0
    try:
        import fetch
        _, added = fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/4] 暴力穷举（最新200期，三位置各选最优公式）")
    import bruteforce
    from engine import load_data
    issues, hh, tt, oo = load_data()
    best, pool_size = bruteforce.search_best(hh, tt, oo, bruteforce.WINDOW)
    new_combo = {pos: best[pos][0] for pos in ['h', 't', 'o']}

    # 判断公式是否变化（对比旧 best_formula.json）
    old_combo = None
    try:
        with open(COMBO_JSON, 'r', encoding='utf-8') as f:
            old_combo = json.load(f).get('combo')
    except Exception:
        pass
    formula_changed = (old_combo != new_combo)

    if added == 0 and not formula_changed:
        print("\n[3/4] 数据与公式均无变化，跳过页面生成（零无效更新）")
    else:
        print("\n[3/4] 200期回测 + 生成网页")
        result = {
            'window': bruteforce.WINDOW,
            'data_info': {'n_issues': len(issues), 'first': issues[0], 'last': issues[-1]},
            'pool_size': pool_size,
            'combo': new_combo,
            'rates': {pos: round(best[pos][1] * 100, 2) for pos in ['h', 't', 'o']},
        }
        with open(COMBO_JSON, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  已写入 {COMBO_JSON}（公式变化: {formula_changed}, 新增数据: {added}期）")
        os.makedirs('static', exist_ok=True)
        import gen_site
        gen_site.main(out_path=OUT_HTML)

    print("\n[4/4] 完成")
    print(f"  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()

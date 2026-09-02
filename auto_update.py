# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV（自动补新期） → 双窗口(200/300期)暴力穷举
      → 生成 static/index.html（部署到 GitHub Pages，页面按钮切换两窗口）→ 每日预测跟踪
幂等设计：数据与公式均无变化时**不重写页面**（含时间戳），
         workflow 的 git diff 检测不到任何变化即跳过提交与部署，零无效更新。
注意：预测跟踪必须放在 best_formula.json 写入之后执行，否则会用旧公式记录预测，
      导致跟踪日志与页面显示不一致（2026-09-02 修复）。
"""
import sys, io, os, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)  # 保证 data/ static/ 相对路径正确

OUT_HTML = 'static/index.html'
COMBO_JSON = 'best_formula.json'
COMBO_300_JSON = 'best_formula_300.json'


def main():
    t0 = time.time()
    print("=" * 46)
    print("  福彩3D 百十个位各杀一码 · 云端全自动更新")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 46)

    print("\n[1/6] 多源降级抓取 + 追加CSV")
    added = 0
    try:
        import fetch
        _, added = fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/6] 双窗口暴力穷举（200期主 + 300期副）")
    import bruteforce
    from engine import load_data
    issues, hh, tt, oo = load_data()
    r200, r300 = bruteforce.run_multi(verbose=True)
    new_combo = r200['combo'] if r200 else None
    new_combo_300 = r300['combo'] if r300 else None

    # 判断公式是否变化（对比旧两份 json）
    def _old_combo(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f).get('combo')
        except Exception:
            return None
    formula_changed = (new_combo is not None and _old_combo(COMBO_JSON) != new_combo) or \
                      (new_combo_300 is not None and _old_combo(COMBO_300_JSON) != new_combo_300)

    if added == 0 and not formula_changed:
        print("\n[3/6] 数据与公式均无变化，跳过页面生成（零无效更新）")
        gen_site_run = False
    else:
        print("\n[3/6] 生成网页（含200/300双窗口）")
        os.makedirs('static', exist_ok=True)
        import gen_site
        gen_site.main(out_path=OUT_HTML)
        gen_site_run = True

    # 每日预测跟踪：必须在 best_formula*.json 更新后执行！
    # （否则跟踪会用旧公式记录预测，与页面显示的新公式预测不一致）
    # 200期与300期各自独立跟踪（独立日志文件，页面切换展示各自真实命中）
    print("\n[4/6] 双窗口每日预测跟踪（200 + 300 各自验证昨日 + 记录今日）")
    track_changed = False
    try:
        import track_predictions
        track_changed = track_predictions.run_both()
    except Exception as e:
        print(f"  ⚠ 预测跟踪异常（不影响主流程）: {str(e)[:80]}")

    # 跟踪有变化但页面已生成过则无需重建；若页面没生成（数据/公式未变）但跟踪有变化 → 补生成页面
    if track_changed and not gen_site_run:
        print("[5/6] 跟踪有新记录，补生成页面（含最新跟踪看板）")
        import gen_site
        gen_site.main(out_path=OUT_HTML)

    print("\n[6/6] 完成")
    print(f"  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()

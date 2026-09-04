# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV（自动补新期） → 200期窗口暴力穷举
      → 生成 static/index.html（部署到 GitHub Pages）→ 每日预测跟踪
幂等设计：数据与公式均无变化时**不重写页面**（含时间戳），
         workflow 的 git diff 检测不到任何变化即跳过提交与部署，零无效更新。
注意：预测跟踪必须放在 best_formula.json 写入之后执行，否则会用旧公式记录预测，
      导致跟踪日志与页面显示不一致（2026-09-02 修复）。
【2026-09-04】已移除 300 期副窗口，只保留 200 期单窗口。
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

    print("\n[1/6] 多源降级抓取 + 追加CSV")
    added = 0
    try:
        import fetch
        _, added = fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/6] 200期窗口暴力穷举")
    import bruteforce
    r200, _ = bruteforce.run_multi(verbose=True)
    new_combo = r200['combo'] if r200 else None

    # 判断公式是否变化（对比旧 json）
    def _old_combo(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f).get('combo')
        except Exception:
            return None
    formula_changed = new_combo is not None and _old_combo(COMBO_JSON) != new_combo

    if added == 0 and not formula_changed:
        print("\n[3/6] 数据与公式均无变化，跳过页面生成（零无效更新）")
        gen_site_run = False
    else:
        print("\n[3/6] 生成网页（200期窗口）")
        os.makedirs('static', exist_ok=True)
        import gen_site
        gen_site.main(out_path=OUT_HTML)
        gen_site_run = True

    # 每日预测跟踪：必须在 best_formula.json 更新后执行！
    # （否则跟踪会用旧公式记录预测，与页面显示的新公式预测不一致）
    print("\n[4/6] 每日预测跟踪（验证昨日 + 记录今日）")
    track_changed = False
    try:
        import track_predictions
        track_changed = track_predictions.run_both()
    except Exception as e:
        print(f"  ⚠ 预测跟踪异常（不影响主流程）: {str(e)[:80]}")

    # 跟踪有变化 → 无论页面是否已生成都要重建！
    # 原因：第[3/6]步生成页面时跟踪日志尚未验证（上期还是pending），
    # 第[4/6]步才验证上期=hit并落盘新预测；若不重建页面，线上会一直显示
    # 验证前的旧预测而非最新的预测（2026-09-03修复）。
    if track_changed:
        print("[5/6] 跟踪有更新，重建页面（含最新验证结果+新预测）")
        import gen_site
        gen_site.main(out_path=OUT_HTML)

    print("\n[6/6] 完成")
    print(f"  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()

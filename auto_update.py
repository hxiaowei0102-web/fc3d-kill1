# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 云端全自动更新入口（GitHub Actions 定时运行）
=============================================
流程：多源降级抓取最新开奖 → 追加到CSV（自动补新期） → 暴力穷举选3条最优公式
      → 200期回测 → 生成 static/index.html（部署到 GitHub Pages）
幂等设计：无新数据时 CSV 与页面不变，Actions 检测到无 diff 即跳过提交。
"""
import sys, io, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)  # 保证 data/ static/ 相对路径正确

OUT_HTML = 'static/index.html'


def main():
    t0 = time.time()
    print("=" * 46)
    print("  福彩3D 百十个位各杀一码 · 云端全自动更新")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 46)

    print("\n[1/4] 多源降级抓取 + 追加CSV")
    try:
        import fetch
        fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/4] 暴力穷举（最新200期，三位置各选最优公式）")
    import bruteforce
    bruteforce.main()

    print("\n[3/4] 200期回测 + 生成网页")
    os.makedirs('static', exist_ok=True)
    import gen_site
    gen_site.main(out_path=OUT_HTML)

    print("\n[4/4] 完成")
    print(f"  总耗时 {time.time()-t0:.1f} 秒")


if __name__ == '__main__':
    main()

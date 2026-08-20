# -*- coding: utf-8 -*-
"""
福彩3D 百十个杀一码 — 一键更新
=============================================
流程：联网补抓最新开奖(多源降级+CSV兜底) → 暴力穷举选3条最优公式 → 200期回测 → 生成网页
"""
import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))

if __name__ == '__main__':
    t0 = time.time()
    print("=" * 46)
    print("  福彩3D 百十个位各杀一码 · 一键更新")
    print(f"  时间(北京): {datetime.now(BJT).strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 46)

    print("\n[1/3] 同步最新数据（联网补抓 + CSV兜底）")
    try:
        import fetch
        fetch.sync_data()
    except Exception as e:
        print(f"  ⚠ 数据同步异常，沿用现有CSV: {str(e)[:80]}")

    print("\n[2/3] 暴力穷举（最新200期，三位置各选最优公式）")
    import bruteforce
    bruteforce.main()

    print("\n[3/3] 生成网页（200期回测）")
    import os, gen_site
    os.makedirs('static', exist_ok=True)
    gen_site.main(out_path='static/index.html')  # 与云端auto_update.py输出路径统一

    print(f"\n完成 ✓  总耗时 {time.time()-t0:.1f} 秒")
    print(f"本地预览: http://127.0.0.1:8899/static/index.html")

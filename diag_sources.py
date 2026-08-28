# -*- coding: utf-8 -*-
"""云端数据源连通性诊断（临时脚本，跑完删除）
在 GitHub Actions 真实环境测试 6 个数据源，输出每个源的连通性与解析结果。
"""
import sys, json
sys.stdout.reconfigure(encoding='utf-8')

import fetch

print("=" * 60)
print("云端数据源连通性诊断")
print("=" * 60)

ok = 0
for src in fetch.DATA_SOURCES:
    name = src['name']
    try:
        raw = fetch._http_get(src['url'], referer=src.get('referer'))
        if src['kind'] == 'json':
            draws = src['parser'](json.loads(raw))
        elif src['kind'] == 'txt17500':
            draws = fetch._parse_17500(raw)
        elif src['kind'] == 'html':
            draws = fetch._parse_html_3d(raw)
        else:
            draws = []
        latest = max((int(d[0]) for d in draws), default=None)
        if draws:
            ok += 1
            print(f"  [{name}] ✓ 解析{len(draws)}条, 最新{latest}")
            for d in draws[-2:]:
                print(f"       {d[0]} = {d[1]}{d[2]}{d[3]}")
        else:
            print(f"  [{name}] ⚠ 有响应但无有效数据 (len={len(raw)})")
    except Exception as e:
        print(f"  [{name}] ✗ {str(e)[:80]}")

print(f"\n可用源: {ok}/{len(fetch.DATA_SOURCES)}")

# 福彩3D 百十个位各杀一码 — 项目全貌（AI 可读技术文档）

> 生成时间：2026-09-04（北京时间，删除300期副窗口后修订）
> 本文件面向「任何 AI / 新接手开发者」：读完即可理解项目做什么、代码怎么组织、数据怎么流动、每天云端自动发生什么。
> 所有描述与仓库当前代码一致（commit ffd0e60，仅保留 200 期单窗口）。

---

## 0. 一句话总结

本项目是一个**福彩3D 每位置各杀 1 个号码**的纯云端全自动预测器：
每晚定时抓最新开奖 → 用**最近 200 期（唯一窗口）**暴力穷举约 **905 万条线性公式** → 给「百位 / 十位 / 个位」各挑 1 条最优杀码公式 → 固定公式做逐期回测 → 生成手机端网页 → 部署到 GitHub Pages，并对每天的预测做**真实留痕 + 次日自动验证**。

- 网页地址：https://hxiaowei0102-web.github.io/fc3d-kill1/
- 项目根目录：`D:\百十个杀一码\`
- 数据量：8745 期（2002001 ~ 2026237，CSV 无日期列）
- 当前最优公式（近 200 期各自命中率 99.0%，即 198/200）：
  - 百位 `2*s2+3*d2+1*sg+0`
  - 十位 `2*S+3*so+3*bsg2+6`
  - 个位 `1*bsg2+1*SL+2*db+2`
- **历史**：2026-09-04 前曾并行 200/300 双窗口（各独立公式、独立跟踪日志、页面按钮切换）；
  老板决定**只保留 200 期单窗口**，已彻底移除 300 期副窗口全部功能与产物。

---

## 1. 玩法定义与核心概念（必须先懂）

| 概念 | 定义 |
|---|---|
| **开奖号** | 福彩3D 每期开出 3 个数字：百位 / 十位 / 个位，各 0-9 |
| **杀一码** | 预测"某位置**不会出**哪个数字"。如预测某期百位杀 `0` = 断言百位开奖 ≠ 0 |
| **命中** | 预测杀码 ≠ 实际开奖号 即杀对。单位置随机基线 = **90%**（10 个数字杀 1 个） |
| **3杀全中** | 百/十/个三位置同时杀对。随机基线 = 0.9³ = **72.9%** |
| **公式** | 形如 `2*s2+3*d2+1*sg+0` 的线性表达式，输入上期（及前2期）开奖，输出 0-9 一个"杀码" |
| **窗口** | 只取**最近 N 期**历史来挑选公式。N=200（经 analyze_window 样本外验证定为 200，唯一窗口） |
| **不偷看未来** | 第 i 期的预测只允许使用第 i-1 期（上期）、第 i-2 期（前2期）数据，代码层面强制保证 |

**注意**：命中率 99% 只代表"这 200 期里该公式最准"（历史拟合 / 幸存者偏差）。
样本外（未参与选公式的期数）真实水平见第 7 节跟踪数据——诚实口径接近随机基线。

---

## 2. 公式数学定义

### 2.1 一条公式长什么样

```
结果 = ( c1 × 特征F1 + c2 × 特征F2 + c3 × 特征F3 + const ) mod 10
```

- `c` 为系数 ∈ {1,2,3,5}（三特征公式限定 {1,2,3} 控规模）
- `const` 为常数 0-9
- 特征取"个位"（mod 10），结果 0-9 即杀码

### 2.2 公式名 ↔ 结构互转

- 编码：`2*s2+3*d2+1*sg+0`（系数*特征名，`+` 连接，常数放末尾）
- 解析：`parse_linear(name)` → `[(系数, 特征下标), ...], 常数`，见 `formulas.py`

### 2.3 公式池规模（≈905万 条 / 1001万 规格）

| 组合 | 数量估算 | 系数集 |
|---|---|---|
| 单特征 | 59 × 4 × 10 = 2,360 | (1,2,3,5) |
| 双特征 | C(59,2) × 4×4 × 10 = 273,760 | (1,2,3,5) |
| 三特征 | C(59,3) × 3×3×3 × 10 ≈ 877.7万 | (1,2,3) |
| **合计** | **≈ 905.4万 条**（线上 pool_size=9053550） | |

> 规格总数约 1001 万（含未去重重复项）；去重后写入 `pool_size`。

### 2.4 59 个特征全表（输入：b,s,g = 上期三码；bL,sL,gL = 前2期三码）

**A 组 · 上期单期基础（34 个，v1）**

| 名称 | 含义 | 名称 | 含义 |
|---|---|---|---|
| b / s / g | 上期百/十/个位 | b2 / s2 / g2 | 各位²尾 |
| b3 / s3 / g3 | 各位³尾 | S | 和值 |
| S10 | 和尾 | P | 跨度(max-min) |
| mx / mn / md | 最大/最小/中间码 | d1 / d2 / d3 | \|b-s\| / \|b-g\| / \|s-g\| |
| bs / bg / sg | 两两乘积尾 | bsg | 三码积尾 |
| S2 / P2 | 和值²尾 / 跨度²尾 | sum2 / sum3 / sum4 | (百+十)/(十+个)/(百+个)尾 |
| bp / gp / sp | b^g / g^b / s^g 尾(底为0时=1) | bo / so / go / So | 百/十/个/和 奇偶(0/1) |

**B 组 · 上期单期派生（9 个，v2）**

| 名称 | 含义 | 名称 | 含义 |
|---|---|---|---|
| d12 / d13 / d23 | 跨度两两乘积尾 | mxmn | 大×小尾 |
| mxmd / mnmd | 大+中 / 小+中 | S3 | 和值³尾 |
| dsum | 三差值和 | bsg2 | 两两积之和尾 (b·s+s·g+g·b)%10 |

**C 组 · 跨期特征（16 个，v2，需前2期数据）**

| 名称 | 含义 | 名称 | 含义 |
|---|---|---|---|
| bL / sL / gL | 前2期三码 | SL / S10L / PL | 前2期和值/和尾/跨度 |
| db / ds / dg | 各位较前2期差分 | dS | 和值较前2期差分 |
| bh / sh / gh | 近2期各位之和尾 | bpr / spr / gpr | 近2期各位之积尾 |

> 全量中文说明 + 计算式详表见 `docs/杀一码公式体系_AI版.md`（export_formulas.py 自动导出）。
> 跨期特征缺前2期数据时安全退化填 0。

---

## 3. 代码文件职责一览（本地与云端同源）

| 文件 | 职责 | 运行环境 |
|---|---|---|
| `auto_update.py` | **云端全自动入口**（6 步流程，见第 5 节） | GitHub Actions |
| `update.py` | 本地一键更新（3 步，不含跟踪；额外把页面复制到根目录 `index.html` 供本地预览） | 本地 |
| `engine.py` | 数据引擎：`load_data()` 读 CSV → (期号,百,十,个)；`get_next_issue()` 期号+1（>359 跨年） | 共用 |
| `formulas.py` | 特征引擎+公式库：59 特征定义、`iter_specs()` 流式生成全部规格、`make_predictor()` 把公式名编译为函数 | 共用 |
| `bruteforce.py` | 暴力穷举：numpy 向量化扫 905 万公式（单窗口 200 期）、流式维护三位置最优；`run_multi()` 写 `best_formula.json` | 共用 |
| `backtest.py` | 回测引擎：固定公式逐期回看 200 期（近期→远期），`predict_next()` 预测下期 | 共用 |
| `fetch.py` | 多源降级抓取 + 校验 + 追加 CSV（防倒灌、保序） | 共用 |
| `gen_site.py` | 生成手机端静态网页 `static/index.html`：内嵌 200 期窗口数据（杀码、回测表、公式、跟踪看板） | 共用 |
| `track_predictions.py` | **每日预测跟踪**：验证 pending + 追加今日预测 + 累计统计。`run_both()` 兼容旧名，实际只跑 200 期日志 `predictions_log.csv` | 共用 |
| `export_formulas.py` | 一次性导出公式体系 AI 文档（`docs/` 下 md + json） | 本地工具 |
| `analyze_window.py` + `sum_window_results.py` | 一次性研究：样本外 walk-forward 测算最优窗口 N（结论=200） | 本地工具 |
| `.github/workflows/update.yml` | GitHub Actions 定时任务定义 | GitHub |

### 关键数据文件

| 文件 | 内容 |
|---|---|
| `data/fc3d-history.csv` | 全部开奖历史，列：`issue,hundreds,tens,ones`（**无日期列**），云端每晚自动追加新期 |
| `best_formula.json` | **200期窗口** 最优公式 + 命中率 + 数据范围 + 公式池大小（下游模块都读它） |
| `predictions_log.csv` | **200期窗口** 预测跟踪日志（508 已验证 = 500 回填 + 8 真实 live，1 pending） |
| `static/index.html` | 最终交付网页（唯一部署到 Pages 的文件） |

---

## 4. 核心模块接口速查（AI 接手必读）

### engine.py
```python
load_data(csv_path='data/fc3d-history.csv') -> (issues, hundreds, tens, ones)
    # 读 CSV→4 个列表，校验/修复严格升序，坏行跳过，空文件抛 ValueError
get_next_issue(latest_issue) -> str
    # '2026237' → '2026238'；序列 >359 则年+1、seq 归 1
```

### formulas.py
```python
FEAT_NAMES          # 59 个特征名（顺序=下标）
COEFFS=(1,2,3,5)    # 单/双特征系数集；TRIPLE_COEFFS=(1,2,3)
feat_list(b,s,g,prev=None) -> [59个特征值]   # prev=(上上期百,十,个)
eval_linear(feats, terms, const) -> v%10
parse_linear('2*S+3*so+6') -> ([(2,idx_S),(3,idx_so)], 6)
formula_name(terms, const) -> str
iter_specs() -> 生成器，yield (terms, const)，流式约 1001 万条不占内存
make_predictor('2*S+3*so+6') -> fn(b,s,g,prev)->int   # 编译复用
```

### bruteforce.py（性能关键，numpy 向量化）
```python
WINDOW = 200
search_best(hh, tt, oo, window) -> (best, pool_size)
    # best = {'h':(公式名,命中率,命中数), 't':..., 'o':...}
    # 原理：最近window期 → 特征矩阵 F(window×59) → 逐条规格算 out=(F·系数+const)%10
    #      → out != 实际开奖 计数 = 命中数
    # 并列裁决：命中率 → 公式名更短 → 字典序
    # 数据 < window+1 期时抛 ValueError
run_multi(verbose) -> (r200, None)   # 单窗口200跑一遍，第二元恒为 None（保留旧签名）
    # r200 = {'combo': {'h','t','o'}, 'rates': ..., 'window': ..., 'pool_size': ...}
main()  # 计算并写 best_formula.json
```
> 905 万条 × 3 位置 向量化约 **6 秒/窗口**（numpy bincount 直方图法，v3.1 提速 ~26 倍）。

### backtest.py
```python
run_backtest(csv_path, combo, n=200) -> {'results': [...], 'summary': {...}}
    # results 已 reverse：近期→远期；第 i 期只用 i-1/i-2 期数据
    # summary: hundreds/tens/ones/all_hit_rate、max_streak、window
predict_next(csv_path, combo) -> {'next_issue','last_issue','last_draw',
                                  'kh','kt','ko'}  # 下期预测杀码
```

### fetch.py（数据源降级链）
```python
sync_data() -> (next_code, added)
DATA_SOURCES = [huiniao(主力 json) → 17500(备用 txt) → apihz(兜底 json)]
    # 每个源：带重试 HTTP(默认3次×2秒) → 解析 → 期号必须 > 本地最新才采纳
    # append_to_csv：只追加严格更新的期号，防伪造旧期倒灌；期号冲突且号码不同则保留原值并告警
```
> 2026-08 实测移除失效源：cwl(403)/55128(拒连)/8200(DNS挂)。全失败沿用现有 CSV 不中断。

### track_predictions.py（真实预测留痕，单日志）
```python
LOG_PATH = 'predictions_log.csv'           # 200期窗口 跟踪日志（唯一）

backfill_history(combo, n=500, path=LOG_PATH)  # 首次启用：固定公式回填最近500期(源=backfill)
verify_pending(combo, path=LOG_PATH)           # pending 预测对应期已开奖 → 回填判定 hit/miss/partial
add_prediction(combo, issue=None, path=LOG_PATH)  # 追加今日新预测(源=live)，按 issue 幂等 upsert
summarize(combo=None, path=LOG_PATH) -> dict   # 累计统计：all_hit_rate/h_rate/t_rate/o_rate/
                                #   max_miss_streak/recent30_all/live/backfill 分源统计
main(combo_path, log_path, label) -> track_changed:bool  # 三步：回填→验证pending→追加今日
run_both() -> bool   # 兼容旧名：只跑 200 期一套 main()
```
CSV 列：`issue,kh,kt,ko,prev_issue,prev_draw,formula_h,formula_t,formula_o,draw,h_hit,t_hit,o_hit,all_hit,status,source,predicted_at,verified_at`
- `source`: `live`=开奖前真实落盘 / `backfill`=历史回填基准
- `status`: `pending` → 开奖后自动变 `hit`(全中) / `partial`(部分) / `miss`(失误)

### gen_site.py
```python
main(out_path='static/index.html')
WINDOW_CONFIG = [  # 唯一窗口：自己的公式json + 跟踪日志
  {'file':'best_formula.json', 'win':200, 'label':'200期', 'log':'predictions_log.csv'},
]
build_data() -> {'200': {...}}
    # 每窗口独立内嵌：数据范围/下期期号/上期开奖/公式+白话解释/
    #   近N回测(百/十/个/全中/连错)/该窗口自己的跟踪看板(summary+近30行)/预测杀码
```
> 页面核心数据逻辑：预测杀码**优先取跟踪日志最新 pending**（开奖前真实落盘值），
> 无 pending 才用公式重算 —— 保证页面与跟踪日志永远一致（2026-09-02 修复 041/061 不一致）。
> 网页纯静态自包含，无外部依赖；浅色主题、480px 移动端适配。

### auto_update.py（云端编排，6 步）
见第 5 节。注意执行顺序的坑：**预测跟踪必须放在 best_formula.json 写入之后**，
否则会用旧公式记录预测，造成日志与页面不一致（已修复并加注释）。

---

## 5. 云端全自动部署机制（每天自动发生什么）

### 5.1 触发：三重备份 cron（GitHub Actions）
```yaml
schedule:          # 北京时间 = UTC+8
  - cron: '0 14 * * *'    # 北京 22:00（21:30 开奖后）
  - cron: '30 15 * * *'   # 北京 23:30（备份1）
  - cron: '0 17 * * *'    # 北京 01:00（备份2）
workflow_dispatch:        # 手动触发，可传 force_deploy=true 强制重新部署
concurrency:              # 三 cron 若撞车 → 取消旧运行只留最新
```

### 5.2 运行步骤（auto_update.py）
```
[1/6] fetch.sync_data() 多源降级抓最新开奖 → 有新品则追加 data/fc3d-history.csv
[2/6] bruteforce.run_multi() 200期穷举905万：
      200期→best_formula.json（唯一窗口）
      对比旧 json：added==0 且公式未变 → 跳过页面生成(零无效更新)
[3/6] 有变化：gen_site.main() 生成 static/index.html（含200期数据+跟踪看板）
[4/6] track_predictions.run_both() 每日预测跟踪（200期）
      ★必须于[3]后执行(依赖新公式)：先验证昨日 pending → 再追加今日新预测
      200期→predictions_log.csv
[5/6] 若[3]未生成页面但[4]有跟踪变化 → 补生成页面(含最新跟踪看板)
      ★2026-09-03 修复：跟踪验证后无条件重建页面，否则线上会停在上期pending(时序bug)
[6/6] 完成
```

### 5.3 workflow 提交与部署判断
- git diff 检查 4 个核心产物：`data/fc3d-history.csv` / `best_formula.json` / `static/index.html` / `predictions_log.csv`
- 全无变化 → **跳过提交与部署**（零无效更新，时间戳不会误判因为无变化时不重写页面）
- `force_deploy=true` → 跳过判断直接走部署链路
- 部署：复制 `static/index.html` → `_site/` → configure-pages → upload-pages-artifact → deploy-pages
- 依赖：`pip install "numpy>=1.26,<3"`（锁 <3 防破坏性升级改变穷举结果）

---

## 6. 本地运行方式

```bash
cd D:\百十个杀一码
# 依赖：Python 3.11+，numpy>=1.26,<3

python update.py          # 一键：抓数据→穷举→回测→生成 static/index.html + 根目录 index.html
python auto_update.py     # 云端完整流程（穷举+跟踪），本地可跑通全链路
python bruteforce.py      # 只重算 best_formula.json（约6秒/次）
python gen_site.py        # 只用现有 json 重新生成页面（200期）
python track_predictions.py  # 只看预测跟踪（验证+追加+统计）
python fetch.py           # 只测数据源抓取
```

本地预览：`http://127.0.0.1:8899/index.html`（或 `/static/index.html`）

---

## 7. 预测跟踪与真实水平（诚实口径）

### 7.1 设计哲学
- **回测 99% ≠ 真实水平**：那是"在窗口里挑最准公式"的历史拟合，样本外必然回落。
- 为了不被拟合数字欺骗，系统启动**真实留痕**：每天开奖前把当天预测落盘（live），次日开奖后自动验证。
- 首次启用时用固定公式**回填最近 500 期**（backfill）作为基准，让看板第一天就有样本。
- 页面明确区分「真实跟踪 / 历史回填」两种来源，回填数字偏乐观。

### 7.2 当前累计（2026-09-04 实测读取）
**200期窗口**（predictions_log.csv）
| 指标 | 数值 |
|---|---|
| 已验证总期数 | 508 |
| 3杀全中率(全部) | **80.91%**（411/508） |
| 百位 / 十位 / 个位 | 94.69% / 92.91% / 92.32% |
| 最大连错 | 4 期 |
| 近 30 期 3杀全中 | 96.67% |
| 真实跟踪(live) | 8 期 3杀全中 87.5%（7/8） |
| 历史回填(backfill) | 500 期 3杀全中 80.8%（404/500） |
| 待开奖(pending) | 1 期（2026238，杀 2/9/1） |

### 7.3 关键诚实结论
- 随机基线：单码 90%，3杀全中 **72.9%**。
- 200期 3杀全中 80.91% 只比基线高约 8pp —— 其中相当部分来自 500 期回填（含公式拟合窗口内）。
- 200期真实 live 8 期 87.5%。**样本太小不足以下结论**；项目的价值在于每天积累真实样本外数据。
- 若想区分真实水平：只看 `source=live` 且期数足够多之后的 `all_hit_rate`（页面看板已单列此项）。
- 福彩3D 属随机独立事件，本工具仅供研究参考，不构成投注建议。

---

## 8. 已知限制与设计取舍（AI 接手须知）

1. **命中率天花板**：单位置随机杀中 90%，公式穷举的 99% 是 200 期窗口内过拟合极值；
   窗口外推无统计优势，不能把 99% 当长期预期。
2. **窗口 200 的由来**：200 期经样本外 walk-forward 验证为最优（analyze_window.py：N ∈ {100..350} 对比，
   grid_scan_window.py：N=320 合并略优但仅 +2.2pp、N=200 拟合-样本外差最小）。
   固定窗口会随数据滚动换公式——**公式会每天/隔天变化是正常现象**，不是 bug。
3. **幂等/防重复**：页面无变化不重写（时间戳不变）→ git diff 判无更新→跳过部署；跟踪按 issue upsert。
4. **无日期列**：CSV 只存期号与三码，跨年由期号序列逻辑处理（>359 进位），时间仅用于展示。
5. **行尾差异坑**：Windows 本地 CRLF vs 云端克隆 LF，对比文件内容须先归一化行尾。
6. **时区**：所有"北京时间"由 `timezone(timedelta(hours=8))` 显式构造，不依赖服务器时区。
7. **依赖锁版**：numpy 锁 `<3`，防止版本升级改变 `%` 运算路径或性能特征导致线上结果漂移。
8. **数据源易失效**：外部免费源随时可能 403/拒连/DNS 挂（历史上已移除 3 个），靠降级链+重试+CSV 兜底保命。
9. **公式名规范**：`c*FEAT[+c*FEAT][+const]`，特征名唯一映射下标（`_IDX`），改特征必须同步 `FEAT_NAMES`/`feat_list`/`FEAT_ZH`(gen_site)/`FEAT_EXPR`(export) 四处。
10. **本地 git 链分叉**：gh api 通道重建 commit 导致本地提交链与云端分叉（内容一致 tree=d0882796），
    本地 push 会因非 fast-forward 失败——同步须走 gh api git data 通道或 force push。

---

## 9. 常见任务速查（怎么改、怎么验）

| 想做什么 | 改哪里 | 验证 |
|---|---|---|
| 调整公式池（特征/系数/是否含三特征） | `formulas.py` 的 `FEAT_NAMES`/`COEFFS`/`iter_specs` | 跑 `bruteforce.py` 看 pool_size 与命中率 |
| 改窗口（如改回双窗口/加 400 期） | `bruteforce.py` 加窗口常量 + json 文件，`gen_site.py` 的 `WINDOW_CONFIG` 加条目（自动出按钮） | 先跑 `analyze_window.py N` 做样本外对比再定 |
| 改网页样式/文案 | `gen_site.py` 的 `HTML_TEMPLATE` / `FEAT_ZH` | 跑 `gen_site.py` 后刷新页面 |
| 调整跟踪回填期数 | `track_predictions.py` 里 main() 的 n=500 | 删 `predictions_log.csv` 重跑 `run_both()`（会自动重建日志） |
| 增加数据源 | `fetch.py` `DATA_SOURCES` + parser | 跑 `python fetch.py` 看日志 |
| 手动触发云端更新 | `gh workflow run update.yml`；强制部署加 `-f force_deploy=true` | Actions 页看 run 状态 |

---

## 10. 部署链路速览（架构图 · 文字版）

```
21:30 开奖
   │
   ▼
GitHub Actions cron(22:00/23:30/01:00 三重兜底)  ── 或手动 workflow_dispatch
   │
   ▼
auto_update.py
   ├─[1] fetch:  huiniao→17500→apihz 降级抓取 → 追加 fc3d-history.csv（防倒灌校验）
   ├─[2] bruteforce.run_multi: 200期×905万 numpy 穷举
   │        → best_formula.json（百/十/个各1条最优）
   ├─[3] 写 json → gen_site → static/index.html（含200期数据+跟踪，无变化则跳过）
   ├─[4] track: run_both() 验证昨日 pending + 落盘今日预测
   │        → predictions_log.csv
   ├─[5] 跟踪有变而页面没生成 → 补生成（无条件重建）
   └─[6] 结束
   │
   ▼
workflow: git diff 四产物 → 有变化才 commit+push → deploy-pages
   │
   ▼
GitHub Pages → https://hxiaowei0102-web.github.io/fc3d-kill1/
   │
   ▼
手机浏览器查看：杀码卡片 / 回测表 / 公式 / 跟踪看板（真实样本外）
```

---

*本文档由 AI 依据仓库代码（commit ffd0e60）与实时数据自动整理，供研究与二次开发参考。*
*仅供研究参考，不构成投注建议。*

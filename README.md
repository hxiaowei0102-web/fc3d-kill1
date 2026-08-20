# 福彩3D 百十个位各杀一码（纯云端全自动）

暴力穷举 · 只参考最新200期 · 每位置各杀1码 · GitHub Pages 云端全自动更新

## 访问地址
手机浏览器直接访问：https://hxiaowei0102-web.github.io/fc3d-kill1/

## 自动更新机制
- GitHub Actions 定时任务，**三重备份 cron**（北京时间 22:00 / 23:30 / 01:00），3 次机会兜底，21:30 开奖后执行
- 多个备用数据源降级抓取（huiniao / 17500 / apihz / cwl官方 / 55128 / 8200），全失败则沿用现有CSV不中断
- 抓到新期号自动**追加**到 `data/fc3d-history.csv`（不覆盖历史），随后自动重算公式并更新网页
- 无新数据时自动跳过提交，不产生无效更新

## 工作原理
1. 多源抓取最新开奖 → 追加CSV（云端自动补期）
2. 最新200期暴力穷举（59特征 × 单/双/三特征线性组合 ≈ **905万条公式**，numpy向量化约2分钟）→ 百/十/个各选1条最优杀码公式
3. 固定公式回看200期 → 生成逐期真实预测回测表 → 部署到 GitHub Pages

## 本地文件
| 文件 | 职责 |
|---|---|
| auto_update.py | 云端全自动更新入口 |
| fetch.py | 多源降级抓取 |
| engine.py / formulas.py | 数据引擎 / 公式库（59特征） |
| bruteforce.py / backtest.py | 暴力穷举(numpy) / 200期回测 |
| gen_site.py | 生成网页 |
| .github/workflows/update.yml | Actions 三重cron定时任务（含numpy依赖） |
| data/fc3d-history.csv | 历史数据（云端自动追加） |

## 手动触发
GitHub Actions 页面 → 选中 workflow → Run workflow，或命令行 `gh workflow run update.yml`

仅供研究参考，不构成投注建议。

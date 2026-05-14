# 手术显微镜招投标信息爬虫

自动爬取招投标网站，生成每日手术显微镜相关招投标信息汇总报告。

## 数据源

| 优先级 | 网站 | 说明 |
|--------|------|------|
| 第一信源 | 必联网/采招网 (bidcenter.com.cn) | 综合招标平台，需登录 |
| 第二信源 | 中国国际招标网 (chinabidding.com) | 机电产品招标，需登录 |
| 补充信源 | 中国政府采购网 (ccgp.gov.cn) | 官方政府采购平台 |
| 医院信源 | 中国医院招标网 (e120.org.cn) | 医疗行业专业平台 |

## 报告格式

Markdown 格式，按信息类型分类：
- **招标信息**（详细表格）：项目名称、招标单位、发布时间、截止时间、预算金额、地区、来源
- **预采购信息**（简略通知）
- **调研信息**（简略通知）
- **中标信息**（简略通知）
- **变更信息**（简略通知）

## 本地运行

```bash
pip install playwright
python -m playwright install chromium

# 设置环境变量
export BIDCENTER_USERNAME="your_username"
export BIDCENTER_PASSWORD="your_password"
export CHINABIDDING_USERNAME="your_username"
export CHINABIDDING_PASSWORD="your_password"

python bidding_scraper.py
```

## GitHub Actions

- **执行时间**: 每天早上9点（北京时间）
- **触发方式**: 定时调度 + 手动触发
- **报告存储**: 自动提交到仓库 `bidding_reports/` 目录

## 医院网站说明

医院招标信息主要通过以下渠道发布：
1. **中国政府采购网** - 已包含在爬虫中，覆盖政府采购类医院招标
2. **中国医院招标网** - 专业医疗招标平台，已添加
3. **医院官网** - 各医院自主招标信息，目前通过上述聚合平台覆盖

如需针对特定重点医院官网定制爬取，可单独配置。

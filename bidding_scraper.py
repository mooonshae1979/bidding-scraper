# -*- coding: utf-8 -*-
"""
手术显微镜招投标信息爬虫 (Playwright版 v3)
数据源：
  1. 必联网/采招网 (bidcenter.com.cn) - 第一信源，需登录
  2. 中国国际招标网 (chinabidding.com) - 第二信源，需登录
  3. 中国政府采购网 (ccgp.gov.cn) - 补充信源，无需登录
  4. 中国医院招标网 (e120.org.cn) - 医院专业信源，无需登录

输出：Markdown 格式的每日汇总报告
"""

import os
import sys
import re
import time
import logging
from datetime import datetime, timedelta
from urllib.parse import quote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ========== 配置 ==========
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bidding_reports'))
KEYWORD = os.environ.get('KEYWORD', '手术显微镜')
RELATED_KEYWORDS = ["手术显微"]

# 必联网账号（从环境变量读取）
BIDCENTER_USERNAME = os.environ.get('BIDCENTER_USERNAME', '')
BIDCENTER_PASSWORD = os.environ.get('BIDCENTER_PASSWORD', '')

# 中国国际招标网账号（从环境变量读取）
CHINABIDDING_USERNAME = os.environ.get('CHINABIDDING_USERNAME', '')
CHINABIDDING_PASSWORD = os.environ.get('CHINABIDDING_PASSWORD', '')

# 企业微信机器人Webhook地址（从环境变量读取）
WECOM_WEBHOOK_URL = os.environ.get('WECOM_WEBHOOK_URL', '')


# ========== 数据结构 ==========
class BiddingItem:
    def __init__(self):
        self.title = ""
        self.source = ""
        self.category = ""
        self.buyer = ""
        self.publish_date = ""
        self.deadline = ""
        self.budget = ""
        self.url = ""
        self.region = ""
        self.detail = ""

    def __repr__(self):
        return f"[{self.category}] {self.title} ({self.publish_date})"


# ========== 必联网爬虫 ==========
def scrape_bidcenter(page, keyword, target_date):
    """爬取必联网/采招网 - 第一信源"""
    items = []
    logger.info(f"[必联网] 搜索关键词: '{keyword}'")

    try:
        # 登录
        logger.info("[必联网] 正在登录...")
        page.goto("https://sso.bidcenter.com.cn/login", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.fill('input[placeholder="手机号/用户名"]', BIDCENTER_USERNAME)
        time.sleep(0.5)
        page.fill('input[placeholder="密码"]', BIDCENTER_PASSWORD)
        time.sleep(0.5)
        page.click('a:has-text("快速登录")')
        time.sleep(3)
        logger.info("[必联网] ✅ 登录成功！")

        # 搜索
        search_url = f"https://search.bidcenter.com.cn/search?keywords={quote(keyword)}&mod=0"
        page.goto(search_url, wait_until="networkidle", timeout=30000)

        # 等待搜索结果加载（AJAX渲染）
        try:
            page.wait_for_selector('.ssjg-list_cell', timeout=15000)
        except PlaywrightTimeout:
            logger.warning("[必联网] 搜索结果加载超时")
            return items

        time.sleep(2)

        # 解析渲染后的搜索结果
        cells = page.query_selector_all('.ssjg-list_cell')
        logger.info(f"[必联网] 找到 {len(cells)} 条结果")

        for cell in cells:
            try:
                item = BiddingItem()
                item.source = "必联网/采招网"

                # 标题
                title_el = cell.query_selector('.ssjg-title')
                if title_el:
                    item.title = title_el.inner_text().strip()
                    href = title_el.get_attribute('href') or ""
                    if href and not href.startswith('http'):
                        item.url = "https://www.bidcenter.com.cn" + href
                    else:
                        item.url = href

                if not item.title or len(item.title) < 5:
                    continue

                # 信息类型
                type_el = cell.query_selector('.ssjg-leixing')
                if type_el:
                    news_type = type_el.inner_text().strip()
                    if '中标' in news_type:
                        item.category = "中标信息"
                    elif '预告' in news_type or '预采购' in news_type or '采购意向' in news_type:
                        item.category = "预采购信息"
                    elif '变更' in news_type or '更正' in news_type:
                        item.category = "变更信息"
                    elif '调研' in news_type:
                        item.category = "调研信息"
                    else:
                        item.category = "招标信息"
                else:
                    item.category = "招标信息"

                # 获取整个cell的文本用于提取更多信息
                cell_text = cell.inner_text()

                # 日期 - 从cell文本中提取
                date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', cell_text)
                if date_match:
                    item.publish_date = date_match.group(1).replace('/', '-')

                # 截止时间
                deadline_match = re.search(r'截止时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})', cell_text)
                if deadline_match:
                    item.deadline = deadline_match.group(1).replace('/', '-')

                # 地区
                region_match = re.search(
                    r'(北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|'
                    r'江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|'
                    r'广东|海南|四川|贵州|云南|陕西|甘肃|青海|'
                    r'内蒙古|广西|西藏|宁夏|新疆)',
                    cell_text
                )
                if region_match:
                    item.region = region_match.group(1)

                # 预算金额
                budget_el = cell.query_selector('.yusuan')
                if budget_el:
                    item.budget = budget_el.inner_text().strip()
                else:
                    budget_match = re.search(r'(?:采购预算|预算)[：:]\s*([^\s]+)', cell_text)
                    if budget_match:
                        item.budget = budget_match.group(1)

                # 日期过滤
                if item.publish_date and target_date:
                    if target_date not in item.publish_date:
                        continue

                items.append(item)

            except Exception as e:
                logger.debug(f"[必联网] 解析单条结果异常: {e}")
                continue

    except PlaywrightTimeout:
        logger.error("[必联网] ❌ 页面加载超时")
    except Exception as e:
        logger.error(f"[必联网] ❌ 爬取异常: {e}")

    return items


# ========== 中国国际招标网爬虫 ==========
def scrape_chinabidding(page, keyword, target_date):
    """爬取中国国际招标网 - 第二信源"""
    items = []
    logger.info(f"[中国国际招标网] 搜索关键词: '{keyword}'")

    try:
        # 登录
        logger.info("[中国国际招标网] 正在登录...")
        page.goto("https://www.chinabidding.com/bid/index/loginIndex.htm",
                   wait_until="networkidle", timeout=30000)
        time.sleep(2)
        page.fill('input[placeholder="用户名/手机/邮箱"]', CHINABIDDING_USERNAME)
        time.sleep(0.5)
        page.fill('input[placeholder="密码"]', CHINABIDDING_PASSWORD)
        time.sleep(0.5)
        page.click('button:has-text("登录")')
        time.sleep(3)
        logger.info("[中国国际招标网] ✅ 登录成功！")

        # 搜索不同类型的公告
        search_types = [
            ('BidNotice', '招标公告', '招标信息'),
            ('BidResult', '评标结果', '中标信息'),
            ('BidChange', '招标变更', '变更信息'),
        ]

        for po_class, type_label, category in search_types:
            try:
                search_url = f"https://www.chinabidding.com/search/proj.htm?key={quote(keyword)}&poClass={po_class}&page=1"
                page.goto(search_url, wait_until="networkidle", timeout=30000)
                time.sleep(3)

                # 解析结果 - chinabidding的搜索结果在渲染后的DOM中
                # 使用多种选择器尝试
                type_items = []

                # 方法1: h5 > a
                h5_links = page.query_selector_all('h5 a')
                for link in h5_links:
                    try:
                        item = BiddingItem()
                        item.source = "中国国际招标网"
                        item.category = category

                        text = link.inner_text().strip()
                        text = re.sub(r'^\[(.+?)\]\s*', '', text).strip()
                        if not text or len(text) < 5:
                            continue

                        item.title = text
                        href = link.get_attribute('href') or ""
                        if href.startswith('/'):
                            item.url = "https://www.chinabidding.com" + href
                        else:
                            item.url = href

                        # 从父元素提取日期和地区
                        parent_text = link.evaluate_handle("el => { let p = el.closest('div'); return p ? p.innerText : ''; }")
                        parent_text = parent_text.inner_text() if parent_text else ""

                        date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', parent_text)
                        if date_match:
                            item.publish_date = date_match.group(1).replace('/', '-')

                        region_match = re.search(r'所属地区[：:]\s*(.+?)(?:\s*所属|\s*$)', parent_text)
                        if region_match:
                            item.region = region_match.group(1).strip()

                        if item.publish_date and target_date:
                            if target_date not in item.publish_date:
                                continue

                        type_items.append(item)
                    except Exception:
                        continue

                # 方法2: 如果h5没找到，尝试其他选择器
                if not type_items:
                    # 尝试 .search-list 或其他容器
                    all_links = page.query_selector_all('.search-list a, .list-content a, .bid-list a')
                    for link in all_links:
                        try:
                            text = link.inner_text().strip()
                            if keyword in text or '显微镜' in text:
                                item = BiddingItem()
                                item.source = "中国国际招标网"
                                item.category = category
                                item.title = text
                                href = link.get_attribute('href') or ""
                                if href.startswith('/'):
                                    item.url = "https://www.chinabidding.com" + href
                                else:
                                    item.url = href
                                type_items.append(item)
                        except Exception:
                            continue

                items.extend(type_items)
                logger.info(f"  {type_label}: {len(type_items)} 条")
                time.sleep(2)

            except Exception as e:
                logger.error(f"  搜索{type_label}异常: {e}")

        logger.info(f"[中国国际招标网] 共找到 {len(items)} 条结果")

    except PlaywrightTimeout:
        logger.error("[中国国际招标网] ❌ 页面加载超时")
    except Exception as e:
        logger.error(f"[中国国际招标网] ❌ 爬取异常: {e}")

    return items


# ========== 中国政府采购网爬虫 ==========
def scrape_ccgp(page, keyword, target_date):
    """爬取中国政府采购网 - 补充信源（无需登录）"""
    items = []
    logger.info(f"[政府采购网] 搜索关键词: '{keyword}'")

    bid_types = [
        ('1', '招标公告', '招标信息'),
        ('2', '邀请招标', '招标信息'),
        ('3', '竞争性谈判', '招标信息'),
        ('4', '询价公告', '招标信息'),
        ('5', '单一来源', '招标信息'),
        ('6', '竞争性磋商', '招标信息'),
    ]

    date_formatted = target_date.replace('-', ':')

    for bid_type, type_name, category in bid_types:
        try:
            params = (
                f"?searchtype=1&page_index=1&bidSort=0&buyerName=&projectId="
                f"&pinMu=2&bidType={bid_type}&dbselect=bidx&kw={quote(keyword)}"
                f"&start_time={date_formatted}&end_time={date_formatted}"
                f"&timeType=6&displayZone=&zoneId=&pppStatus=&agentName="
            )
            url = f"http://search.ccgp.gov.cn/bxsearch{params}"
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            list_items = page.query_selector_all('.vT-srch-result-list-bid li')
            for li in list_items:
                try:
                    link = li.query_selector('a')
                    if not link:
                        continue
                    item = BiddingItem()
                    item.source = "中国政府采购网"
                    item.category = category
                    item.title = link.inner_text().strip()
                    href = link.get_attribute('href') or ""
                    if href.startswith('/'):
                        item.url = "http://www.ccgp.gov.cn" + href
                    else:
                        item.url = href
                    li_text = li.inner_text()
                    date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', li_text)
                    if date_match:
                        item.publish_date = date_match.group(1).replace('/', '-')
                    items.append(item)
                except Exception:
                    continue

            logger.info(f"  {type_name}: {len([i for i in items if i.source == '中国政府采购网'])} 条")
            time.sleep(3)

        except Exception as e:
            logger.error(f"  搜索{type_name}异常: {e}")

    logger.info(f"[政府采购网] 共找到 {len(items)} 条结果")
    return items


# ========== 中国医院招标网爬虫 ==========
def scrape_e120(page, keyword, target_date):
    """爬取中国医院招标网 (e120.org.cn) - 医院专业信源"""
    items = []
    logger.info(f"[医院招标网] 搜索关键词: '{keyword}'")

    try:
        # 中国医院招标网列表页
        # URL格式: http://www.e120.org.cn/l_hospital-zhaobiao_{page}.html
        base_url = "http://www.e120.org.cn"
        list_url = f"{base_url}/l_hospital-zhaobiao_1.html"

        page.goto(list_url, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # 解析列表页
        # 页面结构：表格形式，每行包含省份、标题、日期
        rows = page.query_selector_all('table tr, .list-item, .news-item')

        if not rows:
            # 尝试其他选择器
            rows = page.query_selector_all('div[class*="list"] > div, div[class*="item"]')

        logger.info(f"[医院招标网] 找到 {len(rows)} 行数据")

        for row in rows:
            try:
                row_text = row.inner_text()

                # 过滤关键词
                if keyword not in row_text and '显微' not in row_text:
                    continue

                item = BiddingItem()
                item.source = "中国医院招标网"

                # 提取标题和链接
                link = row.query_selector('a')
                if link:
                    item.title = link.inner_text().strip()
                    href = link.get_attribute('href') or ""
                    if href.startswith('/'):
                        item.url = base_url + href
                    elif href.startswith('http'):
                        item.url = href
                    else:
                        item.url = base_url + '/' + href
                else:
                    # 从文本中提取标题
                    title_match = re.search(r'([^\s]{10,100})', row_text)
                    if title_match:
                        item.title = title_match.group(1)

                if not item.title or len(item.title) < 5:
                    continue

                # 提取日期
                date_match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', row_text)
                if date_match:
                    item.publish_date = date_match.group(1).replace('/', '-')
                else:
                    # 尝试匹配 MM-DD 格式
                    date_match = re.search(r'(\d{2}-\d{2})', row_text)
                    if date_match:
                        mm_dd = date_match.group(1)
                        year = datetime.now().year
                        item.publish_date = f"{year}-{mm_dd}"

                # 提取地区（省份）
                region_match = re.search(
                    r'(北京|上海|天津|重庆|河北|山西|辽宁|吉林|黑龙江|'
                    r'江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|'
                    r'广东|海南|四川|贵州|云南|陕西|甘肃|青海|'
                    r'内蒙古|广西|西藏|宁夏|新疆)',
                    row_text
                )
                if region_match:
                    item.region = region_match.group(1)

                # 判断信息类型
                if '中标' in item.title or '成交' in item.title:
                    item.category = "中标信息"
                elif '变更' in item.title or '更正' in item.title:
                    item.category = "变更信息"
                else:
                    item.category = "招标信息"

                # 日期过滤
                if item.publish_date and target_date:
                    if target_date not in item.publish_date:
                        continue

                items.append(item)

            except Exception as e:
                logger.debug(f"[医院招标网] 解析行异常: {e}")
                continue

        logger.info(f"[医院招标网] 共找到 {len(items)} 条结果")

    except PlaywrightTimeout:
        logger.error("[医院招标网] ❌ 页面加载超时")
    except Exception as e:
        logger.error(f"[医院招标网] ❌ 爬取异常: {e}")

    return items


# ========== 报告生成器 ==========
def generate_report(items, date_str):
    """生成Markdown格式的每日汇总报告"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 按信息类型分类
    categories = {
        '招标信息': [],
        '预采购信息': [],
        '调研信息': [],
        '中标信息': [],
        '变更信息': [],
    }

    for item in items:
        cat = item.category if item.category in categories else '招标信息'
        categories[cat].append(item)

    # 去重
    for cat in categories:
        seen = set()
        unique = []
        for item in categories[cat]:
            key = item.title[:50]
            if key not in seen:
                seen.add(key)
                unique.append(item)
        categories[cat] = unique

    # 构建报告
    lines = []
    lines.append("# 手术显微镜招投标信息日报")
    lines.append("")
    lines.append(f"**日期**: {date_str}")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**关键词**: {KEYWORD}")
    lines.append("")

    # 统计摘要
    total = sum(len(v) for v in categories.values())
    lines.append("## 今日摘要")
    lines.append("")
    lines.append("| 信息类型 | 数量 |")
    lines.append("|:--------|:----:|")
    for cat, cat_items in categories.items():
        lines.append(f"| {cat} | {len(cat_items)} |")
    lines.append(f"| **合计** | **{total}** |")
    lines.append("")

    # 详细招标信息
    if categories['招标信息']:
        lines.append("---")
        lines.append("")
        lines.append("## 招标信息（详细）")
        lines.append("")
        lines.append("| 序号 | 项目名称 | 招标单位 | 发布时间 | 截止时间 | 预算金额 | 地区 | 来源 |")
        lines.append("|:----:|:---------|:---------|:--------:|:--------:|:--------:|:----:|:----:|")
        for i, item in enumerate(categories['招标信息'], 1):
            title_md = f"[{item.title}]({item.url})" if item.url else item.title
            lines.append(
                f"| {i} | {title_md} | {item.buyer or '-'} | "
                f"{item.publish_date or '-'} | {item.deadline or '-'} | "
                f"{item.budget or '-'} | {item.region or '-'} | {item.source} |"
            )
        lines.append("")

    # 简略通知类信息
    for cat in ['预采购信息', '调研信息', '中标信息', '变更信息']:
        if categories[cat]:
            lines.append("---")
            lines.append("")
            lines.append(f"## {cat}（简略通知）")
            lines.append("")
            for item in categories[cat]:
                title_md = f"[{item.title}]({item.url})" if item.url else item.title
                info_parts = [title_md]
                if item.publish_date:
                    info_parts.append(f"发布: {item.publish_date}")
                if item.region:
                    info_parts.append(f"地区: {item.region}")
                if item.budget:
                    info_parts.append(f"金额: {item.budget}")
                info_parts.append(f"来源: {item.source}")
                lines.append(f"- {' | '.join(info_parts)}")
            lines.append("")

    # 页脚
    lines.append("---")
    lines.append("")
    lines.append("*本报告由自动化脚本生成，数据来源于公开招投标信息平台。*")
    lines.append("*数据源：必联网/采招网、中国国际招标网、中国政府采购网、中国医院招标网*")

    report = '\n'.join(lines)

    # 保存
    filename = f"手术显微镜招投标日报_{date_str}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    logger.info(f"报告已生成: {filepath}")
    return filepath


# ========== 主流程 ==========
def main():
    today = datetime.now().strftime('%Y-%m-%d')
    logger.info(f"========== 开始爬取手术显微镜招投标信息 ({today}) ==========")

    all_items = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
            ]
        )

        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            locale='zh-CN',
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        page = context.new_page()

        # === 1. 爬取必联网（第一信源）===
        try:
            items1 = scrape_bidcenter(page, KEYWORD, today)
            all_items.extend(items1)
            for kw in RELATED_KEYWORDS:
                time.sleep(3)
                ext_items = scrape_bidcenter(page, kw, today)
                all_items.extend(ext_items)
        except Exception as e:
            logger.error(f"必联网爬取失败: {e}")

        time.sleep(3)

        # === 2. 爬取中国国际招标网（第二信源）===
        try:
            items2 = scrape_chinabidding(page, KEYWORD, today)
            all_items.extend(items2)
        except Exception as e:
            logger.error(f"中国国际招标网爬取失败: {e}")

        time.sleep(3)

        # === 3. 爬取中国政府采购网（补充信源）===
        try:
            items3 = scrape_ccgp(page, KEYWORD, today)
            all_items.extend(items3)
        except Exception as e:
            logger.error(f"政府采购网爬取失败: {e}")

        time.sleep(3)

        # === 4. 爬取中国医院招标网（医院专业信源）===
        try:
            items4 = scrape_e120(page, KEYWORD, today)
            all_items.extend(items4)
        except Exception as e:
            logger.error(f"医院招标网爬取失败: {e}")

        browser.close()

    # === 4. 生成报告 ===
    logger.info(f"========== 共收集 {len(all_items)} 条信息 ==========")
    report_path = generate_report(all_items, today)
    logger.info(f"========== 任务完成！报告路径: {report_path} ==========")

    # === 5. 推送到企业微信 ===
    if WECOM_WEBHOOK_URL:
        try:
            push_to_wecom(all_items, today, report_path)
        except Exception as e:
            logger.error(f"企业微信推送失败: {e}")
    else:
        logger.info("未配置企业微信Webhook，跳过推送")

    return report_path


# ========== 企业微信推送 ==========
def push_to_wecom(items, date_str, report_path):
    """推送招投标日报到企业微信群"""
    import requests as req

    logger.info("正在推送日报到企业微信...")

    # 按类型分类统计
    cat_count = {}
    for item in items:
        cat = item.category if item.category else '招标信息'
        cat_count[cat] = cat_count.get(cat, 0) + 1

    total = len(items)

    # 构建Markdown消息（企业微信支持Markdown格式）
    lines = []
    lines.append(f"## 🔬 手术显微镜招投标日报")
    lines.append(f"> 日期：**{date_str}**")
    lines.append(f"")

    if total == 0:
        lines.append(f"> ⚠️ 今日暂无新的手术显微镜相关招投标信息")
    else:
        lines.append(f"**📊 今日共 {total} 条信息**")
        lines.append("")

        # 统计摘要
        for cat, count in sorted(cat_count.items(), key=lambda x: -x[1]):
            lines.append(f"- {cat}：{count} 条")
        lines.append("")

        # 招标信息（详细，最多显示10条）
        bidding_items = [i for i in items if i.category == '招标信息']
        if bidding_items:
            lines.append("### 🔔 招标信息")
            for item in bidding_items[:10]:
                title = item.title[:60] + ('...' if len(item.title) > 60 else '')
                info = f"- [{title}]({item.url})" if item.url else f"- {title}"
                if item.publish_date:
                    info += f"  ({item.publish_date})"
                if item.region:
                    info += f"  [{item.region}]"
                lines.append(info)
            if len(bidding_items) > 10:
                lines.append(f"- ... 共{len(bidding_items)}条，详见完整报告")
            lines.append("")

        # 其他类型（简略，各最多显示5条）
        for cat in ['中标信息', '预采购信息', '调研信息', '变更信息']:
            cat_items = [i for i in items if i.category == cat]
            if cat_items:
                lines.append(f"### 📋 {cat}")
                for item in cat_items[:5]:
                    title = item.title[:50] + ('...' if len(item.title) > 50 else '')
                    info = f"- {title}"
                    if item.publish_date:
                        info += f"  ({item.publish_date})"
                    lines.append(info)
                if len(cat_items) > 5:
                    lines.append(f"- ... 共{len(cat_items)}条")
                lines.append("")

    content = '\n'.join(lines)

    # 发送消息
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    resp = req.post(WECOM_WEBHOOK_URL, json=payload, timeout=15)
    result = resp.json()

    if result.get('errcode') == 0:
        logger.info("✅ 企业微信推送成功！")
    else:
        logger.error(f"❌ 企业微信推送失败: {result}")


if __name__ == '__main__':
    main()

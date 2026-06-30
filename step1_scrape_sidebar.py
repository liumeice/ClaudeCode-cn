#!/usr/bin/env python3
"""
Step 1: Scrape the Claude Code Docs sidebar structure.

The Claude Code docs site uses a custom Tailwind-based navigation with top-level
nav tabs. Each tab has its own sidebar. This script visits each nav tab, extracts
the sidebar groups and pages, and outputs a full tree structure.

Outputs:
  - sidebar.json: Full tree with {title, href, level, children}
  - sidebar.md:   Human-readable Markdown table of contents

Usage:
  source .venv/Scripts/activate
  python step1_scrape_sidebar.py
"""

import json
import sys
import io
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = 'https://code.claude.com/docs/zh-CN/'
ORIGIN = 'https://code.claude.com'

# Top-level nav tabs with their starting URLs
NAV_TABS = [
    ('快速开始', '/docs/zh-CN/overview'),
    ('使用 Claude Code 代理', '/docs/zh-CN/agents'),
    ('管理', '/docs/zh-CN/admin-setup'),
    ('设置', '/docs/zh-CN/settings'),
    ('参考', '/docs/zh-CN/cli-reference'),
    ('Agent SDK', '/docs/zh-CN/agent-sdk/overview'),
    ('新闻动态', '/docs/zh-CN/whats-new'),
    ('资源', '/docs/zh-CN/legal-and-compliance'),
]


def extract_sidebar_groups(page):
    """Extract sidebar groups and items from the current page."""
    # Scroll sidebar to bottom to trigger lazy-loading
    page.evaluate('''() => {
        const el = document.querySelector('#sidebar-content');
        if (el) el.scrollTop = el.scrollHeight;
    }''')
    page.wait_for_timeout(1000)

    groups = page.evaluate('''() => {
        const cls = (el) => {
            if (!el) return '';
            return typeof el.className === 'string' ? el.className : (el.getAttribute('class') || '');
        };

        const sidebar = document.querySelector('nav#sidebar');
        if (!sidebar) return [];

        const result = [];
        const sections = sidebar.querySelectorAll('#navigation-items > div');

        for (const section of sections) {
            const header = section.querySelector('.sidebar-group-header h3');
            const groupName = header ? header.querySelector('span')?.textContent?.trim() : 'Unknown';

            const items = [];
            const lis = section.querySelectorAll('ul.sidebar-group > li');
            for (const li of lis) {
                const a = li.querySelector('a');
                if (!a) continue;
                const href = a.getAttribute('href');
                const span = a.querySelector('span');
                const title = span ? span.textContent.trim() : a.textContent.trim();
                const isExternal = a.hasAttribute('target') || (href && href.startsWith('http'));

                if (!isExternal && href && href.includes('/docs/zh-CN/')) {
                    items.push({ title, href });
                }
            }

            if (items.length > 0) {
                result.push({ group: groupName, items });
            }
        }
        return result;
    }''')

    return groups


def build_tree(nav_tabs_data):
    """Build a hierarchical tree from the nav tabs data.

    Structure: nav_tab -> group -> pages (flat within each group).
    """
    tree = []

    for section_name, groups in nav_tabs_data:
        section_node = {
            'title': section_name,
            'href': '',
            'level': 1,
            'children': [],
        }

        for group_info in groups:
            group_name = group_info['group']
            items = group_info['items']

            group_node = {
                'title': group_name,
                'href': items[0]['href'] if items else '',
                'level': 2,
                'children': [],
            }

            for item in items:
                group_node['children'].append({
                    'title': item['title'],
                    'href': item['href'],
                    'level': 3,
                })

            section_node['children'].append(group_node)

        tree.append(section_node)

    return tree


def count_leaves(tree):
    """Count leaf pages in the tree."""
    count = 0
    for node in tree:
        if not node.get('children'):
            count += 1
        else:
            count += count_leaves(node['children'])
    return count


def clean_tree(nodes):
    """Remove empty hrefs from tree."""
    result = []
    for n in nodes:
        cleaned = {
            'title': n['title'],
            'href': n['href'],
            'level': n['level'],
        }
        if n.get('children'):
            cleaned['children'] = clean_tree(n['children'])
        result.append(cleaned)
    return result


def tree_to_markdown(tree, indent=0):
    """Convert the tree to a Markdown table of contents."""
    lines = []
    for node in tree:
        prefix = '  ' * indent
        children = node.get('children', [])
        if children:
            lines.append(f'{prefix}- **{node["title"]}**')
            lines.extend(tree_to_markdown(children, indent + 1))
        else:
            lines.append(f'{prefix}- [{node["title"]}](https://code.claude.com{node["href"]})')
    return lines


def main():
    print('Step 1: Scraping sidebar structure from', BASE_URL)
    print()

    nav_tabs_data = []
    seen_hrefs = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1600, 'height': 900},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        )
        page = context.new_page()

        for section_name, start_url in NAV_TABS:
            full_url = f'{ORIGIN}{start_url}'
            print(f'  [{section_name}] {start_url}')

            try:
                page.goto(full_url, wait_until='networkidle', timeout=60000)
            except Exception as e:
                print(f'    Navigation timeout: {e}')

            page.wait_for_timeout(2000)
            groups = extract_sidebar_groups(page)

            # Count unique pages in this section
            section_count = 0
            for g in groups:
                for item in g['items']:
                    if item['href'] not in seen_hrefs:
                        seen_hrefs.add(item['href'])
                        section_count += 1

            nav_tabs_data.append((section_name, groups))
            print(f'    {len(groups)} groups, {section_count} new pages')

        browser.close()

    # Build tree
    tree = build_tree(nav_tabs_data)
    total = count_leaves(tree)
    print(f'\n  Total unique pages: {len(seen_hrefs)}')
    print(f'  Total leaf nodes: {total}')
    print(f'  Top-level sections: {len(tree)}')

    # Show structure
    for node in tree:
        leaf_count = count_leaves(node['children']) if node.get('children') else 1
        print(f'    [{node["level"]}] + {node["title"]} ({leaf_count} pages)')
        for child in node.get('children', []):
            sub_count = count_leaves(child['children']) if child.get('children') else 1
            print(f'        [{child["level"]}] + {child["title"]} ({sub_count} pages)')

    clean_sidebar = clean_tree(tree)

    # Output sidebar.json
    output_json = {
        'source': BASE_URL,
        'root': 'Claude Code Documentation (zh-CN)',
        'total_pages': len(seen_hrefs),
        'children': clean_sidebar,
    }

    with open('sidebar.json', 'w', encoding='utf-8') as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)
    print('  Written: sidebar.json')

    # Output sidebar.md
    md_lines = [
        '# Claude Code Documentation - Table of Contents (zh-CN)',
        '',
        f'Source: {BASE_URL}',
        f'Total pages: {len(seen_hrefs)}',
        '',
    ]
    md_lines.extend(tree_to_markdown(tree))

    with open('sidebar.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines) + '\n')
    print('  Written: sidebar.md')

    print()
    print('Done!')


if __name__ == '__main__':
    main()

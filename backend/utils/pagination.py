# -*- coding: utf-8 -*-
"""
共享分页工具
V3.9.0
"""


def paginate_query(query, page: int = 1, page_size: int = 20):
    """统一分页查询

    Returns:
        (items, total, total_pages)
    """
    if page < 1:
        page = 1
    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total, total_pages


def build_pagination_html(page: int, total: int, total_pages: int, max_visible: int = 9) -> str:
    """生成分页栏 HTML（与原有 _build_pagination 输出一致）"""
    if total_pages <= 1:
        return ""

    parts = []
    # 上一页
    disabled_prev = ' opacity-50 pointer-events-none' if page <= 1 else ''
    parts.append(
        f'<button class="px-3 py-1 rounded text-sm border hover:bg-gray-50{disabled_prev}" '
        f'onclick="goPage({page - 1})" {"disabled" if page <= 1 else ""}>上一页</button>'
    )

    # 页码
    if total_pages <= max_visible:
        pages = list(range(1, total_pages + 1))
    else:
        pages = []
        pages.append(1)
        half = max_visible // 2
        start = max(2, page - half)
        end = min(total_pages - 1, page + half)
        if start > 2:
            pages.append('...')
        for i in range(start, end + 1):
            pages.append(i)
        if end < total_pages - 1:
            pages.append('...')
        pages.append(total_pages)

    for p in pages:
        if p == '...':
            parts.append('<span class="px-2 py-1 text-gray-400 text-sm">...</span>')
        elif p == page:
            parts.append(
                f'<span class="px-3 py-1 rounded text-sm bg-blue-600 text-white font-medium">{p}</span>'
            )
        else:
            parts.append(
                f'<button class="px-3 py-1 rounded text-sm border hover:bg-gray-50" '
                f'onclick="goPage({p})">{p}</button>'
            )

    # 下一页
    disabled_next = ' opacity-50 pointer-events-none' if page >= total_pages else ''
    parts.append(
        f'<button class="px-3 py-1 rounded text-sm border hover:bg-gray-50{disabled_next}" '
        f'onclick="goPage({page + 1})" {"disabled" if page >= total_pages else ""}>下一页</button>'
    )

    return f'''<div class="flex items-center justify-between mt-4">
        <span class="text-sm text-gray-500">共 {total} 条，第 {page}/{total_pages} 页</span>
        <div class="flex gap-1">{" ".join(parts)}</div>
    </div>'''

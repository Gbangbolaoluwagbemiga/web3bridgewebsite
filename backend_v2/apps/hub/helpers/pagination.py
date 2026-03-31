"""
Shared pagination for hub list endpoints (page/limit, no full-table COUNT).
"""


def paginate_queryset(request, queryset, *, default_limit=100, max_limit=200):
    """
    Slice queryset with page/limit. Uses limit+1 rows to compute has_next without COUNT(*).

    Returns:
        tuple: (page_slice_queryset, pagination_meta_dict)
    """
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        limit = int(request.GET.get("limit", default_limit))
    except (TypeError, ValueError):
        limit = default_limit

    limit = min(max(1, limit), max_limit)
    offset = (page - 1) * limit

    window = list(queryset[offset : offset + limit + 1])
    has_next = len(window) > limit
    if has_next:
        window = window[:limit]

    has_previous = page > 1
    pagination = {
        "current_page": page,
        "limit": limit,
        "has_next": has_next,
        "has_previous": has_previous,
        "next_page": page + 1 if has_next else None,
        "previous_page": page - 1 if has_previous else None,
    }
    return window, pagination

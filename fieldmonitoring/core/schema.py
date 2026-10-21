def only_app_api(endpoints):
    """drf-spectacular hook: /api/docs/ documents the field app API (/api/v1/…) only.

    The MIS read-only API under /<lang>/api/v1/ keeps its own drf-yasg pages.
    """
    return [e for e in endpoints if e[0].startswith("/api/v1/")]

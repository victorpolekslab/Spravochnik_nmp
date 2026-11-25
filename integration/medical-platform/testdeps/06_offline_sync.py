"""Reference decision policy for a durable, partitioned Android/PWA queue."""


def next_action(status, error=None, *, matches_ack=False, retries=0):
    """None denotes a transport loss. The caller persists state and retry count."""
    if status == 200 and matches_ack:
        return "delete_confirmed"
    if status == 401:
        return "pause_for_auth"
    if status == 403:
        return "pause_for_permission"
    if status == 409:
        return "retake" if error == "TEST_VERSION_UNAVAILABLE" else "needs_review"
    if status is None or status in (200, 408, 429) or 500 <= status <= 599:
        return "retry_same_payload" if retries < 5 else "pause_retry_budget"
    return "needs_review"

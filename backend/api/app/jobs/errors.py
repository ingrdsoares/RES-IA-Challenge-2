class JobDeferred(Exception):
    """A dependency is still pending; do not consume a failure attempt."""

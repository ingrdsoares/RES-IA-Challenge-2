class DependencyUnavailable(Exception):
    """A required service cannot complete the operation."""


class DependencyTimeout(DependencyUnavailable):
    """A required service exceeded its time budget."""


class CollectionIncompatible(DependencyUnavailable):
    """Existing collection cannot be queried using this configuration."""

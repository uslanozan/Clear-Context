class ProviderError(Exception):
    """Expose only a fixed error code, never provider response bodies."""

    def __init__(self, code: str, usage=None):
        self.code = code
        self.usage = usage
        super().__init__(code)

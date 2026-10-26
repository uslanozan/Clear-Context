class ProviderError(Exception):
    """Expose only a fixed error code, never provider response bodies."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

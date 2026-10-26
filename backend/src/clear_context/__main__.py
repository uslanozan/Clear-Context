import uvicorn

from clear_context.core.settings import Settings
from clear_context.main import create_app


def main() -> None:
    settings = Settings()
    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level,
        workers=1,
    )


if __name__ == "__main__":
    main()

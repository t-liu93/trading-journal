from fastapi import FastAPI
import uvicorn

from app.api.router import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()

    application = FastAPI(title="Trading Journal Backend")
    application.state.settings = app_settings
    application.include_router(api_router, prefix=app_settings.api_base_path)

    return application

def run() -> None:
    settings = get_settings()
    application = create_app(settings)
    uvicorn.run(
        application,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()

import time
from ollama import AsyncClient, ProgressResponse
from app.logging import logger
from app.settings import settings


class OllamaClient:
    """
    Асинхронный клиент для работы с Ollama:
    - pull модели с прогрессом
    - generate
    """

    def __init__(self):
        self.client = AsyncClient(host=settings.OLLAMA_BASE_URL)

    async def pull_model(self):
        """
        Асинхронная загрузка модели с throttle логированием прогресса.
        """

        logger.info("ollama.pull_start", model=settings.OLLAMA_MODEL)

        last_log_time = 0
        last_percent = -1

        async for chunk in await self.client.pull(
            settings.OLLAMA_MODEL,
            stream=True
        ):
            if isinstance(chunk, ProgressResponse):
                if chunk.total and chunk.completed:
                    percent = int(chunk.completed / chunk.total * 100)
                else:
                    percent = 0

                now = time.time()

                # Логируем только если процент изменился и прошло 0.5s
                if percent != last_percent and (now - last_log_time) > 0.5:
                    logger.info(
                        "ollama.pull_progress",
                        model=settings.OLLAMA_MODEL,
                        status=chunk.status,
                        completed=chunk.completed,
                        percent=f"{percent}%"
                    )
                    last_percent = percent
                    last_log_time = now

        logger.info("ollama.pull_done", model=settings.OLLAMA_MODEL, total=chunk.total)

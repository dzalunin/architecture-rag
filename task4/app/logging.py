import logging
import structlog
from structlog.processors import JSONRenderer
from structlog.stdlib import add_log_level, filter_by_level
from structlog.contextvars import merge_contextvars
from app.settings import settings

async def logging_lifespan(app):
    configure_logging()
    yield


def configure_logging():
    """
    Глобальная настройка логирования.
    Вызывается один раз при старте приложения.
    """
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(message)s",
        handlers=[
            logging.StreamHandler()
        ],
    )

    structlog.configure(
        processors=[
            # Общие поля контекста
            merge_contextvars,

            # Фильтрация по уровню
            filter_by_level,

            # Добавляем level, timestamp
            add_log_level,
            structlog.processors.TimeStamper(
                fmt="%Y-%m-%dT%H:%M:%S.%fZ",  # Явный формат с миллисекундами и Zulu time
                utc=True,
                key="timestamp"  # Явно задаем ключ для timestamp
            ),

            structlog.processors.EventRenamer("message"),

            # Преобразуем исключения в структурированный вид
            structlog.processors.format_exc_info,

            # Преобразуем Unicode в строки (для избежания проблем с сериализацией)
            structlog.processors.UnicodeDecoder(),
            
            # Финальный рендер в JSON
            JSONRenderer(
                # ensure_ascii=False,  # Раскомментировать если нужны не-ASCII символы
                sort_keys=True  # Для предсказуемого порядка полей
            )
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


# Экспортируем глобальный логгер
logger = structlog.get_logger()

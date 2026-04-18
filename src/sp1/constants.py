import pathlib
import time

USER_AGENT: str = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)

##############################
# Logging
##############################

LOG_FILE_PATH: pathlib.Path = (pathlib.Path.cwd() / ".." / "logs" / "news_agg.log").resolve()
MAX_LOG_FILE_SIZE: int = 10 * (2**20)  # 10 MB
MAX_LOG_BACKUP_COUNT: int = 5

##############################
# Time
##############################
TIME_FORMAT = lambda time_: time.strftime("%Y-%m-%dT%H:%M:%SZ", time_)  # noqa: E731

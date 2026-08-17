from redis import Redis
from rq import Queue, Worker

from .config import get_settings


def main() -> None:
    connection = Redis.from_url(get_settings().redis_url)
    worker = Worker([Queue("email", connection=connection)], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()


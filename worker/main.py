import asyncio
import signal

from core.config import Settings
from core.logging import setup_logging
from services.worker import run_worker


async def main() -> None:
    setup_logging()
    settings = Settings.from_env()
    stop = asyncio.Event()

    def _handle_signal(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _handle_signal())

    await run_worker(stop, settings)


if __name__ == "__main__":
    print('0')
    asyncio.run(main())

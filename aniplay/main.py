import sys
import asyncio
from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop
import logging
from aniplay.ui.main_window import MainWindow
from aniplay.database.db import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AniPlay")

def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    db_manager = DatabaseManager()

    async def setup():
        await db_manager.initialize()
        window = MainWindow(db_manager)
        await window.load_initial_data()
        window.show()
        # Ensure window is kept alive
        app._window = window 

    # Schedule the initial setup
    asyncio.ensure_future(setup())

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

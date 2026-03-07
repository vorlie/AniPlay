# AniPlay - Personal media server and player for anime libraries.
# Copyright (C) 2026  Charlie
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
import asyncio
from PyQt6.QtWidgets import QApplication
import qdarktheme
from qasync import QEventLoop
import logging
from aniplay.utils.logger import setup_logging
from aniplay.ui.main_window import MainWindow
from aniplay.database.db import DatabaseManager

# Initialize logging
setup_logging(level=logging.DEBUG) # Using DEBUG for now to see more info
logger = logging.getLogger("AniPlay")

def main():
    app = QApplication(sys.argv)
    
    # Apply Dark Theme
    qdarktheme.setup_theme("dark", corner_shape="rounded")
    
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

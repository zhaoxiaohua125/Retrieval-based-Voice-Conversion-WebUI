"""Profile cold UI startup phases."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
t0 = time.perf_counter()


def mark(label):
    print('%s\t%.2fs' % (label, time.perf_counter() - t0))


from app.runtime_env import bootstrap_runtime

bootstrap_runtime(ROOT)
mark('bootstrap')
from PyQt6.QtWidgets import QApplication

mark('pyqt_import')
from app.integration import ClientController
from app.scheduler import AppScheduler
from app.ui import MainWindow, UiBridge

mark('app_imports')
app = QApplication([])
bridge = UiBridge()
sch = AppScheduler.instance().start()
c = ClientController(sch, project_root=ROOT)
c.start()
mark('controller_start')
from app.ui.pages import PlaybackPage, SongMakePage, AnnouncePage
mark('pages_import')
p1 = PlaybackPage(bridge)
mark('playback_page')
p2 = SongMakePage(bridge, project_root=ROOT)
mark('song_make_page')
w = MainWindow(bridge, project_root=ROOT, config_store=c.config_store)
mark('mainwindow')
w.show()
app.processEvents()
mark('show_total')

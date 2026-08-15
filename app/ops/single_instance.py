"""单实例：重复启动时唤醒已有窗口，不新开进程。"""
import hashlib

from PyQt6.QtCore import QSharedMemory
from PyQt6.QtNetwork import QLocalServer, QLocalSocket


def _instance_key(root: str) -> str:
    return 'rvc_client_%s' % hashlib.md5(root.encode('utf-8')).hexdigest()[:12]


def _send_raise(key: str):
    sock = QLocalSocket()
    sock.connectToServer(key)
    if sock.waitForConnected(1000):
        sock.write(b'raise')
        sock.waitForBytesWritten(1000)
        sock.disconnectFromServer()


def notify_existing_instance(root: str) -> bool:
    key = _instance_key(root)
    mem = QSharedMemory(key)
    if mem.attach():
        mem.detach()
        _send_raise(key)
        return True
    return False


class SingleInstanceGuard:
    def __init__(self, root: str, on_raise):
        self._key = _instance_key(root)
        self._mem = QSharedMemory(self._key)
        if not self._mem.create(1):
            if self._mem.error() == QSharedMemory.SharedMemoryError.AlreadyExists:
                _send_raise(self._key)
                raise RuntimeError('already_running')
            raise RuntimeError('single instance lock failed')
        QLocalServer.removeServer(self._key)
        self._server = QLocalServer()
        if not self._server.listen(self._key):
            QLocalServer.removeServer(self._key)
            if not self._server.listen(self._key):
                raise RuntimeError('single instance server listen failed')
        self._on_raise = on_raise
        self._server.newConnection.connect(self._on_connection)

    def _on_connection(self):
        conn = self._server.nextPendingConnection()
        if not conn:
            return
        if conn.waitForReadyRead(500) and conn.readAll() == b'raise':
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._on_raise)
        conn.disconnectFromServer()

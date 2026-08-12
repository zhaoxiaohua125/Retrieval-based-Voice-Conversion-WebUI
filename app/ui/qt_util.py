"""PyQt 信号槽小工具。"""


def clicked(fn):
    """绑定 QPushButton.clicked(bool)，忽略 Qt 传入的 checked 参数。"""
    return lambda *_: fn()

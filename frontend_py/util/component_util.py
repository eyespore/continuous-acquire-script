"""
控件工具类
"""


class ScaleProcessBar:
    """ 分度进度条装饰器 """
    step = 0  # 步长
    scale = 0  # 缩放
    cursor = 0  # 游标
    position = 0  # 位置

    def __init__(self, process_bar):
        self.process_bar = process_bar

    def setScale(self, scale: int):
        """ 重设缩放，同时清除进度条 """
        self.scale = scale
        self.step = 100 // scale
        self.cursor = 0
        self.position = 0
        self.process_bar.setValue(self.position)

    def increase(self):
        self.cursor += 1
        if self.cursor >= self.scale:
            self.cursor = self.scale
            return

        if self.cursor == self.scale:
            self.process_bar.setValue(100)
        else:
            self.position += self.step
            self.process_bar.setValue(self.position)

    def decrease(self):
        self.cursor -= 1
        if self.cursor <= 0:
            self.cursor = 0
            return

        if self.cursor == 0:
            self.process_bar.setValue(0)
        else:
            self.position -= self.step
            self.process_bar.setValue(self.position)

    def reset(self):
        """ 重置进度条 """
        self.cursor = 0
        self.position = 0
        self.process_bar.setValue(self.position)

    def fulfill(self):
        """ 填满进度条 """
        self.cursor = self.scale
        self.position = 100
        self.process_bar.setValue(self.position)

    def isFulfilled(self):
        """ 判断进度条是否加载完成 """
        return self.cursor == self.scale



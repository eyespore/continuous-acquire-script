"""
Created on 2024.4.9
@author: Pineclone
"""
import sys
import threading
from datetime import datetime
from enum import Enum
from typing import List

from PyQt5 import QtCore
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import *
from loguru import logger

from config_util import config
from pycomm.util.math_util import MathUtil
from pycomm.util.network import Message
from data_processor import MessageProcessor

logger.info(f'Launching frontend process by python')
QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)  # 修正窗口界面尺寸

MENU_UI_PATH = f'main_gui.ui'  # 菜单UI路径设定
DEF_FONT = QFont(config['font'], config['font_size'])  # 字体设定
DEF_WINDOW_TITLE = 'Continuous Acquire Scripts'  # 窗口标题设置
DEF_WIDTH_WITHOUT_LOG = 350  # 窗口大小设置
DEF_WIDTH_WITH_LOG = 520
DEF_HEIGHT = 230  # 窗口高度设置
DEF_MESSAGE_BOX_TEXT_LEN = 35  # 默认弹窗消息宽度，这在很大程度上影响了弹窗的大小


class Status(Enum):
    VANILLA = 'EXEC'
    UNAVAILABLE = 'N/A'
    TERMINABLE = "STOP"


class Gui(QWidget):
    # 基础常量
    CHECK_BOX_CHECKED = 2  # 单选框被选中后表现的value
    TAB_XY_CONTINUOUS_NUM = 0  # xy坐标横移连拍tab对应的下标
    TAB_SINGLE_POINT_NUM = 1  # 单点连拍tab对应的下标
    DEF_EXTENSION_UNIT_LIST = ['px', '%', ]  # 边缘拓展单位
    DEF_DURATION_UNIT_LIST = ['millis', 'seconds', 'minutes', 'hours']  # 可用时间单位列表

    progress_signal = pyqtSignal(int)  # 进度条信号，提供线程设置主线程进度条渲染的能力
    log_signal = pyqtSignal(str)  # 控制台信号，提供线程在控制台打印输出的能力
    status_signal = pyqtSignal(Status)  # 回复执行按钮信号，提供线程恢复主控按钮exec的能力

    # 渲染主界面
    def __init__(self):
        super().__init__()
        self.client = None  # 消息转发
        logger.debug('Launching Main Thread')
        uic.loadUi(MENU_UI_PATH, self)
        self.setWindowTitle(DEF_WINDOW_TITLE)
        self.components = self.__dict__  # 将组件作为对象属性
        self.log_cache: List[str] = []  # 程序输出窗口信息缓存
        self.client: MessageProcessor  # 网络连接

        self.done_task_num = 0  # 完成任务数
        self.task_num = 0  # 运行任务数
        self.lock = threading.Lock()  # 全局锁

        logger.debug('Initializing GUI')
        self.init_gui()  # 初始化GUI界面
        logger.debug('Initializing Task Threads')
        self.init_threads()  # 初始化子线程
        logger.debug('Initializing Signals and Slot')
        self.init_signals()  # 绑定信号和槽函数
        logger.debug('Initializing Network Connection')
        self.init_network()  # 初始化网络

        logger.info('Successfully launch Main UI')

    """
    =============================================================
    ----------------------- init --------------------------------
    =============================================================
    """
    def init_gui(self):
        """ GUI组件初始化，主要负责图形化界面的初始化工作 """
        self.init_font()  # 初始化字体
        self.init_enable_extension()  # 初始化是否允许边界拓展
        self.init_stick_on_top()  # 初始化是否保持在顶端
        self.init_splitting_format()  # 初始化切割规格
        self.init_program_output()  # 初始化控制台输出
        self.init_progress_bar()  # 初始化进度条
        self.init_exposure()  # 初始化曝光度
        self.init_binning()  # 初始化binning
        self.init_single_point_pos()  # 初始化单点连拍坐标参数
        self.init_enable_duration()  # 初始化是否启用持续时间
        self.init_duration_value()  # 初始化连拍持续时间
        self.init_framerate()  # 初始化每秒帧率
        self.init_camera_combo_box()  # 初始化相机下拉选单
        self.init_exec_btn()  # 初始化执行按钮

    def init_threads(self):
        """
        子线程初始化方法，使用容器存储所有需要管理的线程对象，由主线程提供接口，子线程通过实现某个对应接口来挂载
        主线程的生命周期，或者事件发送事件
        """

    def init_signals(self):
        # 组件信号
        self.components['enable_extension'].stateChanged.connect(self.check_enable_extension_slot)  # 拓展命令行窗口
        self.components['stick_on_top'].stateChanged.connect(self.check_stick_on_top_slot)  # 将窗口置于最前端
        self.components['program_output'].stateChanged.connect(self.check_program_output_slot)  # 通过菜单日志栏打印日志信息
        self.components['program_output_clean'].clicked.connect(self.click_output_clean_slot)  # 执行日志栏清空
        self.components['exec_btn'].clicked.connect(self.click_exec_btn_slot)  # 执行程序按钮
        self.components['load_cameras'].clicked.connect(self.load_cameras_slot)  # 刷新可用相机下拉选单
        self.components['enable_duration'].stateChanged.connect(self.check_enable_duration_slot)  # 是否启用单区域连拍持续时间

        # 日志信号，控制日志输出
        self.log_signal.connect(self.print_log)
        # 渲染进度条
        self.progress_signal.connect(self.set_progress)

    def init_network(self):
        # 网络初始化
        self.client = MessageProcessor(config['server_host'], config['server_port'], config['server_timeout'])
        self.client.start()

    def init_font(self):
        # 初始化字体
        self.setFont(DEF_FONT)

    def init_exec_btn(self):
        # 初始化执行按钮
        self.status = Status.VANILLA
        self.set_status(self.status)

    def init_single_point_pos(self):
        # 初始化单点连拍坐标参数
        self.components['single_pos_top'].setValidator(QIntValidator())
        self.components['single_pos_left'].setValidator(QIntValidator())
        self.components['single_pos_bottom'].setValidator(QIntValidator())
        self.components['single_pos_right'].setValidator(QIntValidator())

        self.components['single_pos_top'].setText(str(config['pos_for_sp'][0]))
        self.components['single_pos_left'].setText(str(config['pos_for_sp'][1]))
        self.components['single_pos_bottom'].setText(str(config['pos_for_sp'][2]))
        self.components['single_pos_right'].setText(str(config['pos_for_sp'][3]))

    def init_enable_duration(self):
        # 初始化是否启用持续时间
        self.components['enable_duration'].setChecked(config['enable_duration'])
        self.components['duration_value'].setEnabled(config['enable_duration'])
        self.components['duration_unit'].setEnabled(config['enable_duration'])

    def init_framerate(self):
        # 初始化默认拍摄帧率
        self.components['framerate'].setValue(config['framerate'])

    def init_duration_value(self):
        for unit in self.DEF_DURATION_UNIT_LIST:
            self.components['duration_unit'].addItem(unit)
        self.components['duration_value'].setValue(config['duration_value'])
        self.components['duration_unit'].setCurrentIndex(config['duration_unit'])

    def init_camera_combo_box(self):
        # TODO: 从后端获取相机信息封装成为字典返回
        # 初始化相机下拉选单
        # cam_dict = CameraUtil.get_cam_dict()
        # for cam_name, cam in cam_dict.items():
        #     self.components['camera_combo_box'].addItem(cam_name)
        pass

    def init_binning(self):
        # 初始化binning选择控件
        self.components['x_bin'].setValue(config['x_bin'])
        self.components['y_bin'].setValue(config['y_bin'])

    def init_exposure(self):
        # 初始化曝光度输出框
        self.components['exposure'].setValidator(QIntValidator())
        self.components['exposure'].setText(str(config['exposure']))

    def init_progress_bar(self):
        # 初始化进度条
        self.components['progress_bar'].setValue(0)

    def init_program_output(self):
        if config['enable_log']:
            self.stick_resize(DEF_WIDTH_WITH_LOG, DEF_HEIGHT)
            self.components['program_output'].setChecked(True)
        else:
            self.stick_resize(DEF_WIDTH_WITHOUT_LOG, DEF_HEIGHT)
            self.components['program_output'].setChecked(False)

    def init_splitting_format(self):
        # 切割规格选择
        self.components['x_splitting_format'].setValue(config['x_splitting_format'])
        self.components['y_splitting_format'].setValue(config['y_splitting_format'])

    def init_stick_on_top(self):
        # 设置窗口是否可以一直处于顶端
        flag = self.components['stick_on_top'].isChecked()
        if flag:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()  # 必须重新显示窗口以使更改生效

    def init_enable_extension(self):
        # 初始化边界拓展参数设定
        for unit in self.DEF_EXTENSION_UNIT_LIST:
            self.components['unit_combo'].addItem(unit)  # 单位选择

        flag = (config['enable_extension'] == 1)
        self.components['enable_extension'].setChecked(flag)
        self.components['x_off'].setEnabled(flag)
        self.components['y_off'].setEnabled(flag)
        self.components['unit_combo'].setEnabled(flag)
        self.components['x_off'].setValue(config['x_off'])  # 设置x，y偏移量
        self.components['y_off'].setValue(config['y_off'])
        self.components['unit_combo'].setCurrentIndex(config['extension_unit'])  # 设置当前选择单位

    """
    =============================================================
    ----------------------- slot --------------------------------
    =============================================================
    """

    def closeEvent(self, event):
        logger.debug('Closing network connection')
        self.client.terminate()
        # self.message_processor.join()
        logger.debug('Frontend process successfully terminated')
        event.accept()

    def check_enable_duration_slot(self, num: int):
        flag = (num == self.CHECK_BOX_CHECKED)
        self.components['duration_value'].setEnabled(flag)
        self.components['duration_unit'].setEnabled(flag)

    def load_cameras_slot(self):
        # TODO: 获取可用相机列表
        # 重新获取相机列表，并重新加载可选相机下拉列表
        self.components['camera_combo_box'].clear()
        # self.print_log('loading cameras')
        self.init_camera_combo_box()

    def set_progress(self, val: int):
        self.components['progress_bar'].setValue(MathUtil.clamp(val, 0, 100))  # 设置进度条

    # 清除控制台输出
    def click_output_clean_slot(self):
        # 清空日志窗口内容
        self.log_cache.clear()
        self.components['program_output_text'].setText('')

    def click_exec_btn_slot(self):
        """
        程序执行入口
        """
        if self.status == Status.UNAVAILABLE:
            return

        # 查询当前运行模式
        if self.status == Status.TERMINABLE:
            # 停止连续拍摄
            self.set_status(Status.UNAVAILABLE)
            ...

        # 如果状态为VANILLA，那么根据当前界面来决定执行
        if self.status == Status.VANILLA:
            self.set_status(Status.UNAVAILABLE)
            current_tab = self.components['mode_tab'].currentIndex()
            if current_tab == self.TAB_XY_CONTINUOUS_NUM:
                self.xy_acquire()  # xy坐标横移连拍

            if current_tab == self.TAB_SINGLE_POINT_NUM:
                self.sp_acquire()  # 单点连拍

    def xy_acquire(self):
        self.progress_signal.emit(0)  # 清空进度条
        # cam_name = self.components['camera_combo_box'].currentText()
        # cam_id = cam_name  # 当前使用相机id，从下拉菜单获取
        cam_id = 1
        enable_extension = self.components['enable_extension'].isChecked()  # 是否启用拓展
        x_split = self.components['x_splitting_format'].value()  # 分片数量
        y_split = self.components['y_splitting_format'].value()

        # 初始化任务
        self.done_task_num = 0
        self.task_num = x_split * y_split

        x_off, y_off, extension_unit = 0, 0, 0  # 拓展单位和拓展量
        if enable_extension:
            x_off = self.components['x_off'].value()
            y_off = self.components['y_off'].value()
            extension_unit = self.components['unit_combo'].currentIndex()

        exposure = self.components['exposure'].text()  # 曝光度
        x_bin = self.components['x_bin'].value()  # xy方向binning参数
        y_bin = self.components['y_bin'].value()

        message = Message()
        message.setHeader('name', 'ContinuousAcquire')
        message.setHeader('option', 0)
        message.set('cam_id', cam_id)
        message.set('enable_extension', 1 if enable_extension else 0)
        message.set('extension_unit', extension_unit)
        message.set('x_off', x_off)
        message.set('y_off', y_off)
        message.set('exposure', exposure)
        message.set('x_bin', x_bin)
        message.set('y_bin', y_bin)
        message.set('x_split', x_split)
        message.set('y_split', y_split)

        self.client.send_msg(message, self.xy_acquire_callback)

    def xy_acquire_callback(self, response: Message):
        self.lock.acquire()
        try:
            self.done_task_num += 1
            # 渲染进度条
            position = MathUtil.clamp(round(100 / self.task_num * self.done_task_num), 0, 100)
            self.progress_signal.emit(position)

            logger.debug(f'done task: {self.done_task_num} / {self.task_num}')

            if self.done_task_num >= self.task_num:
                self.progress_signal.emit(100)
                self.log_signal.emit('Done xy acquire task!')
                self.set_status(Status.VANILLA)
        finally:
            self.lock.release()

    def sp_acquire(self):
        self.set_progress(0)  # 清空进度条
        # cam_name = self.components['camera_combo_box'].currentText()
        # cam_id = cam_name  # 相机id
        cam_id = 1

        # 获取拍摄坐标
        pos_top = self.components['single_pos_top'].text()
        pos_left = self.components['single_pos_left'].text()
        pos_bottom = self.components['single_pos_bottom'].text()
        pos_right = self.components['single_pos_right'].text()

        enable_duration = self.components['enable_duration'].isChecked()  # 是否启用持续时间
        duration_value = self.components['duration_value'].value()  # 持续时间数值
        duration_unit = self.components['duration_unit'].currentIndex()  # 持续时间单位，0：毫秒、1：秒、2：分钟、3：小时
        framerate = self.components['framerate'].value()  # 帧率
        exposure = self.components['exposure'].text()  # 曝光度
        x_bin = self.components['x_bin'].value()  # xy方向binning参数
        y_bin = self.components['y_bin'].value()

        # 构建消息
        message = Message()
        message.setHeader('name', 'ContinuousAcquire')
        message.setHeader('option', 1)
        message.set('cam_id', cam_id)
        message.set('pos_top', pos_top)
        message.set('pos_left', pos_left)
        message.set('pos_bottom', pos_bottom)
        message.set('pos_right', pos_right)
        message.set('enable_duration', 1 if enable_duration else 0)
        message.set('duration_value', duration_value)
        message.set('duration_unit', duration_unit)
        message.set('framerate', framerate)
        message.set('exposure', exposure)
        message.set('x_bin', x_bin)
        message.set('y_bin', y_bin)

        self.client.send_msg(message, self.sp_acquire_callback)

    def sp_acquire_callback(self, response: Message):
        print(response)
        self.set_status(Status.VANILLA)

    def check_stick_on_top_slot(self, num: int):
        flag = (num == self.CHECK_BOX_CHECKED)
        if flag:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()  # 必须重新显示窗口以使更改生效

    def check_program_output_slot(self, num: int):
        flag = (num == self.CHECK_BOX_CHECKED)
        if flag:
            self.stick_resize(DEF_WIDTH_WITH_LOG, DEF_HEIGHT)
        else:
            self.stick_resize(DEF_WIDTH_WITHOUT_LOG, DEF_HEIGHT)

    def check_enable_extension_slot(self, num: int):
        """ XY界面，是否开启边界拓展拍摄 """
        flag = (num == self.CHECK_BOX_CHECKED)
        self.components['x_off'].setEnabled(flag)
        self.components['y_off'].setEnabled(flag)
        self.components['unit_combo'].setEnabled(flag)

    """
    =============================================================
    --------------------- tool function -------------------------
    =============================================================
    """

    # 变更执行按钮状态
    def set_status(self, status: Status):
        self.status = status
        self.components['exec_btn'].setText(str(status.value))
        if self.status == Status.UNAVAILABLE:
            self.components['exec_btn'].setEnabled(False)
        else:
            self.components['exec_btn'].setEnabled(True)

    def stick_resize(self, width: int, height: int):
        # 固定窗口尺寸并且重新渲染
        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)
        self.resize(width, height)
        self.repaint()

    # 控制台输出日志
    def print_log(self, line: str):
        """
        控制台输出方法，可以向GUI中的控制台输出信息
        """
        # 通过菜单控制台打印日志输出
        log_line = f'<span style="color:red">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}:{line}</span><br/>'
        self.log_cache.append(log_line)
        text = " ".join(self.log_cache)
        self.components['program_output_text'].setText(text)
        bottom = self.components['program_output_text'].verticalScrollBar().maximum()
        self.components['program_output_text'].verticalScrollBar().setValue(bottom)  # 滚动到最底部


if __name__ == '__main__':
    # 主执行函数
    app = QApplication(sys.argv)
    menu = Gui()
    menu.show()
    app.exec_()

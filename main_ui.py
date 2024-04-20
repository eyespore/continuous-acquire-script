"""
Created on 2024.4.9
@author: Pineclone
@version: 0.2.5
"""
__version__ = '0.2.5'

import concurrent.futures
import json
import random
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from math import floor
from threading import Thread
from typing import List

import yaml
from PyQt5 import QtCore
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import *
from loguru import logger


logger.info(f'Launching ContinuousAcquireScripts, current version: {__version__}')

# 修正窗口界面尺寸
QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

# 项目根目录路径设置
ROOT_DIR = '.'

# 菜单UI路径设定
MENU_UI_PATH = f'{ROOT_DIR}/main.ui'

# yaml配置文件路径设定
CONFIG_PATH = f'{ROOT_DIR}/config.yaml'

# 程序配置字典，通过字典来获取程序配置
cfg = {}
# 尝试读取配置，如果配置存在错误则会采用默认配置
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    yml_cfg = yaml.safe_load(f)

    logger.debug(f'Loading config, yaml config path: {CONFIG_PATH}')


    def load_val(val_path, yml_sup, def_val):
        # 加载配置文件并且将值用于参数初始化
        try:
            yml_val = yml_sup()
            if type(yml_val) is not type(def_val):
                logger.error(
                    f'\'{val_path}\' is in wrong type, expect {type(def_val)} but receive {type(yml_val)}, using default value: {def_val}')
                cfg[val_path] = def_val
                return

            # 如果参数为list需要额外判断
            if type(yml_val) is list:
                # 判断长度是否相等
                if len(yml_val) != len(def_val):
                    logger.error(
                        f'\'{val_path}\' bad given params in list, expect {len(def_val)} elements but receive {len(yml_val)}, using default value: {def_val}')
                    cfg[val_path] = def_val
                    return

                # 判断每一位上面元素类型是否相等
                for index, element in enumerate(yml_val):
                    if type(element) is not type(def_val[index]):
                        logger.error(
                            f'\'{val_path}\' bad given params in list, expect {type(def_val[index])} for index {index}, but receive {type(element)}, using default value: {def_val}')
                    cfg[val_path] = def_val
                    return

            cfg[val_path] = yml_val
        except KeyError as e:
            logger.error(f'\'{val_path}\' has not been defined in yaml config, using default value: {def_val}')
            cfg[val_path] = def_val


    # 通过yml_path来获取yml配置文件参数，以list的形式传入

    # xy轴连续横移拍摄参数初始化
    load_val('exposure', lambda: yml_cfg['acquire']['xy']['exposure'], 1000)  # 曝光度默认值
    load_val('x_bin', lambda: yml_cfg['acquire']['xy']['x_bin'], 1)  # x_bin默认值
    load_val('y_bin', lambda: yml_cfg['acquire']['xy']['y_bin'], 1)  # y_bin默认值
    load_val('x_off', lambda: yml_cfg['acquire']['xy']['x_off'], 0)  # x轴拓展默认值
    load_val('y_off', lambda: yml_cfg['acquire']['xy']['y_off'], 0)  # y轴拓展默认值
    load_val('enable_extension', lambda: yml_cfg['acquire']['xy']['enable_extension'], 0)  # 是否启用边界拓展
    load_val('extension_unit', lambda: yml_cfg['acquire']['xy']['extension_unit'], 0)  # 边界拓展默认单位，0：px、1：%
    load_val('x_splitting_format', lambda: yml_cfg['acquire']['xy']['x_splitting_format'], 2)  # x轴默认切割格式
    load_val('y_splitting_format', lambda: yml_cfg['acquire']['xy']['y_splitting_format'], 2)  # y轴默认切割格式
    load_val('multi_thread_num', lambda: yml_cfg['acquire']['xy']['multi_thread_num'], 10)  # 默认线程数
    load_val('multi_process_num', lambda: yml_cfg['acquire']['xy']['multi_process_num'], 5)  # 默认线程数

    # 单点连续拍摄参数初始化
    load_val('pos_for_sp', lambda: yml_cfg['acquire']['sp']['pos_for_sp'],
             [0, 0, 0, 0])  # 默认坐标参数，从上到下依次是top,left,bottom,right
    load_val('enable_duration', lambda: yml_cfg['acquire']['sp']['enable_duration'], False)  # 是否开启持续时间
    load_val('duration_value', lambda: yml_cfg['acquire']['sp']['duration_value'], 10)  # 默认持续时间
    load_val('duration_unit', lambda: yml_cfg['acquire']['sp']['duration_unit'], 1)  # 持续连拍默认采用时间单位
    load_val('framerate', lambda: yml_cfg['acquire']['sp']['framerate'], 10)  # 持续连拍默认采用时间单位

    # 界面参数设定
    load_val('font', lambda: yml_cfg['ui']['main']['font'], 'consolas')
    load_val('font_size', lambda: yml_cfg['ui']['main']['font_size'], 8)
    load_val('enable_log', lambda: yml_cfg['ui']['main']['enable_log'], True)

# 默认字体设定
DEF_FONT = QFont(cfg['font'], cfg['font_size'])

# 窗口大小设置
DEF_WINDOW_TITLE = 'Continuous Acquire Scripts'
DEF_WIDTH_WITHOUT_LOG = 350
DEF_WIDTH_WITH_LOG = 520
DEF_HEIGHT = 230

# 默认弹窗消息宽度，这在很大程度上影响了弹窗的大小
DEF_MESSAGE_BOX_TEXT_LEN = 35


# 定时任务类，用于启动定时任务
class ScheduleTaskUtil:
    @staticmethod
    def schedule(ms: int, task):
        QTimer.singleShot(ms, task)


class ImageUtil:
    """
    拍摄结束之后回传的图片结果处理，图像结果通常是数组对象
    """

    @staticmethod
    def handle_images(images: dict):
        # todo: 图像结果处理逻辑
        for index, img in images.items():
            logger.info(f'{index} : {img}')


class CameraUtil:
    """
    相机操作类，通过该类来执行相机相关方法
    """

    @staticmethod
    def acquire_img(cam_id: int, exposure: int, x_bin: int, y_bin: int,
                    top: int, left: int, bottom: int, right: int):
        """
        拍摄函数，返回一个Py_Image，需要传入一个相机，以及提供拍摄坐标
        :param cam_id: 拍摄使用的相机id
        :param exposure: 拍摄时采用的曝光度
        :param x_bin, y_bin : x_y方向binning值
        :param top: 顶部坐标
        :param left: 左侧坐标
        :param bottom: 底部坐标
        :param right: 右侧坐标
        :return: 图片对象
        """
        # 模拟耗时任务，假设每张图片需要1-2s完成拍摄，需要使用QTimer模拟耗时任务，避免阻塞主线程
        # todo: 实现相机拍摄
        delay = random.randint(1000, 2000)
        time.sleep(float(delay) / 1000)
        return f'complete in {delay}'

    @staticmethod
    def get_cam_size(cam_id: int) -> (int, int):
        """ 通过相机id获取相机镜头尺寸 """
        return 4096, 4096

    @staticmethod
    def get_cam_by_id(cam_id: int):
        """ 通过相机id获取相机对象 """
        return 'cam'

    @staticmethod
    def get_active_cam():
        """ 获取当前激活相机 """

    @staticmethod
    def get_cam_dict() -> dict:
        """ 获取可用相机列表，以id作为键名 """
        return {
            "cam1_name": {
                "id": 1,
                "name": "cam1_name",
                "x_size": 4096,
                "y_size": 4096,
                "x_px_size": 1,
                "y_px_size": 1
            },
            "cam2_name": {
                "id": 1,
                "name": "cam2_name",
                "x_size": 4096,
                "y_size": 4096,
                "x_px_size": 1,
                "y_px_size": 1
            },
        }


class AcquireFacade:
    """ 拍摄门面，通过拍摄门面可以提前设定拍摄参数，然后通过坐标列表的形式完成拍摄任务 """

    def __init__(self, cam_id: int, exposure=cfg['exposure'], x_bin=cfg['x_bin'], y_bin=cfg['y_bin']):
        self.exposure = exposure
        self.x_bin = x_bin
        self.y_bin = y_bin
        self.cam_id = cam_id

    def simple_img(self, pos_top, pos_left, pos_bottom, pos_right) -> str:
        return CameraUtil.acquire_img(self.cam_id, self.exposure, self.x_bin, self.y_bin,
                                      pos_top, pos_left, pos_bottom, pos_right)


class MainUI(QWidget):
    # 当前GUI状态，根据执行的任务改变
    class TaskThread(QThread):
        """
        任务线程基类，任务线程是基于GUI线程MainUI运行的，程序采用了IOC和DI的设计思想来管理所有任务线程，
        一个任务线程从创建到销毁的生命周期如下：
        
        - 编写任务线程类，使其继承于TaskThread
        - MainUI会在被创建时执行MainUI.init_threads用于将任务线程添加到线程容器threads当中
        - 之后会逐步对线程执行初始化流程，流程为：初始化 -> aware依赖注入 -> 线程启动前置 -> 线程启动
          -> 线程启动后置方法
        - 在主界面MainUI关闭时，任务线程的thread_close方法会被执行，用于判断任务线程是否可关闭
        
        注意任务线程仍然基于QThread创建，这意味着在任务线程中运行例如time.sleep依旧会导致GUI线程阻塞针
        对会出现阻塞的情况，应该使用threading或者processing来进行并发或者并行调用，来避免主线程阻塞
        """

        def thread_init(self):
            """
            线程初始化方法
            :param signals: 信号对象，在调用的时候可以用于对自身信号属性进行初始化
            """
            pass

        def thread_pre_launch(self):
            """
            线程启动前执行方法
            主线程将在对子线程调用start方法直线执行此方法
            """
            pass

        def thread_post_launch(self):
            """
            线程启动之后执行此方法
            """
            pass

        def thread_close(self) -> bool:
            """
            线程关闭方法
            该方法会在主线程关闭时被调用，如果子线程返回false则可以拒绝关闭响应
            :return: 如果返回False，那么将会拒绝关闭请求，返回True则允许关闭
            """
            pass

    class Status(Enum):
        VANILLA = 'EXEC'
        UNAVAILABLE = 'N/A'
        TERMINABLE = "STOP"

    # 基础常量
    # 单选框被选中后表现的value
    CHECK_BOX_CHECKED = 2
    # xy坐标横移连拍tab对应的下标
    TAB_XY_CONTINUOUS_NUM = 0
    # 单点连拍tab对应的下标
    TAB_SINGLE_POINT_NUM = 1
    # 边缘拓展单位
    DEF_EXTENSION_UNIT_LIST = ['px', '%', ]
    # 可用时间单位列表
    DEF_DURATION_UNIT_LIST = ['millis', 'seconds', 'minutes', 'hours']

    # 进度条信号，提供线程设置主线程进度条渲染的能力
    prog_signal = pyqtSignal(int)
    # 控制台信号，提供线程在控制台打印输出的能力
    log_signal = pyqtSignal(str, bool, int)
    # 回复执行按钮信号，提供线程恢复主控按钮exec的能力
    status_signal = pyqtSignal(Status)

    # 错误弹窗信号，接收一个function作为confirm按钮被点击之后的处理槽
    error_signal = pyqtSignal(str, object)
    # 消息弹窗信号
    warning_signal = pyqtSignal(str, object)
    # 定时任务信号，方便子线程引入定时任务，参数为毫秒
    schedule_signal = pyqtSignal(int, object)

    # 关闭信号，当注册菜单被关闭的时候会发送给监听关闭信号的子线程
    close_signal = pyqtSignal()
    # 确认关闭信号，如果子线程确认可以关闭那么使用这个信号来回复主线程的关闭请求
    confirm_close_signal = pyqtSignal(bool)

    # 图像信号，子线程完成图像拍摄任务之后通过图像信号携带图像列表回传主线程
    # 主线程再对信号进行处理后展示，由于返回数据通常是无序的，因此需要通过index索引来排序
    img_signal = pyqtSignal(dict)

    def __init__(self):
        """
        主界面构造方法
        """
        super().__init__()
        logger.debug('Launching Main Thread')
        # GUI属性初始化
        uic.loadUi(MENU_UI_PATH, self)
        self.setWindowTitle(DEF_WINDOW_TITLE)
        self.components = self.__dict__  # 将组件作为对象属性
        # 程序输出窗口信息缓存
        self.program_output_cache: List[str] = []

        # exec按钮状态信息
        self.exec_btn_status = self.Status.VANILLA

        # 子线程池
        self.threads: dict[str, MainUI.TaskThread] = {}

        logger.debug('Initializing GUI')
        # 执行GUI界面初始化方法
        self.init_ui()

        logger.debug('Initializing Task Threads')
        # 初始化任务线程对象
        self.init_threads()

        self.acquire_thread = self.threads['acquire_thread']

        # 绑定信号和槽函数
        logger.debug('Initializing Signals and Slot')
        self.init_signals()

        self.print_log(f'<span style="color: {LogColor.SAFE}; font-weight:bold">successfully launch menu</span>')
        logger.info('Successfully launch Main UI, Waiting for executing commands...')

    """
    =============================================================
    ----------------------- init --------------------------------
    =============================================================
    """

    def init_ui(self):
        """ GUI组件初始化，主要负责图形化界面的初始化工作 """
        self.init_font()
        self.init_enable_extension()
        self.init_stick_on_top()
        self.init_splitting_format()
        self.init_program_output()
        self.init_progress_bar()
        self.init_exposure()
        self.init_binning()
        # 初始化单点连拍坐标参数
        self.init_single_point_pos()
        # 初始化是否启用持续时间
        self.init_enable_duration()
        self.init_duration_value()
        self.init_framerate()

        # 初始化相机下拉选单
        self.init_camera_combo_box()
        # 初始化执行按钮
        self.init_exec_btn()

    def init_threads(self):
        """
        子线程初始化方法，使用容器存储所有需要管理的线程对象，由主线程提供接口，子线程通过实现某个对应接口来挂载
        主线程的生命周期，或者事件发送事件
        """
        self.threads['acquire_thread'] = AcquireThread()

        for name, t in self.threads.items():
            t.thread_init()

            # 判断线程是否是实现了aware接口，调用以传入某个初始化参数
            if issubclass(type(t), Aware.MainUI):
                t.aware_main_ui(self)
                # 下面这一句只会执行抽象类当中的实现
                # Aware.MainUI.aware_main_ui(t, self)

            t.thread_post_launch()
            t.start()
            t.thread_post_launch()

    def init_signals(self):
        """ 绑定函数与槽 """
        # 拓展命令行窗口
        self.components['enable_extension'].stateChanged.connect(self.check_enable_extension_slot)
        # 将窗口置于最前端
        self.components['stick_on_top'].stateChanged.connect(self.check_stick_on_top_slot)
        # 是否启用多线程策略（现在默认启用多线程）
        # self.threading_strategy_btn_group.buttonClicked.connect(self.check_threading_mode)
        # 通过菜单日志栏打印日志信息
        self.components['program_output'].stateChanged.connect(self.check_program_output_slot)
        # 执行日志栏清空
        self.components['program_output_clean'].clicked.connect(self.click_output_clean_slot)
        # 启动程序
        self.components['exec_btn'].clicked.connect(self.click_exec_btn_slot)

        # 进度条信号，控制进图条渲染
        self.prog_signal.connect(self.set_progress_bar_val)
        # 日志信号，控制日志输出
        self.log_signal.connect(self.print_log)
        # 恢复信号，恢复按钮正常使用
        self.status_signal.connect(self.set_status)

        # 分片信息更改，重新渲染分片信息label
        # self.components['splitting_spin_box'].valueChanged.connect(self.change_splitting_pieces_slot)

        # 将图像列表回传信号和处理槽函数连接
        self.img_signal.connect(ImageUtil.handle_images)
        # 刷新可用相机下拉选单
        self.components['load_cameras'].clicked.connect(self.load_cameras_slot)

        # 对AcquireThread线程的信号和槽进行挂载
        self.acquire_thread.xy_task_signal.connect(self.acquire_thread.xy_acquire)
        # 区域连拍信号
        self.acquire_thread.single_point_signal.connect(self.acquire_thread.sp_acquire)
        # 是否启用单区域连拍持续时间
        self.components['enable_duration'].stateChanged.connect(self.check_enable_duration_slot)
        # 终止线程信号
        self.acquire_thread.terminating_signal.connect(self.acquire_thread.terminating_thread)
        # 定时任务信号
        self.schedule_signal.connect(ScheduleTaskUtil.schedule)

    # 初始化字体
    def init_font(self):
        self.setFont(DEF_FONT)

    # 初始化执行按钮
    def init_exec_btn(self):
        self.set_status(self.Status.VANILLA)

    # 初始化单点连拍坐标参数
    def init_single_point_pos(self):
        self.components['single_pos_top'].setValidator(QIntValidator())
        self.components['single_pos_left'].setValidator(QIntValidator())
        self.components['single_pos_bottom'].setValidator(QIntValidator())
        self.components['single_pos_right'].setValidator(QIntValidator())

        self.components['single_pos_top'].setText(str(cfg['pos_for_sp'][0]))
        self.components['single_pos_left'].setText(str(cfg['pos_for_sp'][1]))
        self.components['single_pos_bottom'].setText(str(cfg['pos_for_sp'][2]))
        self.components['single_pos_right'].setText(str(cfg['pos_for_sp'][3]))

    # 初始化是否启用持续时间
    def init_enable_duration(self):
        self.components['enable_duration'].setChecked(cfg['enable_duration'])
        self.components['duration_value'].setEnabled(cfg['enable_duration'])
        self.components['duration_unit'].setEnabled(cfg['enable_duration'])

    # 初始化默认拍摄帧率
    def init_framerate(self):
        self.components['framerate'].setValue(cfg['framerate'])

    def init_duration_value(self):
        for unit in self.DEF_DURATION_UNIT_LIST:
            self.components['duration_unit'].addItem(unit)
        self.components['duration_value'].setValue(cfg['duration_value'])
        self.components['duration_unit'].setCurrentIndex(cfg['duration_unit'])

    # 初始化相机下拉选单
    def init_camera_combo_box(self):
        cam_dict = CameraUtil.get_cam_dict()
        for cam_name, cam in cam_dict.items():
            self.components['camera_combo_box'].addItem(cam_name)

    # 初始化拍摄线程
    def init_acquire_thread(self):
        self.acquire_thread.start()

    # 初始化binning选择控件
    def init_binning(self):
        self.components['x_bin'].setValue(cfg['x_bin'])
        self.components['y_bin'].setValue(cfg['y_bin'])

    # 初始化曝光度输出框
    def init_exposure(self):
        self.components['exposure'].setValidator(QIntValidator())
        self.components['exposure'].setText(str(cfg['exposure']))

    # 初始化进度条
    def init_progress_bar(self):
        self.components['progress_bar'].setValue(0)

    def init_program_output(self):
        if cfg['enable_log']:
            self.stick_resize(DEF_WIDTH_WITH_LOG, DEF_HEIGHT)
            self.components['program_output'].setChecked(True)
        else:
            self.stick_resize(DEF_WIDTH_WITHOUT_LOG, DEF_HEIGHT)
            self.components['program_output'].setChecked(False)

    def init_splitting_format(self):
        # 切割规格选择
        self.components['x_splitting_format'].setValue(cfg['x_splitting_format'])
        self.components['y_splitting_format'].setValue(cfg['y_splitting_format'])

    def init_stick_on_top(self):
        # 设置窗口是否可以一直处于顶端
        flag = self.components['stick_on_top'].isChecked()
        # self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        if flag:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.show()
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            self.show()  # 必须重新显示窗口以使更改生效

    def init_enable_extension(self):
        # 初始化边界拓展参数设定
        # 单位选择
        for unit in self.DEF_EXTENSION_UNIT_LIST:
            self.components['unit_combo'].addItem(unit)

        flag = (cfg['enable_extension'] == 1)
        self.components['enable_extension'].setChecked(flag)
        self.components['x_off'].setEnabled(flag)
        self.components['y_off'].setEnabled(flag)
        self.components['unit_combo'].setEnabled(flag)
        # 设置spinBox初始值
        self.components['x_off'].setValue(cfg['x_off'])
        self.components['y_off'].setValue(cfg['y_off'])
        # 设置当前选择单位
        self.components['unit_combo'].setCurrentIndex(cfg['extension_unit'])

    """
    =============================================================
    ----------------------- slot --------------------------------
    =============================================================
    """

    def closeEvent(self, event):
        for name, t in self.threads.items():
            if not t.thread_close():
                event.ignore()
                logger.debug('Main UI ignore close event')
                return

        logger.debug('Main UI accept close event')
        event.accept()

    def check_enable_duration_slot(self, num: int):
        flag = (num == self.CHECK_BOX_CHECKED)
        self.components['duration_value'].setEnabled(flag)
        self.components['duration_unit'].setEnabled(flag)

    # 重新获取相机列表，并重新加载可选相机下拉列表
    def load_cameras_slot(self):
        self.components['camera_combo_box'].clear()
        self.print_log('loading cameras')
        self.init_camera_combo_box()

    # 分片数量改变
    # def change_splitting_pieces_slot(self, num: int):
    #     self.components['splitting_result_label'].setText(f'{num} x {num}')

    # 设置进度条
    def set_progress_bar_val(self, val: int):
        self.components['progress_bar'].setValue(MathUtil.clamp(val, 0, 100))

    # 清除控制台输出
    def click_output_clean_slot(self):
        # 清空日志窗口内容
        self.program_output_cache.clear()
        self.components['program_output_text'].setText('')

    def click_exec_btn_slot(self):
        """
        程序执行入口
        """
        if self.get_status() == self.Status.UNAVAILABLE:
            return

        # 首先查询当前运行模式
        if self.get_status() == self.Status.TERMINABLE:
            # 停止连续拍摄
            self.set_status(self.Status.UNAVAILABLE)
            self.acquire_thread.terminating_signal.emit()

        # 如果状态为VANILLA，那么根据当前界面来决定执行
        if self.get_status() == self.Status.VANILLA:
            self.set_status(self.Status.UNAVAILABLE)
            current_tab = self.components['mode_tab'].currentIndex()
            if current_tab == self.TAB_XY_CONTINUOUS_NUM:
                # xy坐标横移连拍
                self.xy_acquire()

            if current_tab == self.TAB_SINGLE_POINT_NUM:
                # 单点连拍
                self.sp_acquire()

    def xy_acquire(self):
        # 清空进度条
        self.set_progress_bar_val(0)

        # 当前使用相机id，从下拉菜单获取
        cam_name = self.components['camera_combo_box'].currentText()
        cam_id = CameraUtil.get_cam_dict()[cam_name]['id']
        # 是否启用拓展
        enable_extension = self.components['enable_extension'].isChecked()

        # 分片数量
        x_split = self.components['x_splitting_format'].value()
        y_split = self.components['y_splitting_format'].value()

        # 拓展单位和拓展量
        x_off, y_off, extension_unit = 0, 0, 0
        if enable_extension:
            x_off = self.components['x_off'].value()
            y_off = self.components['y_off'].value()
            extension_unit = self.components['unit_combo'].currentIndex()

        # 曝光度
        exposure = self.components['exposure'].text()
        # xy方向binning参数
        x_bin = self.components['x_bin'].value()
        y_bin = self.components['y_bin'].value()

        param_dict = {
            'cam_id': cam_id,
            'enable_extension': enable_extension,
            'extension_unit': extension_unit,
            'x_off': x_off,
            'y_off': y_off,
            'exposure': exposure,
            'x_bin': x_bin,
            'y_bin': y_bin,
            'x_split': x_split,
            'y_split': y_split
        }

        # 通过信号发送参数
        self.acquire_thread.xy_task_signal.emit(json.dumps(param_dict))

    def sp_acquire(self):
        # 清空进度条
        self.set_progress_bar_val(0)

        # 相机id
        cam_name = self.components['camera_combo_box'].currentText()
        cam_id = CameraUtil.get_cam_dict()[cam_name]['id']

        # 获取拍摄坐标
        pos_top = self.components['single_pos_top'].text()
        pos_left = self.components['single_pos_left'].text()
        pos_bottom = self.components['single_pos_bottom'].text()
        pos_right = self.components['single_pos_right'].text()

        # 是否启用持续时间
        enable_duration = self.components['enable_duration'].isChecked()
        # 持续时间数值
        duration_value = self.components['duration_value'].value()
        # 持续时间单位，0：毫秒、1：秒、2：分钟、3：小时
        duration_unit = self.components['duration_unit'].currentIndex()

        # 获取帧率
        framerate = self.components['framerate'].value()

        # 曝光度
        exposure = self.components['exposure'].text()
        # xy方向binning参数
        x_bin = self.components['x_bin'].value()
        y_bin = self.components['y_bin'].value()

        param_dict = {
            'cam_id': cam_id,
            'positions': [pos_top, pos_left, pos_bottom, pos_right],
            'enable_duration': enable_duration,
            'duration_value': duration_value,
            'duration_unit': duration_unit,
            'framerate': framerate,
            'exposure': exposure,
            'x_bin': x_bin,
            'y_bin': y_bin,
        }

        # 通过信号发送参数
        self.acquire_thread.single_point_signal.emit(json.dumps(param_dict))

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
        # print(num)
        flag = (num == self.CHECK_BOX_CHECKED)
        self.components['x_off'].setEnabled(flag)
        self.components['y_off'].setEnabled(flag)
        self.components['unit_combo'].setEnabled(flag)

    """
    =============================================================
    --------------------- static method -------------------------
    =============================================================
    """

    # 变更执行按钮状态
    def set_status(self, status: Status):
        self.exec_btn_status = status
        self.components['exec_btn'].setText(str(status.value))
        if self.get_status() == self.Status.UNAVAILABLE:
            self.components['exec_btn'].setEnabled(False)
        else:
            self.components['exec_btn'].setEnabled(True)

    def get_status(self) -> Status:
        return self.exec_btn_status

    # 固定窗口尺寸并且重新渲染
    def stick_resize(self, width: int, height: int):
        self.setMaximumSize(width, height)
        self.setMinimumSize(width, height)
        self.resize(width, height)
        self.repaint()

    # 控制台输出日志
    def print_log(self, msg: str, prefix: bool = True, blank: int = 2):
        """
        控制台输出方法，可以向GUI中的控制台输出信息
        :param msg: 输出内容
        :param prefix: 是否携带时间日期前缀
        :param blank: 和下一句输出保留空行，默认保留两次空行
        """
        # 通过菜单控制台打印日志输出
        if prefix:
            before_line = f'<span style="color:red">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}:</span><br/>'
            self.program_output_cache.append(before_line + msg + '<br/>' * blank)
        else:
            self.program_output_cache.append(msg + '<br/>' * blank)

        text = ''
        for ui_line in self.program_output_cache:
            # 两次换行
            text += ui_line
        self.components['program_output_text'].setText(text)
        # 滚动到最底部
        (self.components['program_output_text'].verticalScrollBar()
         .setValue(self.components['program_output_text'].verticalScrollBar().maximum()))


class Aware:
    """
    兴趣接口，对于所有TaskThread线程子类，可以通过继承Aware下某个具体的接口，来实现创建过程中实例的注入
    注意注入过程发生在thread_init方法执行之后
    """

    class MainUI:
        def aware_main_ui(self, main_ui: MainUI):
            pass


class AcquireThread(MainUI.TaskThread, Aware.MainUI):
    """
    拍摄线程，在程序运行期间保持启动状态，执行拍摄任务
    """

    # 拍摄子线程ID
    class ClosureID(Enum):
        ACQUIRE_THREAD_1 = 1
        """ XY坐标轴横纵移动连拍线程ID """

        ACQUIRE_THREAD_2 = 2
        """ 单点连续拍摄线程ID """

    """
    拍摄线程，并发执行拍摄任务
    """
    # 执行xy横纵轴平移连拍需要用到的信号，这个信号接收一个json数据，并且会调用handle_xy_continuous_acquire处理信号
    xy_task_signal = pyqtSignal(str)

    # 执行定点连拍需要用到的信号，信号接收json数据，调用handle_single_point_acquire
    single_point_signal = pyqtSignal(str)

    # 终止连拍信号，传递信号后该任务线程会终止所有正在运行的任务
    terminating_signal = pyqtSignal()

    # def __init__(self, prog_signal, log_signal, resume_signal, img_signal):
    def __init__(self):
        super().__init__()

        # 闭包容器，每一个闭包线程需要存在自己的线程id
        self.closures: dict[AcquireThread.ClosureID, None] = {}

        # 初始化闭包任务，避免空指针异常
        for closure_id in self.ClosureID:
            self.closures[closure_id] = None

        # 创建线程池，用于提交拍摄任务，定义默认线程数为5
        self.pool = ThreadPoolExecutor(max_workers=cfg['multi_thread_num'])

    def aware_main_ui(self, main_ui: MainUI):
        # 获取main_ui用于打印弹窗
        self.main_ui = main_ui

        self.prog_signal = self.main_ui.prog_signal  # 通过进度条信号实时向主线程回传进度信息
        self.log_signal = self.main_ui.log_signal  # 通过日志信号向控制台输出信息
        self.status_signal = self.main_ui.status_signal  # 通过恢复信号，在适当的时候恢复主执行按钮
        self.img_signal = self.main_ui.img_signal  # 图像信号，用于在获取图像完成后返回图像
        self.schedule_signal = self.main_ui.schedule_signal  # 定时任务信号

    def thread_close(self) -> bool:
        flag = False
        for closure_id in self.ClosureID:
            if self.closures[closure_id] is not None:
                flag = True

        if flag:
            dialog = QMessageFactory.create_box()
            dialog.setWindowTitle("Undone Task")
            dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)

            # XY轴横移拍摄线程未结束 或 单区域连续拍摄任务未结束

            text = '<br/>'.join(textwrap.wrap('A Running Task has not finished yet, '
                                              'do you want to stop the task and exit?', DEF_MESSAGE_BOX_TEXT_LEN))
            dialog.setText(text)

            dialog.setIcon(QMessageBox.Warning)
            button_clicked = dialog.exec_()

            if button_clicked == QMessageBox.Yes:
                return True
            else:
                # 线程拒绝退出
                return False

        return True

    def print_log(self, msg: str, prefix: bool = True, blank: int = 2):
        self.log_signal.emit(msg, prefix, blank)

    def terminating_thread(self):
        """
        通过传入的线程id来终止所有线程
        :return: 无返回值，通过等待线程发送线程完成关闭信号来确认线程已经关闭
        """
        for closure_id in self.ClosureID:
            if self.closures[closure_id]:
                logger.debug('Terminating thread %s' % closure_id)
                self.status_signal.emit(MainUI.Status.UNAVAILABLE)
                for e_index, element in enumerate(self.closures[closure_id].__closure__):
                    # print(e_index, type(element.cell_contents))
                    if type(element.cell_contents) is list:
                        is_terminated = self.closures[closure_id].__closure__[e_index].cell_contents
                        is_terminated[0] = True

    def sp_acquire(self, param_json: str):
        """
        执行单点连拍功能
        :param param_json: 拍摄参数，以json形式传输，包含参数如下：
                cam_id:                 : 当前使用相机id
                positions               : 拍摄固定点位坐标，索引：0: top、1: left、2: bottom、3: right
                enable_duration         : 是否开启持续时间（若不开启则保持执行连拍直至手动停止）
                duration_value          : 持续时间数值（可选）
                duration_unit           : 持续时间单位（可选）,持续时间单位，0：毫秒、1：秒、2：分钟、3：小时
                framerate               : 帧率
                exposure:               : 曝光度
                x_bin, y_bin:           : 方向binning
        :return: 拍摄获得的图像列表
        """
        try:
            # 接收数据
            param = json.loads(param_json)
            cam_id = int(param['cam_id'])
            positions = list(param["positions"])
            enable_duration = bool(param["enable_duration"])
            duration_value = int(param["duration_value"])
            duration_unit = int(param['duration_unit'])
            framerate = int(param["framerate"])
            exposure = int(param["exposure"])
            x_bin = int(param["x_bin"])
            y_bin = int(param["y_bin"])

            logging = [f'<span style="color: #1ba035; font-weight: bold">SINGLE POINT</span>',
                       f'cam_id          : {cam_id}',
                       f'positions       : <br/>{positions}',
                       f'enable_duration : {enable_duration}',
                       f'duration_value  : {duration_value}',
                       f'extension_unit  : {duration_unit}',
                       f'framerate       : {framerate}',
                       f'exposure        : {exposure}',
                       f'x_bin           : {x_bin}',
                       f'y_bin           : {y_bin}']
            self.print_log('<br/>.'.join(logging))
            logging[0] = 'SINGLE POINT'
            logging[2] = f'positions       : {positions}'
            for line in logging:
                logger.debug(line)

            # index代表策略，0：并行执行单点连拍，1表示串行执行单点连拍
            self.closures[self.ClosureID.ACQUIRE_THREAD_2] = (
                self.create_sp_acquire_closure(cam_id=cam_id, positions=positions, enable_duration=enable_duration,
                                               duration_value=duration_value, duration_unit=duration_unit,
                                               framerate=framerate, exposure=exposure, x_bin=x_bin, y_bin=y_bin,
                                               index=0))

            Thread(target=self.closures[self.ClosureID.ACQUIRE_THREAD_2]).start()

        except Exception as e:
            msg = f'<span style="color: {LogColor.WARNING}; font-weight: bold">Exception Occur:<br/>{e}</span>'
            self.print_log(msg)
            # 打印日志
            QMessageFactory.message(msg).exec_()

    def create_sp_acquire_closure(self, **kwargs):
        # 执行单点连拍业务逻辑
        # 执行初始化工作
        cam_id = kwargs['cam_id']
        positions = kwargs["positions"]
        enable_duration = kwargs["enable_duration"]
        duration_value = kwargs["duration_value"]
        duration_unit = kwargs['duration_unit']
        framerate = kwargs["framerate"]
        exposure = kwargs["exposure"]
        x_bin = kwargs["x_bin"]
        y_bin = kwargs["y_bin"]
        index = kwargs['index']

        # 闭包式执行，且监听关闭信号，如果监听到关闭信号则临时终止拍摄，返回已经获取的图像列表
        # 线程执行钩子，可以用于停止线程
        is_terminated = [False]

        # 获取相机尺寸，进行合法性校验
        sx, sy = CameraUtil.get_cam_size(cam_id)

        # 根据binning和positions获取实际拍摄坐标，同时进行参数合法性校验
        pos_top = MathUtil.clamp(int(positions[0]), 0, sy - 1) // y_bin
        pos_left = MathUtil.clamp(int(positions[1]), 0, sx - 1) // x_bin
        pos_bottom = MathUtil.clamp(int(positions[2]), pos_top, sy - 1) // y_bin
        pos_right = MathUtil.clamp(int(positions[3]), pos_left, sx - 1) // x_bin

        # 拍摄门面
        facade = AcquireFacade(cam_id, exposure, x_bin, y_bin)

        # 计算持续时间，单位采用毫秒
        duration = -1
        if enable_duration and duration_value != 0:
            if duration_unit == 0:
                # millis
                duration = duration_value
            elif duration_unit == 1:
                # seconds
                duration = duration_value * 1000
            elif duration_unit == 2:
                # minutes
                duration = duration_value * 60 * 1000
            elif duration_unit == 3:
                duration = duration_value * 60 * 60 * 1000

        def single_thread_run():
            # 打印变量，确保is_terminated变量处于索引为0的位置
            self.print_log('Single task exec', True, 1)

            # todo: 编写单点连续拍摄业务逻辑
            if duration != -1:
                self.print_log(
                    f'program will stop in <br/><span style="color: {LogColor.ALERT}">'
                    f'{duration_value} {MainUI.DEF_DURATION_UNIT_LIST[duration_unit]}</span>',
                    False, 1)

                # 终止线程
                self.schedule_signal.emit(duration, lambda: self.terminating_thread(self.ClosureID.ACQUIRE_THREAD_2))

            self.print_log(
                f'<span style="color: {LogColor.SAFE}">Collecting result:</span>', False, 1)

            self.status_signal.emit(MainUI.Status.TERMINABLE)

            # 创建图像列表，用于储存拍摄数据
            img_dict = {}
            count = 0
            # 起始点计时
            start = time.perf_counter()

            while True:
                # 拍摄图像
                count += 1
                img = facade.simple_img(pos_top=pos_top, pos_left=pos_left, pos_right=pos_right, pos_bottom=pos_bottom)
                img_dict[datetime.now().strftime("%Y-%m-%d %H:%M:%S")] = img
                self.print_log(f'current index: {count}', False, 1)

                if is_terminated[0]:
                    break

            # 返回拍摄数据
            self.img_signal.emit(img_dict)
            self.print_log(f'<span style="color: {LogColor.SAFE}">Complete Task</span>', True, 1)
            self.print_log(f'<span style="color: {LogColor.SAFE}">Total count: {count}</span>', False, 1)
            self.print_log('cost: {:.2f} s'.format(float(time.perf_counter()) - start), False, 2)
            self.status_signal.emit(MainUI.Status.VANILLA)
            # 将闭包移除
            self.closures[self.ClosureID.ACQUIRE_THREAD_2] = None

        closures = [single_thread_run]
        return closures[index]

    def xy_acquire(self, param_json: str):
        """
        处理xy轴横纵向移动连拍功能
        :parse param_json: 拍摄参数，以json形式传输，包含参数：
               cam_id:           当前使用相机id
               x_split:           拍摄分片数量
               enable_extension: 否启用边界拓展
               x_off, y_off:     x，y方向上的拓展量
               extension_unit:   拓展单位
               exposure:         曝光度
               x_bin, y_bin:     方向binning
        :return: 返回图像列表，目前使用假数据代替
        """
        try:
            parse: dict = json.loads(param_json)

            cam_id = int(parse["cam_id"])
            x_split = int(parse["x_split"])
            y_split = int(parse["y_split"])
            enable_extension = bool(parse["enable_extension"])
            x_off = int(parse["x_off"])
            y_off = int(parse['y_off'])
            extension_unit = parse["extension_unit"]
            exposure = int(parse["exposure"])
            x_bin = int(parse["x_bin"])
            y_bin = int(parse["y_bin"])

            logging = [f'<span style="color: #1ba035; font-weight: bold">XY CONTINUOUS</span>',
                       f'cam_id          : {cam_id}',
                       f'enable_extension: {enable_extension}',
                       f'x_off           : {x_off}',
                       f'y_off           : {y_off}',
                       f'extension_unit  : {extension_unit}',
                       f'exposure        : {exposure}',
                       f'x_bin           : {x_bin}',
                       f'y_bin           : {y_bin}',
                       f'x_split         : {x_split}',
                       f'y_split         : {y_split}']
            self.print_log('<br/>'.join(logging))
            logging[0] = 'XY CONTINUOUS'
            for line in logging:
                logger.debug(line)

            # index为策略，1为并行策略，2为串行策略，3为切割策略（未实现）
            self.closures[self.ClosureID.ACQUIRE_THREAD_1] = (
                self.create_xy_acquire_closure(cam_id=cam_id, x_split=x_split, y_split=y_split,
                                               enable_extension=enable_extension,
                                               x_off=x_off, y_off=y_off, extension_unit=extension_unit,
                                               exposure=exposure, x_bin=x_bin, y_bin=y_bin, index=0))

            # 使用策略构建线程并且执行
            Thread(target=self.closures[self.ClosureID.ACQUIRE_THREAD_1]).start()

        except Exception as e:
            msg = f'<span style="color: {LogColor.WARNING}; font-weight: bold">Exception Occur:<br/>{e}</span>'
            self.print_log(msg)
            # 打印日志
            QMessageFactory.message(msg).exec_()

    # 可以切换策略执行
    def create_xy_acquire_closure(self, **kwargs):
        # 采用并行的形式执行拍摄任务
        # 通过主线程发送的信号，解析字符串，获取参数
        # print(type())
        cam_id = kwargs["cam_id"]
        x_split = kwargs["x_split"]
        y_split = kwargs["y_split"]
        enable_extension = kwargs["enable_extension"]
        x_off = kwargs["x_off"]
        y_off = kwargs['y_off']
        extension_unit = kwargs["extension_unit"]
        exposure = kwargs["exposure"]
        x_bin = kwargs["x_bin"]
        y_bin = kwargs["y_bin"]
        index = kwargs["index"]

        # 创建任务并且提交到任务线程池任务队列，需要计算出拍摄坐标合集
        # 获取相机镜头像素范围，计算步长
        sx, sy = CameraUtil.get_cam_size(cam_id)
        # 需要将binning纳入计算
        sx //= x_bin
        sy //= y_bin

        # 拍摄门面
        facade = AcquireFacade(cam_id, exposure, x_bin, y_bin)

        # 坐标列表
        positions = []

        # 计算步长
        x_step_len = sx // x_split
        y_step_len = sy // y_split

        for line_num in range(y_split):
            # 行循环
            for col_num in range(x_split):
                # 列循环，计算得到目标坐标
                top = line_num * y_step_len
                left = col_num * x_step_len
                bottom = (line_num + 1) * y_step_len
                right = (col_num + 1) * x_step_len

                # 执行策略，启用拓展的情况下
                if enable_extension and (x_off != 0 or y_off != 0):
                    # 如果启用了边界拓展，那么需要对拓展的尺寸进行计算
                    if extension_unit == 0:
                        # 像素拓展，向四周拓展
                        top -= y_off
                        left -= x_off
                        bottom += y_off
                        right += x_off

                    # 百分比拓展，需要计算出拓展的像素
                    if extension_unit == 1:
                        v_off = floor(y_step_len * (0.01 * x_off))
                        h_off = floor(x_step_len * (0.01 * x_off))

                        top -= v_off
                        left -= h_off
                        bottom += v_off
                        right += h_off

                # 执行对坐标的圆整，注意坐标从0开始，因此无法访问边界坐标
                top = MathUtil.clamp(top, 0, sy - 1)
                left = MathUtil.clamp(left, 0, sx - 1)
                bottom = MathUtil.clamp(bottom, top, sy - 1)
                right = MathUtil.clamp(right, left, sx - 1)

                positions.append([top, left, bottom, right])

        # 检查坐标添加情况
        # msg = f'<span style="color: {LogColor.ALERT}; font-weight: bold">Acquire Positions:</span><br/>'
        # for i, pos in enumerate(positions):
        #     if i != len(positions):
        #         msg += f'{pos},<br/>'
        #     else:
        #         msg += f'{pos}'
        # self.print_log(msg)

        # 通过坐标列表构建任务添加到线程池当中
        # 用于暂停程序的执行一段时间。然而，在PyQt应用中，直接使用time.sleep会导致应用程序的界面无法响应，因为它会阻塞主线程
        # 线程执行钩子，可以用于停止线程
        is_terminated = [False]

        # 定义闭包函数用于创建线程执行
        def multi_thread_run():
            """ ========== 多线程策略 ========== """
            start = time.perf_counter()
            futures = {}
            for f_index, pos in enumerate(positions):
                # 构建任务，将坐标信息传入
                future = self.pool.submit(facade.simple_img, pos[0], pos[1], pos[2], pos[3])
                futures[future] = f_index

            progress_step = 100.0 / len(positions)
            completed_num = 0
            # 在此处阻塞等待线程完成任务
            img_dict = {}
            self.print_log('Collecting result:', True, 1)

            # 更改按钮样式，支持线程终止
            self.status_signal.emit(MainUI.Status.TERMINABLE)

            for completed_future in concurrent.futures.as_completed(futures):
                # 开始执行前判断是否线程被中断
                if is_terminated[0]:
                    break

                self.print_log(f'done index: {futures[completed_future]}', False, 1)
                # 构建返回值
                img_dict[futures[completed_future]] = completed_future.result()
                # 完成一个拍摄任务之后需要渲染进度条
                completed_num += 1
                num = progress_step * completed_num
                self.prog_signal.emit(floor(num))

            # 完成之后将图像列表回传给主线程
            self.img_signal.emit(img_dict)
            self.print_log(f'<span style="color: {LogColor.SAFE}">Complete Task</span>', True, 1)
            self.print_log('cost: {:.2f} s'.format(float(time.perf_counter()) - start), False, 2)

            # 任务完成后，将进度条置于100%，如果为强制终止线程，那么进度条不应该置于100%
            if not is_terminated[0]:
                self.prog_signal.emit(100)
            # 恢复执行按钮可用
            self.status_signal.emit(MainUI.Status.VANILLA)
            # 解除闭包引用
            self.closures[self.ClosureID.ACQUIRE_THREAD_1] = None

        def single_thread_run():
            """ ========== 单线程策略 ========== """
            img_dict = {}

            progress_step = 100 // len(positions)
            completed_num = 0
            self.print_log('collecting result:', True, 1)
            for index, pos in enumerate(positions):
                # 调用门面函数执行拍摄
                # future = self.pool.submit(facade.simple_img, pos[0], pos[1], pos[2], pos[3])
                # futures[future] = index
                img = facade.simple_img(pos[0], pos[1], pos[2], pos[3])
                self.print_log(f'done index: {index}', False, 1)
                img_dict[index] = img
                completed_num += 1
                # 渲染进度条
                self.prog_signal.emit(progress_step * completed_num)

            # 完成之后将图像列表回传给主线程
            self.img_signal.emit(img_dict)
            self.print_log(f'completed acquire!', True, 2)
            # 任务完成后，将进度条置于100%
            self.prog_signal.emit(100)
            # 恢复执行按钮可用
            self.status_signal.emit(MainUI.Status.VANILLA)
            # 解除闭包引用
            self.closures[self.ClosureID.ACQUIRE_THREAD_1] = None

        def single_splitting_run():
            # 单次拍摄后执行切割获得结果
            ...

        closures = [multi_thread_run, single_thread_run, single_splitting_run]
        return closures[index]

    def run(self):
        # 线程执行函数，通过死循环保持线程运行
        while True:
            # 线程刷新间隔
            time.sleep(1)


class LogColor:
    ALERT = '#1ba035'
    WARNING = '#fc3d49'
    SAFE = '#0067a6'


class QMessageFactory:
    """
    弹窗工厂，提供基本弹窗对象，同时作为弹窗工厂，产生弹窗对象
    """

    @staticmethod
    def create_box() -> QMessageBox:
        """
        创建基本对话框窗体，可以使用这个方法来构建基础对话框，然后在此之上添加元素
        如果需要快速构建某一类弹窗，那么可以使用下面提供的工厂方法来快速构建
        :return:
        """
        box = QMessageBox()
        box.setFont(DEF_FONT)
        return box

    @staticmethod
    def confirm(msg, title='Warning', no_icon=False) -> QMessageBox:
        """ 警告弹窗，包含确定和取消按钮 """
        box = QMessageFactory.create_box()
        box.setWindowTitle(title)

        # 实现自动换行
        textwrap.wrap(msg, DEF_MESSAGE_BOX_TEXT_LEN)
        box.setText(msg.join('<br/>'))

        if not no_icon:
            box.setIcon(QMessageBox.Warning)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        return box

    @staticmethod
    def message(msg, title='Message', no_icon=False) -> QMessageBox:
        """ 普通消息弹窗，包含确认按钮 """
        box = QMessageFactory.create_box()
        box.setWindowTitle(title)

        # 实现自动换行
        textwrap.wrap(msg, DEF_MESSAGE_BOX_TEXT_LEN)
        box.setText(msg.join('<br/>'))

        if not no_icon:
            box.setIcon(QMessageBox.Information)
        box.setStandardButtons(QMessageBox.Ok)
        return box


class MathUtil:
    """
    数学函数定义
    """

    @staticmethod
    def clamp(val, min_val, max_val):
        """
        Clamp value between min_val and max_val
        """
        if val <= min_val:
            return min_val
        if val >= max_val:
            return max_val
        return val


def main():
    # 主执行函数
    app = QApplication(sys.argv)
    menu = MainUI()
    menu.show()
    app.exec_()


if __name__ == '__main__':
    main()

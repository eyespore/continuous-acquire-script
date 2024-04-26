"""
Created on 2024.4.24
@author: Pineclone
@version: 0.0.1
主要是为后端提供socket连接适配，创建中间件线程接收前端数据，处理之后将数据转发到后端程序，
"""
__version__ = '0.0.1'

import cmd
import os
import pickle
import queue
import socket
import threading
import sys
from collections import defaultdict

import yaml
from loguru import logger

from message import Message
from mq_py.properties import Properties

# 配置日志输出等级
logger.info(f'Launching MQ process by python, current version: {__version__}')

# 配置文件初始化
ROOT_DIR = '.'  # 项目根路径
CONFIG_PATH = f'{ROOT_DIR}/config.yaml'
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    yml_cfg = yaml.safe_load(f)

logger.debug(f'Loading MessageQueue yaml config, path: {CONFIG_PATH}')

logger.debug(f'Loading backend process config, path: {yml_cfg["path"]["backend_config"]}')
prop_cfg = Properties(yml_cfg['path']['backend_config']).get_prop()
logger.debug(f'Complete loading program config')



# 请求消息队列，由后端接口读取输出管道数据写入此处，由前端接口读出派发给对应前端程序
# 格式: [ip:port]<空格>[操作名]<空格>[响应体]<换行符> 字符串
request_mq = queue.Queue()

# 响应消息队列，由前端接口会被缓存到此处，由后端接口写入输入管道中
# 格式: [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> 字符串
response_mq = queue.Queue()

# 连接队列，通过connection_handler处理之后产生的连接对象会被存储在此处
connection_cache = queue.Queue()
# 连接处理线程追踪器，为二维字典，以address作为键名，connection连接以及connection_thread作为键值
connection_tracker = defaultdict(dict)

# 中间件绑定ip地址
server_host = yml_cfg['server']['host']
# 中间件绑定端口
server_port = yml_cfg['server']['port']

# 超时时间，超时后会再次检查线程状态
timeout = yml_cfg['server']['timeout']

# 线程退出信号量
is_terminated = False
is_launched = False


# 输入管道文件，通过输入管道文件以 [ip:port]<空格>[操作名]<空格>[请求体] 的格式写入数据
input_pip_path = prop_cfg['input_pip_path']
# 输入管道锁文件，完成写入之后移除锁，使后端读取消息，没有锁的时候不应该写入数据，直至后端进程归还锁
input_pip_lock = prop_cfg['input_pip_lock']

# 输出管道文件，输出管道以 [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> 的格式写出数据
output_pip_path = prop_cfg['output_pip_path']
# 输出管道锁文件，如果不存在锁文件，可以直接读取消息，读取完成之后需要创建锁文件，存在锁文件的时候不应该读取输出管道消息
output_pip_lock = prop_cfg['output_pip_lock']

# 检测管道文件是否存在
if not os.path.exists(input_pip_path):
    raise FileNotFoundError(f'Cannot find input pip file at : {input_pip_path}')

if not os.path.exists(output_pip_path):
    raise FileNotFoundError(f'Cannot find output pip file at : {output_pip_path}')


class connection_builder(threading.Thread):
    def run(self):
        """
        创建连接对象线程，连接被创建之后会被加入connection_queue以及conn_pool当中
        """
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((server_host, server_port))
        # 设置超时时间，避免等待时间过长
        server.settimeout(timeout)
        server.listen()
        logger.info(f'Connection Builder launched, listening connection from {server_host}:{server_port}')

        global is_terminated
        while not is_terminated:
            try:
                connection, address = server.accept()
                logger.info(f'Accept connection from {address[0]}:{address[1]}')
                connection_tracker[address]['connection'] = connection
                # 将连接对象添加进入连接池
                connection_cache.put((connection, address))
            except socket.timeout:
                # 如果线程已经停止运行，那么退出程序
                if is_terminated:
                    break
        # 线程退出，关闭服务器
        server.close()
        logger.debug('Middleware Server shutdown')


class backend_input_middleware(threading.Thread):
    """
    消息中间件 -> 后端输入管道
    读取request_mq消息队列获取请求消息，将消息封装成为后端可读格式，写入后端输入管道中，完成写入之后
    删除input_pip_lock锁文件，当锁文件不存在的时候不允许写入，锁文件由 后端进程 维护

    消息格式-后端输入管道 : [ip:port]<空格>[操作名]<空格>[请求体]<换行符>
    消息格式-消息中间件  : Message实例

    """

    def run(self) -> None:
        logger.debug('Backend-Input-Middleware interface launched')
        global is_terminated, timeout
        while not is_terminated:
            try:
                request_message: str = request_mq.get(timeout=timeout)

                print(request_message)

            except queue.Empty:
                # 超时退出
                if is_terminated:
                    break
        # 线程退出


class backend_output_middleware(threading.Thread):
    """
    后端输出管道 -> 消息中间件
    读取后端输出管道消息，封装成为Message对象加入response_mq当中，锁文件output_pip_lock不存在的时候
    可以执行读取，读取完成之后需要手动创建锁文件，允许后端进程继续写入响应，锁文件存在的时候不允许读取，output_pip_lock
    锁文件由 中间件进程 维护

    消息格式-后端输出管道   : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
    消息格式-response_mq : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>

    """

    def run(self) -> None:
        logger.debug('Backend-Output-Middleware interface launched')
        ...


class frontend_output_middleware(threading.Thread):
    """
    前端进程 -> 消息中间件
    通过connection_cache缓冲池获取前端连接实例，处理实例构建处理线程，线程创建 消息中间件 和 某一个前端进程 的长连接
    长连接存在时可以维持双端数据传输，传输时使用Message实例对象作为传输格式

    消息格式-前端进程    : Message实例

    """
    def run(self):
        logger.debug('Frontend-Input-Middleware interface launched')

        # 从连接缓冲区获取连接对象
        global is_terminated
        while not is_terminated:
            try:
                # 设置超时事件，避免退出后线程阻塞
                connection, address = connection_cache.get(timeout=timeout)
                connection.settimeout(timeout)
                connection_thread = threading.Thread(target=self.handle_connection, args=(connection, address))
                # 将处理线程添加进入线程池中
                connection_tracker[address]['connection_thread'] = connection_thread
                connection_thread.start()
            except queue.Empty:
                if is_terminated:
                    break
        logger.debug('Frontend-Input-Middleware interface shutdown')

    def handle_connection(self, connection, address):
        """
        连接处理线程，主要是将address中的ip地址和port信息加入消息中，封装成为 管道消息格式 ，然后加入
        request_mq当中，等待输入进程将消息写入管道文件中

        消息格式-前端进程     : Message实例
        消息格式-request_mq : [ip:port]<空格>[操作名]<空格>[请求体]<换行符> （字符串形式）

        """
        global is_terminated
        while not is_terminated:
            try:
                data = connection.recv(4096)
                if not data:
                    break
                if len(data) < 4:
                    raise ValueError("Received packet is too small to contain pickle data.")
                # 长度部分取前四个字节
                length = int.from_bytes(data[:4:], byteorder='big')
                if len(data) < length + 4:
                    # 如果没有接收到完整的数据，继续接收余下部分
                    # 注意这里没有设置缓冲区，需要避免接收过大体量的请求
                    remaining = length + 4 - len(data)
                    data += connection.recv(remaining)

                # 解码对象，对象数据在四字节之后
                message = pickle.loads(data[4:])
                # 或取当前用户ip地址，为message设置
                message.setAddress(address)

                # 将消息转化为字符串格式加入队列中
                request_mq.put(message.to_backend_input())

            except socket.timeout as e:
                if is_terminated:
                    connection.close()
                    logger.debug(f'Connection timeout : {address[0]}:{address[1]}')
                    return

        # 用户线程退出，关闭连接
        connection.close()
        # 不再追踪该地址信息
        connection_tracker.pop(address)
        logger.debug(f'Connection close : {address[0]}:{address[1]}')


class frontend_input_middleware(threading.Thread):
    """
    前端响应线程，将response_mq当中已有消息取出，然后根据Message格式解析，同时获取源的ip以及端口，通过
    connection_pool获取原始连接对象，将封装好的Message返回给前端进程，前端进程通过函数接收

    消息格式-前端进程     : Message实例
    消息格式-response_mq : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> （字符串形式）

    """

    def run(self):
        logger.debug('Frontend-Output-Middleware interface launched')
        ...


class middleware_cmd(cmd.Cmd):
    """
    命令行界面构建
    提供简单的指令，用于对消息中间件程序进行流程控制
    """
    prompt = '> '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.conn_builder = connection_builder()  # 连接处理器

        self.interface_1 = frontend_output_middleware()  # 前端 -> 中间件
        self.interface_2 = backend_input_middleware()  # 中间件 -> 后端
        self.interface_3 = backend_output_middleware()  # 后端 -> 中间件
        self.interface_4 = frontend_input_middleware()  # 中间件 -> 前端

        """Launch MessageQueue program"""
        global is_launched
        if is_launched:
            logger.info('Middleware has already launched')
            return

        # 启动接口
        is_launched = True
        self.conn_builder.start()
        self.interface_1.start()
        self.interface_2.start()
        self.interface_3.start()
        self.interface_4.start()

    def do_quit(self, line):
        """ 关闭所有消息中间件所有接口之后退出程序 """
        # 触发关闭事件
        global is_terminated, timeout
        is_terminated = True
        # 为连接设置超时时间

        # 等待线程全部退出
        logger.info('Waiting middleware shutdown...')
        self.conn_builder.join()
        self.interface_1.join()
        self.interface_2.join()
        self.interface_3.join()
        self.interface_4.join()

        # 等待所有连接线程退出
        for address, connection_bundle in connection_tracker.items():
            connection_bundle['connection_thread'].join()

        logger.info('Middleware successfully shutdown')
        return True

    # 默认指令
    def default(self, line):
        """Default action for any command not recognized"""
        print("指令未识别，键入 'help' 来查询可用的指令.")


if __name__ == '__main__':
    # 启动命令行程序，避免进程退出
    middleware_cmd().cmdloop("Successfully launch Middleware for DM Script, input 'help' for available command.")

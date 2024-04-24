"""
Created on 2024.4.24
@author: Pineclone
@version: 0.0.1
主要是为后端提供socket连接适配，创建中间件线程接收前端数据，处理之后将数据转发到后端程序，
"""
__version__ = '0.0.1'

import pickle
import queue
import socket
import threading

import yaml
from loguru import logger

from message import Message
from mq_py.properties import Properties

logger.info(f'Launching MQ process by python, current version: {__version__}')

# 配置文件初始化
ROOT_DIR = '../mq_py_dir'  # 项目根路径
CONFIG_PATH = f'{ROOT_DIR}/config.yaml'
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    yml_cfg = yaml.safe_load(f)

logger.debug(f'Loading MessageQueue yaml config, path: {CONFIG_PATH}')

logger.debug(f'Loading backend process config, path: {yml_cfg["path"]["backend_config"]}')
prop_cfg = Properties(yml_cfg['path']['backend_config']).get_prop()
logger.debug(f'Complete loading program config')

# 输入管道文件，通过输入管道文件以 [ip:port]<空格>[操作名]<空格>[请求体] 的格式写入数据
input_pip_path = prop_cfg['input_pip_path']
# 输入管道锁文件，完成写入之后移除锁，使后端读取消息，没有锁的时候不应该写入数据，直至后端进程归还锁
input_pip_lock = prop_cfg['input_pip_lock']

# 输出管道文件，输出管道以 [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> 的格式写出数据
output_pip_path = prop_cfg['output_pip_path']
# 输出管道锁文件，如果不存在锁文件，可以直接读取消息，读取完成之后需要创建锁文件，存在锁文件的时候不应该读取输出管道消息
output_pip_lock = prop_cfg['output_pip_lock']

# 请求消息队列，由后端接口读取输出管道数据写入此处，由前端接口读出派发给对应前端程序
# 格式: [ip:port]<空格>[操作名]<空格>[响应体]<换行符> 字符串
request_mq = queue.Queue()

# 响应消息队列，由前端接口会被缓存到此处，由后端接口写入输入管道中
# 格式: [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> 字符串
response_mq = queue.Queue()

# 连接队列，通过connection_handler处理之后产生的连接对象会被存储在此处
connection_cache = queue.Queue()
# 连接池，通过ip和端口建立起对某个连接对象的映射，从而在消息回传的时候能够将回传消息
# 重新映射到某个具体的前端程序上
connection_pool = {}


def backend_in_interface():
    """
    消息中间件 -> 后端输入管道
    读取request_mq消息队列获取请求消息，将消息封装成为后端可读格式，写入后端输入管道中，完成写入之后
    删除input_pip_lock锁文件，当锁文件不存在的时候不允许写入，锁文件由 后端进程 维护

    消息格式-后端输入管道 : [ip:port]<空格>[操作名]<空格>[请求体]<换行符>
    消息格式-消息中间件  : Message实例

    """
    ...


def backend_out_interface():
    """
    后端输出管道 -> 消息中间件
    读取后端输出管道消息，封装成为Message对象加入response_mq当中，锁文件output_pip_lock不存在的时候
    可以执行读取，读取完成之后需要手动创建锁文件，允许后端进程继续写入响应，锁文件存在的时候不允许读取，output_pip_lock
    锁文件由 中间件进程 维护

    消息格式-后端输出管道   : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
    消息格式-response_mq : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>

    """
    ...


def frontend_in_interface():
    """
    前端进程 -> 消息中间件
    通过connection_cache缓冲池获取前端连接实例，处理实例构建处理线程，线程创建 消息中间件 和 某一个前端进程 的长连接
    长连接存在时可以维持双端数据传输，传输时使用Message实例对象作为传输格式

    消息格式-前端进程    : Message实例

    """

    def handle_connection(conn, addr):
        """
        连接处理线程，主要是将address中的ip地址和port信息加入消息中，封装成为 管道消息格式 ，然后加入
        request_mq当中，等待输入进程将消息写入管道文件中

        消息格式-前端进程     : Message实例
        消息格式-request_mq : [ip:port]<空格>[操作名]<空格>[请求体]<换行符> （字符串形式）

        """
        while True:
            try:
                data = conn.recv(4096)
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
                    data += conn.recv(remaining)

                # 解码对象，对象数据在四字节之后
                message = pickle.loads(data[4:])
                print(f'Received object: {message}')
            except socket.error as e:
                logger.debug(f'Connection close : {addr[0]}:{addr[1]}')

    # 从连接缓冲区获取连接对象
    while True:
        connection, address = connection_cache.get()
        # 创建新的线程处理连接请求
        threading.Thread(target=handle_connection, args=(connection, address))


def frontend_out_interface():
    """
    前端响应线程，将response_mq当中已有消息取出，然后根据Message格式解析，同时获取源的ip以及端口，通过
    connection_pool获取原始连接对象，将封装好的Message返回给前端进程，前端进程通过函数接收

    消息格式-前端进程     : Message实例
    消息格式-response_mq : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> （字符串形式）

    """
    ...


def connection_builder():
    """
    创建连接对象线程，连接被创建之后会被加入connection_queue以及conn_pool当中
    :return:
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    host = socket.gethostname()
    port = 25565
    server.bind((host, 25565))
    server.listen()
    logger.debug(f'Server launch on {host}:{port}')

    while True:
        connection, address = server.accept()
        print(f'Accept connection from client: {address}, submit to sub-thread')
        connection_pool[address] = connection
        # 将连接对象添加进入连接池
        connection_cache.put((connection, address))

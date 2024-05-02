"""
数据传输模块
"""
import pickle
import threading
import socket
import uuid
from typing import Callable, Dict
from loguru import logger

from .network import Message


class MessageProcessor(threading.Thread):
    def __init__(self, config_):
        """
        消息转发器，融合了消息发送器，消息接收器功能的连接处理器
        :param config_: 连接配置，配置连接的端口和主机信息
        """
        threading.Thread.__init__(self)
        self.is_terminated = False  # 是否停止线程
        self.callbacks: Dict[str, Callable[[Message], None]] = {}  # 回调映射，uuid->callback
        server_host = config_['server_host']  # 连接主机
        server_port = config_['server_port']  # 连接端口
        server_timeout = config_['server_timeout']  # 连接超时事件
        logger.info(f'Connecting to MessageQueue Server on {server_host}:{server_port}')
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 设置超时时间
        self.connection.settimeout(server_timeout)
        self.connection.connect((server_host, server_port))
        logger.info(f'Successfully construct connection head to {server_host}:{server_port}')

    def send_str(self, string: str, callback: Callable[[Message], None]):
        """
        以字符串的形式发送消息，消息字符串随后被解码成为Message对象然后进行转发，
        通过回调函数的形式在数据返回时进行回调
        :param string: 编码之后的Message实例
        :param callback: 回调函数，在请求响应时会被调用
        """
        message = Message.loads(string)  # 消息解码
        self.send_msg(message, callback)

    def send_msg(self, message: Message, callback: Callable[[Message], None]):
        """
        直接发送消息实例，消息回传之后会执行回调函数
        :param message: message实例
        :param callback: 回调函数，在请求响应时会被调用
        """
        if self.is_terminated:
            logger.error('This MessageProcessor has already terminated')
            return

        if not message:
            return

        task_id = str(uuid.uuid4())  # 创建回调映射
        message.setHeader('task_id', task_id)
        self.callbacks[task_id] = callback

        data = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)  # 编码对象
        length = len(data).to_bytes(4, byteorder='big')
        self.connection.sendall(length)  # 发送数据长度
        self.connection.sendall(data)  # 发送数据

    def run(self):
        """
        模拟前端接收线程，负责接收消息
        """
        while not self.is_terminated:
            try:
                data = self.connection.recv(4096)
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
                    data += self.connection.recv(remaining)

                # 解码对象，并且将对象解析为Message实例，传递给对应的执行函数
                message = pickle.loads(data[4:])
                task_id = message.getHeader('task_id')
                self.callbacks[task_id](message)

            except socket.timeout:
                if self.is_terminated:
                    self.connection.close()
                    return
        # 线程退出
        self.connection.close()
        logger.info('Connection Close, MessageProcessor out')

    def terminate(self):
        self.is_terminated = True



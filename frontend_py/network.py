"""
Created on 2024.4.30
@author: Pineclone
@version: 0.0.1
网络组件
"""
from loguru import logger


class Message:
    """
    消息封装类，数据层对象，储存前端进程和消息中间件，消息中间件和后端进程之间通讯的信息，提供了到后端
    数据格式以及解析后端数据相关API，不推荐手动构建Message对象，推荐使用提供的静态方法创建对象

    输入管道消息格式: [ip:port]<空格>[操作名]<空格>[响应体]<换行符>
    输出管道消息格式: [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
    """

    def __init__(self):
        self.code = -1
        self.name = 'NotFound'
        self.body = 'Nil'
        self.address = ('127.0.0.1', 25565)

    def __str__(self):
        return (
            f"address: {self.address}\n"
            f"name: {self.name} \n"
            f"code: {self.code}\n"
            f"body: {self.body}")

    def getCode(self) -> int:
        return self.code

    def getName(self) -> str:
        return self.name

    def getBody(self) -> str:
        return self.body

    def getAddress(self) -> tuple:
        return self.address

    def setBody(self, body):
        self.body = body

    def setName(self, name):
        self.name = name

    def setCode(self, code):
        self.code = code

    def setAddress(self, address):
        self.address = address

    """
    ============================ Formatter ============================
    """

    def to_backend_input(self):
        """
        将消息转换为后端程序输入管道消息格式，需要提供ip地址和端口信息，调用
        这个方法会设置该消息的地址源信息
        :param address: 消息来源地址信息，包括ip和端口信息
        :return:
        """
        # [ip:port]<空格>[操作名]<空格>[响应体]<换行符>
        return f'{self.address[0]}:{self.address[1]} {self.name} {self.body}'

    def to_frontend_input(self):
        """
        将消息转换为前端输入接口格式
        :return:
        """
        return self

    @staticmethod
    def from_frontend_output(line: str):
        """
        解析前端传输至中间件的消息，从字符串格式化为Message格式
        :param line: 前端通过socket传输至后端的数据
        :return: Message对象
        """
        # [操作名]<空格>[请求体]<换行符>
        pos = line.find(' ')
        if pos == -1:
            raise ValueError('Unsupported frontend output message format : {line}')
        name = line[:pos:]
        body = line[pos + 1:]
        message = Message()
        message.setName(name)
        message.setBody(body)
        return message

    @staticmethod
    def from_backend_output(line: str):
        """
        格式化后端消息输出管道文件行数据，返回地址信息和Message对象
        :param line: 后端消息输出管道行数据
        :return: 地址信息以及Message对象
        """
        # [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
        try:
            split = []
            for i in range(0, 3):
                pos = line.find(' ')
                split.append(line[:pos])
                line = line[pos + 1:]
            split.append(line)
            host = split[0].split(':')[0]
            port = int(split[0].split(':')[1])
            address = (host, port)
            message = Message()
            message.setAddress(address)
            message.setName(split[1])
            message.setCode(split[2])
            message.setBody(split[3])
            return message
        except Exception as e:
            logger.error(f'Unsupported backend output message format : {line}')

import socket

from loguru import logger


class Message:
    """
    消息封装类，数据层对象，储存前端进程和消息中间件，消息中间件和后端进程之间通讯的信息，提供了到后端
    数据格式以及解析后端数据相关API

    输入管道消息格式: [ip:port]<空格>[操作名]<空格>[响应体]<换行符>
    输出管道消息格式: [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
    """

    def __init__(self, ip=socket.gethostname(), port=25565, name="NotFound", body="Nil", code=-1):
        self.code = code
        self.name = name
        self.body = body
        self.ip = ip
        self.port = port

    def __str__(self):
        return (
            f"ip: {self} \n"
            f"body: {self.body} \n"
            f"code: {self.code}\n"
            f"name: {self.name} \n"
            f"body: {self.body}")

    """
    ============================ Getter ============================
    """

    def getIp(self):
        return self.ip

    def getPort(self):
        return self

    def getCode(self) -> int:
        return self.code

    def getName(self) -> str:
        return self.name

    def getBody(self) -> str:
        return self.body

    """
    ============================ Setter ============================
    """

    def setBody(self, body):
        self.body = body

    def setName(self, name):
        self.name = name

    def setIp(self, ip):
        self.ip = ip

    def setPort(self, port):
        self.port = int(port)

    def setCode(self, code):
        self.code = code

    """
    ============================ Formatter ============================
    """

    def toInputPipLine(self):
        # [ip:port]<空格>[操作名]<空格>[响应体]<换行符>
        return f'{self.ip}:{self.port} {self.name} {self.body}'

    def toOutputPipLine(self):
        # [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
        return f'{self.ip}:{self.port} {self.code} {self.name} {self.body}'

    """
    ============================ Parser ============================
    """

    @staticmethod
    def fromInputPipLine(line: str):
        # [ip:port]<空格>[操作名]<空格>[响应体]<换行符>
        try:
            split = []
            for i in range(0, 3):
                pos = line.find(' ')
                split.append(line[:pos])
                line = line[pos + 1:]
            return Message(
                ip=split[0].split(':')[0],
                port=split[0].split(':')[1],
                name=split[1],
                body=split[2]
            )
        except Exception as e:
            logger.error(f'Unsupported input pip message format : {line}')

    @staticmethod
    def fromOutputPipLine(line: str):
        # [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
        try:
            split = []
            for i in range(0, 4):
                pos = line.find(' ')
                split.append(line[:pos])
                line = line[pos + 1:]
            return Message(
                ip=split[0].split(':')[0],
                port=split[0].split(':')[1],
                name=split[1],
                code=split[2],
                body=split[3]
            )
        except Exception as e:
            logger.error(f'Unsupported output pip message format : {line}')

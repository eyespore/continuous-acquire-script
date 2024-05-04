"""
数据传输模块
"""
from typing import Dict

from loguru import logger


class Message:
    """
    消息封装类，数据层对象，储存前端进程和消息中间件，消息中间件和后端进程之间通讯的信息，提供了到后端
    数据格式以及解析后端数据相关API，不推荐手动构建Message对象，推荐使用提供的静态方法创建对象
    """
    colon_seperator = "=>"  # 键值对分隔符
    comma_seperator = "##"  # 元素分隔符，分隔消息头元素
    message_seperator = "$$$"  # 消息分隔符，用于分隔消息头和消息体

    def __init__(self):
        self.head: Dict[str, str] = {}  # 消息头
        self.body: Dict[str, str] = {}  # 消息体

    def __str__(self):
        return f'{self.head}->{self.body}'

    def get(self, key) -> str:
        return self.body[str(key)]

    def set(self, key, val) -> None:
        self.body[str(key)] = str(val)

    def setHeader(self, key, val):
        self.head[str(key)] = str(val)

    def getHeader(self, key):
        return self.head[str(key)]

    def getBody(self) -> Dict[str, str]:
        return self.body

    def setBody(self, body: Dict[str, str]) -> None:
        self.body = body

    @staticmethod
    def dumps(msg) -> str:
        """
        将消息转换为后端程序输入管道消息格式，需要提供ip地址和端口信息，调用
        这个方法会设置该消息的地址源信息
        """
        head_entries = []
        for key, val in msg.head.items():
            head_entries.append(key + Message.colon_seperator + val)
        head_str = Message.comma_seperator.join(head_entries)

        body_entries = []
        for key, val in msg.body.items():
            body_entries.append(key + Message.colon_seperator + val)
        body_str = Message.comma_seperator.join(body_entries)

        return head_str + Message.message_seperator + body_str

    @staticmethod
    def loads(line: str):
        """
        格式化后端消息输出管道文件行数据，返回地址信息和Message对象
        :param line: 后端消息输出管道行数据
        """
        try:
            msg = Message()  # 创建消息对象
            head_n_body = line.split(Message.message_seperator)
            if len(head_n_body) == 1:
                head_str = ''  # 不包含消息头部
                body_str = head_n_body[0]
            else:
                head_str = head_n_body[0]
                body_str = head_n_body[1]

            if head_str != '':
                for entry in head_str.split(Message.comma_seperator):
                    kv = entry.split(Message.colon_seperator)
                    msg.setHeader(kv[0], kv[1])

            if body_str != '':
                for entry in body_str.split(Message.comma_seperator):
                    kv = entry.split(Message.colon_seperator)
                    msg.set(kv[0], kv[1])

            return msg

        except IndexError as e:
            logger.error(f'Incorrect k-v format, write k-v as \'key{Message.colon_seperator}val\'')
        except Exception as e:
            logger.error(f'Unable load a message due to incorrect message type : {line}, exception: {e}')


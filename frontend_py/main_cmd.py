"""
简易实现的命令行操作界面，提供通过命令行操作的方式来向中间件发送消息
"""
import cmd
import pickle
import socket
import threading

import yaml
from loguru import logger

from util.config_util import config
from network import Message

logger.info(f'Launching MainCMD program by python')


class ConnectionHandler:
    """
    连接处理类，在程序初始化时构建与后端程序的连接
    """
    # 前端程序与后端程序连接实例
    connection = None

    def __init__(self, config_):
        """
        连接处理器初始化方法
        :param config_: 连接配置，配置连接的端口和主机信息
        """
        server_host = config_['server_host']
        server_port = config_['server_port']
        server_timeout = config_['server_timeout']
        logger.info(f'Connecting to MessageQueue Server on {server_host}:{server_port}')
        self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 设置超时时间
        self.connection.settimeout(server_timeout)

        self.connection.connect((server_host, server_port))
        logger.info(f'Connect Success')


# 配置文件初始化
connection_handler = ConnectionHandler(config)

# 线程退出信号量
is_terminated = False
is_launched = False


# 接收线程
class MessageReceiver(threading.Thread):
    """
    消息接收器，从外部读取输入信息，对信息进行处理（通常是渲染gui）
    """
    def run(self):
        """
        模拟前端接收线程，负责接收消息
        """
        while not is_terminated:
            try:
                data = connection_handler.connection.recv(4096)
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
                    data += connection_handler.connection.recv(remaining)

                # 解码对象，并且将对象解析为Message实例，传递给对应的执行函数
                response_message = pickle.loads(data[4:])
                logger.debug(f'Received object from backend output: \n{response_message}')
            except socket.timeout:
                if is_terminated:
                    connection_handler.connection.close()
                    return
        # 线程退出
        connection_handler.connection.close()
        logger.info('Connection Close')


class MessageSender:
    """
    消息发送器，将前端消息发送往后端进程（通常是表单参数）
    """

    @staticmethod
    def send_str(line: str):
        """ 通过字符串的形式发送消息，消息遵循 '[操作名]<空格>[请求体]' 的格式 """
        request_message = Message.from_frontend_output(line)

        # 编码对象
        data = pickle.dumps(request_message, protocol=pickle.HIGHEST_PROTOCOL)
        length = len(data).to_bytes(4, byteorder='big')

        # 发送数据长度
        connection_handler.connection.sendall(length)
        # 发送数据
        connection_handler.connection.sendall(data)


message_receiver = MessageReceiver()


class MainCmd(cmd.Cmd):
    prompt = '> '

    def do_send(self, line):
        """ 以字符串的形式发送请求 """
        MessageSender.send_str(line)

    def do_quit(self, line):
        """ 终止程序 """
        global is_terminated
        is_terminated = True
        message_receiver.join()
        logger.info('MainCMD successfully shutdown')
        return True


def main():
    # 初始化线程
    message_receiver.start()
    MainCmd().cmdloop("Program already launched, Type 'help' for available commands.")


if __name__ == '__main__':
    main()

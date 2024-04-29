"""
简易实现的命令行操作界面，提供通过命令行操作的方式来向中间件发送消息
"""
import cmd
import socket
import pickle

from loguru import logger
from middleware_py.message import Message


__version__ = '0.0.1'
logger.info(f'Launching MainCMD program by python, current version: {__version__}')

server_host = '127.0.0.1'
server_port = 25565

logger.info(f'Connecting to MessageQueue Server on {server_host}:{server_port}')
connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connection.connect((server_host, server_port))
logger.info(f'Connect Success')


# 接收线程
def recv_():
    """
    模拟前端接收线程，负责接收消息
    """
    while True:
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
            print(f'Received object: {message}')
        except socket.error as e:
            logger.debug(f'lost connection with server')


class MainCmd(cmd.Cmd):
    prompt = '> '

    def do_send(self, line):
        """ 通过字符串的形式发送消息，消息遵循 '[操作名]<空格>[请求体]' 的格式 """
        message = Message.from_frontend_output(line)

        # 编码对象
        data = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)
        length = len(data).to_bytes(4, byteorder='big')

        # 发送数据长度
        connection.sendall(length)
        # 发送数据
        connection.sendall(data)


    def do_quit(self, line):
        """Quit the program"""
        return True


if __name__ == '__main__':
    MainCmd().cmdloop("Program already launched, Type 'help' for available commands.")

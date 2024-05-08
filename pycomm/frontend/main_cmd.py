"""
简易实现的命令行操作界面，提供通过命令行操作的方式来向中间件发送消息
"""
import cmd

from loguru import logger

from config_util import config
from pycomm.util.network_util import ClientSocketProcessor, Message


class MainCmd(cmd.Cmd):
    prompt = '> '

    def __init__(self):
        logger.info(f'Launching MainCMD program by python')
        super().__init__()
        self.processor = ClientSocketProcessor(
            config['server_host'], config['server_port'], config['server_timeout'])

    def do_send(self, line):
        """ 以字符串的形式发送请求 """
        self.processor.send(Message.loads(line))

    def do_quit(self, line):
        """ 终止程序 """
        self.processor.terminate()
        logger.info('MainCMD successfully shutdown')
        return True


if __name__ == '__main__':
    MainCmd().cmdloop("Program already launched, Type 'help' for available commands.")

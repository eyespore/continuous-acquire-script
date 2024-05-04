"""
简易实现的命令行操作界面，提供通过命令行操作的方式来向中间件发送消息
"""
import cmd

from loguru import logger

from config_util import config
from data_processor import MessageProcessor

logger.info(f'Launching MainCMD program by python')
message_processor = MessageProcessor(config['server_host'], config['server_port'], config['server_timeout'])


def when_recv(message):
    pass


class MainCmd(cmd.Cmd):
    prompt = '> '

    def do_send(self, line):
        """ 以字符串的形式发送请求 """
        message_processor.send_str(line, when_recv)

    def do_quit(self, line):
        """ 终止程序 """
        message_processor.terminate()
        message_processor.join()
        logger.info('MainCMD successfully shutdown')
        return True


def main():
    message_processor.start()  # 初始化消息转发器
    MainCmd().cmdloop("Program already launched, Type 'help' for available commands.")


if __name__ == '__main__':
    main()

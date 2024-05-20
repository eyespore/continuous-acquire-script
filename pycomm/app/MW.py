"""
Created on 2024.4.24
@author: Pineclone
@version: 0.0.1
主要是为后端提供socket连接适配，创建中间件线程接收前端数据，处理之后将数据转发到后端程序，
"""
import cmd
from loguru import logger
from .comm import ServerSocketProcessor, DMProcessor
from . import config


class Properties:
    """
    Properties配置文件类
    """
    def __init__(self, file_name):
        self.file_name = file_name

    def get_prop(self):
        try:
            pro_file = open(self.file_name, 'r', encoding='utf-8')
            properties = {}
            for line in pro_file:
                if line.find('=') > 0:
                    strs = line.replace('\n', '').split('=')
                    properties[strs[0]] = strs[1]
        except Exception as e:
            raise e
        else:
            pro_file.close()
        return properties


logger.info(f'Launching MQ process by python')
logger.debug(f'Loading backend process config, path: {config.BE_CONFIG_PATH}')
prop = Properties(config.BE_CONFIG_PATH).get_prop()
logger.debug(f'Complete loading program config')

input_pip_path = prop['input_pip_path']  # 输入管道文件
input_pip_lock = prop['input_pip_lock']  # 输入管道锁文件
output_pip_path = prop['output_pip_path']  # 输出管道文件
output_pip_lock = prop['output_pip_lock']  # 输出管道锁文件

encoding = config.LISTEN_ENCODING  # 编码格式
host = config.LISTEN_HOST  # 中间件绑定ip地址
port = config.LISTEN_PORT  # 中间件绑定端口
timeout = config.LISTEN_TIMEOUT  # 超时时间，超时后会再次检查线程状态

dm_config = {
    'timeout': timeout,
    'encoding': encoding,
    'input_pip_path': input_pip_path,
    'input_pip_lock': input_pip_lock,
    'output_pip_path': output_pip_path,
    'output_pip_lock': output_pip_lock
}


class CMD(cmd.Cmd):
    prompt = '> '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.socket_processor = None  # Socket服务端处理器
        self.dm_processor = None
        self.simpleLaunch()

    def simpleLaunch(self):
        self.socket_processor = ServerSocketProcessor(host, port, timeout, encoding)  # Socket服务端处理器
        self.dm_processor = DMProcessor(**dm_config)

        self.socket_processor.linkTo(self.dm_processor.getNode())  # 服务端请求连接到DM进程
        self.dm_processor.linkTo(self.socket_processor.getNode())  # DM进程响应连接到服务端

        self.socket_processor.launch()
        self.dm_processor.launch()

    def simpleQuit(self):
        self.socket_processor.terminate(True)
        self.dm_processor.terminate(True)

    def do_restart(self, line):
        """ 重新启动中间件 """
        self.simpleQuit()
        logger.info('Middleware successfully shutdown, starting relaunching')
        self.simpleLaunch()

    def do_quit(self, line):
        """ 关闭所有消息中间件所有接口之后退出程序 """
        self.simpleQuit()
        logger.info('Middleware successfully shutdown')
        return True

    def default(self, line):  # 默认指令
        """Default action for any command not recognized"""
        print("指令未识别，键入 'help' 来查询可用的指令.")

    @staticmethod
    def run():
        CMD().cmdloop("Successfully launch Middleware for DM Script, input 'help' for available command.")


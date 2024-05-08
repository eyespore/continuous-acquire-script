"""
Created on 2024.4.24
@author: Pineclone
@version: 0.0.1
主要是为后端提供socket连接适配，创建中间件线程接收前端数据，处理之后将数据转发到后端程序，
"""

import cmd

import yaml
from loguru import logger

from pycomm.util.network_util import ServerSocketProcessor, DMProcessor
from pycomm.util.properties import Properties

with open('./config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

logger.info(f'Launching MQ process by python')
logger.debug(f'Loading backend process config, path: {config["path"]["backend_config"]}')
prop_cfg = Properties(config['path']['backend_config']).get_prop()
logger.debug(f'Complete loading program config')

input_pip_path = prop_cfg['input_pip_path']  # 输入管道文件
input_pip_lock = prop_cfg['input_pip_lock']  # 输入管道锁文件
output_pip_path = prop_cfg['output_pip_path']  # 输出管道文件
output_pip_lock = prop_cfg['output_pip_lock']  # 输出管道锁文件

encoding = config['server']['encoding']  # 编码格式
host = config['server']['host']  # 中间件绑定ip地址
port = config['server']['port']  # 中间件绑定端口
timeout = config['server']['timeout']  # 超时时间，超时后会再次检查线程状态


class MiddlewareCMD(cmd.Cmd):
    prompt = '> '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.socket_processor = ServerSocketProcessor(host, port, timeout, encoding)  # Socket服务端处理器
        self.dm_processor = DMProcessor(timeout=timeout, encoding=encoding,  # DM处理器
                                        input_pip_path=input_pip_path, input_pip_lock=input_pip_lock,
                                        output_pip_path=output_pip_path, output_pip_lock=output_pip_lock)

        self.socket_processor.linkTo(self.dm_processor.getNode())  # 服务端请求连接到DM进程
        self.dm_processor.linkTo(self.socket_processor.getNode())  # DM进程响应连接到服务端

        self.socket_processor.launch()
        self.dm_processor.launch()

    def do_quit(self, line):
        """ 关闭所有消息中间件所有接口之后退出程序 """
        self.socket_processor.terminate(True)
        self.dm_processor.terminate(True)
        logger.info('Middleware successfully shutdown')
        return True

    def default(self, line):  # 默认指令
        """Default action for any command not recognized"""
        print("指令未识别，键入 'help' 来查询可用的指令.")


if __name__ == '__main__':
    # 启动命令行程序，避免进程退出
    MiddlewareCMD().cmdloop("Successfully launch Middleware for DM Script, input 'help' for available command.")

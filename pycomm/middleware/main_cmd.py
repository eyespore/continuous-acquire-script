"""
Created on 2024.4.24
@author: Pineclone
@version: 0.0.1
主要是为后端提供socket连接适配，创建中间件线程接收前端数据，处理之后将数据转发到后端程序，
"""

import cmd
import os
import pickle
import queue
import socket
import threading
from collections import defaultdict

from loguru import logger
import yaml

from pycomm.util.network import Message
from pycomm.util.properties import Properties

with open('./config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

logger.info(f'Launching MQ process by python')
logger.debug(f'Loading backend process config, path: {config["path"]["backend_config"]}')
prop_cfg = Properties(config['path']['backend_config']).get_prop()
logger.debug(f'Complete loading program config')

# 请求消息队列，由后端接口读取输出管道数据写入此处，由前端接口读出派发给对应前端程序
request_mq = queue.Queue()
# 响应消息队列，由前端接口会被缓存到此处，由后端接口写入输入管道中
response_mq = queue.Queue()
# 连接队列，通过connection_handler处理之后产生的连接对象会被存储在此处
connection_cache = queue.Queue()

# 编码格式
server_encoding = config['server']['encoding']
server_host = config['server']['host']  # 中间件绑定ip地址
server_port = config['server']['port']  # 中间件绑定端口
server_timeout = config['server']['timeout']  # 超时时间，超时后会再次检查线程状态


class ConnectionContext:
    """
    连接上下文管理，提供了线程安全地方式来集中管理连接，管理由socket创建的connection连接对象以及由此
    衍生出的连接处理器线程，在程序退出时上下文管理器能够负责处理所有连接处理器线程的正确退出
    """
    connection_tracker = defaultdict(dict)
    lock = threading.Lock()

    # 添加一个新的连接上下文
    def add_connection(self, **kwargs):
        self.lock.acquire()
        self.connection_tracker[kwargs['address']]['connection'] = kwargs['connection']
        self.connection_tracker[kwargs['address']]['connection_handler_thread'] = kwargs['connection_handler_thread']
        self.lock.release()

    # 移除一个连接上下文
    def rem_connection(self, address: tuple):
        self.lock.acquire()
        self.connection_tracker.pop(f'{address[0]}:{address[1]}')
        self.lock.release()

    def join_connection(self):
        for address, connection_bundle in self.connection_tracker.items():
            try:
                connection_bundle['connection_handler_thread'].join()
            except KeyError as e:
                logger.error(f'Hit Nonexistent Key : {address[0]}:{address[1]}')

    # 通过地址元组获取映射到的连接实例
    def get_connection(self, address: str):
        self.lock.acquire()
        if self.connection_tracker.get(address):
            self.lock.release()
            return self.connection_tracker[address].get('connection')
        self.lock.release()
        return None


# 连接上下文管理
conn_context = ConnectionContext()

is_terminated = False
is_launched = False


# 输入管道文件，通过输入管道文件以 [ip:port]<空格>[操作名]<空格>[请求体] 的格式写入数据
input_pip_path = prop_cfg['input_pip_path']
# 输入管道锁文件，完成写入之后移除锁，使后端读取消息，没有锁的时候不应该写入数据，直至后端进程归还锁
input_pip_lock = prop_cfg['input_pip_lock']

# 输出管道文件，输出管道以 [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符> 的格式写出数据
output_pip_path = prop_cfg['output_pip_path']
# 输出管道锁文件，如果不存在锁文件，可以直接读取消息，读取完成之后需要创建锁文件，存在锁文件的时候不应该读取输出管道消息
output_pip_lock = prop_cfg['output_pip_lock']

# 检查管道文件是否存在
if not os.path.exists(input_pip_path):
    logger.error('Unable to find pip file, check if a dm script is running')
    raise FileNotFoundError(f'{input_pip_path} pip file not found')

if not os.path.exists(output_pip_path):
    logger.error('Unable to find pip file, check if a dm script is running')
    raise FileNotFoundError(f'{output_pip_path} pip file not found')


class connection_builder(threading.Thread):
    def run(self):
        """
        创建连接对象线程，连接被创建之后会被加入connection_queue以及conn_pool当中
        """
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((server_host, server_port))
        # 设置超时时间，避免等待时间过长
        server.settimeout(server_timeout)
        server.listen()
        logger.info(f'Connection Builder launched, listening connection from {server_host}:{server_port}')

        global is_terminated
        while not is_terminated:
            try:
                connection, address = server.accept()
                logger.info(f'Accept connection from {address[0]}:{address[1]}')
                # 将连接对象添加进入连接池
                connection_cache.put((connection, address))
            except socket.timeout:
                # 如果线程已经停止运行，那么退出程序
                if is_terminated:
                    break
        # 线程退出，关闭服务器
        server.close()
        logger.debug('Middleware Server shutdown')


class backend_input_middleware(threading.Thread):
    """
    消息中间件 -> 后端输入管道
    读取request_mq消息队列获取请求消息，将消息封装成为后端可读格式，写入后端输入管道中，完成写入之后
    删除input_pip_lock锁文件，当锁文件不存在的时候不允许写入，锁文件由 后端进程 维护

    消息格式-后端输入管道 : [ip:port]<空格>[操作名]<空格>[请求体]<换行符>
    消息格式-消息中间件  : Message实例

    """
    def run(self) -> None:
        logger.debug('Backend-Input-Middleware interface launched')
        global is_terminated, server_timeout
        request_list = []
        while not is_terminated:
            try:
                # 从请求消息缓存队列获取消息并加入列表
                item: str = request_mq.get(timeout=server_timeout)
                request_list.append(item)

                # 检测锁文件是否存在
                if not os.path.exists(input_pip_lock):
                    # 锁文件不存在，不允许写入
                    continue
                else:
                    # 锁文件存在，允许写入
                    input_pip = open(input_pip_path, 'w', encoding=server_encoding)
                    try:
                        for request_message in request_list:
                            input_pip.writelines(request_message)
                            input_pip.flush()
                    # 关闭文件流
                    finally:
                        # 清空缓存列表
                        request_list.clear()
                        # 关闭文件流
                        input_pip.close()

                    # 删除锁文件，触发DM进程读消息
                    try:
                        os.remove(input_pip_lock)
                    except OSError as e:
                        logger.error(f'Unable handle deleting input_pip_lock file at {input_pip_path}: {e}')

            except queue.Empty:
                # 超时退出
                if is_terminated:
                    break
        # 线程退出
        logger.debug('Backend-Input-Middleware interface shutdown')


class backend_output_middleware(threading.Thread):
    """
    后端输出管道 -> 消息中间件
    读取后端输出管道消息，封装成为Message对象加入response_mq当中，锁文件output_pip_lock不存在的时候
    可以执行读取，读取完成之后需要手动创建锁文件，允许后端进程继续写入响应，锁文件存在的时候不允许读取，output_pip_lock
    锁文件由 中间件进程 维护

    消息格式-后端输出管道   : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
    消息格式-response_mq : [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>

    """

    def run(self) -> None:
        logger.debug('Backend-Output-Middleware interface launched')
        global is_terminated
        while not is_terminated:
            # 检查文件锁是否存在
            if not os.path.exists(output_pip_lock):
                # 锁文件不存在时可以执行读取操作
                read_pip = None
                try:
                    read_pip = open(output_pip_path, 'r', encoding=server_encoding)
                    for line in read_pip:
                        response_message = line.strip()
                        logger.debug(f"line from output pip : {response_message}")
                        # 将内容写入响应队列
                        response_mq.put(response_message)

                except FileNotFoundError as e:
                    logger.error(f'could not open pip file with given path : {output_pip_path}')
                finally:
                    if read_pip is not None:
                        read_pip.close()

                # 清空文件内容
                write_pip = open(output_pip_path, 'w', encoding=server_encoding)
                write_pip.close()

                # 重新创建锁文件
                pip_lock = open(output_pip_lock, 'w', encoding=server_encoding)
                pip_lock.close()

            # 主循环仅仅检查文件内容
            pass
        # 线程退出
        logger.debug('Frontend-Input-Middleware interface shutdown')


class frontend_output_middleware(threading.Thread):
    """
    前端进程 -> 消息中间件
    通过connection_cache缓冲池获取前端连接实例，处理实例构建处理线程，线程创建 消息中间件 和 某一个前端进程 的长连接
    长连接存在时可以维持双端数据传输，传输时使用Message实例对象作为传输格式

    消息格式-前端进程    : Message实例

    """
    def run(self):
        logger.debug('Frontend-Output-Middleware interface launched')

        # 从连接缓冲区获取连接对象
        global is_terminated
        while not is_terminated:
            try:
                # 设置超时事件，避免退出后线程阻塞
                connection, address = connection_cache.get(timeout=server_timeout)
                connection.settimeout(server_timeout)
                connection_thread = threading.Thread(target=self.handle_connection, args=(connection, address))

                # 将连接构建成上下文交由连接上下文管理
                conn_context.add_connection(address=f'{address[0]}:{address[1]}',
                                            connection=connection,
                                            connection_handler_thread=connection_thread)

                connection_thread.start()
            except queue.Empty:
                if is_terminated:
                    break
        logger.debug('Frontend-Output-Middleware interface shutdown')

    def handle_connection(self, connection, address):
        """
        连接处理线程，主要是将address中的ip地址和port信息加入消息中，封装成为 管道消息格式 ，然后加入
        request_mq当中，等待输入进程将消息写入管道文件中

        消息格式-前端进程     : Message实例
        消息格式-request_mq : [ip:port]<空格>[操作名]<空格>[请求体]<换行符> （字符串形式）

        """
        global is_terminated
        while not is_terminated:
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
                message = pickle.loads(data[4:].strip())
                # 或取当前用户ip地址，为message设置
                message.setHeader('address', f'{address[0]}:{address[1]}')
                # 将消息转化为字符串格式加入队列中
                try:
                    request_mq.put(Message.dumps(message))
                except Exception as e:
                    logger.error(f'Bad message format : {e}')

            except socket.timeout as e:
                if is_terminated:
                    connection.close()
                    # 在连接上下文中取消追踪当前连接上下文
                    conn_context.rem_connection(address)
                    logger.debug(f'Connection timeout : {address[0]}:{address[1]}')
                    return
            except AttributeError as e:
                logger.error('Cannot correctly set message due to incorrect message type')
            except ConnectionResetError as e:
                # 在连接上下文中取消追踪当前连接上下文
                conn_context.rem_connection(address)
                # logger.debug(f'远程主机强迫关闭了一个现有的连接 : {address[0]}:{address[1]}')
                logger.debug(f'Detected host force to terminating an existed connection : {address[0]}:{address[1]}')
                return

        # 用户线程退出，关闭连接
        connection.close()
        # 在连接上下文中取消追踪当前连接上下文
        conn_context.rem_connection(address)
        logger.debug(f'Connection close : {address[0]}:{address[1]}')


class frontend_input_middleware(threading.Thread):
    """
    前端响应线程，将response_mq当中已有消息取出，然后根据Message格式解析，同时获取源的ip以及端口，通过
    connection_pool获取原始连接对象，将封装好的Message返回给前端进程，前端进程通过函数接收
    """

    def run(self):
        logger.debug('Frontend-Input-Middleware interface launched')
        while not is_terminated:
            try:
                # 从请求消息缓存队列获取消息并加入列表
                item: str = response_mq.get(timeout=server_timeout)
                # 将消息转化为Message格式，然后通过连接对象发送给前端
                response_message = Message.loads(item)
                connection = conn_context.get_connection(response_message.getHeader('address'))

                if not connection:
                    continue

                data = pickle.dumps(response_message, protocol=pickle.HIGHEST_PROTOCOL)
                length = len(data).to_bytes(4, byteorder='big')

                connection.sendall(length)  # 发送数据长度
                connection.sendall(data)  # 发送数据

            except queue.Empty:
                # 超时退出
                if is_terminated:
                    break
            except KeyError as e:
                # 过程中无法找到某个connection实例，通常是实例在执行任务过程中被清除
                logger.error(f'Hit Nonexistent Key Exception: {e}')
                continue

        # 线程退出
        logger.debug('Frontend-Input-Middleware interface shutdown')


class middleware_cmd(cmd.Cmd):
    """
    命令行界面构建
    提供简单的指令，用于对消息中间件程序进行流程控制
    """
    prompt = '> '

    def __init__(self):
        cmd.Cmd.__init__(self)
        self.conn_builder = connection_builder()  # 连接处理器

        self.interface_1 = frontend_output_middleware()  # 前端 -> 中间件
        self.interface_2 = backend_input_middleware()  # 中间件 -> 后端
        self.interface_3 = backend_output_middleware()  # 后端 -> 中间件
        self.interface_4 = frontend_input_middleware()  # 中间件 -> 前端

        """Launch MessageQueue program"""
        global is_launched
        if is_launched:
            logger.info('Middleware has already launched')
            return

        # 启动接口
        is_launched = True
        self.conn_builder.start()
        self.interface_1.start()
        self.interface_2.start()
        self.interface_3.start()
        self.interface_4.start()

    def do_quit(self, line):
        """ 关闭所有消息中间件所有接口之后退出程序 """
        # 触发关闭事件
        global is_terminated, server_timeout
        is_terminated = True
        # 为连接设置超时时间

        # 等待线程全部退出
        logger.info('Waiting middleware shutdown...')
        self.conn_builder.join()
        self.interface_1.join()
        self.interface_2.join()
        self.interface_3.join()
        self.interface_4.join()

        # 等待所有连接线程退出
        conn_context.join_connection()

        logger.info('Middleware successfully shutdown')
        return True

    # 默认指令
    def default(self, line):
        """Default action for any command not recognized"""
        print("指令未识别，键入 'help' 来查询可用的指令.")


if __name__ == '__main__':
    # 启动命令行程序，避免进程退出
    middleware_cmd().cmdloop("Successfully launch Middleware for DM Script, input 'help' for available command.")

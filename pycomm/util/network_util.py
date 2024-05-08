import os
import queue
import socket
import threading
import uuid
from typing import Callable, Dict, List

from loguru import logger


class Message:
    """
    消息封装类，数据层对象
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
        return self.body.get(str(key))

    def set(self, key, val) -> None:
        self.body[str(key)] = str(val)

    def setHeader(self, key, val):
        self.head[str(key)] = str(val)

    def getHeader(self, key):
        return self.head.get(str(key))

    def getBody(self) -> Dict[str, str]:
        return self.body

    def setBody(self, body: Dict[str, str]) -> None:
        self.body = body

    @staticmethod
    def dumps(msg) -> str:
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
        try:
            msg = Message()  # 创建消息对象
            head_n_body = line.strip().split(Message.message_seperator)
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


class PipComponent(threading.Thread):
    input_buffer = None  # 消息缓冲
    output_buffer = None  # 消息缓冲

    def __init__(self, timeout: float = 3):
        threading.Thread.__init__(self)
        self.is_terminated = False
        self.timeout = timeout
        self.input_buffer = queue.Queue()  # 消息缓冲
        self.output_buffer = None  # 消息缓冲

    def onLaunching(self) -> bool:
        return True

    def preHandling(self, message: Message) -> bool:
        return True

    def onHandling(self, message: Message):
        pass

    def postHandling(self, message: Message) -> bool:
        return True

    def onTerminating(self) -> bool:
        return True

    def onClosing(self, reason: str) -> None:
        pass

    def postMessage(self, message: Message):
        self.input_buffer.put(message)

    def terminate(self) -> None:
        if not self.onTerminating():
            return
        self.is_terminated = True

    def link(self, dst):
        if isinstance(dst, queue.Queue):
            self.output_buffer = dst
        elif isinstance(dst, PipComponent):
            logger.debug(f'linked {self} to {dst}')
            self.output_buffer = dst.input_buffer

    def run(self):
        if not self.onLaunching():
            return

        reason = 'normal'
        while not self.is_terminated:
            try:
                message: Message = self.input_buffer.get(timeout=self.timeout)
                if not self.preHandling(message):  # 过滤消息
                    continue

                self.onHandling(message)  # 处理消息

                if not self.postHandling(message):  # 后置处理消息
                    continue

                if self.output_buffer:  # 将消息写入输出区
                    self.output_buffer.put(message)

            except queue.Empty:
                if self.is_terminated:  # 超时退出
                    reason = 'timeout'
                    break
        self.onClosing(reason)


class ConnectionProxy(threading.Thread):
    def __init__(self, connection: socket, timeout: float = 3.0, encoding='utf-8'):
        super().__init__()
        self.is_terminated = True
        self.encoding = encoding
        self.connection = connection
        self.connection.settimeout(timeout)  # 设置超时时间
        self.pre_sending = lambda message: True  # 消息发送前
        self.post_sending = lambda message: None  # 消息发送后
        self.pre_receiving = lambda message: True  # 消息接收前
        self.post_receiving = lambda message: None  # 消息接收后
        self.on_receiving = lambda message: None  # 接收消息
        self.on_terminating = lambda: True  # 代理关闭时
        self.on_closing = lambda reason: None  # 连接关闭时
        self.on_launching = lambda: True  # 代理对象启动时

    def onLaunching(self, func: Callable[[], bool]):
        """
        线程启动事件
        代理对象被启动时会调用该方法
        :param func: 事件触发时会调用该函数，函数返回真时，线程才能够正常启动
        """
        self.on_launching = func

    def preSending(self, func: Callable[[Message], bool]):
        """
        消息预发送事件
        send方法被调用时，会在实际通过socket发送消息之前触发该事件
        :param func: 事件触发时会调用该函数，函数返回真时，消息能够正常发送，否则消息会被拦截
        """
        self.pre_sending = func

    def postSending(self, func: Callable[[Message], None]):
        """
        消息已发送事件
        send方法被调用时，消息已经完成发送之后触发该事件
        :param func: 事件触发时会调用该函数
        """
        self.post_sending = func

    def preReceiving(self, func: Callable[[Message], bool]):
        """
        消息预接收事件
        当代理对象接收到消息时会触发该事件
        :param func: 事件触发时会调用该函数，函数返回值决定消息是否会被处理
        """
        self.pre_receiving = func

    def onReceiving(self, func: Callable[[Message], None]):
        """
        消息处理事件
        代理对象接收到消息时会调用该方法用于处理消息
        """
        self.on_receiving = func

    def postReceiving(self, func: Callable[[Message], None]):
        """
        消息已处理事件
        消息处理完成后会调用该方法对处理完的消息再次进行后处理
        """
        self.post_receiving = func

    def onTerminating(self, func: Callable[[], bool]):
        """
        代理对象被关闭时会触发该事件
        :param func: 函数的返回值决定代理对象是否会被关闭
        """
        self.on_terminating = func

    def onClosing(self, func: Callable[[str], None]):
        """
        代理对象关闭事件
        :param func: 代理对象退出时（主要是连接关闭时）该方法会被调用
        """
        self.on_closing = func

    def send(self, message: Message) -> None:
        """
        直接发送消息实例，消息回传之后会执行回调函数
        :param message: message实例
        """
        if self.is_terminated:
            logger.error('Proxy has already terminated')
            return

        if not message:
            logger.error('A NULL message cannot be sent')
            return

        if not self.pre_sending(message):  # 消息预发送
            return

        data = Message.dumps(message).encode(encoding=self.encoding)  # 编码对象
        length = len(data).to_bytes(4, byteorder='big')
        self.connection.sendall(length)  # 发送数据长度
        self.connection.sendall(data)  # 发送数据
        self.post_sending(message)  # 消息已发送

    def run(self):  # 消息接受线程
        if not self.on_launching():
            return

        self.is_terminated = False
        closing_reason = 'normal'
        while not self.is_terminated:
            try:
                length_prefix = self.connection.recv(4)
                if not length_prefix:
                    break
                length = int.from_bytes(length_prefix, byteorder='big')  # 获取数据长度
                message_data = self.connection.recv(length)  # 接收指定长度数据
                message = Message.loads(message_data.decode(encoding=self.encoding))  # 解码

                if not self.pre_receiving(message):  # 消息预接收
                    return

                self.on_receiving(message)  # 接收消息
                self.post_receiving(message)  # 消息已接收

            except socket.timeout:
                if self.is_terminated:
                    closing_reason = 'Connection timed out'
                    break
            except ConnectionResetError as e:
                closing_reason = 'Detected connection reset'
                break

        self.connection.close()  # 线程退出
        self.on_closing(closing_reason)  # 线程退出

    def terminate(self):  # 关闭代理
        if not self.on_terminating():
            return

        self.is_terminated = True


class Processor:  # 处理器门户
    def launch(self):
        pass

    def terminate(self, synchronized: bool = False):
        pass


class ClientSocketProcessor(Processor):
    def __init__(self, host: str, port: int, timout: float = 3, encoding='utf-8') -> None:
        self.callbacks: Dict[str, Callable[[Message], None]] = {}  # 回调映射，uuid->callback
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        logger.info(f'Connecting to MessageQueue Server on {host}:{port}')
        connection.connect((host, port))
        logger.info(f'Connection established')

        self.proxy = ConnectionProxy(connection, timout, encoding)
        self.proxy.onReceiving(self.onReceiving)  # 执行回调
        self.proxy.onLaunching(ClientSocketProcessor.launchingProxy)
        self.proxy.onClosing(lambda reason: logger.info(f'ConnectionProxy Closed: {reason}'))

    def sendAsync(self, message, callback: Callable[[Message], None]) -> None:
        """
        直接发送消息实例，消息回传之后会执行回调函数
        :param message: message实例
        :param callback: 回调函数，在请求响应时会被调用
        """
        callback_id = str(uuid.uuid4())
        message.setHeader('callback_id', callback_id)  # 注册回调
        self.callbacks[callback_id] = callback
        self.proxy.send(message)  # 发送消息

    @staticmethod
    def launchingProxy() -> bool:
        logger.info('ConnectionProxy launched')
        return True

    def launch(self):  # 启动客户端处理器
        self.proxy.start()

    def onReceiving(self, message: Message) -> None:
        callback_id = message.getHeader('callback_id')
        callback = self.callbacks.get(callback_id)
        if callback:
            callback(message)

    def terminate(self, synchronized: bool = False):
        self.proxy.terminate()
        if synchronized:
            self.proxy.join()


class ServerSocketProcessor(Processor):
    def __init__(self, host: str, port: int, timeout: float = 3, encoding='utf-8'):
        self.host = host  # 服务器绑定主机
        self.port = port  # 服务器绑定端口
        self.timeout = timeout  # 超时时间
        self.encoding = encoding  # 编解码字符集

        self.connection_builder = self.ConnectionBuilder(self)  # 连接构建器
        self.connection_context = self.ConnectionContext(self)  # 连接上下文
        self.request_pipline: PipComponent = self.RequestPipline(self)  # 请求管道
        self.response_pipline: PipComponent = self.ResponsePipline(self)  # 响应管道

    def getNode(self) -> PipComponent:  # 输入管道
        return self.response_pipline

    def linkTo(self, pip_component: PipComponent):
        self.request_pipline.link(pip_component)

    def launch(self):  # 启动服务端处理器
        self.connection_builder.start()
        self.request_pipline.start()
        self.response_pipline.start()

    def terminate(self, synchronized=False):  # 终止服务端
        self.connection_builder.terminate()
        self.connection_context.terminate()
        self.request_pipline.terminate()
        self.response_pipline.terminate()

        if synchronized:
            self.connection_builder.join()
            logger.debug(f'Connection Builder terminated')
            self.connection_context.join()
            logger.debug(f'Connection Context terminated')
            self.request_pipline.join()
            logger.debug(f'Request PipComponent terminated')
            self.response_pipline.join()
            logger.debug(f'Response PipComponent terminated')

    class ConnectionBuilder(threading.Thread):
        """
        连接构建器，监听客户端连接，客户端连接后创建连接上下文对象
        """

        def __init__(self, app_context):
            super().__init__()
            self.is_terminated = False
            self.app_context = app_context  # 应用程序上下文
            self.server: socket = None

            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.bind((self.app_context.host, self.app_context.port))
            self.server.settimeout(self.app_context.timeout)  # 设置超时时间，避免等待时间过长

        def run(self):
            self.server.listen()
            logger.info(f'Connection Builder launched, listening connection '
                        f'from {self.app_context.host}:{self.app_context.port}')

            while not self.is_terminated:
                try:
                    connection, address = self.server.accept()
                    logger.info(f'Accept connection from {address[0]}:{address[1]}')
                    # 构建上下文对象
                    self.app_context.connection_context.addConnection(
                        address, connection, self.app_context.timeout, self.app_context.encoding)

                except socket.timeout:
                    if self.is_terminated:  # 如果线程已经停止运行，那么退出程序
                        break
            # 线程退出，关闭服务器
            self.server.close()

        def terminate(self):
            self.is_terminated = True

    class ConnectionContext:
        def __init__(self, app_context):
            self.lock = threading.RLock()  # 全局锁
            self.app_context = app_context
            self.connection_context: Dict[str, ConnectionProxy] = {}

        def addConnection(self, address, connection: socket, timeout=3, encoding='utf-8'):
            proxy = ConnectionProxy(connection, timeout, encoding)  # 创建代理

            def onClosing(reason: str) -> None:  # 构建代理对象
                logger.info(f'Connection {str(address)} closed: {reason}')
                self.remConnection(address)

            def onReceiving(message: Message) -> None:
                message.setHeader('address', address)  # 设置头部信息
                self.app_context.request_pipline.postMessage(message)  # 提交请求到输出管道

            proxy.onClosing(onClosing)  # 线程退出时需要退出上下文
            proxy.onReceiving(onReceiving)  # 代理会将接收到的消息提交给消息队列

            with self.lock:
                self.connection_context[str(address)] = proxy
                proxy.start()  # 启动线程

        def getConnection(self, address) -> ConnectionProxy or None:
            proxy: ConnectionProxy = self.connection_context.get(str(address))
            return proxy

        def remConnection(self, address) -> None:
            with self.lock:
                try:
                    self.connection_context.pop(str(address))
                except KeyError as e:
                    logger.error(f'Hit nonexistent key: {e}')

        def terminate(self) -> None:
            with self.lock:
                for address, proxy in self.connection_context.items():
                    # 若是强制关闭中间件，此时关闭连接对象时将连接对象从容器剔除会发生死锁
                    proxy.onClosing(lambda reason: logger.info(f'Connection {str(address)} closed: {reason}'))
                    proxy.terminate()

        def join(self):
            with self.lock:
                for address, proxy in self.connection_context.items():
                    proxy.join()

    class RequestPipline(PipComponent):
        def __init__(self, app_context):
            super().__init__(app_context.timeout)
            self.app_context = app_context

    class ResponsePipline(PipComponent):
        def __init__(self, app_context):
            super().__init__(app_context.timeout)
            self.is_terminated = False
            self.app_context = app_context

        def onHandling(self, message):
            address = message.getHeader('address')
            if not address:  # 地址不存在
                logger.error(f'\'address\' cannot be found at {message}')
                return

            proxy = self.app_context.connection_context.getConnection(address)  # 通过连接发送请求
            if not proxy:  # 连接不存在
                logger.error(f'Hit nonexistent connection for {address}')
                return

            proxy.send(message)  # 响应消息


class DMProcessor(Processor):
    def __init__(self, **kwargs):
        self.timeout = kwargs['timeout']
        self.encoding = kwargs['encoding']

        self.input_pip_path = kwargs['input_pip_path']
        self.input_pip_lock = kwargs['input_pip_lock']
        self.output_pip_path = kwargs['output_pip_path']
        self.output_pip_lock = kwargs['output_pip_lock']

        # 检查管道文件是否存在
        if not os.path.exists(self.input_pip_path):
            logger.error('Unable to find pip file, check if a dm script is running')
            raise FileNotFoundError(f'{self.input_pip_path} pip file not found')

        if not os.path.exists(self.output_pip_path):
            logger.error('Unable to find pip file, check if a dm script is running')
            raise FileNotFoundError(f'{self.output_pip_path} pip file not found')

        self.pip_writer = self.PipFileWriter(self)
        self.pip_reader = self.PipFileReader(self)

    def getNode(self) -> PipComponent:
        return self.pip_writer

    def linkTo(self, pip_component: PipComponent):
        self.pip_reader.linkTo(pip_component)

    def launch(self):
        self.pip_writer.start()
        self.pip_reader.start()

    def terminate(self, synchronized: bool = False):
        self.pip_writer.terminate()
        self.pip_reader.terminate()
        if synchronized:
            self.pip_writer.join()
            self.pip_reader.join()

    class PipFileWriter(PipComponent):
        def __init__(self, app_context):
            super().__init__(app_context.timeout)
            self.app_context = app_context
            self.request_cache: List[Message] = []

        def onClosing(self, reason: str) -> None:
            logger.debug(f'PipFileWriter shutdown: {reason}')

        def onHandling(self, request: Message) -> None:
            self.request_cache.append(request)  # 将读取的消息加入缓存
            if not os.path.exists(self.app_context.input_pip_lock):  # 锁文件不存在，不允许写入
                return

            input_pip = open(self.app_context.input_pip_path, 'w', encoding=self.app_context.encoding)  # 锁文件存在，允许写入
            try:
                for cache in self.request_cache:
                    input_pip.writelines(Message.dumps(cache))
                    input_pip.flush()
            finally:
                self.request_cache.clear()  # 清空缓存列表
                input_pip.close()  # 关闭文件流

            try:  # 删除锁文件，触发DM进程读消息
                os.remove(self.app_context.input_pip_lock)
            except OSError as e:
                logger.error(f'Unable handle deleting input_pip_lock file at {self.app_context.input_pip_path}: {e}')

    class PipFileReader(threading.Thread):
        """
        后端输出管道 -> 消息中间件
        锁文件output_pip_lock不存在的时候可以读取，读取完成之后需要手动创建锁文件，允许后端进程继续写入响应，
        锁文件存在的时候不允许读取，output_pip_lock锁文件由 中间件进程 维护
        """

        def __init__(self, app_context):
            super().__init__()
            self.is_terminated = False
            self.app_context = app_context
            self.next_node = None

        def linkTo(self, node: PipComponent):  # 连接输出管道
            self.next_node = node

        def terminate(self):
            self.is_terminated = True

        def onClosing(self, reason):
            logger.debug(f'PipFileReader shutdown: {reason}')

        def run(self) -> None:
            while not self.is_terminated:
                if not os.path.exists(self.app_context.output_pip_lock):  # 锁文件不存在时可以执行读取操作
                    read_pip = None
                    try:
                        read_pip = open(self.app_context.output_pip_path, 'r', encoding=self.app_context.encoding)
                        for line in read_pip:
                            message = Message.loads(line.strip())
                            logger.debug(f"line from output pip : {message}")
                            if self.next_node:
                                self.next_node.postMessage(message)  # 将内容写入响应队列

                    except FileNotFoundError as e:
                        logger.error(f'could not open pip file with given path : {self.app_context.output_pip_path}')
                    finally:
                        if read_pip is not None:
                            read_pip.close()
                    write_pip = open(self.app_context.output_pip_path, 'w', encoding=self.app_context.encoding)
                    write_pip.close()  # 清空文件内容

                    pip_lock = open(self.app_context.output_pip_lock, 'w', encoding=self.app_context.encoding)
                    pip_lock.close()  # 重新创建锁文件
                pass  # 主循环仅仅检查文件内容
            # 线程退出
            self.onClosing('normal')


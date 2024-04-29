// $BACKGROUND$
// DM软件脚本执行线程
// 日志类简单实现
class Logger : object
{
    string name

    object init(object self, string name_)
    {
        name = name_
        return self
    }

    void info(object self, number line, string msg)
    {
        Result("\n" + GetTime(1) + "| INFO     |<" + name + ">:" + line + " - " + msg)
    }

    void warn(object self, number line, string msg)
    {
        Result("\n" + GetTime(1) + "| WARN     |<" + name + ">:" + line + " - " + msg)
    }

    void debug(object self, number line, string msg)
    {
        Result("\n" + GetTime(1) + "| DEBUG    |<" + name + ">:" + line + " - " + msg)
    }
}

Class TGFacade : object
{
    taggroup tg

    object init(object self, taggroup tg_)
    {
        tg = tg_
        return self
    }

    string get(object self, string key)
{
    string value
        tg.TagGroupGetTagAsString(key, value)
        return value
    }
}

ClearResults()
Result(GetTime(1) + "| DEBUG    |<main>:34 - Launching DM Script Process")

object logger = alloc(Logger).init("main")  // 日志
taggroup config_tg = NewTagGroup()  // 配置
object config = alloc(TGFacade).init(config_tg)  // 配置文件门户

// 加载全局配置配置文件
void initConfiguration() 
{
    string ROOT_DIR = "D:\\Desktop\\Note\\Python\\Python_Projects\\continuous_acquire-main\\backend"
    string CONFIG_PATH = ROOT_DIR + "\\config.properties"

    if ( ! DoesFileExist(CONFIG_PATH) )
        Throw( "Cannot Found Config File" )

    number config_file = OpenFileForReading(CONFIG_PATH)
    logger.debug(47, "Loading config, properties config path: " + CONFIG_PATH)
    string line
    try {
        while (1) {
            ReadFileLine( config_file, line )
            if (line == "")
                // 读取完成后退出 
                break
                    
            // 58为"#"ASCII码值
            number pos = line.find(chr(35))
            if (pos != -1) continue

            // 58为"="ASCII码值
            pos = line.find(chr(61))
            // 如果格式错误，抛出异常
            if (pos <= 0) Throw("Unsupported config format at: " + line)

            string key = line.left(pos)
            string value = line.right(line.len() - pos - 1)

            pos = value.find("\n")
            if (pos != -1) {
                // 存在换行符，将换行符去除
                value = value.left(pos)
            }
                
            config_tg.TagGroupSetTagAsString(key, value)
        }
            
    } recover {
        // 不论是否抛出异常，关闭文件流
        CloseFile(config_file)
    }
}

initConfiguration()

// 请求消息队列
object request_mq = NewMessageQueue()
// 响应消息队列
object response_mq = NewMessageQueue()
// 线程注册队列
object thread_register_queue = NewMessageQueue()

// ===========================================================================
// 消息对象类，请求消息通过输入线程会被逐条封装成为任务实例，压入消息队列中
// 请求消息数据格式: [ip:port]<空格>[操作名]<空格>[请求体]<换行符>
// 响应消息数据格式: [ip:port]<空格>[操作名]<空格>[返回码]<空格>[响应体]<换行符>
// ===========================================================================
class Message : object
{
    string address  // ipv4地址
    number port  // 端口
    number code  // 返回码
    string name  // 操作名
    string body  // 数据体

    Message(object self)
    {
        // 初始化返回码
        code = -1
    }

    void setAddress(object self, string address_)
    {
        address = address_
    }

    void setPort(object self, number port_)
    {
        port = port_
    }

    void setName(object self, string name_)
    {
        name = name_
    }

    void setBody(object self, string body_)
    {
        body = body_
    }

    void setCode(object self, number code_)
    {
        code = code_
    }

    number getPort(object self)
    {
        return port
    }

    string getAddress(object self)
    {
        return address
    }

    string getName(object self)
    {
        return name
    }

    string getBody(object self)
    {
        return body
    }

    string toString(object self)
    {
        if (code != -1)
        {
            return address + ":" + port + " " + name + " " + code + " " + body
        }
        return address + ":" + port + " " + name + " " + body
    }
}

// 线程管理器注册事件
class register_msg: object {
	string option
	
	object init(object self, string option_) {
		option = option_
		return self
	}
	
	string get_option(object self) {
		return option
	}

}

// ===========================================================================
// 线程管理器，管理线程注册
// ===========================================================================
class ThreadManager : thread
{
    number current_thread_num
    object inc_msg
    object dec_msg
    
    object Init(object self)
    {
        // 初始化注册事件
		inc_msg = alloc(register_msg).Init("increase")
		dec_msg = alloc(register_msg).Init("decrease")
        current_thread_num = 0
        return self
    }

    void RunThread( object self ) 
    {
		while (1) {
		    object option = thread_register_queue.WaitOnMessage(2, null)
            if (option.ScriptObjectIsValid())
            {
			    string opt = option.get_option()
                if (opt == "increase") {
                    current_thread_num ++
                } 
                else if (opt == "decrease") 
                {
                    current_thread_num --
			    }
			}
		}
    }

    number increase(object self)
    {
        thread_register_queue.PostMessage(inc_msg)
    }

    number decrease(object self)
    {
        thread_register_queue.PostMessage(dec_msg)
    }

    number count_thread_num(object self)
    {
        return current_thread_num
    }
}

// 线程管理器
object thread_manager = alloc(ThreadManager).Init()

// ===========================================================================
// 输入线程，负责创建和销毁输入管道文件，启动后定时从管道文件数据拉取数据到内存当中，
// 每次完成拉取之后会清空管道内容，解析读取数据，封装成为任务对象存入任务队列中
// ===========================================================================
class InputThread : thread
{

    number is_terminated  // 是否终止线程 
    string input_pip_path  // 输入管道路径
    string input_pip_lock  // 输入管道锁

    object request_message_prototype  // 请求消息原型

    object init(object self)
    {
        // 初始化属性
        is_terminated = 0
        input_pip_path = config.get("input_pip_path")
        input_pip_lock = config.get("input_pip_lock")

        // 用于快速创建消息对象
        request_message_prototype = alloc(Message)

        return self
    }

    // 解析字符串，将字符串按空格分隔，组成taglist并返回
    TagGroup parseLine(object self, string inputString)
    {
        // initialize a tag list to store parsing results
        TagGroup tgWordList = NewTagList();

        // 32为空格符在ASCII字符集中的码值
        // 通过空格将消息切割称为3段即可返回
        try
        {
            for (number i = 0; i < 3; i++)
            {
                if (i == 2)
                {
                    tgWordList.TagGroupInsertTagAsString(tgWordList.TagGroupCountTags(), inputString);
                }
                else
                {
                    number pos = inputString.find(chr(32));
                    string str = inputString.left(pos);
                    tgWordList.TagGroupInsertTagAsString(tgWordList.TagGroupCountTags(), str);
                    inputString = inputString.right(inputString.len() - pos - 1);
                }
            }
        }
        catch
        {
            Throw("Unsupported request message format")
            break
        }
        return tgWordList;
    };

    // 消息转换方法，将单行消息封装成为request_message
    object ConvertLine2Request(object self, string line)
    {
        // 消息格式: 127.0.0.1:25565 acquireImg x_bin: 18
        // 解析字符串
        TagGroup str_list = self.parseLine(line)
        number pos  // 字符串索引

        string str_1  // 地址和端口
        string str_2  // 操作名
        string str_3  // 请求体
        str_list.TagGroupGetIndexedTagAsString(0, str_1)
        str_list.TagGroupGetIndexedTagAsString(1, str_2)
        str_list.TagGroupGetIndexedTagAsString(2, str_3)

        pos = str_1.find(chr(58))

        string address = str_1.left(pos)  // 地址
        number port = str_1.right(str_1.len() - pos - 1).val()  // 端口
        string name = str_2  // 操作名
        string body = str_3  // 请求体

        // 以原型模式构建任务实例RequestMessage
        object request_message = request_message_prototype.ScriptObjectClone()
        request_message.setAddress(address)
        request_message.setPort(port)
        request_message.setName(name)
        request_message.setBody(body)
        return request_message
    }

    void RunThread(object self)
    {
        number encoding = 0  // 系统默认字符集
        number input_pip  // 输入管道文件句柄
        object input_pip_stream = NULL  // 输入管道流
        number input_pip_read_interval = config.get("input_pip_read_interval").val()  // 输入管道读线程读取间隔

        // 创建输入管道文件
        if (DoesFileExist(input_pip_path))
            DeleteFile(input_pip_path)
        CreateFile(input_pip_path)

        // 创建输入管道锁文件
        if (DoesFileExist(input_pip_lock))
            DeleteFile(input_pip_lock)
        CreateFile(input_pip_lock)

        // 注册线程
        thread_manager.increase()
        Logger.debug(352, "InputThread done registered")

        // 初始化线程状态量
        is_terminated = 0

        // 消息线程主循环
        while (!is_terminated)
        {
            // 降低读取管道的频率，避免造成异常
            sleep(input_pip_read_interval)
            if (!DoesFileExist(input_pip_lock))
            {
                // 如果锁文件被删除，那么读取管道消息
                input_pip_stream = NULL

                // 获取管道输入输出流
                while (input_pip_stream == NULL)
                {
                    try
                    {
                        input_pip = OpenFileForReadingAndWriting(input_pip_path)
                        input_pip_stream = NewStreamFromFileReference(input_pip, 1)
                    }
                    catch
                    {
                        Logger.debug(313, "Cannot create file stream, retry creating...")
                        // 无法获取输入流，通常是由于外部写入数据造成
                        sleep(0.5)
                        break
                    }

                    result ("is_terminate : " + is_terminated)
                    if (is_terminated) break
                }

                // 如果此时仍旧没有获取输入流，关闭文件流，并且退出主循环
                if (input_pip_stream == NULL) 
                {
                    CloseFile(input_pip)
                    break
                }

                // 读取输入管道数据
                string line
                while (input_pip_stream.StreamReadTextLine(encoding, line))
                {
                    try
                    {
                        // 格式不正确时能够正确处理异常情况
                        object request_message = self.ConvertLine2Request(line)
                        logger.debug(414, "InputThread: Accepted message : [" + request_message.toString() + "]")
                        // 将消息提交到队列
                        request_mq.PostMessage(request_message)
                    }
                    catch
                    {
                        break
                        continue
                    }
                }

                // 将管道文件内容清空
                input_pip_stream.StreamSetSize(0)
                // 关闭管道文件输入流，并且等待间隔
                CloseFile(input_pip)
                // 重新创建锁文件，避免循环读取文件内容
                // result(input_pip_lock)
                CreateFile(input_pip_lock)
            }
        }

        // 主循环结束，删除管道文件
        Logger.debug(359, "InputThread: InputThread terminating, delete dm_in.pip file...")
        if (DoesFileExist(input_pip_path))
            DeleteFile(input_pip_path)

        // 删除锁文件
        Logger.debug(364, "InputThread: InputThread terminating, delete dm_in.lock file...")
        if (DoesFileExist(input_pip_lock))
            DeleteFile(input_pip_lock)

        // 注销线程
        thread_manager.decrease()
        Logger.debug(327, "InputThread: InputThread terminated")
    }

    void terminate(object self)
    {
        is_terminated = 1
    }
}


// ===========================================================================
// DM任务派发器，封装了请求消息，通过这个类来将操作派发到某个具体的功能上
// ===========================================================================
class DMTaskDispatcher
{
    object request_message

    void setRequestMessage(object self, object request_message_)
    {
        request_message = request_message_
    }

    // TODO: 添加功能方法 
    // ================== 功能定义 ======================
    // 未找到资源
    void NotFound(object self)
    {
        // 处理消息
        request_message.setBody("Unable accessing target resources")
        request_message.setCode(404)
        response_mq.PostMessage(request_message)
    }

}

// ===========================================================================
// 任务线程，和输入流读取线程之间使用request_mq进行通讯，输入流读取线程负责循环读取
// 输入管道数据，并且将数据封装成为message，压入request_mq队列，任务线程循环提取
// request_mq队列，提取message进行处理，产生responses_message压入
// ===========================================================================
class TaskThread : thread
{

    number is_terminated  // 是否终止线程 
    object response_message_prototype  // 响应消息原型
    object dm_task_dispatcher  // 任务派发器

    object init(object self)
    {
        is_terminated = 0
        response_message_prototype = alloc(Message)
        dm_task_dispatcher = alloc(DMTaskDispatcher)
        return self
    }

    void RunThread(object self)
    {

        // 注册线程
        thread_manager.increase()
        Logger.debug(510, "TaskThread done registered")

        // 初始化线程状态量
        is_terminated = 0

        while (!is_terminated)
        {
            object request_message = request_mq.WaitOnMessage(2, null)
            // 检查合法性
            if (request_message.ScriptObjectIsValid())
            {
                logger.debug(518, "TaskThread: Handle message from InputThread : [" + request_message.toString() + "]")

                // 获取操作名，将数据映射到具体的路由上
                try
                {
                    dm_task_dispatcher.setRequestMessage(request_message)
                    string name = request_message.getName()
                    number task_id = AddMainThreadSingleTask(dm_task_dispatcher, name, 0)
                }
                catch
                {
                    // 如果没有找到操作名，引导至NotFound
                    Logger.debug(377, "TaskThread: Unsupported operation name, lead to NotFound")
                    number task_id = AddMainThreadSingleTask(dm_task_dispatcher, "NotFound", 0)
                    break
                }
            }
        }

        // 主循环结束，退出循环
        Logger.debug(384, "TaskThread: TaskThread terminating...")

        // 注销线程
        thread_manager.decrease()
        Logger.debug(385, "TaskThread: TaskThread terminated")
    }

    void terminate(object self)
    {
        is_terminated = 1
    }
}


// ===========================================================================
// 输出线程，和任务线程之间通过response_mq进行通讯，任务线程将任务处理完成后，响应
// 消息会被提交给response_mq，输出线程通过其获取响应，写入输出管道中
// ===========================================================================
class OutputThread : thread
{
    number is_terminated  // 是否终止线程 
    string output_pip_path  // 输出管道路径
    string output_pip_lock  // 输出管道锁

    TagGroup response_message_cache_prototype  // 写出消息缓存原型
    TagGroup response_message_cache  // 写出消息缓存

    object init(object self)
    {
        // 初始化属性
        is_terminated = 0
        output_pip_path = config.get("output_pip_path")
        output_pip_lock = config.get("output_pip_lock")

        response_message_cache_prototype = NewTagList()
        response_message_cache = response_message_cache_prototype.TagGroupClone()

        return self
    }

    void RunThread(object self)
    {
        // 创建输出管道文件
        if (DoesFileExist(output_pip_path))
            DeleteFile(output_pip_path)
        CreateFile(output_pip_path)

        // 创建输出锁文件
        if (DoesFileExist(output_pip_lock))
            DeleteFile(output_pip_lock)
        CreateFile(output_pip_lock)

        // 注册线程
        thread_manager.increase()
        Logger.debug(607, "OutputThread done registered")

        // 初始化线程状态量
        is_terminated = 0

        // 提取响应并且写入输出文件当中
        while (!is_terminated)
        {
            object response_message = response_mq.WaitOnMessage(2, null)
            // 检查合法性
            if (response_message.ScriptObjectIsValid())
            {
                // 将消息加载到缓存
                logger.debug(458, "OutputThread: Caching response message : [" + response_message.toString() + "]")
                response_message_cache.TagGroupInsertTagAsString(response_message_cache.TagGroupCountTags(), response_message.toString());
            }

            // 响应消息队列缓存数量
            number response_message_count = response_message_cache.TagGroupCountTags()
            // 是否存在锁文件，仅仅在锁文件存在时支持写出
            number lock_exist = DoesFileExist(output_pip_lock)

            if (response_message_count > 0 && lock_exist)
            {
                // 如果缓存区存在响应数据，将缓冲区响应消息写入文件
                number output_pip
                object output_pip_stream
                // 获取输出管道文件句柄
                while (1)
                {
                    try
                    {
                        output_pip = OpenFileForWriting(output_pip_path)
                        output_pip_stream = NewStreamFromFileReference(output_pip, 1)
                        output_pip_stream.StreamSetPos(2, 0)  // 将文件指针偏移到文件末尾，执行追加写入
                        break
                    }
                    catch
                    {
                        Logger.debug(451, "Fail on acquiring output pip file handler, retrying acquiring...")
                        // 重试机制
                        sleep(0.5)
                    }
                }

                for (number i = 0; i < response_message_count; i++)
                {
                    string response_message_str
                    response_message_cache.TagGroupGetIndexedTagAsString(i, response_message_str)
                    logger.debug(488, "OutputThread: Write response message to File : [" + response_message_str + "]")
                    // WriteFile(output_pip, response_message_str + "\n")
                    output_pip_stream.StreamWriteAsText(0, response_message_str + "\n")
                }

                // 清空缓冲区 
                response_message_cache = response_message_cache_prototype.TagGroupClone()
                // 关闭文件输入流
                output_pip.CloseFile()
                // 删除锁文件，触发外部读取信号，完成之后由外部重新上锁
                if (DoesFileExist(output_pip_lock))
                    DeleteFile(output_pip_lock)
            }
        }

        // 主循环结束，删除管道文件
        Logger.debug(458, "OutputThread: OutputThread terminating, delete dm_out.pip file...")
        if (DoesFileExist(output_pip_path))
            DeleteFile(output_pip_path)

        // 删除锁文件
        Logger.debug(541, "OutputThread: OutputThread terminating, delete dm_out.lock file...")
        if (DoesFileExist(output_pip_lock))
            DeleteFile(output_pip_lock)

        // 注销线程
        thread_manager.decrease()
        Logger.debug(545, "OutputThread: OutputThread terminated")
    }

    void terminate(object self)
    {
        is_terminated = 1
    }
}

// 构建线程对象
object input_thread = alloc(InputThread).init()  // 输入线程
object task_thread = alloc(TaskThread).init()  // 任务线程
object output_thread = alloc(OutputThread).init()  // 输出线程

// object input_thread  // 输入线程
// object task_thread  // 任务线程
// object output_thread  // 输出线程

// 启动程序
void launch() {
    thread_manager.StartThread()  // 线程管理器

    input_thread.StartThread()
    task_thread.StartThread()
    output_thread.StartThread()
}

// 终止程序
void shutdown()
{
    input_thread.terminate()
    task_thread.terminate()
    output_thread.terminate()
}

// ===========================================================================
// 程序GUI线程，操作后端程序运行
// ===========================================================================
class GUI : UIFrame
{

    // 程序状态量，表示是否启动程序
    number is_launched

    // 程序析构函数，如果GUI被关闭，应该终止程序执行 
    ~GUI(object self) 
    {
        if (is_launched) {
            shutdown()  // 关闭程序
            logger.debug(600, "Shutdown Program due to gui closed")
        }
    }

    TagGroup CreateDLGTagGroup(object self)
    {
        // Dialog building method
        TagGroup DLGtgs, DLGItems
        DLGtgs = DLGCreateDialog("CDialog", DLGItems)

        // 启动按钮
        TagGroup launch_Label = DLGCreateLabel("Launch Program").DLGIdentifier("Label_1")
        TagGroup launch_button = DLGCreatePushButton("Initiate", "launch")

        // 停止按钮
        TagGroup shutdown_Label = DLGCreateLabel("Shutdown Program").DLGIdentifier("Label_2")
        TagGroup shutdown_button = DLGCreatePushButton("Terminate", "shutdown")

        DLGItems.DLGAddElement(launch_Label)
        DLGItems.DLGAddElement(launch_button)

        DLGItems.DLGAddElement(shutdown_Label)
        DLGItems.DLGAddElement(shutdown_button)

        DLGtgs.DLGTableLayout(2, 2, 1)
        return DLGtgs
    }

    object LaunchAsModelessDialog(object self)
    {

        is_launched = 0  // 初始化状态量

        self.init(self.CreateDLGTagGroup())
        self.Display("DM Process GUI")
    }

    // Methods invoked by buttons
    void launch(object self)
    {
        if (is_launched)
        {
            Logger.debug(640, "Cannot launch program as the program has already launched")
        }
        else
        {
            ClearResults()
            Result(GetTime(1) + "| DEBUG    |<main>:670 - Launching DM Script Process")
            launch()  // 启动程序线程

            while (1) {
                if (thread_manager.count_thread_num() == 3)
                    break
            }

            sleep(0.1)
            logger.debug(785, "Program threads all done register work!")
            
            is_launched = 1
            Logger.debug(640, "DM Script Process launching successfully")
        }
    }

    void shutdown(object self)
    {
        if (is_launched)
        {
            Logger.debug(640, "Shutdown backend program")
            shutdown()  // 关闭程序

            while (1) {
                if (thread_manager.count_thread_num() == 0)
                    break
            }

            sleep(0.1)
            logger.debug(785, "Program threads all done register work!")

            is_launched = 0
            Logger.debug(640, "DM Script Process terminating successfully")
        }
        else
        {
            Logger.debug(640, "Cannot shutdown program as the program has not launched yet")
        }
    }
}

// ===========================================================================
// 程序入口
// ===========================================================================
void main(void)
{

    // initConfiguration()

    // 判断是否启用gui
    number enable_gui = config.get("enable_gui").val()
    if (enable_gui)
    {
        // 启动携带gui的后端程序
        Logger.debug(668, "Launching program with gui.")
        Alloc(GUI).LaunchAsModelessDialog()
    }
    else
    {
        // 如果不启用gui，那么程序将会在运行一段程序后自动停止
        Logger.debug(647, "Detect NOT enable gui, program will automatically stop in some time.")
        launch()  // 启动程序
        sleep(90)  // 模拟耗时任务
        shutdown()  // 关闭程序
    }
}

// 启动程序
main()

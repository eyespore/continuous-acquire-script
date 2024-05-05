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

// ===========================================================================
// 数学工具类
// ===========================================================================
class MathUtils: object
{
    number clamp(object self, number x, number min, number max)
    {
        if (x > max)
            return max
        if (x < min)
            return min
        return x
    }

    number floor(object self, number x)
    {
        number val = round(x)
        return val > x ? val - 1 : val
    }
}

object math_utils = alloc(MathUtils)

// 请求消息队列
object request_mq = NewMessageQueue()
// 响应消息队列
object response_mq = NewMessageQueue()

// ===========================================================================
// 消息对象类，请求消息通过输入线程会被逐条封装成为任务实例，压入消息队列中
// ===========================================================================
class Message : object
{
    taggroup head  // 消息头
    taggroup body  // 消息体

    void setHead(object self, taggroup head_)
    {
        head = head_
    }

    void setBody(object self, taggroup body_)
    {
        body = body_
    }

    void setHeader(object self, string key, string val)
    {
        head.TagGroupSetTagAsString(key, val)
    }

    void set(object self, string key, string val) {
        body.TagGroupSetTagAsString(key, val)
    }

    // 根据键名获取消息头中的键值
    string getHeader(object self, string key)
    {
        string val
        head.TagGroupGetTagAsString(key, val)
        return val
    }

    // 根据键名获取消息体中的键值
    string get(object self, string key) {
        string val
        body.TagGroupGetTagAsString(key, val)
        return val        
    }

    taggroup getHead(object self)
    {
        return head
    }

    taggroup getBody(object self)
    {
        return body
    }
}

// ===========================================================================
// 消息适配器，可以将前端传入字符串处理成为DM进程消息格式，也可以将DM进程消息转换为
// 字符串前端支持格式
// ===========================================================================
class MessageAdapter : object
{
    string comma_seperator  // 键值对分隔符
    string colon_seperator  // 元素分隔符
    string message_seperator  // 消息分隔符
    object message_prototype  // 请求消息原型

    MessageAdapter(object self)
    {
        comma_seperator = "##"
        colon_seperator = "=>"
        message_seperator = "$$$"
        message_prototype = alloc(Message)
    }

    // 解析消息头和消息体
    TagGroup parse(object self, string str)
    {
        TagGroup tg = NewTagGroup()  // 头部键值对
        try
        {
            // 循环解析头部字符串
            while (1)
            {
                // 以逗号作为键值对分隔
                number comma_pos = str.find(comma_seperator)
                string kv
                if (comma_pos != -1)
                {
                    kv = str.left(comma_pos)
                    str = str.right(str.len() - comma_pos - comma_seperator.len())
                }
                else
                {
                    kv = str
                }

                // 根据分隔符解析得到key和val
                number colon_pos = kv.find(colon_seperator)
                string key = kv.left(colon_pos)
                string val = kv.right(kv.len() - colon_pos - colon_seperator.len())
                tg.TagGroupSetTagAsString(key, val)

                if (comma_pos == -1) break
            }
            return tg
        }
        catch
        {
            break  // 出现异常则将消息重定向到InvalidMessageException
        }

        tg.TagGroupSetTagAsString("name", "InvalidMessageException")
        return tg
    }

    // 格式化头部
    string format(object self, taggroup tg) 
    {
        number count = tg.TagGroupCountTags()
        string str = ""
        for (number i = 0; i < count; i++)
        {
            string key = tg.TagGroupGetTagLabel(i)
            string val
            tg.TagGroupGetTagAsString(key, val)
            if (str.len() == 0)
                str = key + colon_seperator + val
            else
                str = str + comma_seperator + key + colon_seperator + val
        }
        return str
    }

    // 将字符串转化为消息实例
    object convertToMessage(object self, string str)
    {
        number pos = str.find(message_seperator)
        taggroup head = self.parse(str.left(pos))  // 消息头
        taggroup body = self.parse(str.right(str.len() - pos - message_seperator.len()));  // 消息体

        object msg = message_prototype.ScriptObjectClone()
        msg.setHead(head)  // 消息头
        msg.setBody(body)  // 消息体
        return msg
    }

    // 将消息实例转化成控制台打印格式
    string convertToString(object self, object msg)
    {
        return self.format(msg.getHead()) + message_seperator + self.format(msg.getBody())
    }

    // 通过已有的一个消息实例创建新的实例，保留原实例头部
    object allocWithHead(object self, object origin)
    {
        object novel = message_prototype.ScriptObjectClone()
        novel.setHead(origin.getHead())
        novel.setBody(NewTagGroup())
        return novel
    }

}

object message_adapter = alloc(MessageAdapter)

// 线程管理器事件
class ThreadMessage: object {
	object thread_obj
    number option
	
	object init(object self, object thread_obj_, number option_) 
    {
		thread_obj = thread_obj_
        option = option_
        return self
	}

	object getThreadObj(object self) 
    {
		return thread_obj
	}

    number getOption(object self) 
    {
        return option
    }
}

// ===========================================================================
// 线程管理器
// ===========================================================================
class ThreadManager : thread
{
    string name  // 线程管理器名称
    object thread_mq // 线程注册队列
    object thread_list  // 线程列表
    object thread_msg_prototype  // 线程消息原型
    number is_terminated
    number running_thread_num  // 运行线程数量
    number register_thread_num  // 注册线程数量

    number REGISTER_THREAD  // 注册线程
    number UNREGISTER_THREAD  // 注销线程
    number LAUNCH_ALL_THREAD  // 启动所有线程
    number STOP_ALL_THREAD  // 终止所有线程
    number LAUNCH_SINGLE_THREAD  // 启动某一个线程
    number STOP_SINGLE_THREAD  // 停止某一个线程

    number INCREASE_RUNNING_THREAD_NUM  // 增加运行线程数
    number DECREASE_RUNNING_THREAD_NUM  // 减少运行线程数

    number SELECT_RUNNING_THREAD_NUM  // 查询运行线程数
    number SELECT_REGISTER_THREAD_NUM  // 查询注册线程数 
    
    object Init(object self, string name_)
    {
        name = name_
        REGISTER_THREAD = 0
        UNREGISTER_THREAD = 1
        LAUNCH_ALL_THREAD = 2
        STOP_ALL_THREAD = 3
        LAUNCH_SINGLE_THREAD = 4
        STOP_SINGLE_THREAD = 5

        INCREASE_RUNNING_THREAD_NUM = 6
        DECREASE_RUNNING_THREAD_NUM = 7

        SELECT_RUNNING_THREAD_NUM = -1
        SELECT_REGISTER_THREAD_NUM = -2
        
        thread_mq = NewMessageQueue()
        running_thread_num = 0  // 运行线程数目
        is_terminated = 0  // 检测线程是否还在运行
        thread_list = alloc(ObjectList)
        thread_msg_prototype = alloc(ThreadMessage)
        return self
    }

    void countRegisterThreadNum(object self)
    {
        register_thread_num = thread_list.SizeOfList()
    }

    // 统计注册线程数目
    number getRegisterThreadNum(object self)
    {
        return register_thread_num
    }

    // 统计运行线程数目
    number getRunningThreadNum(object self)
    {
        return running_thread_num
    }

    void RunThread( object self ) 
    {
		while (! is_terminated) 
        {
		    object thread_msg = thread_mq.WaitOnMessage(2, null)
            if (thread_msg.ScriptObjectIsValid())
            {
                number option = thread_msg.getOption()
                object thread_obj = thread_msg.getThreadObj()
                // 注销线程
                if (option == UNREGISTER_THREAD) 
                {
                    thread_list.RemoveObjectFromList(thread_obj)
                } 
                
                // 注册线程
                else if (option == REGISTER_THREAD) 
                {
                    thread_list.AddObjectToList(thread_obj)
                } 

                // 启动指定线程
                else if (option == LAUNCH_SINGLE_THREAD)
                {
                    AddMainThreadSingleTask(thread_obj, "terminate", 0)
                }
                
                // 启动所有线程
                else if (option == LAUNCH_ALL_THREAD)
                {
                    number count = thread_list.SizeOfList()
                    for (number i = 0; i < count; i++) {
	                    object thread_obj = thread_list.ObjectAt(i)
                        thread_obj.StartThread()
                    }
                }

                // 停止单个线程
                else if (option == STOP_SINGLE_THREAD)
                {
                    thread_obj.StartThread()
                }

                // 停止所有线程
                else if (option == STOP_ALL_THREAD) 
                {
                    number count = thread_list.SizeOfList()
                    for (number i = 0; i < count; i++) {
	                    object thread_obj = thread_list.ObjectAt(i)
                        AddMainThreadSingleTask(thread_obj, "terminate", 0)
                    }
                }

                // 增加线程个数
                else if (option == INCREASE_RUNNING_THREAD_NUM)
                {
                    running_thread_num ++
                }

                // 减少运行线程个数
                else if (option == DECREASE_RUNNING_THREAD_NUM)
                {
                    running_thread_num --
                }

                // 查询运行线程总数
                else if (option == SELECT_RUNNING_THREAD_NUM)
                {
                    thread_msg = thread_msg.Init(null, running_thread_num)
                }

                // 查询注册线程总数
                else if (option == SELECT_REGISTER_THREAD_NUM)
                {
                    number count = thread_list.SizeOfList()
                    thread_msg = thread_msg.Init(null, count)
                }
            }
		}

        // 线程退出，检查是否还存在运行线程
        number count = thread_list.SizeOfList()
        if (count > 0) {
            Logger.debug(413, "Teminating " + name + ", shutdown running thread")
            for (number i = 0; i < count; i++) 
            {
	            object thread_obj = thread_list.ObjectAt(i)
                AddMainThreadSingleTask(thread_obj, "terminate", 0)
            }
        }
        Logger.debug(420, name + " terminated")
        
    }

    // 停止线程管理器 
    void terminate(object self)
    {
        is_terminated = 1
    }

    // 注销线程
    void unregister(object self, object thread_obj)
    {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(thread_obj, UNREGISTER_THREAD)
        thread_mq.PostMessage(thread_msg)
    }

    // 注册线程
    void register(object self, object thread_obj)
    {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(thread_obj, REGISTER_THREAD)
        thread_mq.PostMessage(thread_msg)
    }

    // 停止所有线程
    void stop(object self)
    {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(null, STOP_ALL_THREAD)
        thread_mq.PostMessage(thread_msg)
    }

    // 停止某一个线程
    void stop(object self, object thread_obj)
    {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(thread_obj, STOP_SINGLE_THREAD)
        thread_mq.PostMessage(thread_msg)
    }

    // 启动所有线程
    void launch(object self)
    {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(null, LAUNCH_ALL_THREAD)
        thread_mq.PostMessage(thread_msg)
    }

    // 启动所有线程
    void launch(object self, object thread_obj)
    {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(thread_obj, LAUNCH_SINGLE_THREAD)
        thread_mq.PostMessage(thread_msg)
    }

    void increase(object self) {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(null, INCREASE_RUNNING_THREAD_NUM)
        thread_mq.PostMessage(thread_msg)
    }

    void decrease(object self) {
        object thread_msg = thread_msg_prototype.ScriptObjectClone().Init(null, DECREASE_RUNNING_THREAD_NUM)
        thread_mq.PostMessage(thread_msg)
    }

    string getName(object self)
    {
        return name
    }

}

// 线程管理器
object thread_manager = alloc(ThreadManager).Init("Main Thread Manager")

// ===========================================================================
// 输入线程，负责创建和销毁输入管道文件，启动后定时从管道文件数据拉取数据到内存当中，
// 每次完成拉取之后会清空管道内容，解析读取数据，封装成为任务对象存入任务队列中
// ===========================================================================
class InputThread : thread
{

    number is_terminated  // 是否终止线程 
    string input_pip_path  // 输入管道路径
    string input_pip_lock  // 输入管道锁


    object init(object self)
    {
        // 初始化属性
        is_terminated = 0
        input_pip_path = config.get("input_pip_path")
        input_pip_lock = config.get("input_pip_lock")
        return self
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

        // 初始化线程状态量
        is_terminated = 0
        thread_manager.increase()

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
                        object request_message = message_adapter.convertToMessage(line)
                        logger.debug(414, "InputThread: Accepted message : [" + message_adapter.convertToString(request_message) + "]")
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

        thread_manager.decrease()
        Logger.debug(327, "InputThread: InputThread terminated")
    }

    void terminate(object self)
    {
        is_terminated = 1
    }
}

// ===========================================================================
// 拍摄任务
// ===========================================================================
class AcquireTask: object
{
    object request
    object response  // 触发回调使用
    number camID  // 使用相机的id
    number exposure  // 曝光度
    number xBin  // x方向binning
    number yBin  // y方向binning
    number processing  // 处理过程
    number areaT  // 顶部边界坐标
    number areaL  // 左部边界坐标
    number areaB  // 底部边界坐标
    number areaR  // 右部边界坐标

    object Init(object self, object request_, object response_, number camID_, number exposure_, number xBin_, number yBin_, number processing_, number areaT_, number areaL_, number areaB_, number areaR_) {
        request = request_
        response = response_
        camID = camID_
        exposure = exposure_
        xBin = xBin_
        yBin = yBin_
        processing = processing_
        areaT = areaT_
        areaL = areaL_
        areaB = areaB_
        areaR = areaR_
        return self
    }

    object getResponse(object self) 
    {
        return response  // 触发回调使用
    }  

    object getRequest(object self)
    {
        return request
    }

    void doCameraAcquire(object self)
    {
        // CameraAcquire( camID, exposure, xBin, yBin, processing, areaT, areaL, areaB, areaR )
        // 模拟耗时任务
        sleep(0.5)
    }
}

// 拍摄任务消息队列
object acquire_task_mq = NewMessageQueue()

interface validator {
    // 验证当前请求是否合法，合法返回1，不合法返回0
    number validate(object self, object request, object response);
}

// ===========================================================================
// 拍摄线程，根据提交的任务执行拍摄，以池的方式运行
// ===========================================================================
class AcquireThread: thread
{
    number is_terminated  // 线程停止信号量
    object validators  // 验证器链

    object Init(object self)
    {
        is_terminated = 0
        validators = alloc(ObjectList)
        return self
    }

    void RunThread(object self)
    {
        // 初始化状态量
        is_terminated = 0

        while (!is_terminated)
        {
            object acquire_task = acquire_task_mq.WaitOnMessage(2, null)  // 获取拍摄任务
            if (acquire_task.ScriptObjectIsValid())
            {
                object response = acquire_task.getResponse()
                object request = acquire_task.getRequest()

                number is_forbidden = 0
                for (number i = 0; i < validators.SizeOfList(); i ++)
                {
                    object validator = validators.ObjectAt(i)
                    if ( ! validator.validate(request, response))
                    {
                        is_forbidden = 1
                        break
                    }
                }

                if (is_forbidden)
                    continue

                acquire_task.doCameraAcquire()  // 执行拍摄
                // 每次拍摄完成进行响应
                response.set("message", "Done")
                response.set("code", "200")
                response_mq.PostMessage(response)
            }
        }

        // 线程退出
    }

    void addValidator(object self, object validator)
    {
        validators.AddObjectToList(validator)
    }

    void terminate(object self)
    {
        is_terminated = 1
    }
}

// ===========================================================================
// 拍摄线程管理器消息
// ===========================================================================
class AcquireManagerMessage: object
{
    object request
    object response

    object Init(object self, object request_, object response_) 
    {
        request = request_
        response = response_
		return self
	}

    object getRequest(object self)
    {
        return request
    }

    object getResponse(object self)
    {
        return response
    }
}

// ===========================================================================
// IP地址验证器，用于禁用某个ip地址的请求
// ===========================================================================
class AddressValidator: object
{
    object lock
    taggroup filter  // 地址过滤

    object Init(object self)
    {
        lock = NewCriticalSection()
        filter = NewTagGroup()
        return self
    }

    // 对任务进行验证，通过返回码判断是否合法
    number validate(object self, object reqeust, object response) 
    {
        object lock_ = lock.acquire()
        if ( ! filter.TaggroupDoesTagExist(reqeust.getHeader("address")))
            return 1
        else 
        {
            // 响应消息
            response.set("code", "403")
            response.set("message", "Reqeust Forbidden, server received the request but reject handling")
            response_mq.PostMessage(response)
        }
        return 0
    }

    // 禁用某个address下的所有请求
    void rejectAddress(object self, string address)
    {
        object lock_ = lock.acquire()
        filter.TaggroupSetTagAsString(address, "reject")
    }  

    // 放行某个address下的所有请求
    void permitAddress(object self, string address)
    {
        object lock_ = lock.acquire()
        filter.TagGroupDeleteTagWithLabel(address)
    }  
}

// ===========================================================================
// 拍摄管理器，守护线程
// ===========================================================================
class AcquireManager : thread
{
    number XY_CONTINUOUS_ACQUIRE
    number SP_CONTINUOUS_ACQUIRE
    number STOP_CONTINUOUS_ACQUIRE

    number is_terminated  // 线程停止信号量
    object acquire_manager_mq  // 操作任务
    number thread_num  // 启用多少条线程执行拍摄任务
    object acquire_thread_manager  // 任务线程管理器，管理所有任务线程
    object address_validator  // 地址验证器

    object acquire_manager_message_prototype  // 连拍管理器消息
    object acquire_task_prototype


    object Init(object self) 
    {
        // option
        XY_CONTINUOUS_ACQUIRE = 0
        SP_CONTINUOUS_ACQUIRE = 1
        STOP_CONTINUOUS_ACQUIRE = 2

        is_terminated = 0
        acquire_manager_mq = NewMessageQueue()
        thread_num = config.get("acquire_thread_num").val()
        acquire_thread_manager = alloc(ThreadManager).Init("Acquire Thread Manager")
        address_validator = alloc(AddressValidator).Init()

        acquire_manager_message_prototype = alloc(AcquireManagerMessage)  // 连拍管理器消息
        acquire_task_prototype = alloc(AcquireTask)
        
        return self
    }

    void RunThread(object self) 
    {
        // 注册线程
        acquire_thread_manager.StartThread()  // 注册线程
        for (number i = 0; i < thread_num; i ++)
        {
            object acquire_thread = alloc(AcquireThread).Init()
            
            acquire_thread.addValidator(address_validator)  // 添加验证器

            acquire_thread_manager.register(acquire_thread)
        }
        
        is_terminated = 0  // 初始化信号量
        while (!is_terminated)
        {
            object acquire_manager_message = acquire_manager_mq.WaitOnMessage(2, null)
            if (acquire_manager_message.ScriptObjectIsValid())
            {
                object request = acquire_manager_message.getRequest()
                object response = acquire_manager_message.getResponse()
                
                address_validator.permitAddress(request.getHeader("address"))  // 放行ip

                number option = request.getHeader("option").val()
                // 判断是否成功获取操作名

                number camID = request.get("cam_id").val()  // 准备相机
                // CameraPrepareForAcquire(camID)

                number exposure = request.get("exposure").val()
                number x_bin = request.get("x_bin").val()
                number y_bin = request.get("y_bin").val()

                number x_size, y_size  // 获取相机参数
                // CameraGetSize(CamID, x_size, y_size)
                x_size = 4096
                y_size = 4096

                x_size = math_utils.floor(x_size / x_bin)  // 计算binning
                y_size = math_utils.floor(y_size / y_bin)

                // 坐标计算
                if (option == XY_CONTINUOUS_ACQUIRE)  // XY轴横移连拍
                {
                    // 计算拍摄坐标提交给消息队列
                    number enable_extension = request.get("enable_extension").val()
                    number extension_unit = request.get("extension_unit").val()
                    number x_off = request.get("x_off").val()
                    number y_off = request.get("y_off").val()
                    number x_split = request.get("x_split").val()
                    number y_split = request.get("y_split").val()

                    // 计算步长
                    number x_step = math_utils.floor(x_size / x_split)
                    number y_step = math_utils.floor(y_size / y_split)

                    // 行循环
                    for (number line_num = 0; line_num < x_split; line_num ++) 
                    {
                        // 列循环
                        for (number col_num = 0; col_num < y_split; col_num ++)
                        {
                            number areaT = line_num * y_step
                            number areaL = col_num * x_step
                            number areaB = (line_num + 1) * y_step
                            number areaR = (col_num + 1) * x_step

                            if (enable_extension && (x_off != 0 || y_off != 0))
                            {
                                if (extension_unit == 0)
                                {
                                    // 像素拓展，向四周拓展
                                    areaT -= y_off
                                    areaL -= x_off
                                    areaB += y_off
                                    areaR += x_off
                                }
                                
                                else if (extension_unit == 1) 
                                {
                                    // 百分比拓展，需要计算出拓展的像素
                                    number v_off = math_utils.floor(y_step * (0.01 * x_off))
                                    number h_off = math_utils.floor(x_step * (0.01 * x_off))

                                    areaT -= v_off
                                    areaL -= h_off
                                    areaB += v_off
                                    areaR += h_off                                
                                }
                            }

                            // 对坐标的圆整，注意无法访问边界坐标
                            areaT = math_utils.clamp(areaT, 0, y_size - 1)
                            areaL = math_utils.clamp(areaL, 0, x_size - 1)
                            areaB = math_utils.clamp(areaB, areaT, y_size - 1)
                            areaR = math_utils.clamp(areaR, areaL, x_size - 1)

                            object request_ = request.ScriptObjectClone()
                            object response_ = response.ScriptObjectClone()
                            object acquire_task = acquire_task_prototype.ScriptObjectClone()
                            // 创建消息
                            // number processing = CameraGetGainNormalizedEnum( ) 
                            number processing = 1
                            acquire_task = acquire_task.Init(request_, response_, camID, exposure, x_bin, y_bin, processing, areaT, areaL, areaB, areaR)
                            // 提交任务
                            acquire_task_mq.PostMessage(acquire_task)
                        }
                    }
                }

                else if (option == SP_CONTINUOUS_ACQUIRE)  // 单点连续拍摄
                {
                    
                }

                else if (option == STOP_CONTINUOUS_ACQUIRE)  // 停止连续拍摄
                {
                    Logger.debug(1024, "Address Validatro reject ip: " + request.getHeader("address"))
                    address_validator.rejectAddress(request.getHeader("address"))  // 拒绝ip

                    response.set("code", "200")
                    response.set("message", "Successfully reject ip")
                    response_mq.PostMessage(response)  // 返回消息
                } 
                else 
                {
                    response.set("code", "400")
                    response.set("message", "Such option cannot map to any operation")
                    response_mq.PostMessage(response)  // 返回消息
                }
            }
        }

        // 线程退出
        acquire_thread_manager.stop()  // 停用所有子线程
    }

    // 停止所有任务线程
    void stop(object self)
    {
        acquire_thread_manager.stop()
    }

    // 启用所有任务线程
    void launch(object self)
    {
        acquire_thread_manager.launch()
    }

    // 统计运行线程数
    number getRunningThreadNum(object self)
    {
        return acquire_thread_manager.getRunningThreadNum()
    }

    void countRegisterThreadNum(object self)
    {
        acquire_thread_manager.countRegisterThreadNum()
    }

    // 统计注册线程数
    number getRegisterThreadNum(object self)
    {
        return acquire_thread_manager.getRegisterThreadNum()
    }

    void submit(object self, object request, object response)
    {
        object acquire_manager_message = acquire_manager_message_prototype.ScriptObjectClone()
        acquire_manager_message = acquire_manager_message.Init(request, response)
        acquire_manager_mq.PostMessage(acquire_manager_message)
    }

    void terminate(object self) 
    {
        acquire_thread_manager.terminate()  // 停止任务线程管理器
        is_terminated = 1
    }

    string getName(object self)
    {
        return acquire_thread_manager.getName()
    }
}

object acquire_manager = alloc(AcquireManager).Init()  // 拍摄管理器

// ===========================================================================
// DM任务派发器，封装了请求消息，通过这个类来将操作派发到某个具体的功能上
// ===========================================================================
class DMTaskDispatcher: object
{
    object request
    object response

    void setRequestMessage(object self, object request_message)
    {
        request = request_message
        response = message_adapter.allocWithHead(request)
    }

    // ================== 功能定义 ======================
    // 未找到资源
    void NotFound(object self)
    {
        response.set("message", "Unable accessing target resources")
        response.set("code", "404")
        response_mq.PostMessage(response)
    }

    // 消息头部解析错误
    void InvalidMessageException(object self)
    {
        response.set("message","Unable parsing message, check if message is in correctly writting")
        response.set("code", "400")
        response_mq.PostMessage(response)
    }

    // 连拍任务，提交给连拍处理器
    void ContinuousAcquire(object self)
    {
        acquire_manager.submit(request, response) // 提交任务
    }

    // TODO: 获取相机参数API

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
        // 初始化线程状态量
        is_terminated = 0
        thread_manager.increase()

        while (!is_terminated)
        {
            object request_message = request_mq.WaitOnMessage(2, null)
            // 检查合法性
            if (request_message.ScriptObjectIsValid())
            {
                logger.debug(518, "TaskThread: Handle message from InputThread : [" + message_adapter.convertToString(request_message) + "]")

                // 获取操作名，将数据映射到具体的路由上
                try
                {
                    dm_task_dispatcher.setRequestMessage(request_message)
                    string name = request_message.getHeader("name")
                    // 判断是否成功获取操作名
                    if (name == null) {
                        // 未设置操作名
                        request_message.setHeader("name", "InvalidMessageException")
                        name = request_message.getHeader("name")
                    }
                    number task_id = AddMainThreadSingleTask(dm_task_dispatcher, name, 0)
                }
                catch
                {
                    // 如果没有找到操作名，引导至NotFound
                    Logger.debug(1111, "TaskThread: Unsupported operation name, lead to NotFound")
                    number task_id = AddMainThreadSingleTask(dm_task_dispatcher, "NotFound", 0)
                    break
                }
            }
        }

        // 主循环结束，退出循环
        Logger.debug(384, "TaskThread: TaskThread terminating...")
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

        // 初始化线程状态量
        is_terminated = 0
        thread_manager.increase()
        logger.debug(744, "Output thread waiting for wrtting output message")

        // 提取响应并且写入输出文件当中
        while (!is_terminated)
        {
            object response_message = response_mq.WaitOnMessage(2, null)
            // 检查合法性
            if (response_message.ScriptObjectIsValid())
            {
                // 将消息加载到缓存
                logger.debug(458, "OutputThread: Caching response message : [" + message_adapter.convertToString(response_message) + "]")
                response_message_cache.TagGroupInsertTagAsString(response_message_cache.TagGroupCountTags(), message_adapter.convertToString(response_message));
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

// 程序初始化
void init() {
    // 守护线程注册
    // 启动主线程管理器
    logger.debug(836, "Launching " + thread_manager.getName())
    thread_manager.StartThread()
    logger.debug(838, "Done")

    logger.debug(836, "Launching " + acquire_manager.getName())
    acquire_manager.StartThread()
    logger.debug(838, "Done")

    thread_manager.register(input_thread)
    Logger.debug(841, "InputThread registered into " + thread_manager.getName())
    thread_manager.register(task_thread)
    Logger.debug(843, "TaskThread registered into " + thread_manager.getName())
    thread_manager.register(output_thread)
    Logger.debug(845, "OutputThread registered into " + thread_manager.getName())
    
    sleep(0.3)
    thread_manager.countRegisterThreadNum()
    logger.debug(1124, thread_manager.getName() + " current register thread num : " + thread_manager.getRegisterThreadNum())

    acquire_manager.countRegisterThreadNum()
    logger.debug(1124, thread_manager.getName() + " current register thread num : " + acquire_manager.getRegisterThreadNum())
}

// ===========================================================================
// 程序GUI线程，操作后端程序运行
// ===========================================================================
class GUI : UIFrame
{
    number is_terminated  // 程序状态量，表示是否启动程序

    // 程序析构函数，如果GUI被关闭，应该终止程序执行 
    ~GUI(object self) 
    {
        thread_manager.terminate()
        acquire_manager.terminate()
        is_terminated = 1
    }

    TagGroup CreateDLGTagGroup(object self)
    {
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

        is_terminated = 1  // 初始化状态量

        self.init(self.CreateDLGTagGroup())
        self.Display("DM Process GUI")
    }

    // Methods invoked by buttons
    void launch(object self)
    {
        if (is_terminated)
        {
            ClearResults()
            Result(GetTime(1) + "| DEBUG    |<main>:1249 - Launching DM Script Process")
            thread_manager.launch()
            acquire_manager.launch()

            // thread_manager.await()
            // acquire_task_dispatcher.await()

            sleep(0.1)
            logger.debug(1257, "Program threads all done register work!")
            
            is_terminated = 0
            Logger.debug(1260, "DM Script Process launching successfully")
        }
        else
        {
            Logger.debug(1264, "Cannot launch program as the program has already launched")
        }
    }

    void shutdown(object self)
    {
        if (! is_terminated)
        {
            Logger.debug(1200, "Shutdown backend program")
            thread_manager.stop()  // 停止管道进程
            acquire_manager.stop()  // 停止拍摄进程

            // thread_manager.join()
            // acquire_task_dispatcher.join()

            sleep(0.1)
            logger.debug(785, "Program threads all done register work!")

            is_terminated = 1
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
    init()  // 初始化线程
    number enable_gui = config.get("enable_gui").val()  // 判断是否启用gui
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
        thread_manager.launch()  // 启动程序
        sleep(90)  // 模拟耗时任务
        thread_manager.stop()  // 关闭程序
        thread_manager.terminate()
    }
}

// 启动程序
main()

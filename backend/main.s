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
        if (str.len() == 0)
            return tg

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
    // 获取验证器名称
    string getName(object self);
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
                string name_of_validator
                for (number i = 0; i < validators.SizeOfList(); i ++)
                {
                    object validator = validators.ObjectAt(i)
                    if ( ! validator.validate(request, response))
                    {
                        is_forbidden = 1
                        name_of_validator = validator.getName()
                        break
                    }
                }

                if (is_forbidden)
                {
                    response.set("code", "403")  // 拍摄请求被禁止
                    response.set("message", "Server do received the message, but reject handling it, validator: " + name_of_validator)
                    response_mq.PostMessage(response)
                    continue  // 继续获取下一个拍摄请求
                }

                acquire_task.doCameraAcquire()  // 执行拍摄

                response.set("code", "200")  // 每次拍摄完成进行响应
                response.set("message", "Done")
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

    // 对任务进行验证，1: 请求合格，0：请求不合格
    number validate(object self, object reqeust, object response) 
    {
        object lock_ = lock.acquire()
        if ( ! filter.TaggroupDoesTagExist(reqeust.getHeader("address")))
            return 1 
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

    string getName(object self)
    {
        return "AddressValidator"
    }
}

interface sp_task_manager {
    void unregisterTaskDispatcher(object self, object task);
}
object acquire_task_prototype = alloc(AcquireTask)  // 拍摄消息原型
// ===========================================================================
// 连拍任务派发类，逻辑为按时间派发子任务
// ===========================================================================
class SPAcquireTaskDispatcher: object
{
    object sp_task_manager  // 任务管理器
    object request  // 获取请求参数
    object response  // 执行过程响应
    number camID  // 使用相机的id
    number exposure  // 曝光度
    number x_bin  // x方向binning
    number y_bin  // y方向binning
    number processing  // 处理过程
    number areaT  // 顶部边界坐标
    number areaL  // 左部边界坐标
    number areaB  // 底部边界坐标
    number areaR  // 右部边界坐标

    number duration  // 持续时间
    number framerate  // 帧率
    number task_id  // 任务id
    number is_terminated  // 是否正在运行状态
    number current_count  // 当前循环轮数，每次循环耗时一秒
    number enable_optimize  // 是否启用自动坐标修正
    number pos_optimize_interval  // 坐标自动修正间隔
    string address  // 派发任务的进程地址
    object lock  // 全局锁

    object Init(object self, object request_, object response_, object sp_task_manager_)
    {
        sp_task_manager = sp_task_manager_
        request = request_
        response = response_
        
        camID = request.get("cam_id").val()
        exposure = request.get("exposure").val()
        x_bin = request.get("x_bin").val()
        y_bin = request.get("y_bin").val()
        //processing = request.getHeader("cam_id").val()   // TODO: 获取处理过程
        processing = 1   // 处理过程
        areaT = request.get("pos_top").val()
        areaL = request.get("pos_left").val()
        areaB = request.get("pos_bottom").val()
        areaR = request.get("pos_right").val()

        framerate = request.get("framerate").val()
        duration = request.get("duration").val()
        enable_optimize = request.get("enable_optimize").val()
        pos_optimize_interval = config.get("pos_optimize_interval").val()
        address = request.getHeader("address")

        is_terminated = 1
        current_count = 0
        lock = NewCriticalSection()
        return self
    }

    string getAddress(object self)
    {
        return address
    }

    // 派发子任务
    void dispatchSubTask(object self) {
        object lock_ = lock.acquire()
        if (is_terminated)
            return
        object acquire_task = acquire_task_prototype.ScriptObjectClone()
        acquire_task = acquire_task.Init(request, response, camID, exposure, x_bin, y_bin, processing, areaT, areaL, areaB, areaR)
        for (number i = 0; i < framerate; i ++)
        {
            acquire_task_mq.PostMessage(acquire_task)  // 派发等同于帧率数量的任务
        }

        // 判断是否需要更新坐标
        if (enable_optimize && !(current_count % (pos_optimize_interval + 1)))
        {
            object response_ = response.ScriptObjectClone()
            response_.setBody(NewTaggroup())
            response_.set("code", "300")
            response_.set("message", "Optimizing request")
            response_mq.PostMessage(response_)
        }

        if (duration > 0)
        {
            current_count ++
            if (current_count >= duration)
            {
                // 当任务执行次数多余持续时间（以秒作为单位，任务每秒执行一次），那么定时任务执行完成
                is_terminated = 1
                sp_task_manager.unregisterTaskDispatcher(self)
            }
        }
    }

    // 定时派发任务，返回定时任务id
    number execute(object self)
    {
        if (! is_terminated)
            return 0  // 任务正在运行，不允许再次启动
        is_terminated = 0  // 重置任务状态
        current_count = 0  // 重置任务运行次数
        task_id = AddMainThreadPeriodicTask(self, "dispatchSubTask", 1)
        return 1
    }

    // 坐标修正
    number optimize(object self, object request, object response)
    {
        areaT = request.get("fix_pos_top").val()
        areaL = request.get("fix_pos_left").val()
        areaB = request.get("fix_pos_bottom").val() 
        areaR = request.get("fix_pos_right").val() 
        return 1
    }

    number shutdown(object self)
    {
        object lock_ = lock.acquire()
        // 终止定时任务
        if (is_terminated)
            return 0

        if (current_count < duration || duration < 0)  // 为中途终止任务
        {
            is_terminated = 1
            sp_task_manager.unregisterTaskDispatcher(self)
            return 1
        }
        return 0
    }
}

// ===========================================================================
// 单点连拍管理器
// ===========================================================================
class SPAcquireManager: object
{
    object sp_acquire_task_dispatcher_prototype
    object task_dipatcher_list  // 连拍任务列表
    object lock  // 全局锁

    object Init(object self)
    {
        sp_acquire_task_dispatcher_prototype = Alloc(SPAcquireTaskDispatcher)
        task_dipatcher_list = Alloc(ObjectList)
        lock = NewCriticalSection()
        return self
    }

    // 注册连拍任务
    number registerTaskDispatcher(object self, object manager)
    {
        object lock_ = lock.acquire()
        return task_dipatcher_list.AddObjectToList(manager)
    }

    // 移除连拍任务
    void unregisterTaskDispatcher(object self, object manager)
    {
        object lock_ = lock.acquire()
        task_dipatcher_list.RemoveObjectFromList(manager)
    }

    // 检查当前进程是否已经存在一个连拍任务
    number hasRunningTaskDispatcher(object self, string address)
    {
        object lock_ = lock.acquire()
        for (number i = 0; i < task_dipatcher_list.SizeOfList(); i++)
        {
            if (task_dipatcher_list.ObjectAt(i).getAddress() == address)
                return 1
        }
        return 0
    }

    // 根据地址获取该进程下正在执行的连拍任务
    object getTaskDispathcer(object self, string address)
    {
        object lock_ = lock.acquire()
        for (number i = 0; i < task_dipatcher_list.SizeOfList(); i++)
        {
            if (task_dipatcher_list.ObjectAt(i).getAddress() == address)
                return task_dipatcher_list.ObjectAt(i)
        }
        return null
    }

    // 执行单点连拍
    number execute(object self, object request, object response) 
    {
        // 查询该ip下是否已经存在一个定时任务，如果存在那么终止请求
        // CameraPrepareForAcquire(camID)  // TODO: 准备相机
        string address = request.getHeader("address")
        if (self.hasRunningTaskDispatcher(address))
            return 0
        
        // 如果ip不存在，创建一个定时连拍任务
        object sp_task_dispatcher = sp_acquire_task_dispatcher_prototype.ScriptObjectClone()
        sp_task_dispatcher = sp_task_dispatcher.Init(request, response, self)

        self.registerTaskDispatcher(sp_task_dispatcher)
        return sp_task_dispatcher.execute()
    }

    // 停止单点连拍
    number stop(object self, object request, object response)
    {
        string address = request.getHeader("address")
        if (self.hasRunningTaskDispatcher(address))
        {
            object sp_task_dispatcher = self.getTaskDispathcer(address)
            return sp_task_dispatcher.shutdown() // TODO: 此处返回值不正常，应该将sp_task_dispatcher.terminate()作为返回值
        }
        return 0  // 不存在可以停止的任务
    }

    // 修正坐标
    void optimize(object self, object request, object response)
    {
        //...
    }
}

// ===========================================================================
// 横移连拍管理器
// ===========================================================================
class XYAcquireManager: object
{
    object lock  // 全局锁

    object Init(object self)
    {
        lock = NewCriticalSection()
        return self
    }

    // 执行XY横移连拍
    number execute(object self, object request, object response)
    {
        number camID = request.get("cam_id").val()  // TODO:准备相机
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

                object acquire_task = acquire_task_prototype.ScriptObjectClone()
                // 创建消息
                // TODO: processing的获取
                // number processing = CameraGetGainNormalizedEnum( ) 
                number processing = 1
                acquire_task = acquire_task.Init(request, response, camID, exposure, x_bin, y_bin, processing, areaT, areaL, areaB, areaR)
                acquire_task_mq.PostMessage(acquire_task)  // 提交拍摄任务
            }
        }

        return 1  // 成功提交任务
    } 

    number stop(object self, object request, object response)
    {
        return 1
    }
}

object sp_acquire_manager = alloc(SPAcquireManager).Init()  // 单点连拍管理器
object xy_acquire_manager = alloc(XYAcquireManager).Init()  // XY横移连拍管理器

// ===========================================================================
// 拍摄管理器，守护线程
// ===========================================================================
class AcquireManager : thread
{
    number XY_CONTINUOUS_ACQUIRE
    number SP_CONTINUOUS_ACQUIRE
    number XY_CANCEL_ACQUIRE
    number SP_CANCEL_ACQUIRE
    number CONNECTION_CLOSE
    number STOP_CONTINUOUS_ACQUIRE

    number is_terminated  // 线程停止信号量
    object acquire_manager_mq  // 操作任务
    number thread_num  // 启用多少条线程执行拍摄任务
    object acquire_thread_manager  // 任务线程管理器，管理所有任务线程
    object address_validator  // 地址验证器

    object acquire_manager_message_prototype  // 连拍管理器消息

    object Init(object self) 
    {
        // option指令码
        XY_CONTINUOUS_ACQUIRE = 0
        SP_CONTINUOUS_ACQUIRE = 1
        XY_CANCEL_ACQUIRE = 2
        SP_CANCEL_ACQUIRE = 3
        CONNECTION_CLOSE = 4

        is_terminated = 0
        acquire_manager_mq = NewMessageQueue()
        thread_num = config.get("acquire_thread_num").val()
        acquire_thread_manager = alloc(ThreadManager).Init("Acquire Thread Manager")
        address_validator = alloc(AddressValidator).Init()

        acquire_manager_message_prototype = alloc(AcquireManagerMessage)  // 连拍管理器消息
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
                
                string option_str = request.get("option")
                if (option_str == null) {  // 判断是否成功获取操作名
                    response.set("code", "400")
                    response.set("message", "option cannot be found in request, no acqure operation will be executed")
                    response_mq.PostMessage(response)  // 返回消息
                    continue
                }
                number option = option_str.val()
                
                // XY轴横移连拍
                if (option == XY_CONTINUOUS_ACQUIRE)  
                {
                    address_validator.permitAddress(request.getHeader("address"))  // 放行ip
                    number result = xy_acquire_manager.execute(request, response)
                    if (result)
                    {
                        // 执行成功
                        
                        response.set("code", "201") // 执行成功
                        response.set("message", "Successfully create xy acquire task")
                        response_mq.PostMessage(response)
                    }
                    else
                    {
                        response.set("code", "400")  // 执行失败
                        response.set("message", "Cannot execute xy continuous acquire task")
                        response_mq.PostMessage(response)
                        return
                    }
                }

                // 停止XY横移连续拍摄
                else if (option == XY_CANCEL_ACQUIRE)  
                {
                    address_validator.rejectAddress(request.getHeader("address"))  // 禁用ip
                    number result = xy_acquire_manager.stop(request, response)
                    if (result)
                    {
                        response.set("code", "202") // 响应消息
                        response.set("message", "Successfully stop xy acqure tasks")
                        response_mq.PostMessage(response)                        
                    }
                    else
                    {
                        response.set("code", "401")  // 停止任务失败
                        response.set("message", "No such xy acquire task can be stopped")
                        response_mq.PostMessage(response) 
                    }
                } 

                // 单点连续拍摄
                else if (option == SP_CONTINUOUS_ACQUIRE)  
                {
                    address_validator.permitAddress(request.getHeader("address"))  // 放行ip
                    number result = sp_acquire_manager.execute(request, response)
                    if (result)
                    {
                        response.set("code", "201") // 执行成功
                        response.set("message", "Successfully create sp acquire task")
                        response_mq.PostMessage(response)
                    }
                    else
                    {
                        response.set("code", "400")  // 执行失败
                        response.set("message", "Cannot execute sp continuous acquire task")
                        response_mq.PostMessage(response)
                        return
                    }
                }

                // 停止单点连续拍摄
                else if (option == SP_CANCEL_ACQUIRE)  
                {
                    address_validator.rejectAddress(request.getHeader("address"))  // 拒绝ip
                    number result = sp_acquire_manager.stop(request, response)
                    if (result)
                    {
                        response.set("code", "202")  // 成功停止任务
                        response.set("message", "Successfully stop sp acqure tasks")
                        response_mq.PostMessage(response) 
                    }
                    else
                    {
                        response.set("code", "401")  // 停止任务失败
                        response.set("message", "No such sp acquire task can be stopped")
                        response_mq.PostMessage(response) 
                    }
                }

                // 前端连接关闭
                else if (option == CONNECTION_CLOSE)  
                {
                    address_validator.rejectAddress(request.getHeader("address"))  // 拒绝ip
                    number xy_result = xy_acquire_manager.stop(request, response)
                    number sp_result = sp_acquire_manager.stop(request, response)

                    if (xy_result)
                        Logger.debug(1360, "Stop xy acquire task cause by connection close")
                    
                    if (sp_result)
                        Logger.debug(1363, "Stop sp acquire task cause by connection close")
                }

                // 没有明确指令
                else 
                {
                    response.set("code", "400")
                    response.set("message", "Given option code cannot apply to any exist operation")
                    response_mq.PostMessage(response)
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
        request = request_message.ScriptObjectClone()  // 采用克隆模式，获取克隆对象
        response = message_adapter.allocWithHead(request)
    }

    // ================== 功能定义 ======================
    // 未找到资源
    void NotFoundException(object self)
    {
        response.set("code", "404")
        response.set("message", "Unable accessing target resources")
        response_mq.PostMessage(response)
    }

    // 消息头部解析错误
    void InvalidMessageException(object self)
    {
        response.set("code", "400")
        response.set("message","Unable parsing message, check if message is in correctly writting")
        response_mq.PostMessage(response)
    }

    // 连拍任务，提交给连拍处理器
    void ContinuousAcquire(object self)
    {
        acquire_manager.submit(request, response) // 提交任务
    }

    // 连接断开
    void ConnectionClosing(object self)
    {
        Logger.debug(1132, "connection close: " + request.getHeader("address"))

        request.set("option", "4")  // 停止前端进程对应的拍摄进程
        acquire_manager.submit(request, response)
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
        // 初始化线程状态量
        is_terminated = 0
        thread_manager.increase()

        while (!is_terminated)
        {
            object request = request_mq.WaitOnMessage(2, null)
            // 检查合法性
            if (request.ScriptObjectIsValid())
            {
                logger.debug(518, "TaskThread: Handle message from InputThread : [" + message_adapter.convertToString(request) + "]")

                try
                {
                    dm_task_dispatcher.setRequestMessage(request)  // 获取操作名，将数据映射到具体的路由上
                    string name = request.get("name") 
                    // 判断是否成功获取操作名
                    if (name == null) {
                        // 未设置操作名
                        request.set("name", "InvalidMessageException")
                        name = request.get("name")
                    }
                    number task_id = AddMainThreadSingleTask(dm_task_dispatcher, name, 0)
                }
                catch
                {
                    // 如果没有找到操作名，引导至NotFoundException
                    Logger.debug(1433, "TaskThread: Unsupported operation name, lead to NotFound")
                    number task_id = AddMainThreadSingleTask(dm_task_dispatcher, "NotFoundException", 0)
                    break
                }
            }
        }

        // 主循环结束，退出循环
        Logger.debug(1441, "TaskThread: TaskThread terminating...")
        thread_manager.decrease()
        Logger.debug(1443, "TaskThread: TaskThread terminated")
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
    number response_message_count // 写出消息缓存数
    number output_pip_write_interval  // 输出管道写间隔

    object lock  // 全局锁

    object init(object self)
    {
        // 初始化属性
        is_terminated = 0
        output_pip_path = config.get("output_pip_path")
        output_pip_lock = config.get("output_pip_lock")
        output_pip_write_interval = config.get("output_pip_write_interval").val()

        response_message_cache_prototype = NewTagList()
        response_message_cache = response_message_cache_prototype.TagGroupClone()
        response_message_count = 0

        lock = NewCriticalSection()
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
                response_message_count ++  // 更新响应消息队列缓存数量
            }

            number lock_exist = 0

            try 
                lock_exist = DoesFileExist(output_pip_lock)
            catch {
                Logger.debug(1607, "Hit check lock file exception")
                break
            }

            if (response_message_count > 0 && lock_exist)
            {
                // 如果缓存区存在响应数据，将缓冲区响应消息写入文件
                number output_pip
                object output_pip_stream
                // 获取输出管道文件句柄
                
                number exeception_occur = 0
                try
                {
                    output_pip = OpenFileForWriting(output_pip_path)
                    output_pip_stream = NewStreamFromFileReference(output_pip, 1)
                    output_pip_stream.StreamSetPos(2, 0)  // 将文件指针偏移到文件末尾，执行追加写入
                }
                catch
                {
                    Logger.debug(451, "Fail on acquiring output pip file handler, left message until next try")
                    exeception_occur = 1
                    break
                }

                if (exeception_occur)
                    continue

                for (number i = 0; i < response_message_count; i++)
                {
                    string response_message_str
                    response_message_cache.TagGroupGetIndexedTagAsString(i, response_message_str)
                    logger.debug(488, "OutputThread: Write response message to File : [" + response_message_str + "]")
                    output_pip_stream.StreamWriteAsText(0, response_message_str + "\n")
                }
                
                response_message_cache = response_message_cache_prototype.TagGroupClone()  // 清空缓冲区 
                response_message_count = 0  // 清除缓冲区数量
                output_pip.CloseFile()  // 关闭文件输入流
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

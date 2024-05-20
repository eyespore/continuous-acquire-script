# 连拍脚本

使用Python结合Digital Micrograph软件提供的开发接口实现的连拍功能

python版本：3.7.1

## 项目部署

解压项目之后推荐采用虚拟环境的形式部署，在项目根目录下执行

```
python -m venv .venv
```

来创建项目虚拟环境，然后切换到项目虚拟环境，使用`pip`和`requirements.txt`构建项目依赖：

```
.venv\Scripts\activate
pip install -r requirements.txt
```

> 注：项目使用PyQt5编写Gui程序，pip版本过旧可能造成PyQt5下载失败，使用
>
> ```
> python -m pip install pip install --upgrade
> ```
>
> 命令来更新pip，然后再执行下载依赖

## 项目结构

项目目录如下：

```
│  README.md  - 项目说明
│  requirements.txt  - 项目依赖
│  
├─backend  - 后端代码 
│      config.properties  - 后端配置文件
│      main.s  - 后端执行程序代码 
│      
└─pycomm  - python相关代码 
    │  app_fe.py  - 前端启动程序 
    │  app_mw.py  - 中间件启动程序
    │  
    └─app
            app.ui  - PyQt编写的GuiUI
            comm.py  - 网络通讯模块
            config.py  - 前端和中间件配置文件
            FE.py  - 前端模块
            MW.py  - 中间件模块
            __init__.py
```

项目运行基于三个进程：

1. 后端（DM进程）
2. 中间件（Python编写的中间件程序）
3. 前端（由PyQt5编写的GUI程序）

### 后端进程

后端DM所支持的接口中具有读写文件的能力，采用文件作为管道，构建一条输入管道（Input Pipline）和一条输出管道（Output Pipline），分别负责 **接收消息** 和 **写出消息** 

基于此后端进程启动后**至少存在三个**运行的子线程：

- `管道读取线程(InputThread)` - 负责读取**输入**管道消息，将消息封装成为**任务**提交给`任务执行线程`
- `任务执行线程(TaskThread)` - 读取**任务**，派发给执行器（Dispatcher），执行器会在执行完毕后将结果提交给`管道写出线程`
- `管道写出线程(OutputThread)` - 获取执行器的结果，处理成为消息格式，写入输出管道中

每一条消息在到达后端进程都会经理这样的处理过程

### 中间件进程

中间件是为了解耦前后端之间的强绑定关系出现的，它一方面采用文件的形式和后端DM进程建立连接，另一方面采用socket的形式和前端进程建立连接，实现两方的通讯

它由5个部分组成：

- `连接构建器(ConnectionBuilder)` - 采用socket，监听前端的连接，接收得到连接之后会将连接提交给`连接上下文`管理
- `连接上下文(ConnectionContext)` - 统一管理 **连接线程** 和 **连接对象**，在适当的时候关闭连接或者停止线程
- `请求管道(RequestPipline)` - 前端提交的请求会在这里被缓存，随后会被提交给写线程写入管道文件
- `响应管道(ResponsePipline)` - 后端响应的消息会在这里被缓存，随后会被通过连接上下文提交给指定的前端
- `管道写线程(PipWriter)` - 读取`请求消息管道`中的消息，写入输入管道文件
- `管道读线程(PipReader)` - 读取由后端写入输出管道中的消息并提交给`响应管道`

### 前端进程

可以存在多个前端进程，也可以仅存在一个，它通过socket建立和中间件的连接，采用`comm`网络模块中定义的Message作为消息格式

## 启动项目

### 后端进程

在启动项目之前需要对后端程序进行简要配置：

在后端程序的配置文件`backend/config.properties`中存在如下配置：

```properties
input_pip_path=D:/Desktop/Note/Python/Python_Projects/continuous_acquire-main/temp/dm_in.pip
input_pip_lock=D:/Desktop/Note/Python/Python_Projects/continuous_acquire-main/temp/dm_in.lock
output_pip_path=D:/Desktop/Note/Python/Python_Projects/continuous_acquire-main/temp/dm_out.pip
output_pip_lock=D:/Desktop/Note/Python/Python_Projects/continuous_acquire-main/temp/dm_out.lock
```

在项目启动之前应该把路径配置到一个存在的目录下，目录将用于存放生成的管道文件，以及控制读写进程之间互斥的锁文件，来保证读写操作的原子性

如果保留项目原本配置可能会因为路径不存在而无法启动项目

首先启动后端进程，即DM进程，直接在Micrograph中通过`File -> Open`来找到`backend\main.s`脚本文件，脚本文件58行处存在对脚本根路径的指定，这里指的是项目根路径

运行之前需要确保这个路径被正确修改到项目根路径下

```c#
string ROOT_DIR = "D:\\Desktop\\Note\\Python\\Python_Projects\\continuous_acquire-main\\backend"
string CONFIG_PATH = ROOT_DIR + "\\config.properties"
```

完成上述修改之后可以点击Execute按钮启动后端程序

后端程序携带简易GUI界面，可以用于执行简单的启动和停止操作，通过析构函数，关闭后端程序时其下所有子线程也会被关闭

### 前端和中间件

关于前端和中间件，pycomm中的`app_fe.py`和`app_mw.py`作为项目提供简单测试脚本，可以单独启动前端或者中间件程序，在虚拟环境下进入`pycomm`目录后，执行：

```
python app_mw.py
python app_ft.py
```

来分别启动中间件程序和前端程序

> 注：项目除开后端采用绝对路径，其余部分均使用相对路径，因此启动的位置可能会影响程序能否正确运行，以上两个脚本文件最好在pycomm下直接启动

> 注：三者应该按照`后端 -> 中间件 -> 前端`的顺序进行启动

中间件为命令行执行，通过`restart`命令来快速重启，`quit`命令来退出程序

 


            

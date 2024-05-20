# 客户端界面配置
UI_FONT = 'consolas'  # 默认字体
UI_PATH = './app/app.ui'  # UI路径设定
UI_FONTSIZE = 8  # 默认字体大小
UI_ENABLE_LOG = True  # 是否启用日志输出窗口
UI_EXPOSURE = 1  # 曝光
UI_X_BIN = 1
UI_Y_BIN = 1
# 连接配置
CONNECT_HOST = '127.0.0.1'  # 连接目标地址
CONNECT_PORT = 25565  # 端口号
CONNECT_TIMEOUT = 3  # 超时时间
CONNECT_ENCODING = 'gbk'  # 采用编码
# 横移连拍配置
XY_X_OFF = 0  # x，y轴偏移量
XY_Y_OFF = 0
XY_ENABLE_EXTENSION = True  # 是否启用拓展
XY_EXTENSION_UNIT = 0  # 拓展单位， 0：px、1：%
XY_X_SPLIT = 2
XY_Y_SPLIT = 2
# 单点连拍配置
SP_AREA_T = 0  # 默认TOP坐标
SP_AREA_L = 0  # 默认LEFT坐标
SP_AREA_B = 0  # 默认BOTTOM坐标
SP_AREA_R = 0  # 默认RIGHT坐标
SP_ENABLE_DURATION = True  # 是否开启持续时间
SP_DURATION_VALUE = 5  # 默认持续时间
SP_DURATION_UNIT = 0  # 持续连拍默认采用时间单位
SP_FRAMERATE = 1  # 默认帧率
SP_ENABLE_OPTIMIZE = True  # 是否启用坐标修正
# 中间件配置
BE_CONFIG_PATH = '../backend/config.properties'
LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 25565
LISTEN_TIMEOUT = 3
LISTEN_ENCODING = 'gbk'

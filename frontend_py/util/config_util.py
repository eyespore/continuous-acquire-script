from loguru import logger
import yaml

"""
前端进程配置类
"""
config = {}  # 程序配置字典，通过字典来获取程序配置
CONFIG_PATH = f'./util/config.yaml'  # yaml配置文件路径设定

# 尝试读取配置，如果配置存在错误则会采用默认配置
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    yml_cfg = yaml.safe_load(f)

    logger.debug(f'Loading config, yaml config path: {CONFIG_PATH}')

    def load_val(val_path, yml_sup, def_val):
        # 加载配置文件并且将值用于参数初始化
        try:
            yml_val = yml_sup()
            if type(yml_val) is not type(def_val):
                logger.error(
                    f'\'{val_path}\' is in wrong type, expect {type(def_val)} but receive {type(yml_val)}, using default value: {def_val}')
                config[val_path] = def_val
                return

            # 如果参数为list需要额外判断
            if type(yml_val) is list:
                # 判断长度是否相等
                if len(yml_val) != len(def_val):
                    logger.error(
                        f'\'{val_path}\' bad given params in list, expect {len(def_val)} elements but receive {len(yml_val)}, using default value: {def_val}')
                    config[val_path] = def_val
                    return

                # 判断每一位上面元素类型是否相等
                for index, element in enumerate(yml_val):
                    if type(element) is not type(def_val[index]):
                        logger.error(
                            f'\'{val_path}\' bad given params in list, expect {type(def_val[index])} for index {index}, but receive {type(element)}, using default value: {def_val}')
                    config[val_path] = def_val
                    return

            config[val_path] = yml_val
        except KeyError as e:
            logger.error(f'\'{val_path}\' has not been defined in yaml config, using default value: {def_val}')
            config[val_path] = def_val


    # 通过yml_path来获取yml配置文件参数，以list的形式传入

    # xy轴连续横移拍摄参数初始化
    load_val('exposure', lambda: yml_cfg['ui']['xy']['exposure'], 1000)  # 曝光度默认值
    load_val('x_bin', lambda: yml_cfg['ui']['xy']['x_bin'], 1)  # x_bin默认值
    load_val('y_bin', lambda: yml_cfg['ui']['xy']['y_bin'], 1)  # y_bin默认值
    load_val('x_off', lambda: yml_cfg['ui']['xy']['x_off'], 0)  # x轴拓展默认值
    load_val('y_off', lambda: yml_cfg['ui']['xy']['y_off'], 0)  # y轴拓展默认值
    load_val('enable_extension', lambda: yml_cfg['ui']['xy']['enable_extension'], 0)  # 是否启用边界拓展
    load_val('extension_unit', lambda: yml_cfg['ui']['xy']['extension_unit'], 0)  # 边界拓展默认单位，0：px、1：%
    load_val('x_splitting_format', lambda: yml_cfg['ui']['xy']['x_splitting_format'], 2)  # x轴默认切割格式
    load_val('y_splitting_format', lambda: yml_cfg['ui']['xy']['y_splitting_format'], 2)  # y轴默认切割格式
    load_val('multi_thread_num', lambda: yml_cfg['ui']['xy']['multi_thread_num'], 10)  # 默认线程数
    load_val('multi_process_num', lambda: yml_cfg['ui']['xy']['multi_process_num'], 5)  # 默认线程数

    # 单点连续拍摄参数初始化
    load_val('pos_for_sp', lambda: yml_cfg['ui']['sp']['pos_for_sp'],
             [0, 0, 0, 0])  # 默认坐标参数，从上到下依次是top,left,bottom,right
    load_val('enable_duration', lambda: yml_cfg['ui']['sp']['enable_duration'], False)  # 是否开启持续时间
    load_val('duration_value', lambda: yml_cfg['ui']['sp']['duration_value'], 10)  # 默认持续时间
    load_val('duration_unit', lambda: yml_cfg['ui']['sp']['duration_unit'], 1)  # 持续连拍默认采用时间单位
    load_val('framerate', lambda: yml_cfg['ui']['sp']['framerate'], 10)  # 持续连拍默认采用时间单位

    # 界面参数设定
    load_val('font', lambda: yml_cfg['ui']['nor']['font'], 'consolas')
    load_val('font_size', lambda: yml_cfg['ui']['nor']['font_size'], 8)
    load_val('enable_log', lambda: yml_cfg['ui']['nor']['enable_log'], True)
    load_val('server_host', lambda: yml_cfg['server']['host'], '127.0.0.1')
    load_val('server_port', lambda: yml_cfg['server']['port'], 25565)
    load_val('server_timeout', lambda: yml_cfg['server']['timeout'], 3)

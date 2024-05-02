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

    load_val('backend_config', lambda: yml_cfg['path']['backend_config'], '')  # 后端配置文件路径
    load_val('server_host', lambda: yml_cfg['server']['host'], '127.0.0.1')  # 连接主机
    load_val('server_port', lambda: yml_cfg['server']['port'], 25565)  # 连接端口
    load_val('server_timeout', lambda: yml_cfg['server']['timeout'], 3)  # 连接超时时间


"""
环境参数初始化脚本
"""
import DigitalMicrograph as DM
from DigitalMicrograph import Py_TagGroup

GLOBAL_TAGS: Py_TagGroup = DM.GetPersistentTagGroup()

# 全局参数路径
SCRIPT_LABEL = 'ContinuousAcquireScript'


class TagUtil(object):

    @staticmethod
    def tags_to_dict():
        return GLOBAL_TAGS.GetTagAsTagGroup(SCRIPT_LABEL)

    @staticmethod
    def dict_to_tags(param: dict, tags: Py_TagGroup, prefix: str = ''):
        """
        能够将字典直接作为元素插入TagGroup当中
        :param prefix: 路径前缀
        :param tags: 目的地
        :param param:  插入元素，以字典的形式保存
        :return:
        """
        for path, data in param.items():
            # path为当前层级目录，data为对应的数据，要求标签名必须为字符串作为路径
            rel_path = prefix + (":" if prefix != '' else '') + path

            if type(path) is not str:
                break
            # 如果数据不是字典，那么可以直接添加元素
            elif type(data) is str:
                tags.SetTagAsString(rel_path, data)
            elif type(data) is int:
                tags.SetTagAsUInt16(rel_path, data)
            elif type(data) is float:
                tags.SetTagAsFloat(rel_path, data)
            elif type(data) is dict:
                # 如果数据类型为字典，那么需要逐级向下添加
                TagUtil.dict_to_tags(data, tags, rel_path)

    @staticmethod
    def init_env():
        """
        初始化全局参数
        """
        # 首先删除原有标签组
        flag = GLOBAL_TAGS.DeleteTagWithLabel(SCRIPT_LABEL)
        if flag:
            print('successfully remove original tag group')

        # 通过dict创建标签组
        TagUtil.dict_to_tags({
            "ContinuousAcquireScript": {
                "XYContinuousAcquire": {
                    "DEF_EXPOSURE": 1000,
                    "DEF_X_BIN": 1,
                    "DEF_Y_BIN": 1,
                },
                "SinglePointAcquire": {
                    "DEF_FRAME_RATE": 10
                }
            },
        }, GLOBAL_TAGS)
        ...


if __name__ == '__main__':
    print(TagUtil.tags_to_dict())
    GLOBAL_TAGS.OpenBrowserWindow(False)

class MathUtil:
    """
    数学函数定义
    """

    @staticmethod
    def clamp(val, min_val, max_val):
        """
        Clamp value between min_val and max_val
        """
        if val <= min_val:
            return min_val
        if val >= max_val:
            return max_val
        return val

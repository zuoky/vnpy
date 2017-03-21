# encoding: UTF-8

"""

一个基于tick级别细粒度撤单追单的交易策略，适合用在商品期貨的数据上。

"""

from datetime import datetime

from ctaBase import *
from vtConstant import STATUS_NOTTRADED, STATUS_CANCELLED, STATUS_ALLTRADED
from ctaTemplate import CtaTemplate


########################################################################
class FishingTicksStrategy(CtaTemplate):
    """Fishing Strategy"""
    className = 'FishingTicksStrategy'
    author = 'zuoky'

    # 策略参数
    orderTimeout = 1000    # In Milliseconds, cancel the order if it didn't get executed within the orderTimeout.
    initDays = 10          # 初始化数据所用的天数

    # 策略变量
    lastOrder = None
    lastDirection = EMPTY_FLOAT # Speculative Direction for the price movements, positive for moving up, vice versa.
    currentDirection = EMPTY_FLOAT
    currentSpread = EMPTY_FLOAT # Bid-Ask Spread

    cancelledOrders = []   # Orders have been cancelled
    executedOrders = []    # Orders have been executed


    # 参数列表，保存了参数的名称
    paramList = ['name',
                 'className',
                 'author',
                 'vtSymbol',
                 'orderTimeout']

    # 变量列表，保存了变量的名称
    varList = ['inited',
               'trading',
               'pos',
               'lastOrder',
               'lastDirection',
               'currentDirection',
               'currentSpread',]

    #----------------------------------------------------------------------
    def __init__(self, ctaEngine, setting):
        """Constructor"""
        super(FishingTicksStrategy, self).__init__(ctaEngine, setting)

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）
        self.cancelledOrders = []
        self.executedOrders = []

    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog('Fishing Ticks Strategy Initialized')

        initData = self.loadTick(self.initDays)
        for bar in initData:
            self.onTick(bar)

        self.putEvent()

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog('Fishing Ticks Strategy Started')
        self.putEvent()

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog('Fishing Ticks Strategy Stopped')
        self.putEvent()

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.currentSpread = tick.askPrice1 - tick.bidPrice1
        self.lastDirection = self.currentDirection
        self.currentDirection = self.get_direction(tick)

        if self.lastOrder:
            if self.lastOrder.status == STATUS_NOTTRADED:
                # No further inoformation for order submitted
                if self.lastOrder.orderTime - datetime.now().time() >= self.orderTimeout:
                    self.cancelOrder(self.lastOrder.vtOrderID)
                    self.cancelledOrders.append(self.lastOrder.vtOrderID)
                    self.lastOrder = None
                else:
                    pass # 让子弹飞

            elif self.lastOrder.status == STATUS_CANCELLED:
                # Order Cancelled
                self.__submit_order_following_direction__(tick)

            elif self.lastOrder.status == STATUS_ALLTRADED:
                # Order executed, reverse the action now
                self.executedOrders.append(self.lastOrder.vtOrderID)

                self.__submit_order_reversing_direction__(tick)

        # 根据tick买卖双方力量对比建立买单测试单
        if not self.lastOrder:
            self.__submit_order_following_direction__(tick)

    def should_reverse_position(last_direction, cur):
        pass

#----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        pass

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder
        self.lastOrder = order

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onTrade
        pass


    def __submit_order_following_direction__(self, tick):
        if self.currentDirection > 0:  # 方向为正，向上试单
            self.buy(tick.bidPrice1 + 1.0, tick.bidVolume1)

        elif self.currentDirection < 0:  # 方向为负，向下试单
            self.sell(tick.askPrice1 - 1.0, tick.askVolume1)

        else:  # 方向不好判断，略过这次tick
            pass


    def __submit_order_reversing_direction__(self, tick):
        pass


    @staticmethod
    def get_direction(tick):
        """根据拿到的Tick信息，计算出将来可能的价位方向值"""

        bid_price = tick.bidPrice1
        bid_volume = tick.bidVolume1
        ask_price = tick.askPrice1
        ask_volume = tick.askVolume1

        # 现在只是计算出中间价与volume加权的期望成交价格的差额
        # 将来应该用其他算法来实现，比如深度学习（时序神经网络）
        median_price = (ask_price + bid_price) / 2
        volume_adjusted_mean_price = (ask_price * ask_volume - bid_price * bid_volume) / (ask_volume + bid_volume) - bid_price
        return median_price - volume_adjusted_mean_price


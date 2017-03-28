# encoding: UTF-8

"""

一个基于tick级别细粒度撤单追单的交易策略，适合用在商品期貨的数据上。

"""

from datetime import datetime

from ctaBase import *
from ctaTemplate import CtaTemplate


########################################################################
class NanoMomentumStrategy(CtaTemplate):
    """Fishing Strategy"""
    className = 'NanoMomentumStrategy'
    author = 'zuoky'

    # 策略参数
    orderTimeout = 1000    # In Milliseconds, cancel the order if it didn't get executed within the orderTimeout.
    orderDeadTime = 1500   # In Milliseconds, flatten the position if the order had been executed times ago
    initDays = 1           # 初始化数据所用的天数

    # 策略变量
    lastPrice = EMPTY_INT
    lastPriceDirection = EMPTY_INT
    lastTick = None

    currentPrice = EMPTY_INT
    currentPriceDirection = EMPTY_INT
    currentTick = None
    currentOrder = None
    currentCost = EMPTY_INT
    currentOrderExecutionTime = None

    pendingOrders = {}   # Orders have been submitted and pending execution


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
               'lastPrice',
               'lastPriceDirection',
               'lastTick',
               'currentPrice',
               'currentPriceDirection',
               'currentTick',
               'currentOrder',
               'currentCost',
               'currentOrderExecutionTime']

    #----------------------------------------------------------------------
    def __init__(self, cta_engine, setting):
        """Constructor"""
        super(NanoMomentumStrategy, self).__init__(cta_engine, setting)

        # 注意策略类中的可变对象属性（通常是list和dict等），在策略初始化时需要重新创建，
        # 否则会出现多个策略实例之间数据共享的情况，有可能导致潜在的策略逻辑错误风险，
        # 策略类中的这些可变对象属性可以选择不写，全都放在__init__下面，写主要是为了阅读
        # 策略时方便（更多是个编程习惯的选择）
        self.pendingOrders = {}

    #----------------------------------------------------------------------
    def onInit(self):
        """初始化策略（必须由用户继承实现）"""
        self.writeCtaLog('Nano Momentum Strategy Initialized')

        init_data = self.loadTick(self.initDays)
        for tick in init_data:
            self.onTick(tick)

        self.putEvent()

    #----------------------------------------------------------------------
    def onStart(self):
        """启动策略（必须由用户继承实现）"""
        self.writeCtaLog('Nano Momentum Strategy Started')
        self.putEvent()

    #----------------------------------------------------------------------
    def onStop(self):
        """停止策略（必须由用户继承实现）"""
        self.writeCtaLog('Nano Momentum Strategy Stopped')
        self.putEvent()

    #----------------------------------------------------------------------
    def onTick(self, tick):
        """收到行情TICK推送（必须由用户继承实现）"""
        self.lastTick = self.currentTick
        self.currentTick = tick
        self.currentPriceDirection = self.currentPrice - self.lastPrice
        self.lastPrice = self.currentPrice
        self.currentPriceDirection = self.currentTick.lastPrice - self.currentPrice
        self.currentPrice = self.currentTick.lastPrice

        current_time = datetime.now().time()

        # Cancel pending orders if timeout
        for vtOrderID, orderTime in self.pendingOrders.iteritems():
            if current_time - orderTime >= self.orderTimeout:
                self.writeCtaLog('Strategy decides to cancel pending order: {}'.format(vtOrderID))
                self.cancelOrder(vtOrderID)

        # When to buy
        # 1. Current Price Increase
        # 2. Current Price = Ask Price
        # 3. Same pattern applied in two ticks -> last price direction > 0
        if self.currentPriceDirection > 0 \
                and self.currentPrice == self.currentTick.askPrice1 \
                and self.lastPriceDirection > 0:
            self.writeCtaLog('Strategy decides to seek for long position according to buy-1')
            self.target_long_position(self.currentTick.bidPrice1,
                                      self.currentTick.askPrice1,
                                      self.currentTick.bidVolume1)
            return

        # When to hold
        # 1. Bid Price Increase
        # OR
        # 1. Bid Price stay same
        # 2. Current Price >= our cost
        # 3. Current Price stay same or increase
        if self.currentTick.bidPrice1 > self.lastTick.bidPrice1:
            self.writeCtaLog('Strategy decides to hold position according to hold-1')
            return

        if self.currentTick.bidPrice1 == self.lastTick.bidPrice1 \
                and self.currentPrice >= self.currentCost \
                and self.currentPriceDirection >= 0:
            self.writeCtaLog('Strategy decides to hold position according to hold-2')
            return

        # When to flatten
        # 1. If hold more than orderDeadTime
        # OR
        # 1. Bid Price Decrease
        # 2. Current Price = Bid Price
        # OR
        # 1. Current Price > Current Cost But decreasing
        # OR
        # 1. Current Price <= Current Cost
        if self.currentOrderExecutionTime \
                and current_time - self.currentOrderExecutionTime >= self.orderDeadTime:
            self.writeCtaLog('Strategy decides to flatten position according to flatten-1')
            self.flatten_position(self.currentTick.bidPrice1, self.currentTick.askPrice1)
            return

        if self.lastTick.bidPrice1 < self.currentTick.bidPrice1 == self.currentPrice:
            self.writeCtaLog('Strategy decides to flatten position according to flatten-2')
            self.flatten_position(self.currentTick.bidPrice1, self.currentTick.askPrice1)
            return


        if self.currentPrice > self.currentCost and self.currentPriceDirection < 0:
            self.writeCtaLog('Strategy decides to flatten position according to flatten-3')
            self.flatten_position(self.currentTick.bidPrice1, self.currentTick.askPrice1)
            return

        if self.currentPrice <= self.currentCost:
            self.writeCtaLog('Strategy decides to flatten position according to flatten-4')
            self.flatten_position(self.currentTick.bidPrice1, self.currentTick.askPrice1)
            return

    #----------------------------------------------------------------------
    def onBar(self, bar):
        """收到Bar推送（必须由用户继承实现）"""
        pass

    #----------------------------------------------------------------------
    def onOrder(self, order):
        """收到委托变化推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onOrder

        # Only traded order will get onOrder(_) triggered
        self.pendingOrders.pop(order.vtOrderID, None)
        self.currentOrder = order

    #----------------------------------------------------------------------
    def onTrade(self, trade):
        """收到成交推送（必须由用户继承实现）"""
        # 对于无需做细粒度委托控制的策略，可以忽略onTrade
        self.currentOrderExecutionTime = datetime.now().time()
        self.currentCost = trade.price

        # 发出状态更新事件
        self.putEvent()


    def target_long_position(self, bid_price, ask_price, target_pos):
        current_time = datetime.now().time()
        current_position = self.pos
        self.writeCtaLog(
            'Strategy targets long position [{}], current position [{}]'.format(target_pos, current_position))

        if target_pos <= 0:
            raise ValueError("target_pos[{}] should not be zero/negative in target_long_position".format(target_pos))

        if current_position > 0:
            diff = target_pos - current_position
            if diff > 0:  # Need more long position
                order_id = self.buy(bid_price, diff)
                self.pendingOrders[order_id] = current_time
            elif diff < 0:  # Need less long position
                order_id = self.sell(ask_price, abs(diff))
                self.pendingOrders[order_id] = current_time
            else:  # No change needed
                pass
        elif current_position < 0:
            cover_order_id = self.cover(bid_price, abs(current_position))
            buy_order_id = self.buy(bid_price, target_pos)
            self.pendingOrders[cover_order_id] = current_time
            self.pendingOrders[buy_order_id] = current_time

        else:  # No position now
            order_id = self.buy(bid_price, target_pos)
            self.pendingOrders[order_id] = current_time

        self.putEvent()


    def flatten_position(self, bid_price, ask_price):
        current_time = datetime.now().time()
        current_position = self.pos
        self.writeCtaLog('Strategy targets flatten position, current position [{}]'.format(current_position))

        if current_position > 0:
            order_id = self.sell(ask_price, current_position)
            self.pendingOrders[order_id] = current_time
        elif current_position < 0:
            order_id = self.cover(bid_price, abs(current_position))
            self.pendingOrders[order_id] = current_time
        else:
            pass

        self.putEvent()


    def target_short_position(self, bid_price, ask_price, target_pos):
        current_time = datetime.now().time()
        current_position = self.pos
        self.writeCtaLog(
            'Strategy targets short position [{}], current position [{}]'.format(target_pos, current_position))

        if target_pos >= 0:
            raise ValueError("target_pos[{}] should not be zero/positive in target_short_position".format(target_pos))

        if current_position < 0:
            diff = target_pos - current_position
            if diff < 0:  # Need more short position
                order_id = self.short(ask_price, abs(diff))
                self.pendingOrders[order_id] = current_time
            elif diff > 0:  # Need less short position
                order_id = self.cover(bid_price, diff)
                self.pendingOrders[order_id] = current_time
            else:  # No change needed
                pass
        elif current_position > 0:
            sell_order_id = self.sell(ask_price, current_position)
            short_order_id = self.short(ask_price, abs(target_pos))
            self.pendingOrders[sell_order_id] = current_time
            self.pendingOrders[short_order_id] = current_time

        else:  # No position now
            order_id = self.short(ask_price, abs(target_pos))
            self.pendingOrders[order_id] = current_time

        self.putEvent()

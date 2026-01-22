# PTrade多因子策略入门

# PTrade适配说明：
# 1. 股票代码后缀：.XSHG → .SS (上交所), .XSHE → .SZ (深交所)
# 2. 佣金/滑点设置函数语法调整
# 3. 财务数据查询方式改为PTrade的get_fundamentals
# 4. attribute_history → get_history
# 5. get_current_data → get_snapshot (停牌判断)
# 6. 持仓获取方式调整
# 7. 回测时间2005-1-01到2016-12-31回测结果450.95%

import numpy as np
from math import isnan
import datetime

'''
================================================================================
总体回测前
================================================================================
'''

def initialize(context):
    """初始化函数，策略启动时运行一次"""
    set_params()        # 1.设置策略参数
    set_variables()     # 2.设置中间变量
    set_backtest()      # 3.设置回测条件


def set_params():
    """设置策略参数"""
    g.tc = 15           # 调仓频率（天）
    g.yb = 63           # 样本长度（天）
    g.N = 20            # 持仓数目
    # 用户选出来的因子（使用PTrade的valuation表字段）
    # market_cap对应total_value(A股总市值), roe在valuation表中可获取
    g.factors = ["total_value", "roe"]
    # 因子等权重：1表示因子值越小越好，-1表示因子值越大越好
    # 市值小优先(1)，ROE大优先(-1)
    g.weights = [[1], [-1]]


def set_variables():
    """设置中间变量"""
    g.t = 0             # 记录回测运行的天数
    g.if_trade = False  # 当天是否交易
    g.all_stocks = []   # 可行股票池


def set_backtest():
    """设置回测条件"""
    # PTrade的佣金设置（仅回测有效）
    # 默认佣金费率万分之三，最低5元
    set_commission(commission_ratio=0.0003, min_commission=5.0)
    # 设置固定滑点为0
    set_fixed_slippage(fixedslippage=0.0)


'''
================================================================================
每天开盘前
================================================================================
'''

def before_trading_start(context, data):
    """每天开盘前要做的事情"""
    if g.t % g.tc == 0:
        # 每g.tc天，交易一次
        g.if_trade = True
        # 根据不同时间段设置手续费（仅回测有效）
        set_slip_fee(context)
        # 设置可行股票池：获得当前开盘的沪深300股票池并剔除停牌股票
        # PTrade中沪深300指数代码为 000300.SS 或 399300.SZ
        hs300_stocks = get_index_stocks('000300.SS')
        g.all_stocks = set_feasible_stocks(hs300_stocks, g.yb, context)
    g.t += 1


def set_feasible_stocks(stock_list, days, context):
    """
    设置可行股票池
    过滤掉当日停牌的股票,且筛选出前days天未停牌股票
    
    参数:
        stock_list: 股票列表(list)
        days: 样本天数(int)
        context: 上下文对象
    返回:
        可行股票列表(list)
    """
    if not stock_list:
        return []
    
    feasible_stocks = []
    
    for stock in stock_list:
        try:
            # 使用get_history获取历史成交量，成交量为0表示停牌
            # 多取1天用于判断当日是否停牌（include=True包含当日）
            hist = get_history(days + 1, '1d', 'volume', security_list=stock, include=True)
            
            if hist is None or len(hist) == 0:
                continue
            
            # 检查是否有停牌（成交量为0）
            # 如果过去days+1天内没有任何停牌，则加入可行股票池
            if 'volume' in hist.columns:
                vol_data = hist['volume']
            else:
                vol_data = hist.iloc[:, 0]  # 单股票返回时列名可能不同
            
            # 统计成交量为0的天数
            suspend_days = (vol_data == 0).sum()
            
            if suspend_days == 0:
                feasible_stocks.append(stock)
                
        except Exception as e:
            # 出错的股票跳过
            log.debug(f"股票{stock}检查停牌出错: {e}")
            continue
    
    return feasible_stocks


def set_slip_fee(context):
    """根据不同的时间段设置滑点与手续费"""
    # 将滑点设置为0
    set_fixed_slippage(fixedslippage=0.0)
    
    # 根据不同的时间段设置手续费
    # PTrade中 set_commission 参数为 commission_ratio 和 min_commission
    dt = context.blotter.current_dt
    
    if dt > datetime.datetime(2013, 1, 1):
        # 2013年后：买入万3，卖出万13（含印花税千1）
        set_commission(commission_ratio=0.0003, min_commission=5.0)
    elif dt > datetime.datetime(2011, 1, 1):
        set_commission(commission_ratio=0.001, min_commission=5.0)
    elif dt > datetime.datetime(2009, 1, 1):
        set_commission(commission_ratio=0.002, min_commission=5.0)
    else:
        set_commission(commission_ratio=0.003, min_commission=5.0)


'''
================================================================================
每天交易时
================================================================================
'''

def handle_data(context, data):
    """盘中函数，按频率运行"""
    if g.if_trade:
        if not g.all_stocks:
            log.info("可行股票池为空，跳过本次交易")
            g.if_trade = False
            return
            
        # 计算现在的总资产，以分配资金，这里是等额权重分配
        g.everyStock = context.portfolio.portfolio_value / g.N
        
        # 获得今天日期的字符串 (格式: YYYYMMDD)
        todayStr = context.blotter.current_dt.strftime('%Y%m%d')
        
        # 获得因子排序
        a, b = getRankedFactors(g.factors, todayStr)
        
        if a is None or b is None or len(a) == 0:
            log.info("获取因子数据失败，跳过本次交易")
            g.if_trade = False
            return
        
        # 计算每个股票的得分
        points = np.dot(a, g.weights)
        
        # 复制股票代码
        stock_sort = list(b[:])
        
        # 对股票的得分进行排名
        points, stock_sort = bubble(points, stock_sort)
        
        # 取前N名的股票
        toBuy = stock_sort[0:min(g.N, len(stock_sort))]
        
        # 对于不需要持仓的股票，全仓卖出
        order_stock_sell(context, data, toBuy)
        
        # 对于需要持仓的股票，按分配到的份额买入
        order_stock_buy(context, data, toBuy)
    
    g.if_trade = False


def order_stock_sell(context, data, toBuy):
    """
    获得卖出信号，并执行卖出操作
    
    参数:
        context: 上下文对象
        data: 数据对象
        toBuy: 需要买入的股票列表
    """
    # PTrade中使用get_positions()获取持仓
    positions = get_positions()
    
    for stock in positions:
        if stock not in toBuy:
            # 将持仓调整到0（卖出）
            order_target(stock, 0)
            log.info(f"卖出股票: {stock}")


def order_stock_buy(context, data, toBuy):
    """
    获得买入信号，并执行买入操作
    
    参数:
        context: 上下文对象
        data: 数据对象
        toBuy: 需要买入的股票列表
    """
    for stock in toBuy:
        # 按分配到的金额买入
        order_target_value(stock, g.everyStock)
        log.info(f"买入股票: {stock}, 目标金额: {g.everyStock:.2f}")


def indexOf(e, a):
    """
    查找一个元素在数组里面的位置，如果不存在则返回-1
    
    参数:
        e: 元素
        a: 数组
    返回:
        位置索引，不存在返回-1
    """
    for i in range(len(a)):
        if e == a[i]:
            return i
    return -1


def getRankedFactors(factors, date):
    """
    取因子数据并排序
    
    参数:
        factors: 因子列表
        date: 日期字符串(YYYYMMDD)
    返回:
        (排序后的因子数据, 股票代码列表)
    """
    if not g.all_stocks:
        return None, None
    
    try:
        # PTrade中获取财务数据
        # 从valuation表获取total_value和roe
        df = get_fundamentals(
            g.all_stocks, 
            'valuation', 
            fields=['total_value', 'roe', 'secu_code'],
            date=date
        )
        
        if df is None or len(df) == 0:
            log.info(f"获取财务数据为空: {date}")
            return None, None
        
        # 获取股票代码列表
        if 'secu_code' in df.columns:
            stock_codes = df['secu_code'].tolist()
        else:
            stock_codes = df.index.tolist()
        
        # 构建因子数据数组
        res = []
        for i in range(len(df)):
            row_data = []
            for f in factors:
                if f in df.columns:
                    val = df[f].iloc[i]
                    # 处理roe字段（可能是百分比字符串）
                    if f == 'roe' and isinstance(val, str) and '%' in val:
                        val = float(val.replace('%', '')) / 100
                    row_data.append(val if val is not None else np.nan)
                else:
                    row_data.append(np.nan)
            res.append(row_data)
        
        # 用均值填充NaN值
        fillNan(res)
        
        # 将数据变成排名
        getRank(res)
        
        return res, stock_codes
        
    except Exception as e:
        log.error(f"获取因子数据出错: {e}")
        return None, None


def getRank(r):
    """
    把每列原始数据变成排序的数据
    
    参数:
        r: 二维列表
    返回:
        排名后的二维列表
    """
    if not r or not r[0]:
        return r
    
    # 定义一个临时数组记住一开始的顺序
    indexes = list(range(len(r)))
    
    # 对每一列进行冒泡排序
    for k in range(len(r[0])):
        for i in range(len(r)):
            for j in range(i):
                if r[j][k] < r[i][k]:
                    # 交换所有的列以及用于记录一开始的顺序的数组
                    indexes[j], indexes[i] = indexes[i], indexes[j]
                    for l in range(len(r[0])):
                        r[j][l], r[i][l] = r[i][l], r[j][l]
        # 将排序好的因子顺序变成排名
        for i in range(len(r)):
            r[i][k] = i + 1
    
    # 再进行一次冒泡排序恢复一开始的股票顺序
    for i in range(len(r)):
        for j in range(i):
            if indexes[j] > indexes[i]:
                indexes[j], indexes[i] = indexes[i], indexes[j]
                for k in range(len(r[0])):
                    r[j][k], r[i][k] = r[i][k], r[j][k]
    
    return r


def fillNan(m):
    """
    用均值填充NaN
    
    参数:
        m: 二维列表
    返回:
        填充后的二维列表
    """
    if not m or not m[0]:
        return m
    
    rows = len(m)
    columns = len(m[0])
    
    # 对每一列进行操作
    for j in range(columns):
        sum_val = 0.0
        count = 0.0
        
        # 计算非NaN值的总和和个数
        for i in range(rows):
            val = m[i][j]
            if val is not None and not isnan(val):
                sum_val += val
                count += 1
        
        # 计算平均值
        avg = sum_val / max(count, 1)
        
        # 用平均值填充NaN
        for i in range(rows):
            val = m[i][j]
            if val is None or isnan(val):
                m[i][j] = avg
    
    return m


def bubble(numbers, indexes):
    """
    冒泡排序函数
    
    参数:
        numbers: 股票的综合得分(list)
        indexes: 股票列表(list)
    返回:
        (排序后的得分, 排序后的股票列表)
    """
    n = len(numbers)
    # 转换为列表以支持交换
    indexes = list(indexes)
    
    for i in range(n):
        for j in range(i):
            if numbers[j][0] < numbers[i][0]:
                # 在进行交换的时候同时交换得分以记录哪些股票得分比较高
                numbers[j][0], numbers[i][0] = numbers[i][0], numbers[j][0]
                indexes[j], indexes[i] = indexes[i], indexes[j]
    
    return numbers, indexes


'''
================================================================================
每天收盘后
================================================================================
'''
def after_trading_end(context, data):
    """每日收盘后要做的事情"""
    log.info(f"====== 交易日结束: {context.blotter.current_dt} ======")
    log.info(f"当日持仓数量: {len(get_positions())}")
    log.info(f"账户总资产: {context.portfolio.portfolio_value:.2f}")
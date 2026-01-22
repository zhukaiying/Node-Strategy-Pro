# 四大搅屎棍策略 - PTrade适配版
# 
# 策略核心逻辑：
# 1. 市场环境判断：识别“存量博弈”环境
# 2. 行业对冲：当银行/煤炭/钢铁/有色领涨时，视为防御信号，策略空仓
# 3. 选股因子：小市值 + ROE/ROA双重财务筛选 (质优小盘股)
#
# 原理参考：多因子策略系列 
#
# PTrade 适配作者: 节点量化 (Node Quant)
# 适用平台:  PTrade 交易终端
# 原回测条件：2012-01-01 到 2024-07-11, ￥100000, 每天 586.45%
# 行业代码格式：申万行业代码需加.XBHS后缀

import numpy as np
import pandas as pd
import datetime 
import talib

# 申万一级行业代码映射
SW1 = {
    '801010': '农林牧渔I',
    '801020': '采掘I',
    '801030': '化工I',
    '801040': '钢铁I',
    '801050': '有色金属I',
    '801060': '建筑建材I',
    '801070': '机械设备I',
    '801080': '电子I',
    '801090': '交运设备I',
    '801100': '信息设备I',
    '801110': '家用电器I',
    '801120': '食品饮料I',
    '801130': '纺织服装I',
    '801140': '轻工制造I',
    '801150': '医药生物I',
    '801160': '公用事业I',
    '801170': '交通运输I',
    '801180': '房地产I',
    '801190': '金融服务I',
    '801200': '商业贸易I',
    '801210': '休闲服务I',
    '801220': '信息服务I',
    '801230': '综合I',
    '801710': '建筑材料I',
    '801720': '建筑装饰I',
    '801730': '电气设备I',
    '801740': '国防军工I',
    '801750': '计算机I',
    '801760': '传媒I',
    '801770': '通信I',
    '801780': '银行I',
    '801790': '非银金融I',
    '801880': '汽车I',
    '801890': '机械设备I',
    '801950': '煤炭I',
    '801960': '石油石化I',
    '801970': '环保I',
    '801980': '美容护理I'
}

# 行业代码列表（用于市场宽度计算）
industry_code = ['801010','801020','801030','801040','801050','801080','801110','801120','801130','801140','801150',
                 '801160','801170','801180','801200','801210','801230','801710','801720','801730','801740','801750',
                 '801760','801770','801780','801790','801880','801890']


def initialize(context):
    """初始化函数"""
    # 设定基准 (PTrade: 指数代码用.SS或.XBHS)
    set_benchmark('000985.SS')
    
    # 设置佣金 (PTrade语法)
    set_commission(commission_ratio=0.0003, min_commission=5.0)
    
    # 设置滑点 (PTrade语法)
    set_fixed_slippage(fixedslippage=0.0)
    
    # 初始化全局变量
    g.stock_num = 8
    g.hold_list = []  # 当前持仓的全部股票
    g.yesterday_HL_list = []  # 记录持仓中昨日涨停的股票
    g.num = 1
    
    # 设置股票池 (PTrade必须调用)
    set_universe([])
    
    # 设置交易运行时间 (PTrade语法: run_daily需要context参数)
    run_daily(context, prepare_stock_list, time='9:05')
    # PTrade没有run_weekly，使用run_daily配合星期判断
    run_daily(context, weekly_adjustment_wrapper, time='9:30')
    run_daily(context, check_limit_up, time='14:00')


def weekly_adjustment_wrapper(context):
    """每周一执行调仓的包装函数"""
    today = get_trading_day(context)
    # weekday() == 0 表示周一
    if today.weekday() == 0:
        weekly_adjustment(context)


def get_trading_day(context):
    """获取当前交易日"""
    return context.blotter.current_dt.date()


def get_previous_date(context):
    """获取前一交易日"""
    # PTrade中获取前一交易日
    today = get_trading_day(context)
    trade_days = get_trade_days(end_date=today.strftime('%Y%m%d'), count=2)
    if len(trade_days) >= 2:
        return trade_days[-2]
    return today


# 1-1 准备股票池
def prepare_stock_list(context):
    """准备股票池：获取持仓列表和昨日涨停列表"""
    # 获取已持有列表 (PTrade语法)
    g.hold_list = []
    positions = get_positions()
    for stock in positions:
        g.hold_list.append(stock)
    
    # 获取昨日涨停列表
    if g.hold_list:
        yesterday = get_previous_date(context)
        yesterday_str = yesterday.strftime('%Y%m%d') if hasattr(yesterday, 'strftime') else str(yesterday).replace('-', '')
        
        g.yesterday_HL_list = []
        for stock in g.hold_list:
            try:
                # PTrade: 使用get_history获取涨停价和收盘价
                df = get_history(1, '1d', ['close', 'high_limit'], security_list=stock, include=False)
                if df is not None and len(df) > 0:
                    close = df['close'].iloc[-1] if 'close' in df.columns else df.iloc[-1, 0]
                    high_limit = df['high_limit'].iloc[-1] if 'high_limit' in df.columns else df.iloc[-1, 1]
                    if close >= high_limit * 0.999:  # 允许小误差
                        g.yesterday_HL_list.append(stock)
            except Exception as e:
                log.debug(f"获取{stock}涨停信息出错: {e}")
    else:
        g.yesterday_HL_list = []


def industry(stockList, industry_code_list, date):
    """计算各行业的股票数量"""
    i_Constituent_Stocks = {}
    date_str = date.strftime('%Y%m%d') if hasattr(date, 'strftime') else str(date).replace('-', '')
    
    for i in industry_code_list:
        # PTrade: 行业代码需要加.XBHS后缀
        try:
            temp = get_industry_stocks(i + '.XBHS')
            i_Constituent_Stocks[i] = list(set(temp).intersection(set(stockList)))
        except:
            i_Constituent_Stocks[i] = []
    
    count_dict = {}
    for name, content_list in i_Constituent_Stocks.items():
        count_dict[name] = len(content_list)
    return count_dict


def getStockIndustry(p_stocks, p_day):
    """获取股票所属行业"""
    dict_stk_2_ind = {}
    date_str = p_day.strftime('%Y%m%d') if hasattr(p_day, 'strftime') else str(p_day).replace('-', '')
    
    # PTrade: 使用get_stock_blocks获取股票所属板块
    for stock in p_stocks:
        try:
            blocks = get_stock_blocks(stock)
            if blocks:
                # 查找申万一级行业
                for block in blocks:
                    if block.startswith('801') and len(block) == 6:
                        dict_stk_2_ind[stock] = block
                        break
        except:
            pass
    
    return pd.Series(dict_stk_2_ind)


# 1-2 选股模块
def get_stock_list(context):
    """选股逻辑"""
    yesterday = get_previous_date(context)
    today = get_trading_day(context)
    today_str = today.strftime('%Y%m%d') if hasattr(today, 'strftime') else str(today).replace('-', '')
    yesterday_str = yesterday.strftime('%Y%m%d') if hasattr(yesterday, 'strftime') else str(yesterday).replace('-', '')
    
    final_list = []
    
    # 获取初始列表 (PTrade: 指数代码用.XBHS)
    initial_list = get_index_stocks('000985.XBHS', today_str)
    
    if not initial_list:
        log.info("获取指数成分股失败")
        return []
    
    p_count = 1
    
    # 获取历史收盘价数据
    try:
        # PTrade: 使用get_price获取多只股票历史数据
        h = get_price(initial_list, end_date=yesterday_str, frequency='1d', fields=['close'], count=p_count + 20)
        
        if h is None or len(h) == 0:
            log.info("获取历史价格数据失败")
            return []
        
        # 数据处理
        if 'code' in h.columns:
            # 多股票返回格式
            h['date'] = pd.to_datetime(h.index).date if hasattr(h.index[0], 'date') else h.index
            df_close = h.pivot(index='code', columns='date', values='close').dropna(axis=0)
        else:
            # 尝试其他格式处理
            df_close = h.T if len(h.columns) > 1 else h
        
        # 计算20日均线
        df_ma20 = df_close.rolling(window=20, axis=1).mean().iloc[:, -p_count:]
        df_bias = (df_close.iloc[:, -p_count:] > df_ma20)
        
        # 获取股票行业信息
        s_stk_2_ind = getStockIndustry(p_stocks=initial_list, p_day=yesterday)
        
        if len(s_stk_2_ind) == 0:
            log.info("获取行业信息失败，使用备选逻辑")
            # 直接使用小市值策略
            return get_small_cap_stocks(context, today_str)
        
        df_bias['industry_code'] = s_stk_2_ind
        
        # 计算行业宽度比例
        df_ratio = ((df_bias.groupby('industry_code').sum() * 100.0) / df_bias.groupby('industry_code').count()).round()
        
        # 获取宽度最高的行业
        column_names = df_ratio.columns.tolist()
        if len(column_names) > 0:
            last_col = column_names[-1]
            top_values = df_ratio[last_col].nlargest(g.num)
            I = top_values.index.tolist()
            
            # 计算全市场宽度
            TT = df_ratio.sum().iloc[-1] if len(df_ratio.sum()) > 0 else 0
            
            name_list = [SW1.get(code, code) for code in I]
            log.info(f"市场宽度最高行业: {name_list}")
            log.info(f"全市场宽度: {np.array(df_ratio.sum(axis=0).mean()):.2f}")
            
            # 搅屎棍逻辑：如果是银行、有色、煤炭、钢铁且处于存量市场，则空仓
            if I and I[0] in ['801780', '801050', '801950', '801040']:
                market_env = judge_market_env(context)
                if market_env == '存量':
                    log.info(f"搅屎棍触发：{name_list[0]}领涨且市场为存量环境，本周空仓")
                    return []
    
    except Exception as e:
        log.error(f"计算市场宽度出错: {e}")
    
    # 获取小市值股票
    return get_small_cap_stocks(context, today_str)


def get_small_cap_stocks(context, today_str):
    """获取小市值股票列表"""
    # 获取中证1000成分股 (PTrade: 指数代码用.XBHS)
    S_stocks = get_index_stocks('399101.XBHS', today_str)
    
    if not S_stocks:
        # 备选：获取所有A股
        S_stocks = get_Ashares(today_str)
    
    # 过滤科创北交股票
    stocks = filter_kcbj_stock(S_stocks)
    # 过滤ST股票
    choice = filter_st_stock(stocks)
    # 过滤次新股
    choice = filter_new_stock(context, choice)
    
    if not choice:
        return []
    
    # 获取财务数据筛选 (PTrade语法)
    try:
        # 获取ROE和ROA数据
        df = get_fundamentals(choice, 'profit_ability', fields=['roe', 'roa'], date=today_str)
        
        if df is not None and len(df) > 0:
            # 筛选ROE > 15%, ROA > 10%
            if 'roe' in df.columns and 'roa' in df.columns:
                # 处理百分比字符串
                if df['roe'].dtype == 'object':
                    df['roe'] = df['roe'].str.replace('%', '').astype(float)
                if df['roa'].dtype == 'object':
                    df['roa'] = df['roa'].str.replace('%', '').astype(float)
                
                qualified = df[(df['roe'] > 15) & (df['roa'] > 10)]
                choice = qualified.index.tolist()
    except Exception as e:
        log.debug(f"获取财务数据出错: {e}")
    
    # 按市值排序，取最小的
    try:
        val_df = get_fundamentals(choice, 'valuation', fields=['total_value'], date=today_str)
        if val_df is not None and len(val_df) > 0:
            val_df = val_df.sort_values('total_value', ascending=True)
            choice = val_df.index.tolist()[:g.stock_num]
    except Exception as e:
        log.debug(f"获取市值数据出错: {e}")
        choice = choice[:g.stock_num]
    
    # 过滤停牌、涨停、跌停股票
    BIG_stock_list = filter_paused_stock(choice)
    BIG_stock_list = filter_limitup_stock(context, BIG_stock_list)
    L = filter_limitdown_stock(context, BIG_stock_list)
    
    return L


# 1-3 整体调整持仓
def weekly_adjustment(context):
    """每周调仓"""
    target_B = get_stock_list(context)
    
    log.info(f"本周目标持仓: {target_B}")
    
    # 调仓卖出
    for stock in g.hold_list:
        if (stock not in target_B) and (stock not in g.yesterday_HL_list):
            position = get_position(stock)
            if position and position.amount > 0:
                close_position(stock)
    
    # 调仓买入
    position_count = len(get_positions())
    target_num = len(target_B)
    
    if target_num > position_count:
        buy_num = min(len(target_B), g.stock_num * g.num - position_count)
        if buy_num > 0:
            value = context.portfolio.cash / buy_num
            for stock in target_B:
                positions = get_positions()
                if stock not in positions:
                    if open_position(stock, value):
                        if len(get_positions()) >= target_num:
                            break


def check_limit_up(context):
    """检查持仓中的涨停股是否需要卖出"""
    if not g.yesterday_HL_list:
        return
    
    now_time = context.blotter.current_dt
    
    for stock in g.yesterday_HL_list:
        try:
            # PTrade: 使用get_snapshot获取实时行情
            snapshot = get_snapshot(stock)
            if snapshot and stock in snapshot:
                last_px = snapshot[stock].get('last_px', 0)
                high_limit = snapshot[stock].get('high_limit', 0)
                
                if last_px > 0 and high_limit > 0 and last_px < high_limit * 0.999:
                    log.info(f"[{stock}]涨停打开，卖出")
                    close_position(stock)
                else:
                    log.info(f"[{stock}]涨停，继续持有")
        except Exception as e:
            log.debug(f"检查{stock}涨停状态出错: {e}")


# 3-1 交易模块-自定义下单
def order_target_value_(security, value):
    """自定义下单函数"""
    if value == 0:
        log.debug(f"Selling out {security}")
    else:
        log.debug(f"Order {security} to value {value}")
    return order_target_value(security, value)


# 3-2 交易模块-开仓
def open_position(security, value):
    """开仓"""
    order_id = order_target_value_(security, value)
    if order_id is not None:
        log.info(f"买入 {security}, 目标金额 {value:.2f}")
        return True
    return False


# 3-3 交易模块-平仓
def close_position(security):
    """平仓"""
    order_id = order_target_value_(security, 0)
    if order_id is not None:
        log.info(f"卖出 {security}")
        return True
    return False


# 2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    if not stock_list:
        return []
    
    result = []
    for stock in stock_list:
        try:
            # PTrade: 使用get_stock_status检查停牌状态
            status = get_stock_status(stock, query_type='HALT')
            if status and stock in status:
                if not status[stock]:  # False表示未停牌
                    result.append(stock)
            else:
                result.append(stock)
        except:
            result.append(stock)
    
    return result


# 2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    """过滤ST股票"""
    if not stock_list:
        return []
    
    result = []
    for stock in stock_list:
        try:
            # PTrade: 使用get_stock_status检查ST状态
            status = get_stock_status(stock, query_type='ST')
            if status and stock in status:
                if not status[stock]:  # False表示非ST
                    # 再检查股票名称
                    name_info = get_stock_name(stock)
                    if name_info and stock in name_info:
                        name = name_info[stock]
                        if name and 'ST' not in name and '*' not in name and '退' not in name:
                            result.append(stock)
                    else:
                        result.append(stock)
            else:
                result.append(stock)
        except:
            result.append(stock)
    
    return result


# 2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    """过滤科创北交股票"""
    if not stock_list:
        return []
    
    result = []
    for stock in stock_list:
        code = stock.split('.')[0] if '.' in stock else stock
        # 过滤科创板(688)、北交所(4/8开头)、创业板(3开头)
        if not (code.startswith('4') or code.startswith('8') or 
                code.startswith('68') or code.startswith('3')):
            result.append(stock)
    
    return result


# 2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    """过滤涨停股票（非持仓）"""
    if not stock_list:
        return []
    
    positions = get_positions()
    result = []
    
    for stock in stock_list:
        if stock in positions:
            result.append(stock)
            continue
        
        try:
            # 获取最新价和涨停价
            hist = get_history(1, '1m', ['close', 'high_limit'], security_list=stock, include=True)
            if hist is not None and len(hist) > 0:
                close = hist['close'].iloc[-1] if 'close' in hist.columns else hist.iloc[-1, 0]
                high_limit = hist['high_limit'].iloc[-1] if 'high_limit' in hist.columns else hist.iloc[-1, 1]
                if close < high_limit * 0.999:
                    result.append(stock)
            else:
                result.append(stock)
        except:
            result.append(stock)
    
    return result


# 2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    """过滤跌停股票（非持仓）"""
    if not stock_list:
        return []
    
    positions = get_positions()
    result = []
    
    for stock in stock_list:
        if stock in positions:
            result.append(stock)
            continue
        
        try:
            # 获取最新价和跌停价
            hist = get_history(1, '1m', ['close', 'low_limit'], security_list=stock, include=True)
            if hist is not None and len(hist) > 0:
                close = hist['close'].iloc[-1] if 'close' in hist.columns else hist.iloc[-1, 0]
                low_limit = hist['low_limit'].iloc[-1] if 'low_limit' in hist.columns else hist.iloc[-1, 1]
                if close > low_limit * 1.001:
                    result.append(stock)
            else:
                result.append(stock)
        except:
            result.append(stock)
    
    return result


# 2-6 过滤次新股
def filter_new_stock(context, stock_list):
    """过滤次新股（上市不满375天）"""
    if not stock_list:
        return []
    
    yesterday = get_previous_date(context)
    result = []
    
    for stock in stock_list:
        try:
            # PTrade: 使用get_stock_info获取上市日期
            info = get_stock_info(stock, field=['listed_date'])
            if info and stock in info:
                listed_date_str = info[stock].get('listed_date', '')
                if listed_date_str:
                    listed_date = datetime.datetime.strptime(listed_date_str, '%Y-%m-%d').date()
                    if hasattr(yesterday, 'date'):
                        yesterday_date = yesterday
                    else:
                        yesterday_date = datetime.datetime.strptime(str(yesterday), '%Y-%m-%d').date()
                    
                    if (yesterday_date - listed_date).days >= 375:
                        result.append(stock)
                else:
                    result.append(stock)
            else:
                result.append(stock)
        except:
            result.append(stock)
    
    return result


def judge_market_env(context, ma_window=20, slope_window=5):
    """
    判断市场环境
    
    类似美林投资时钟，尝试将市场分为四种状态：
    - 全市场成交额趋势上涨 + 银行指数上涨 : 权重增量市场
    - 全市场成交额趋势上涨 + 银行指数下跌 : 成长增量市场
    - 全市场成交额趋势下跌 + 银行指数上涨 : 存量/减量市场
    - 全市场成交额趋势下跌 + 银行指数下跌 : 熊市/退潮市场
    """
    yesterday = get_previous_date(context)
    yesterday_str = yesterday.strftime('%Y%m%d') if hasattr(yesterday, 'strftime') else str(yesterday).replace('-', '')
    
    try:
        trade_days = get_trade_days(end_date=yesterday_str, count=ma_window + slope_window)
        if len(trade_days) < ma_window + slope_window:
            return None
        
        start_date = trade_days[0]
        start_date_str = start_date.strftime('%Y%m%d') if hasattr(start_date, 'strftime') else str(start_date).replace('-', '')
        
        # 获取上证指数和深证成指的成交额
        sh_data = get_price('000001.SS', start_date=start_date_str, end_date=yesterday_str, 
                           frequency='1d', fields=['money'])
        sz_data = get_price('399001.SZ', start_date=start_date_str, end_date=yesterday_str, 
                           frequency='1d', fields=['money'])
        
        if sh_data is None or sz_data is None:
            return None
        
        total_money = sh_data['money'] + sz_data['money']
        
        # 计算成交额MA
        ma_total = total_money.rolling(ma_window).mean().dropna()
        if len(ma_total) < slope_window + 1:
            return None
        
        change_total = (ma_total.iloc[-1] - ma_total.iloc[-slope_window - 1]) / ma_total.iloc[-slope_window - 1]
        
        # 获取银行指数数据 (中证银行: 399986.SZ)
        bank_data = get_price('399986.SZ', end_date=yesterday_str, frequency='1d', 
                             fields=['close'], count=ma_window)
        
        if bank_data is None or len(bank_data) < ma_window:
            return None
        
        close_prices = bank_data['close']
        bank_return = close_prices.iloc[-1] / close_prices.iloc[0]
        
        # 判断市场环境
        if change_total <= 0.1 or bank_return <= 0.9:
            return '存量'
        
        return None
        
    except Exception as e:
        log.debug(f"判断市场环境出错: {e}")
        return None


def handle_data(context, data):
    """盘中函数（必须定义）"""
    pass


def after_trading_end(context, data):
    """盘后函数"""
    log.info(f"====== 交易日结束 ======")
    log.info(f"持仓数量: {len(get_positions())}")
    log.info(f"总资产: {context.portfolio.portfolio_value:.2f}")
import pandas as pd
import numpy as np

class DualMovingAverageStrategy:
    """
    策略名称: 双均线趋势追踪策略 (Dual Moving Average Crossover)
    策略逻辑: 
    1. 短周期均线 (Short MA) 上穿 长周期均线 (Long MA) -> 买入 (Golden Cross)
    2. 短周期均线 (Short MA) 下穿 长周期均线 (Long MA) -> 卖出 (Death Cross)
    
    适用场景: 趋势明显的市场 (Trend Following)
    """

    def __init__(self, short_window=20, long_window=60):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, data):
        """
        输入: 包含 'Close' 列的 DataFrame
        输出: 带有 'Signal' 列的 DataFrame
        """
        signals = pd.DataFrame(index=data.index)
        signals['signal'] = 0.0

        # 1. 计算均线
        signals['short_mavg'] = data['Close'].rolling(window=self.short_window, min_periods=1, center=False).mean()
        signals['long_mavg'] = data['Close'].rolling(window=self.long_window, min_periods=1, center=False).mean()

        # 2. 生成信号 (1为买入状态, 0为持币状态)
        # 注意：这里我们使用 np.where 做向量化计算，提高回测速度
        signals['signal'][self.short_window:] = np.where(
            signals['short_mavg'][self.short_window:] > signals['long_mavg'][self.short_window:], 1.0, 0.0
        )   

        # 3. 生成买卖指令 (signal差分: 1为买入, -1为卖出)
        signals['positions'] = signals['signal'].diff()

        return signals

if __name__ == "__main__":
    # 模拟数据生成 (仅供示例运行)
    print("正在加载模拟数据...")
    dates = pd.date_range('2025-01-01', periods=100)
    df = pd.DataFrame(np.random.randn(100).cumsum() + 100, index=dates, columns=['Close'])
    
    # 初始化策略
    strategy = DualMovingAverageStrategy(short_window=5, long_window=20)
    
    # 运行策略
    print("正在计算交易信号...")
    results = strategy.generate_signals(df)
    
    # 打印最近5天的信号
    print("\n--- 最近5天交易信号 ---")
    print(results[['short_mavg', 'long_mavg', 'positions']].tail())
    print("\n策略运行成功！(此代码仅为演示框架)")

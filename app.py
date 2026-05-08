import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# 頁面配置
st.set_page_config(page_title="專業級量化雷達", layout="wide")

# --- 頂部：決策邏輯說明 ---
st.title("🏛️ 專業經理人：全球量化環境診斷雷達")
with st.expander("ℹ️ 查看系統決策邏輯 (四選二推薦規則)", expanded=True):
    st.markdown("""
    本系統採用 **「四選二 (4-Select-2)」** 量化策略，當下列四項指標中有 **至少兩項** 觸發時，系統將判定為進場訊號：
    
    | 指標名稱 | 判斷邏輯 | 技術含意 |
    | :--- | :--- | :--- |
    | **1. KD 黃金交叉** | K值 > D值 | 短線動能轉強，股價開始發動。 |
    | **2. MACD 多頭** | MACD > 訊號線 | 中線趨勢確認，適合波段持有。 |
    | **3. RSI 超跌** | RSI < 45 | 股價進入相對低位區，具備反彈空間。 |
    | **4. 布林下軌觸碰** | 股價 < 布林下軌 | 股價跌破統計學合理區間，極短線超跌。 |
    
    *此外，系統還會結合 **歷史勝率 (>50%)** 與 **大盤環境** 進行最終篩選。*
    """)

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("1. 掃描設定")
    # 💡 修改這裡：將您的預設清單直接寫入
    # 如果未來要換股票，直接改這一行即可
    default_list = "2330.TW, 0050.TW, 00981A.TW, MSFT, NOK, NVDA, TSLA, AAPL, GOOGL, AMD, SPY"
    
    # 💡 重點：加入 key="ticker_input"，強制瀏覽器刷新時帶入 default_list
    ticker_input = st.text_area(
        "監控清單 (代號用逗號隔開)", 
        value=default_list, 
        height=150,
        key="ticker" 
    )
    
    period = st.selectbox("回測長度 (建議 5y)", ["1y", "2y", "5y"], index=2)
    
    st.divider()
    st.header("2. 推薦門檻")
    min_win_rate = st.slider("最低勝率門檻 (%)", 0, 100, 50)
    
    st.divider()
    st.header("3. 資金管理")
    kelly_cap = st.slider("單一標的上限 (%)", 5, 30, 15)
    run_radar = st.button("啟動全量化掃描", type="primary")

# --- 市場環境診斷 (保持原邏輯) ---
def get_market_audit():
    try:
        tw_idx = yf.Ticker("^TWII").history(period="5d")
        tsmc = yf.Ticker("2330.TW").history(period="5d")
        price_change = (tsmc['Close'].iloc[-1] / tsmc['Close'].iloc[-2]) - 1
        vol_avg = tsmc['Volume'].mean()
        if price_change > 0.01 and tsmc['Volume'].iloc[-1] > vol_avg:
            ins_action = "🔥 外資進場攻擊"
        elif price_change < -0.01 and tsmc['Volume'].iloc[-1] > vol_avg:
            ins_action = "🚨 外資大單調節"
        else:
            ins_action = "⚖️ 法人中性觀望"
        return {"tw_pc": (tw_idx['Close'].iloc[-1]/tw_idx['Close'].iloc[-2]-1)*100, "ins": ins_action}
    except: return {"tw_pc": 0, "ins": "數據連線中"}

# --- 核心運算引擎 (四選二邏輯) ---
def analyze_v13(ticker, period, kelly_cap=15):
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df.empty or len(df) < 200: return None
        
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA200'] = df['Close'].rolling(200).mean()
        df['BIAS'] = ((df['Close'] - df['MA20']) / df['MA20']) * 100
        
        # MACD / KD / RSI / Bollinger
        ema12, ema26 = df['Close'].ewm(span=12).mean(), df['Close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MAC_S'] = df['MACD'].ewm(span=9).mean()
        l9, h9 = df['Low'].rolling(9).min(), df['High'].rolling(9).max()
        df['K'] = ((df['Close'] - l9) / (h9 - l9) * 100).ewm(com=2).mean()
        df['D'] = df['K'].ewm(com=2).mean()
        delta = df['Close'].diff()
        g, l = (delta.where(delta > 0, 0)).rolling(14).mean(), (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (g / (l + 1e-9))))
        df['BBL'] = df['MA20'] - (df['Close'].rolling(20).std() * 2)
        
        # 判定
        s1, s2, s3, s4 = df['K']>df['D'], df['MACD']>df['MAC_S'], df['RSI']<45, df['Close']<df['BBL']
        score = sum([s1.iloc[-1], s2.iloc[-1], s3.iloc[-1], s4.iloc[-1]])
        
        df['Future'] = df['Close'].shift(-5) / df['Close'] - 1
        p = (df[df['Future'].notnull()]['Future'] > 0).mean()
        kelly = min(max(0, (2 * p - 1) * 100), kelly_cap) if p > 0.5 else 0

        return {
            "代號": ticker, "當前價": df['Close'].iloc[-1], "勝率": p, 
            "趨勢": "🔵 多頭" if df['Close'].iloc[-1] > df['MA200'].iloc[-1] else "⚪ 空頭", 
            "BIAS": df['BIAS'].iloc[-1], "RSI": df['RSI'].iloc[-1], 
            "觸發買入": score >= 2, "凱利": kelly, "訊號得分": score
        }
    except: return None

# --- 顯示介面 ---
if run_radar:
    audit = get_market_audit()
    st.info(f"📊 市場掃描完成 | 台股大盤：{audit['tw_pc']:.2f}% | 外資動向：{audit['ins']}")

    tickers = [t.strip() for t in ticker_input.split(",")]
    results = [r for r in (analyze_v13(t, period, kelly_cap) for t in tickers) if r is not None]
    
    if results:
        res_df = pd.DataFrame(results)
        st.subheader("🎯 專業進場推薦 (精選診斷)")
        recommend = res_df[(res_df['觸發買入'] == True) & (res_df['勝率'] >= min_win_rate/100)]
        
        if not recommend.empty:
            for _, row in recommend.iterrows():
                with st.container(border=True):
                    col_t, col_s = st.columns([1, 4])
                    col_t.markdown(f"### {row['代號']}")
                    col_t.write(f"**趨勢：{row['趨勢']}**")
                    col_t.markdown(f":violet[💜 法人動作：{audit['ins']}]")
                    col_t.caption(f"訊號強度：{int(row['訊號得分'])} / 4")
                    
                    c1, c2, c3, c4 = col_s.columns(4)
                    c1.metric("歷史勝率", f"{row['勝率']*100:.1f}%")
                    c1.markdown(f":{'red' if row['勝率']>=0.6 else 'gray'}[{'🔥 高勝率' if row['勝率']>=0.6 else '建議 >60%'}]")
                    c2.metric("RSI 指標", f"{row['RSI']:.1f}")
                    c2.markdown(f":{'red' if row['RSI']<=45 else 'gray'}[{'📉 超跌反彈' if row['RSI']<=45 else '建議 <45'}]")
                    c3.metric("乖離 BIAS", f"{row['BIAS']:.2f}%")
                    c3.markdown(f":{'red' if row['BIAS']<=-3 else 'gray'}[{'🧲 強力吸引' if row['BIAS']<=-3 else '建議 <-3%'}]")
                    c4.metric("凱利公式", f"{row['凱利']:.1f}%")
                    c4.markdown(f":{'red' if row['凱利']>=10 else 'gray'}[{'💰 建議進場' if row['凱利']>=10 else '建議 >10%'}]")
        
        st.divider()
        st.subheader("📊 監控清單全數據表格")
        st.dataframe(res_df.style.map(lambda v: 'color: red; font-weight: bold' if v == True else '', subset=['觸發買入']), use_container_width=True)

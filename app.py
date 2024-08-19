import streamlit as st
import pandas as pd
import requests
from flask import Flask, jsonify
from threading import Thread
import time
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Tạo một Flask app
app = Flask(__name__)

@app.route('/api/tickers', methods=['GET'])
def get_tickers():
    # Tối ưu hóa: Chỉ gửi yêu cầu API một lần để lấy dữ liệu ticker và dữ liệu tương ứng
    url = "https://stocktraders.vn/service/data/getTotalTrade"
    payload = {
        "TotalTradeRequest": {
            "account": "StockTraders"
        }
    }
    response = requests.post(url, json=payload)
    tickers = []
    stock_data = {}

    if response.status_code == 201:
        data = response.json()

        if 'TotalTradeReply' in data and 'stockTotals' in data['TotalTradeReply']:
            stock_totals = data['TotalTradeReply']['stockTotals']

            for stock in stock_totals:
                ticker = stock['ticker']
                tickers.append(ticker)

                # Lưu trữ dữ liệu theo ticker
                all_data = []
                for trade in stock['totalDatas']:
                    filtered_data = {
                        'close': trade.get('close'),
                        'date': trade.get('date'),
                        'high': trade.get('high'),
                        'low': trade.get('low'),
                        'open': trade.get('open'),
                        'vol': trade.get('vol')
                    }
                    all_data.append(filtered_data)
                stock_data[ticker] = all_data

    return jsonify({"tickers": tickers, "stock_data": stock_data})

# Chạy Flask app trong một thread riêng
def run_flask():
    app.run(debug=True, use_reloader=False)

flask_thread = Thread(target=run_flask)
flask_thread.start()

# Cho Flask server thời gian để khởi động
time.sleep(2)

# Hàm lấy dữ liệu từ API Flask
@st.cache_data
def fetch_tickers_and_data():
    url = 'http://localhost:5000/api/tickers'  # URL của Flask API
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['tickers'], data['stock_data']
    return [], {}

# Giao diện người dùng bằng Streamlit
st.title('Stock Viewer')

# Lấy danh sách ticker và dữ liệu từ Flask API
tickers, stock_data = fetch_tickers_and_data()

# Cho phép người dùng chọn ticker
selected_ticker = st.selectbox('Chọn ticker:', tickers)

# Sử dụng cột để làm cho các widget nhỏ hơn và trên cùng một hàng
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input('Chọn ngày bắt đầu', value=pd.to_datetime('2023-01-01'))
with col2:
    end_date = st.date_input('Chọn ngày kết thúc', value=pd.to_datetime('2023-12-31'))

# Lấy dữ liệu và hiển thị
if selected_ticker:
    df = pd.DataFrame(stock_data[selected_ticker])
    df['date'] = pd.to_datetime(df['date'])  # Chuyển cột 'date' thành kiểu datetime
    
    # Lọc dữ liệu dựa trên khoảng thời gian được chọn
    df = df[(df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))]

    if not df.empty:
        indicate = ['Original Data', 'RSI', 'MACD']
        selected_indicate = st.selectbox('Chọn chỉ số:', indicate)
        if selected_indicate == 'RSI':
            df['RSI'] = ta.rsi(df['close'], length=14)
            st.write(f'Data for {selected_ticker}')
            st.write(df)
            chart = st.button('Vẽ biểu đồ')
            if chart:
                # Tạo biểu đồ với hai trục y (y-axis)
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                    vertical_spacing=0.1,
                                    subplot_titles=('Candlestick Chart', 'RSI'),
                                    row_heights=[0.7, 0.3])

                # Thêm biểu đồ nến vào trục y đầu tiên
                fig.add_trace(go.Candlestick(x=df['date'],
                                            open=df['open'],
                                            high=df['high'],
                                            low=df['low'],
                                            close=df['close'],
                                            name='Candlestick'),
                            row=1, col=1)

                # Thêm biểu đồ RSI vào trục y thứ hai
                fig.add_trace(go.Scatter(x=df['date'],
                                        y=df['RSI'],
                                        mode='lines',
                                        name='RSI',
                                        line=dict(color='blue')),
                            row=2, col=1)

                # Tinh chỉnh giao diện biểu đồ
                fig.update_layout(title='Candlestick Chart with RSI',
                                xaxis_title='Date',
                                yaxis_title='Price',
                                xaxis_rangeslider_visible=False,
                                yaxis2_title='RSI',
                                yaxis2_range=[0, 100])

                # Hiển thị biểu đồ trong Streamlit
                st.plotly_chart(fig, use_container_width=True)
            
        elif selected_indicate == 'MACD':
            macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
            df['MACD'] = macd['MACD_12_26_9']
            df['MACD_signal'] = macd['MACDs_12_26_9']
            df['MACD_hist'] = macd['MACDh_12_26_9']
            st.write(f'Data for {selected_ticker}')
            st.write(df)
            chart = st.button('Vẽ biểu đồ')
            if chart:
                fig = go.Figure(data=[

                go.Scatter(x=df['date'],
                        y=df['MACD'],
                        mode='lines',
                        name='MACD',
                        line=dict(color='red')),

                go.Scatter(x=df['date'],
                        y=df['MACD_signal'],
                        mode='lines',
                        name='MACD_Signal',
                        line=dict(color='blue')),

                go.Bar(x=df['date'],
                        y=df['MACD_hist'],
                        name='MACD Histogram',
                        marker=dict(color='red'))
                ])

                # Tinh chỉnh giao diện biểu đồ
                fig.update_layout(title='MACD',
                            xaxis_title='Date',
                            yaxis_title='Price',
                            xaxis_rangeslider_visible=False)

                # Hiển thị biểu đồ trong Streamlit
                st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.write(f'Data for {selected_ticker}')
            st.write(df)
            
    else:
        st.write('No data available for the selected ticker.')

import os
import time
import pandas as pd
import yfinance as yf
import talib
import matplotlib.pyplot as plt

def download_stock_data(ticker, start, end):
    return yf.download(ticker, start=start, end=end)

def calculate_indicators(data, length=15, macdfast=12, macdslow=26, macdsignal=9):
    """Add ADX, MACD, PLUS_DI, MINUS_DI indicators to the data."""
    data['ADX'] = talib.ADX(data['High'], data['Low'], data['Close'], timeperiod=length)
    macd, macdsignal, macdhist = talib.MACD(data['Close'], fastperiod=macdfast, slowperiod=macdslow, signalperiod=macdsignal)
    data['MACD'] = macd
    data['MACDSignal'] = macdsignal
    data['PLUS_DI'] = talib.PLUS_DI(data['High'], data['Low'], data['Close'], timeperiod=length)
    data['MINUS_DI'] = talib.MINUS_DI(data['High'], data['Low'], data['Close'], timeperiod=length)
    return data

def initialize_columns(data):
    data['Buy_Signal'] = 0
    data['Sell_Signal'] = 0
    data['Portfolio_Value'] = 0

def evaluate_signals(data):
    """Evaluate buy and sell signals based on the ADX, MACD, PLUS_DI, and MINUS_DI indicators."""
    data['Buy_Condition'] = (data['PLUS_DI'] > data['MINUS_DI']) & (data['MACD'] > data['MACDSignal'])
    data['Sell_Condition'] = (data['MINUS_DI'] > data['PLUS_DI']) & (data['MACD'] < data['MACDSignal'])

def run_simulation(data, initial_cash):
    cash = initial_cash
    stock_quantity = 0
    transactions = []
    last_action = None
    total_trades = 0
    successful_trades = 0
    last_buy_price = 0  # To track the price at which stock was last bought

    # Start at the index where both PLUS_DI and MINUS_DI indicators first have non-NaN values
    start_index = max(data['MINUS_DI'].first_valid_index(), data['PLUS_DI'].first_valid_index())
    # Convert the Timestamp to its integer-based location
    start_index = data.index.get_loc(start_index)

    for i in range(start_index, len(data)):
        close_price = data['Close'].iloc[i]

        if data['Buy_Condition'].iloc[i] and cash > 0 and last_action != 'Buy':
            stock_quantity = cash // close_price
            cash -= stock_quantity * close_price
            transactions.append([data.index[i], 'Buy', close_price, stock_quantity, cash, cash + stock_quantity * close_price])
            data.at[data.index[i], 'Buy_Signal'] = 1
            last_action = 'Buy'
            last_buy_price = close_price

        elif data['Sell_Condition'].iloc[i] and stock_quantity > 0 and last_action != 'Sell':
            cash += stock_quantity * close_price
            transactions.append([data.index[i], 'Sell', close_price, 0, cash, cash])
            stock_quantity = 0
            data.at[data.index[i], 'Sell_Signal'] = 1
            last_action = 'Sell'

            total_trades += 1
            if close_price > last_buy_price:
                successful_trades += 1

        data.at[data.index[i], 'Portfolio_Value'] = cash + stock_quantity * close_price

    return pd.DataFrame(transactions, columns=['Date', 'Action', 'Price', 'Quantity', 'Cash', 'Portfolio_Value']), total_trades, successful_trades

def plot_signals(data, ticker):
    plt.figure(figsize=(12,6))
    plt.plot(data['Close'], label='Close Price', alpha=0.5)

    # Plotting Buy and Sell Signals
    plt.scatter(data[data['Buy_Signal'] == 1].index, data[data['Buy_Signal'] == 1]['Close'], marker='^', color='green', label='Buy Signal', alpha=1)
    plt.scatter(data[data['Sell_Signal'] == 1].index, data[data['Sell_Signal'] == 1]['Close'], marker='v', color='red', label='Sell Signal', alpha=1)

    # Additional plot settings
    plt.title(f'{ticker} Buy/Sell Signals')
    plt.xlabel('Date')
    plt.ylabel('Close Price')
    plt.legend(loc='best')
    plt.grid(True)

    # Save the plot in the 'graphs' subfolder
    plt.savefig(f'graphs/{ticker}_signals.png')
    plt.close()

def main():
    if not os.path.exists('graphs'):
        os.makedirs('graphs')
    if not os.path.exists('transactions'):
        os.makedirs('transactions')

    tickers_df = pd.read_csv('tickers.csv')
    tickers = tickers_df['Ticker'].tolist()
    number_of_tickers = len(tickers)

    individual_stock_return = {}
    initial_investment_per_stock = 100000
    initial_total_investment = initial_investment_per_stock * number_of_tickers
    
    start_date = '2018-10-30'
    end_date = '2023-10-30'

    total_portfolio_value = 0
    transactions_dict = {}
    total_trades_all = 0
    successful_trades_all = 0

    for ticker in tickers:
        initial_cash = 100000  # Resetting initial_cash for each ticker
        try:
            data = download_stock_data(ticker, start_date, end_date)
            if data.empty:
                print(f"Failed to download data for {ticker}. Skipping.")
                continue

            data = calculate_indicators(data)
            initialize_columns(data)
            evaluate_signals(data)
            transactions, total_trades, successful_trades = run_simulation(data, initial_cash)
            total_trades_all += total_trades
            successful_trades_all += successful_trades

            initial_stock_value = transactions['Price'].iloc[0] * transactions['Quantity'].iloc[0]
            final_stock_value = transactions['Portfolio_Value'].iloc[-1]
            stock_return_percent = ((final_stock_value - initial_stock_value) / initial_stock_value) * 100
            individual_stock_return[ticker] = stock_return_percent

            final_portfolio_value = transactions['Portfolio_Value'].iloc[-1]
            total_portfolio_value += final_portfolio_value

            transactions_dict[ticker] = transactions

            # Plot and save the signals for each ticker
            plot_signals(data, ticker)

        except Exception as e:
            print(f"An exception occurred for {ticker}: {e}. Skipping.")

    for ticker, transactions in transactions_dict.items():
        transactions.to_csv(f'transactions/{ticker}_transactions.csv', index=False)

    # Calculate and display the total trades and successful trade percentage
    if total_trades_all > 0:
        success_rate = (successful_trades_all / total_trades_all) * 100
    else:
        success_rate = 0

    print(f"Total Portfolio Value: {total_portfolio_value:.2f}")
    total_return_percent = ((total_portfolio_value - initial_total_investment) / initial_total_investment) * 100
    print(f"Total Return: {total_return_percent:.2f}%")
    print(f"Total Trades: {total_trades_all}")
    print(f"Successful Trades (%): {success_rate:.2f}%")
    for ticker, return_percent in individual_stock_return.items():
        print(f"{ticker} Return: {return_percent:.2f}%")

if __name__ == "__main__":
    main()

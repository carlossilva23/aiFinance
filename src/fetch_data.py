import yfinance as yf
import matplotlib.pyplot as plt

# Statement to catch date of highest closeing price.
# max_date = new.idxmax()

def fetch_stock(ticker_list): 
    plt.figure()
    for ticker in ticker_list:
        portfolio = yf.download(ticker, period='1y')
        if portfolio.empty:
            # Debugging Statement
            # print(portfolio.empty)
            print(f"'{ticker}' does not exist.\n")    
            exit()
        else:
            close_port = portfolio['Close']
            plt.plot(close_port, label=f"{ticker}")
    plt.legend()
    plt.title("Closing Price Past Year")
    plt.show()
    


def main(): 
    ticker_list = []
    while True:
        ticker = input("Please type in a stock: ")
        if ticker == "":
            break
        else: 
            ticker_list.append(ticker.upper())
    fetch_stock(ticker_list)

main()


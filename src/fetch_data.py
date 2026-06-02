import yfinance as yf
import matplotlib.pyplot as plt

ticker_list = ['IBM']
ticker = yf.download(ticker_list, period = '1y')
new = ticker['Close']
#print(new)
new.plot(kind='line')
#plt.show()

length = len(new)
max = new.max()
min = new.min()
avg = new.mean()
print(length, max, min, avg)
max_date = new.idxmax()
print(max_date)
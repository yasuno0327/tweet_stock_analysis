
from datetime import datetime, timedelta
import numbers
from pymongo import MongoClient
import matplotlib.pyplot as plt
import numpy as np
from emotion_recognition.emotion_predictor import EmotionPredictor
from statistics import mean
from statsmodels.tsa.stattools import grangercausalitytests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

client = MongoClient('0.0.0.0', 27017)
db = client.trump_stock
tweet_col = db.days_tweets
dow_col = db.djia
maxlag = 20

def zscore(x, axis=None):
    xmean = np.array(x).mean(axis=axis, keepdims=True)
    xstd = np.std(x, axis=axis, keepdims=True)
    zscore = (x-xmean)/xstd
    return zscore

def rate_of_change(base, changed):
    return (changed-base)/base

def fluctuating(base, changed):
    return base-changed

def granger_causality(df, time_key, causality_key):
    return grangercausalitytests(df[[time_key, causality_key]], maxlag=maxlag)

def get_stock_data(data_type, date):
    base_date = None
    comparison_date = None
    if data_type == 'before_open':
        base_date = date - timedelta(1)
        base_type = 'close'
        comparison_date = date
        comparison_type = 'open'
    elif data_type == 'opening':
        base_date = date
        base_type = 'open'
        comparison_date = date
        comparison_type = 'close'
    elif data_type == 'after_close':
        base_date = date
        base_type = 'close'
        comparison_date = date + timedelta(1)
        comparison_type = 'open'
    else:
        return None
    base_stock = dow_col.find_one({'date': base_date})
    while base_stock is None:
        base_date -= timedelta(1)
        base_type = 'close'
        base_stock = dow_col.find_one({'date': base_date})

    comparison_stock = dow_col.find_one({'date': comparison_date})
    while comparison_stock is None:
        comparison_date += timedelta(1)
        base_type = 'open'
        comparison_stock = dow_col.find_one({'date': comparison_date})

    return {'base': base_stock[base_type], 'comparison': comparison_stock[comparison_type]}

take_office_at = datetime(2017, 1, 20)
days_tweets = tweet_col.find({'date': {'$gte': take_office_at}}).sort('date', 1)
rate_datas = []
fluctuation_datas = []
prices = []
tweet_texts = []
dates = []

# Initialize poms model
model = EmotionPredictor(classification='poms', setting='mc')

for tweets in days_tweets:
    texts = ''
    for tweet in tweets['datas']:
        texts += tweet['text'] + " "
    tweet_texts.append(texts)
    price = get_stock_data(tweets['data_type'], tweets['date'])
    if price is None:
        print('continue')
        continue
    rate = rate_of_change(price['base'], price['comparison'])
    fluctuation = fluctuating(price['base'], price['comparison'])
    rate_datas.append(rate)
    prices.append(price['comparison'])
    dates.append(tweets['date'])
    fluctuation_datas.append(fluctuation)


result = model.predict_probabilities(tweet_texts)
df = pd.DataFrame({
    'rate': zscore(rate_datas),
    'fluctuation': zscore(fluctuation_datas),
    'prices': zscore(prices),
    'anger': zscore(result['Anger'].values),
    'depression': zscore(result['Depression'].values), # ゆううつ
    'fatigue': zscore(result['Fatigue'].values),
    'tension': zscore(result['Tension'].values), # 緊張
    'confusion': zscore(result['Confusion'].values),
    'vigour': zscore(result['Vigour'].values),
    'dates': dates
})

df.plot(x='dates', xlim=[datetime(2017,1,20),datetime(2017,4,20)], subplots=True, layout=(3,3), figsize=(9,6), title='zscore')
plt.savefig('result/images/zscore.png')
plt.close()

mood_index = ['anger', 'depression', 'fatigue', 'tension', 'confusion', 'vigour']
data_index = ['rate', 'fluctuation', 'prices']

# response = granger_causality(df, 'rate', 'anger')
# print(response[0])

# グレンジャー因果検定
for data in data_index:
    for mood in mood_index:
        response = granger_causality(df, data, mood)
        f_datas = []
        p_datas = []
        for key in response:
            ftest = response[key][0]['ssr_ftest']
            f_datas.append(ftest[0])
            p_datas.append(ftest[1])
        g_df = pd.DataFrame({'F': f_datas, 'p': p_datas}, index=[i for i in range(1, maxlag+1)])
        g_df.to_csv(f'result/{data}/{mood}.csv', index_label='Lag')
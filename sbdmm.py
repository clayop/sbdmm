import hashlib
import time
import requests
import hmac
import requests
import urllib.parse
import random
from piston.steem import Steem

api_key = "BITTREX_API_KEY"          # Allow all authorities
api_secret = "BITTREX_API_SECRET"
account = "YOUR_STEEM_ACCOUNT"
wif = "YOUR_STEEM_ACTIVE_KEY"
bittrexmemo = "BITTREX_STEEM_DEPOSIT_MEMO"

dust = 0.2     # Filtering dust orders (ratio to my order)
margin = 0.01  # Spread between buy and sell
target = 0.95  # Targeted SBD value
batch = 100    # The amount of SBD conversion for each time

BUY_ORDERBOOK = 'buy'
SELL_ORDERBOOK = 'sell'
BOTH_ORDERBOOK = 'both'

BASE_URL = 'https://bittrex.com/api/v1.1/%s/'
MARKET_SET = {'getopenorders', 'cancel', 'sellmarket', 'selllimit', 'buymarket', 'buylimit'}
ACCOUNT_SET = {'getbalances', 'getbalance', 'getdepositaddress', 'withdraw'}


class Bittrex(object):
    def __init__(self, api_key, api_secret):
        self.api_key = str(api_key) if api_key is not None else ''
        self.api_secret = str(api_secret) if api_secret is not None else ''
    def api_query(self, method, options={}):
        nonce = str(int(time.time() * 1000))
        method_set = 'public'
        if method in MARKET_SET:
            method_set = 'market'
        elif method in ACCOUNT_SET:
            method_set = 'account'
        request_url = (BASE_URL % method_set) + method + '?'
        if method_set != 'public':
            request_url += 'apikey=' + self.api_key + "&nonce=" + nonce + '&'
        request_url += urllib.parse.urlencode(options)
        return requests.get(
            request_url,
            headers={"apisign": hmac.new(self.api_secret.encode(), request_url.encode(), hashlib.sha512).hexdigest()}
        ).json()
    def get_balance(self, currency):
        return self.api_query('getbalance', {'currency': currency})
    def get_orderbook(self, market, depth_type, depth=50):
        return self.api_query('getorderbook', {'market': market, 'type': depth_type, 'depth': depth})
    def get_open_orders(self, market):
        return self.api_query('getopenorders', {'market': market})
    def buy_limit(self, market, quantity, rate):
        return self.api_query('buylimit', {'market': market, 'quantity': quantity, 'rate': rate})
    def sell_limit(self, market, quantity, rate):
        return self.api_query('selllimit', {'market': market, 'quantity': quantity, 'rate': rate})
    def cancel(self, uuid):
        return self.api_query('cancel', {'uuid': uuid})
    def withdraw(self, currency, quantity, address):
        return self.api_query('withdraw', {'currency': currency, 'quantity': quantity, 'address': address})

if __name__ == '__main__':

    def balance(currency):
        res = bt.get_balance(currency)["result"]["Available"]
        if res == None:
            res = 0
        return res

    def prices(btcbal, sbdbal, buyprice=None, sellprice=None, buyquantity=None, sellquantity=None):
        btcsum = 0
        sbdsum = 0
        orderbook = bt.get_orderbook("BTC-SBD", "both")["result"]
        buy = orderbook["buy"]
        sell = orderbook["sell"]
        bfbtc = float(requests.get("https://api.bitfinex.com/v1/pubticker/BTCUSD").json()["mid"])
        avgprice = target/bfbtc
        avgpmargin = avgp+margin
        avgpricemargin = avgpmargin/bfbtc
        buylimit = round(avgprice-0.000000005, 8)
        selllimit = round(avgpricemargin-0.000000005, 8)
        for i in buy:
            btcsum += i["Rate"]*i["Quantity"]
            buyp = i["Rate"]
            if btcsum >= dust*btcbal and buyp <= buylimit:
                if buyprice != None and buyquantity != None:
                    if buyp == buyprice:
                        if i["Quantity"] < (1+dust)*buyquantity:
                            pass
                        else:
                            break
                    else:
                        break
                else:
                    break
        for i in sell:
            sbdsum += i["Quantity"]
            sellp = i["Rate"]
            if sbdsum >= dust*sbdbal and sellp >= selllimit:
                if sellprice != None and sellquantity != None:
                    if sellp == sellprice:
                        if i["Quantity"] < (1+dust)*sellquantity:
                            pass
                        else:
                            break
                    else:
                        break
                else:
                    break
        return (buyp, sellp)

    def steemp(steembal, steemprice=None, steemquantity=None):
        orderbook = bt.get_orderbook("BTC-STEEM", "sell")["result"]
        steemsum = 0
        for i in orderbook:
            steemsum += i["Quantity"]
            sellp = i["Rate"]
            if steemsum >= dust*steembal and steemsum > 100:
                if steemprice != None and steemquantity != None:
                    if sellp == steemprice:
                        if i["Quantity"] < (1+dust)*steemquantity:
                            pass
                        else:
                            break
                    else:
                        break
                else:
                    break
        return sellp

    def cancel_all(type):
        openo = bt.get_open_orders("BTC-SBD")["result"]
        if openo != None:
            for i in openo:
                if type == "both":
                    bt.cancel(i["OrderUuid"])
                if type == "buy":
                    if i["OrderType"] == "LIMIT_BUY":
                        bt.cancel(i["OrderUuid"])
                if type == "sell":
                    if i["OrderType"] == "LIMIT_SELL":
                        bt.cancel(i["OrderUuid"])

    def cancel_steem():
        openo = bt.get_open_orders("BTC-STEEM")["result"]
        if openo != None:
            for i in openo:
                bt.cancel(i["OrderUuid"])

    def steemjob():
        cancel_all("sell")
        time.sleep(2)
        sbdbal = balance("SBD")
        bt.withdraw("SBD", batch+0.01, account)
        stbal = steem.get_balances(account)
        ststeembal = float(stbal["balance"].split()[0])
        stsbdbal = float(stbal["sbd_balance"].split()[0])
        if stsbdbal >= batch:
            steem.convert(batch, account=account)
        if ststeembal >= 10:
            steem.transfer("bittrex", ststeembal, "STEEM", memo=bittrexmemo)

    bt = Bittrex(api_key, api_secret)
    steem = Steem(wif=wif)
#    steem = Steem(wif=wif, node="ws://127.0.0.1:8090")   # If you want to use local node, replace above lien with this
    cancel_all("both")
    cancel_steem()
    time.sleep(2)
    btcbal = balance("BTC")
    sbdbal = balance("SBD")
    steembal = balance("STEEM")
    buyprice, sellprice = prices(btcbal, sbdbal)
    steemprice = steemp(steembal)
    buyquantity = round(btcbal/buyprice-0.0005,3)*0.9975
    sellquantity = sbdbal
    steemquantity = steembal
    if buyquantity > 10:
        print(bt.buy_limit("BTC-SBD", buyquantity, buyprice))
    if sellquantity > 10:
        print(bt.sell_limit("BTC-SBD", sellquantity, sellprice))
    if steemquantity > 10:
        print(bt.sell_limit("BTC-STEEM", steemquantity, steemprice))
    time.sleep(random.uniform(3,7))
    timeh = int(time.time()/3600)
    timet = int(time.time()/600)
    while True:
        try:
            newbuyprice, newsellprice = prices(btcbal, sbdbal, buyprice, sellprice, buyquantity, sellquantity)
            newsteemprice = steemp(steembal, steemprice)
            if int(time.time()/3600) > timeh:   # Every hour, withdraw sbd and convert
                timeh = int(time.time()/3600)
                steemjob()
                sbdbal = balance("SBD")
                sellprice = newsellprice
                sellquantity = sbdbal
                if sellquantity > 10:
                    print(bt.sell_limit("BTC-SBD", sellquantity, sellprice))
            if int(time.time()/600) > timet:    # Every 10 minutes, update balances
                timet = int(time.time()/600)
                tempbtcbal = balance("BTC")
                tempsbdbal = balance("SBD")
                tempsteembal = balance("STEEM")
                if tempbtcbal > 0.01:
                    cancel_all("buy")
                    time.sleep(2)
                    btcbal = balance("BTC")
                    buyprice = newbuyprice
                    buyquantity = round(btcbal/buyprice-0.0005,3)*0.9975
                    if buyquantity > 10:
                        print(bt.buy_limit("BTC-SBD", buyquantity, buyprice))
                if tempsbdbal > 10:
                    cancel_all("sell")
                    time.sleep(2)
                    sbdbal = balance("SBD")
                    sellprice = newsellprice
                    sellquantity = sbdbal
                    if sellquantity > 10:
                        print(bt.sell_limit("BTC-SBD", sellquantity, sellprice))
                if tempsteembal > 10:
                    cancel_steem()
                    time.sleep(2)
                    steembal = balance("STEEM")
                    steemprice = newsteemprice
                    steemquantity = steembal
                    if steemquantity > 10:
                        print(bt.sell_limit("BTC-STEEM", steemquantity, steemprice))
            if newbuyprice != buyprice:
                cancel_all("buy")
                time.sleep(2)
                btcbal = balance("BTC")
                buyprice = newbuyprice
                buyquantity = round(btcbal/buyprice-0.0005,3)*0.9975
                if buyquantity > 10:
                    print(bt.buy_limit("BTC-SBD", buyquantity, buyprice))
            if newsellprice != sellprice:
                cancel_all("sell")
                time.sleep(2)
                sbdbal = balance("SBD")
                sellprice = newsellprice
                sellquantity = sbdbal
                if sellquantity > 10:
                    print(bt.sell_limit("BTC-SBD", sellquantity, sellprice))
            if newsteemprice != steemprice:
                cancel_steem()
                time.sleep(2)
                steembal = balance("STEEM")
                steemprice = newsteemprice
                steemquantity = steembal
                if steemquantity > 10:
                    print(bt.sell_limit("BTC-STEEM", steemquantity, steemprice))
            time.sleep(random.uniform(3,7))
        except Exception as e:
            print(str(e))
            time.sleep(10)
            cancel_all("both")    # Cancel all orders
            cancel_steem()
            newbuyprice, newsellprice = (buyprice/10, sellprice*10)    # Set prices at safe numbers
            newsteemprice = steemprice*10

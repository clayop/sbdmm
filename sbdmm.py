import hashlib
import time
import requests
import hmac
import requests
import urllib.parse
import random
from piston.steem import Steem
from Crypto.Cipher import XOR
import base64
import yaml
import getpass

activebuy = 0

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

    def encrypt(key, plaintext):
      cipher = XOR.new(key)
      return base64.b64encode(cipher.encrypt(plaintext))

    def decrypt(key, ciphertext):
      cipher = XOR.new(key)
      return cipher.decrypt(base64.b64decode(ciphertext))

    def create_config():
        pw = getpass.getpass("Enter your password: ")
        repw = getpass.getpass("Confirm your password: ")
        if pw == repw:
            default = {"Account":{"Bittrex_API_Key":"", "Bittrex_API_Secret":"", "Bittrex_STEEM_Memo":"", "Steemit_Account":"", "Steemit_Active_Key":""}, "Market":{"Dust_Level":0.2, "Target_SBD_Price":0.96, "Spread":0.02, "Offset":0.00000000, "Batch_Amount":100, "Interval_Long":7200,"Interval_Short":1200}}
            for i in sorted(default):
                for j in sorted(default[i]):
                    msg = "Enter %s (Default: %s) : " % (str(j), str(default[i][j]))
                    if type(default[i][j]) is str:
                        if j == "Bittrex_API_Secret" or j == "Steemit_Active_Key":
                            inp = getpass.getpass(msg)
                            if inp != "":
                                default[i][j] = encrypt(pw, str(inp)).decode()
                        else:
                            inp = input(msg)
                            if inp != "":
                                if j == "Steemit_Account":
                                    default[i][j] = str(inp).lower()
                                else:
                                    default[i][j] = str(inp)
                    if type(default[i][j]) is int:
                        inp = input(msg)
                        if inp != "":
                            default[i][j] = int(inp)
                    if type(default[i][j]) is float:
                        inp = input(msg)
                        if inp != "":
                            default[i][j] = float(inp)
            with open("sbdmm_config.yml", 'w') as f:
                yaml.dump(default, f, default_flow_style=False)

    def avg_prices():
        ts = time.time() - 1800*13 + 1
        url = "https://poloniex.com/public?command=returnChartData&currencyPair=BTC_SBD&start="+str(ts)+"&end=9999999999&period=1800"
        histsbd = requests.get(url).json()
        url = "https://poloniex.com/public?command=returnChartData&currencyPair=USDT_BTC&start="+str(ts)+"&end=9999999999&period=1800"
        histbtc = requests.get(url).json()
        p = 0
        for i, j in zip(histsbd, histbtc):
            p += float(i["weightedAverage"])*float(j["weightedAverage"])
        ap = p/len(histsbd)
        bfbtc = float(requests.get("https://api.bitfinex.com/v1/pubticker/BTCUSD").json()["mid"])
        abtcp = (histbtc[-1]["weightedAverage"]+bfbtc)/2
        return (ap, abtcp)

    def balance(currency):
        res = bt.get_balance(currency)["result"]["Available"]
        if res == None:
            res = 0
        return res

    def prices(btcbal, sbdbal, buyprice=None, sellprice=None, buyquantity=None, sellquantity=None):
        avgp, abtcp = avg_prices()
        if avgp < target:
            avgp = target
        avgprice = avgp/abtcp
        avgpmargin = avgp+margin
        avgpricemargin = avgpmargin/abtcp
        if activebuy == 1:
            buyp = avgprice
            sellp = avgpricemargin
        elif activebuy == 0:
            btcsum = 0
            sbdsum = 0
            orderbook = bt.get_orderbook("BTC-SBD", "both")["result"]
            poloob = requests.get("https://poloniex.com/public?command=returnOrderBook&currencyPair=BTC_SBD&depth=50").json()
            polobidtotalsbd = 0
            polobidtotalbtc = 0
            poloasktotalsbd = 0
            poloasktotalbtc = 0
            for i in poloob["asks"]:
                poloasktotalbtc += float(i[0])*float(i[1])
                poloasktotalsbd += float(i[1])
                if poloasktotalbtc > btcbal:
                    poloaskp = poloasktotalsbd/poloasktotalbtc
                    break
            for i in poloob["bids"]:
                polobidtotalbtc += float(i[0])*float(i[1])
                polobidtotalsbd += float(i[1])
                if polobidtotalsbd > sbdbal:
                    polobidp = polobidtotalsbd/polobidtotalbtc
                    break
            buy = orderbook["buy"]
            sell = orderbook["sell"]
            buylimit = avgprice
            selllimit = avgpricemargin
            if buylimit > poloaskp*1.005:
                buylimit = poloaskp*1.005
            if selllimit < polobidp/1.005:
                selllimit = polobidp/1.005
            for i in buy:
                btcsum += i["Rate"]*i["Quantity"]
                buyp = i["Rate"]
                if btcsum >= dust*btcbal and buyp <= buylimit:
                    if buyprice != None and buyquantity != None:
                        if buyp == buyprice:
                            if i["Quantity"] >= (1+dust)*buyquantity:
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
                            if i["Quantity"] >= (1+dust)*sellquantity:
                                break
                        else:
                            break
                    else:
                        break
        return (buyp, sellp)

    def steemp(steembal, steemprice=None, steemquantity=None):
        orderbook = bt.get_orderbook("BTC-STEEM", "sell")["result"]
        poloob = requests.get("https://poloniex.com/public?command=returnOrderBook&currencyPair=BTC_STEEM&depth=50").json()
        polobidtotalbtc = 0
        polobidtotalsteem = 0
        for i in poloob["bids"]:
            polobidp = float(i[0])
            polobidtotalbtc += float(i[0])*float(i[1])
            polobidtotalsteem += float(i[1])
            if polobidtotalsteem > steembal:
                polobidp = polobidtotalbtc/polobidtotalsteem
                break
        steemsum = 0
        for i in orderbook:
            steemsum += i["Quantity"]
            sellp = i["Rate"]
            if steemsum >= dust*steembal and steemsum > 100:
                if steemprice != None and steemquantity != None:
                    if sellp == steemprice:
                        if i["Quantity"] >= (1+dust)*steemquantity:
                            break
                    else:
                        break
                else:
                    break
        if sellp < polobidp/1.005:
            sellp = polobidp/1.005
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
                        print("Cancelled SBD buy orders")
                if type == "sell":
                    if i["OrderType"] == "LIMIT_SELL":
                        bt.cancel(i["OrderUuid"])
                        print("Cancelled SBD sell orders")
            if type == "both":
                print("Cancelled all SBD orders")

    def cancel_steem():
        openo = bt.get_open_orders("BTC-STEEM")["result"]
        if openo != None:
            for i in openo:
                bt.cancel(i["OrderUuid"])
                print("Cancelled STEEM sell orders")

    def transfers():
        cancel_all("sell")
        time.sleep(1)
        sbdbal = balance("SBD")
        bt.withdraw("SBD", batch+0.01, account)
        stbal = steem.get_balances(account)
        ststeembal = float(stbal["balance"].split()[0])
        if ststeembal >= 10:
            steem.transfer("bittrex", ststeembal, "STEEM", memo=bittrexmemo, account=account)
            msg = "Transfered %s STEEM to Bittrex" % steembal
            print(msg)

    def convert():
        stbal = steem.get_balances(account)
        stsbdbal = float(stbal["sbd_balance"].split()[0])
        if stsbdbal >= batch:
            steem.convert(batch, account=account)
            msg = "Converted %s SBD" % str(batch)
            print(msg)

    def rounding(value):
        return float(str(value)[0:10])

    try:
        config_file = open("sbdmm_config.yml", "r")
        pw = getpass.getpass("Enter your password: ")
    except:
        create_config()
    config = yaml.load(config_file)
    account_conf = config["Account"]
    api_key = account_conf["Bittrex_API_Key"]
    api_secret = decrypt(pw, account_conf["Bittrex_API_Secret"]).decode()
    bittrexmemo = account_conf["Bittrex_STEEM_Memo"]
    account = account_conf["Steemit_Account"]
    wif = decrypt(pw, account_conf["Steemit_Active_Key"]).decode()
    market = config["Market"]
    dust = float(market["Dust_Level"])
    target = float(market["Target_SBD_Price"])
    margin = float(market["Spread"])
    offset = float(market["Offset"])
    batch = float(market["Batch_Amount"])
    intvlong = int(market["Interval_Long"])
    intvshort = int(market["Interval_Short"])

    bt = Bittrex(api_key, api_secret)
    steem = Steem(wif=wif, node="ws://127.0.0.1:8090")    #steem = Steem(wif=wif)
    cancel_all("both")
    cancel_steem()
    convert()
    time.sleep(2)
    btcbal = balance("BTC")
    sbdbal = balance("SBD")
    steembal = balance("STEEM")
    buyprice, sellprice = prices(btcbal, sbdbal)
    steemprice = steemp(steembal)
    buyprice = rounding(buyprice+offset)
    sellprice = rounding(sellprice-offset)
    steemprice = rounding(steemprice-offset)
    buyquantity = round(btcbal/buyprice-0.0005,3)*0.9975
    sellquantity = sbdbal
    steemquantity = steembal
    if buyquantity > 10:
        res = bt.buy_limit("BTC-SBD", buyquantity, buyprice)
        if res["success"] == True:
            print("Buy order %s SBD at %s" % (format(buyquantity, ".3f"), format(buyprice, ".8f")))
    if sellquantity > 10:
        res = bt.sell_limit("BTC-SBD", sellquantity, sellprice)
        if res["success"] == True:
            print("Sell order %s SBD at %s" % (format(sellquantity, ".3f"), format(sellprice, ".8f")))
    if steemquantity > 10:
        res = bt.sell_limit("BTC-STEEM", steemquantity, steemprice)
        if res["success"] == True:
            print("Sell order %s STEEM at %s" % (format(steemquantity, ".3f"), format(steemprice, ".8f")))
    time.sleep(random.uniform(3,7))
    timeh = int(time.time()/intvlong)
    timet = int(time.time()/intvshort)
    while True:
        try:
            newbuyprice, newsellprice = prices(btcbal, sbdbal, buyprice, sellprice, buyquantity, sellquantity)
            newsteemprice = steemp(steembal, steemprice, steemquantity)
            if int(time.time()/intvlong) > timeh:
                timeh = int(time.time()/intvlong)
                transfers()
                sbdbal = balance("SBD")
                sellprice = float(format(newsellprice-offset, ".8f"))
                sellquantity = sbdbal
                if sellquantity > 10:
                    res = bt.sell_limit("BTC-SBD", sellquantity, sellprice)
                    if res["success"] == True:
                        print("Sell order %s SBD at %s" % (format(sellquantity, ".3f"), format(sellprice, ".8f")))
                convert()
            if int(time.time()/intvshort) > timet:
                timet = int(time.time()/intvshort)
                tempbtcbal = balance("BTC")
                tempsbdbal = balance("SBD")
                tempsteembal = balance("STEEM")
                if tempbtcbal > 0.01:
                    cancel_all("buy")
                    time.sleep(1)
                    btcbal = balance("BTC")
                    buyprice = rounding(newbuyprice+offset)
                    buyquantity = round(btcbal/buyprice-0.0005,3)*0.9975
                    if buyquantity > 10:
                        res = bt.buy_limit("BTC-SBD", buyquantity, buyprice)
                        if res["success"] == True:
                            print("Buy order %s SBD at %s" % (format(buyquantity, ".3f"), format(buyprice, ".8f")))
                if tempsbdbal > 10:
                    cancel_all("sell")
                    time.sleep(1)
                    sbdbal = balance("SBD")
                    sellprice = rounding(newsellprice-offset)
                    sellquantity = sbdbal
                    if sellquantity > 10:
                        res = bt.sell_limit("BTC-SBD", sellquantity, sellprice)
                        if res["success"] == True:
                            print("Sell order %s SBD at %s" % (format(sellquantity, ".3f"), format(sellprice, ".8f")))
                if tempsteembal > 10:
                    cancel_steem()
                    time.sleep(1)
                    steembal = balance("STEEM")
                    steemprice = rounding(newsteemprice-offset)
                    steemquantity = steembal
                    if steemquantity > 10:
                        res = bt.sell_limit("BTC-STEEM", steemquantity, steemprice)
                        if res["success"] == True:
                            print("Sell order %s STEEM at %s" % (format(steemquantity, ".3f"), format(steemprice, ".8f")))
            if rounding(newbuyprice+offset) != buyprice:
                cancel_all("buy")
                time.sleep(1)
                btcbal = balance("BTC")
                buyprice = rounding(newbuyprice+offset)
                buyquantity = round(btcbal/buyprice-0.0005,3)*0.9975
                if buyquantity > 10:
                    res = bt.buy_limit("BTC-SBD", buyquantity, buyprice)
                    if res["success"] == True:
                        print("Buy order %s SBD at %s" % (format(buyquantity, ".3f"), format(buyprice, ".8f")))
            if rounding(newsellprice-offset) != sellprice:
                cancel_all("sell")
                time.sleep(1)
                sbdbal = balance("SBD")
                sellprice = rounding(newsellprice-offset)
                sellquantity = sbdbal
                if sellquantity > 10:
                    res = bt.sell_limit("BTC-SBD", sellquantity, sellprice)
                    if res["success"] == True:
                        print("Sell order %s SBD at %s" % (format(sellquantity, ".3f"), format(sellprice, ".8f")))
            if rounding(newsteemprice-offset) != steemprice:
                cancel_steem()
                time.sleep(1)
                steembal = balance("STEEM")
                steemprice = rounding(newsteemprice-offset)
                steemquantity = steembal
                if steemquantity > 10:
                    res = bt.sell_limit("BTC-STEEM", steemquantity, steemprice)
                    if res["success"] == True:
                        print("Sell order %s STEEM at %s" % (format(steemquantity, ".3f"), format(steemprice, ".8f")))
            time.sleep(random.uniform(3,7))
        except Exception as e:
            print(str(e))
            time.sleep(10)
            cancel_all("both")
            cancel_steem()
            newbuyprice, newsellprice = (buyprice/10, sellprice*10)
            newsteemprice = steemprice*10

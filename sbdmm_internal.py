import hashlib
import time
import requests
import hmac
import requests
import urllib.parse
import random
from steem import Steem
from steem.dex import Dex
from Crypto.Cipher import XOR
import base64
import yaml
import getpass

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
            default = {"Account":{"Steemit_Account":"", "Steemit_Active_Key":""}, "Market":{"Target_SBD_Price":1.00, "Spread":0.02, "Sensitivity":0.005, "Batch_Amount":200, "Interval_Long":3600,"Interval_Short":600}}
            for i in sorted(default):
                for j in sorted(default[i]):
                    msg = "Enter %s (Default: %s) : " % (str(j), str(default[i][j]))
                    if type(default[i][j]) is str:
                        if j == "Steemit_Active_Key":
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

    def steem_price():
        ts = time.time() - 1800*3 + 1
        url = "https://poloniex.com/public?command=returnChartData&currencyPair=BTC_STEEM&start="+str(ts)+"&end=9999999999&period=1800"
        histsteem = requests.get(url).json()
        url = "https://poloniex.com/public?command=returnChartData&currencyPair=USDT_BTC&start="+str(ts)+"&end=9999999999&period=1800"
        histbtc = requests.get(url).json()
        p = 0
        n = min(len(histsteem), len(histbtc))
        for i in range(n):
            p += float(histsteem[i]["weightedAverage"])*float(histbtc[i]["weightedAverage"])
        peg_price = p/n
        url = "https://api.coinmarketcap.com/v1/ticker/steem/"
        cmcsteem = float(requests.get(url).json()[0]["price_usd"])
        if abs(peg_price/cmcsteem-1) > 0.3:
            file = open("pricesbdmm.txt", "w")
            text = "%s %s %s"  % (str(histsteem), str(histbtc), str(cmcsteem))
            file.write(text)
            file.close()
            raise ValueError("Price Error")
        else:
            peg_price = (peg_price+cmcsteem)/2
            peg_price_target = peg_price/target
        return peg_price_target

    def balances():
        bals = steem.get_balances(account)
        steem_balance = float(bals["balance"].amount)
        sbd_balance = float(bals["sbd_balance"].amount)
        if steem_balance < 1:
            steem_balance = 0
        if sbd_balance < 1:
            sbd_balance = 0
        return steem_balance, sbd_balance

    def cancel():
        openorders = dex.returnOpenOrders(account=account)
        for i in openorders:
            dex.cancel(str(i["orderid"]), account=account)
            print("Cancelled order")
            time.sleep(3)

    def sell_sbd(price, amount):
        if amount > 0:
            price_margin = (1/price)*(1+margin)
            sell = dex.sell(amount, "SBD", price_margin, account=account)
            sell["operations"][0][1]["orderid"]
            msg = "Selling %s SBD at %s SBD/STEEM" % (str(amount), str(rounding(1/price_margin)))
            print(msg)
            time.sleep(3)

    def sell_steem(price, amount):  # peg point
        if amount > 0:
            sell = dex.sell(amount, "STEEM", price, account=account)
            sell["operations"][0][1]["orderid"]
            msg = "Selling %s STEEM at %s SBD/STEEM" % (str(amount), str(rounding(price)))
            print(msg)
            time.sleep(3)

    def convert():
        steembal, sbdbal = balances()
        if sbdbal >= batch:
            steem.convert(batch, account=account)
            msg = "Converted %s SBD" % str(batch)
            print(msg)
            time.sleep(3)

    def renew_order(peg_price):
        steembal, sbdbal = balances()
        sell_steem(peg_price, steembal)
        time.sleep(3)
        sell_sbd(peg_price, sbdbal)

    def rounding(value):
        return float(str(value)[0:5])

    try:
        config_file = open("sbdmm_config.yml", "r")
        pw = getpass.getpass("Enter your password: ")
    except:
        create_config()
    config = yaml.load(config_file)
    account_conf = config["Account"]
    account = account_conf["Steemit_Account"]
    wif = decrypt(pw, account_conf["Steemit_Active_Key"]).decode()
    pw = ""
    market = config["Market"]
    target = float(market["Target_SBD_Price"])
    margin = float(market["Spread"])
    sensitivity = float(market["Sensitivity"])
    batch = float(market["Batch_Amount"])
    intvlong = int(market["Interval_Long"])
    config_file.close()

    steem = Steem(wif=wif, node="ws://127.0.0.1:8090")    #steem = Steem(wif=wif, node="wss://node.steem.ws")
    dex = Dex(steem)
    wif = ""
    cancel()
    print("Done cancellation")
    time.sleep(5)
    try:
        old_price = steem_price()
        peg_price = old_price
    except:
        raise ValueError("Error")
        time.sleep(300)
    steembal, sbdbal = balances()
    sell_steem(peg_price, steembal)
    sell_sbd(peg_price, sbdbal)
    timeh = int(time.time()/intvlong)
    while True:
        try:
            new_price= steem_price()
            newsteembal, newsbdbal = balances()
            msg = str(rounding(new_price/old_price-1)*100)
            msg = "%s  %s / %s" % (time.ctime(), str(old_price)[0:7], str(new_price)[0:7])
            print(msg + "                                           \r", end="")
            peg_price = new_price
            if abs(new_price/old_price - 1) > 0.3:
                new_price = old_price
            if int(time.time()/intvlong) > timeh:
                timeh = int(time.time()/intvlong)
                cancel()
                convert()
                with open("sbdmm_config.yml", "r") as config_file:
                    config = yaml.load(config_file)
                    market = config["Market"]
                    target = float(market["Target_SBD_Price"])
                    margin = float(market["Spread"])
                    sensitivity = float(market["Sensitivity"])
                    batch = float(market["Batch_Amount"])
                    intvlong = int(market["Interval_Long"])
                renew_order(peg_price)
                old_price = new_price
            if abs(new_price/old_price - 1) > sensitivity or newsteembal > 1 or newsbdbal > 1:
                cancel()
                renew_order(peg_price)
                old_price = new_price
            time.sleep(random.uniform(3,7))
        except Exception as e:
            time.sleep(3)
            cancel()
            print(str(e))
            time.sleep(300)

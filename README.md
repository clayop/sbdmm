# Steem Dollar Pegging Bot

## Installation
```
sudo apt-get install python-dev python3-pip git
sudo pip3 install requests
sudo pip3 install steem
sudo pip3 install pycrypto
git clone https://github.com/clayop/sbdmm
screen -S sbdmm
cd sbdmm

# If you want to run a bot on Bittrex
python3 sbdmm.py

# If you want to run a bot on the internal market
python3 sbdmm_internal.py
```

## Miscellaneous
You can use your local Steem node by modifying the line 253, e.g. `steem = Steem(wif=wif, node="ws://127.0.0.1:8090")`

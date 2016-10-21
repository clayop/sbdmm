# Steem Dollar Pegging Bot

## Installation
```
sudo apt-get install python-dev python3-pip git
sudo pip3 install requests
sudo pip3 install steem-piston
sudo pip3 install pycrypto
git clone https://github.com/clayop/sbdmm
screen -S sbdmm
cd sbdmm
python3 sbdmm.py
```

## Miscellaneous
You can use your local Steem node by modifying the line 253, e.g. `steem = Steem(wif=wif, node="ws://127.0.0.1:8090")`

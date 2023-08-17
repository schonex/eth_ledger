#!/usr/bin/python3

from datetime import datetime
from pytz import timezone

from beancount.core import data
from beancount import loader
from beancount.parser import printer
from beancount.core.data import Booking
from decimal import Decimal as D

import pandas as pd
import argparse

from pycoingecko import CoinGeckoAPI

import pickle
import os

cg = CoinGeckoAPI()

if os.path.exists("./prices.pickle"):
  f = open('prices.pickle','rb')
  prices = pickle.load(f)
  f.close()
else:
  prices = {}

def get_price_on_date(d):
    global prices,cg
    if d in prices:
        return prices[d]
    else:
        data=cg.get_coin_history_by_id(id='ethereum', date=d)
        price=data['market_data']['current_price']['usd']
        prices[d] = round(price,2)
        return prices[d]

def createEntry(item, f):
    txtype, _, date, payee, nar, rounded_eth, price, usd, tag, link = item
    from_acct = prop_account if txtype == "P" else cl_account
    printer.print_entry(
        data.Transaction(
            meta = None,
            date = date,
            flag = "*",
            payee = payee,
            narration = nar,
            tags = {tag} if tag != None else set(),
            links = {link} if link != None else set(),
            postings = [
                data.Posting(to_account, data.Amount(D(rounded_eth), 'ETH'), data.Cost(D(str(price)),'USD', None, None), data.Amount(D(str(price)), 'USD'), None, None),
                data.Posting(from_acct, None, None, None, None, None),
                ]
        )
    ,file=f)

parser=argparse.ArgumentParser(description='Validator Rewards Beancount Generator')
parser.add_argument('--bean-file',type=str,default=None,required=True,help="Load previous file and continue from last block processed")
parser.add_argument('--es-file',type=str,default=None,required=True,help="Etherscan.io csv file to compare to")
parser.add_argument('--address',type=str,default=None,required=True,help="Asset address this eth is going to")

args = parser.parse_args()

cl_account = "Income:ETH:Staking:CL"
prop_account = "Income:ETH:Staking:MinerTips"
to_account= f"Assets:ETH:{args.address[-4:]}"

entries, errors, option_map = loader.load_file(args.bean_file)

csv = pd.read_csv(args.es_file)

f = open(args.bean_file,'w')

for ln in csv.iloc:
    txtype = "P"
    wei = ln['Value_IN(ETH)'] * 1_000_000_000_000_000_000

    d_utc = datetime.utcfromtimestamp(ln.UnixTimestamp)
    d_utc = d_utc.replace(tzinfo=timezone('UTC'))
    d_lcl = d_utc.astimezone(tz=timezone('US/Eastern'))
    p_date = d_utc.strftime('%d-%m-%Y') #dont forget this is 00:00:00 on UTC timezone

    payee = f"Ethereum MEV: {ln['From']}"
    nar = f"Proposal for block #{ln['Blockno']}"
    rounded_eth = str(round(ln['Value_IN(ETH)'], 6))
    price = get_price_on_date(p_date)
    usd = None
    tag = None
    link = ln['Blockno']
    t = (txtype, wei, d_lcl.date(), payee, nar, rounded_eth, price, usd, tag, link)
    createEntry(t,f)
    print(t)

f.close()
f = open('prices.pickle','wb')
pickle.dump(prices, f)
f.close()


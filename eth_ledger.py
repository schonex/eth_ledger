#!/usr/bin/python3

import asyncio
from web3 import AsyncWeb3
from web3.providers import WebsocketProviderV2
import argparse
import sys
import signal

from rich.progress import track
from rich.console import Console

from datetime import datetime
from pytz import timezone

from beancount.core import data
from beancount import loader
from beancount.parser import printer
from beancount.core.data import Booking
from decimal import Decimal as D

from pycoingecko import CoinGeckoAPI

parser=argparse.ArgumentParser(description='Validator Rewards Beancount Generator')
parser.add_argument('--el-url',required=True,help='beaocn chain RPC url')
parser.add_argument('--address',required=True, help="EL Address to monitor")
parser.add_argument('--count-stop',type=int,default=None,help="Greater or equal number of transactions to stop at")
parser.add_argument('--start-block',type=int,default=None,help="Start from block n instead of latest chain head")
parser.add_argument('--stop-block',type=int,default=None,help="Stop after processing block number")
parser.add_argument('--load-file',type=str,default=None,help="Load previous file and continue from last block processed")
parser.add_argument('--batch-size',type=int,default=100,help="Change batch size for requests going to the EL client, default is 100")
parser.add_argument('--internal',action='store_true',default=False)

args = parser.parse_args()

w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(args.el_url))#,request_kwargs={'timeout': 60}))

cg = CoinGeckoAPI()
console = Console()
"""
date_open = datetime(2022,1,1).date()
cl_account = data.Open(
        date=date_open,
        currencies={'ETH'},
        account="Income:ETH:Staking:CL",
        meta=None, #data.new_metadata(filename='./2022.beancount', lineno=0)
        booking=Booking.FIFO,
        )
prop_account = data.Open(
        date=date_open,
        currencies={'ETH'},
        account="Income:ETH:Staking:MinerTips",
        meta=None,
        booking=Booking.FIFO,
        )

to_account = data.Open(
        date=date_open,
        currencies={'USD'},
        account=f"Assets:ETH:{args.address[-4:]}",
        meta=None,
        booking=Booking.FIFO,
        )
"""
cl_account = "Income:ETH:Staking:CL"
prop_account = "Income:ETH:Staking:MinerTips"
to_account= f"Assets:ETH:{args.address[-4:]}"

class GracefulKiller:
  file = None
  def __init__(self, f):
    signal.signal(signal.SIGINT, self.exit_gracefully)
    signal.signal(signal.SIGTERM, self.exit_gracefully)
    self.file = f

  def exit_gracefully(self, *args):
    console.log("Closing file cleanly")
    self.file.close()
    sys.exit(0)

prices = {}
async def get_price_on_date(d):
    global prices,cg
    if d in prices:
        return prices[d]
    else:
        data=cg.get_coin_history_by_id(id='ethereum', date=d)
        price=data['market_data']['current_price']['usd']
        prices[d] = round(price,2)
        return prices[d]

async def trace_transactions(block_num):
    return w3http.tracing.trace_replay_block_transactions(block_num, ["Trace"])

async def processBlock(block,w3):
    miner = block['miner']
#    console.log(block['extraData'])
    address = args.address

    d_utc = datetime.utcfromtimestamp(block['timestamp'])
    d_utc = d_utc.replace(tzinfo=timezone('UTC'))
    d_lcl = d_utc.astimezone(tz=timezone('US/Eastern'))
    p_date = d_utc.strftime('%d-%m-%Y') #dont forget this is 00:00:00 on UTC timezone

    entries = []
    #check for withdrawals
    if 'withdrawals' in block: # doesn't happen until Shapella
      for w in block['withdrawals']:
        if w['address'] == address:
            eth = w['amount'] / 1_000_000_000
            price = await get_price_on_date(p_date)
            rounded_eth = str(round(eth, 6))
            usd = str(round(price * round(eth,6),2))
            vind = w['validatorIndex']
            payee = "Ethereum Blockchain"
            nar = f"Withdrawal for validator {vind} (CL Work)"
            entries.append(("W",w['amount'] * 1_000_000_000, d_lcl.date(), payee, nar, rounded_eth, price, usd, vind, block.number))

    if miner == args.address:
      #non MEV block
      totalfee = 0
      totalgas = 0
      for r in asyncio.as_completed([w3.eth.get_transaction_receipt(tx['hash']) for tx in block['transactions']]):
          recpt = await r
          tx = block['transactions'][recpt['transactionIndex']]
          gasPrice = int(tx['gasPrice'])
          gasUsed = int(recpt['gasUsed'])
          totalfee += gasUsed*gasPrice
          totalgas += gasUsed
      assert totalgas == int(block['gasUsed'])
      burned = int(block['baseFeePerGas']) * totalgas
      minerTip = totalfee - burned
      #prepare entry data for non MEV block
      eth = minerTip / 1_000_000_000_000_000_000
      rounded_eth = str(round(eth, 6))
      price = await get_price_on_date(p_date)
      usd = str(round(price * round(eth,6),2))
      payee = "Ethereum Blockchain"
      nar = f"Proposal for block #{block.number}"
      entries.append(("P",minerTip, d_lcl.date(), payee, nar, rounded_eth, price, usd, None, block.number))
    else:
      #mev block
      for tx in block['transactions']:
          if tx['to'] == address and tx['from'] == miner:
            eth = tx['value'] / 1_000_000_000_000_000_000
            rounded_eth = str(round(eth, 6))
            price = await get_price_on_date(p_date)
            usd = str(round(price * round(eth,6),2))
            payee = f"Ethereum MEV: {tx['from']}"
            nar = f"Proposal for block #{block.number}"
            entries.append(("P",tx['value'], d_lcl.date(), payee, nar, rounded_eth, price, usd, None, block.number))
            break

    if proposal and args.internal: #possible to have an internal tx from a diff entity (MEV BOT)
        res = await trace_transactions(block.number)
        for tx in res:
            for op in tx['trace']:
                if 'action' in op and 'to' in op['action']:
                 if op['action']['to'] == address:
                    code = await w3.eth.get_code(op['action']['from'])
                    if code != bytes(): #check if this is just the normal tx made above or if its from a smart contract
                      wei = op['action']['value']
                      eth = wei / 1_000_000_000_000_000_000 #from wei to eth
                      rounded_eth = str(round(eth, 6))
                      price = await get_price_on_date(p_date)
                      usd = None
                      payee = f"Ethereum MEV: {op['action']['from']}"
                      nar = f"Proposal for block #{block.number}"
                      entries.append(("P",wei, d_lcl.date(), payee, nar, rounded_eth, price, usd, None, block.number))
 
    return entries

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
    console.log(f"wrote block {link} entry")

async def main():
    start_block = args.start_block if args.start_block != None else -1
    if args.load_file != None:
      entries, errors, option_map = loader.load_file(args.load_file)
      s = set(entries[-1].links)
      start_block = max(int(s.pop()) + 1, args.start_block or 0)
      f = open(args.load_file, 'a')
    else:
      f = open("./2022.beancount",'w') #using 2022 for London's inception
      #printer.print_entry(cl_account, file=f)
      #printer.print_entry(prop_account, file=f)
      #printer.print_entry(to_account, file=f)
    min_block = 15537394 # London
    start_block = max(min_block, start_block)
    console.log(f"Starting at block {start_block}...")
    killer = GracefulKiller(f)
    console.log(f"Installed graceful killer")
    
#    async with AsyncWeb3.persistent_websocket(WebsocketProviderV2(args.el_url)) as w3:
    step = args.batch_size
    q = asyncio.Queue()
    currentBlock=await w3.eth.block_number
    console.log(f"chain height at: {currentBlock}")
    console.log(f"is connected: {await w3.is_connected()}")
    acct_bal = await w3.eth.get_balance(args.address)
    console.log(f"Acct Bal: {acct_bal/1_000_000_000_000_000_000}")
    bal = 0
    count = 0
    console.log(f"Set step size to: {step}")
    with console.status('[bold green]Processing blocks...') as status:
      for blockNum in range(start_block, currentBlock, step):
          processors = []
          last_time = 0
          console.log("submitting next batch")
          for result in asyncio.as_completed([w3.eth.get_block(i, full_transactions=True) for i in range(blockNum, blockNum+step, 1)]):
              b = await result
              last_time = b['timestamp']
              processors.append(asyncio.create_task(processBlock(b,w3)))
          await asyncio.gather(*processors)

          unpacked_results = []
          for r in processors:
              result = await r
              if len(result) > 0:
                  for item in result:
                      bal += item[1]
                      unpacked_results.append(item)
          
          unpacked_results.sort(key=lambda x: x[-1])
          for item in unpacked_results:
              createEntry(item,f)
              count +=1

          d_utc = datetime.utcfromtimestamp(last_time)
          console.log(f"Processed blocks {blockNum} -> {blockNum+step} last date: {d_utc}")
          if len(unpacked_results) > 0: 
              f.flush()

          if acct_bal == bal:
              console.log("Reached the same balance as account {args.address} has, quitting")
              break

          if args.count_stop != None and count >= args.count_stop:
              console.log("Reached number of transactions limited by, quitting")
              break

          if args.stop_block != None and blockNum >= args.stop_block:
              console.log("Reached stop block requested, quitting")
              break
    f.close()

if __name__ == "__main__":
    asyncio.run(main())

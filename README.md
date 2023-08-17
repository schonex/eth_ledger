You will have to pip3 install the following:
* web3.py
* rich
* beancount
* pycoingecko
* pytz

Converting an etherscan.io internal tx csv file after its downloaded:

1) add on the first line, at the very end, a new column by adding this string with the quotes ``,"Blank"``
2) run ./convert_internal.py --address 0xabcd --bean-file books/2023/internal_additions.beancount --es-file /my/path/to/internal-txs.csv

For the tax plugin to work, you must have the books full path defined in PYTHONPATH
```
export PYTHONPATH=/my/path/books
```

Make sure you change the asset account name in `books/accounts.beancount` to the last 4 characters of your account that you'll be running `eth_ledger.py --address` with

```
usage: as.py [-h] --el-url EL_URL --address ADDRESS [--count-stop COUNT_STOP] [--start-block START_BLOCK] [--stop-block STOP_BLOCK] [--load-file LOAD_FILE] [--batch-size BATCH_SIZE]

Validator Rewards Beancount Generator

options:
  -h, --help            show this help message and exit
  --el-url EL_URL       beaocn chain RPC url
  --address ADDRESS     EL Address to monitor
  --count-stop COUNT_STOP
                        Greater or equal number of transactions to stop at
  --start-block START_BLOCK
                        Start from block n instead of latest chain head
  --stop-block STOP_BLOCK
                        Stop after processing block number
  --load-file LOAD_FILE
                        Load previous file and continue from last block processed
  --batch-size BATCH_SIZE
                        Change batch size for requests going to the EL client, default is 100
```

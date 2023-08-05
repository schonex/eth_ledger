You will have to pip3 install the following:
* web3.py
* rich
* beancount
* pycoingecko
* pytz

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

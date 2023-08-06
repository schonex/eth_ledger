__plugins__ = ['tax_adder']

from beancount.core import data
from beancount.core import convert
from beancount.core import amount
from beancount.core.data import Booking
from decimal import Decimal as D

import yaml

l_acct = "Liabilities:Taxes:Income-Tax"
e_acct = "Expenses:Taxes:Staking"

rates_loc = None
def find_rate(rates, income):
    global rates_loc
    if isinstance(rates, dict) == False:
        #when NOT using progressive rates, only simple tax rate
        return rates

    if rates_loc != None:
        #on every other run, saves going thru all the rates
        if (rates_loc+1) < len(rates['rates']) and income >= rates['rates'][rates_loc+1]['base']:
            rates_loc += 1
        return rates['rates'][rates_loc]['rate']
    else:
        #only on the first run to determine where we start
        last_rate = 0
        rates_loc = -1
        for entry in rates['rates']:
            if income < entry['base']:
                break
            last_rate = entry['rate']
            rates_loc += 1
        return last_rate

def tax_adder(entries, options_map, config):
    config = config.split("=")
    if config[0] == "tax":
        rates = config[1]
        income = 0
    else:
        with open(config[1], 'r') as file:
          rates=yaml.safe_load(file)
        income = rates['initial-income']

    rate = find_rate(rates, income)
    #print(f"initial income {income} and rate {rate} loc {rates_loc}")
    for entry in entries:
        if type(entry) == data.Transaction and entry.payee != None:
            if "Ethereum" in entry.payee:
                last_posting = entry.postings[-1]

                usd_amount = convert.get_cost(entry.postings[0])
                income += usd_amount.number
                rate = find_rate(rates, income)
                #print(f"income: {income} rate: {rate} loc {rates_loc}")
                usd_taxable_amount = amount.mul(usd_amount,D(rate))

                l_posting = data.Posting(l_acct, amount.mul(usd_taxable_amount, D(-1)), None, None, None, None)
                e_posting = data.Posting(e_acct, usd_taxable_amount, None, None, None, None)

                entry.postings.remove(last_posting)
                entry.postings.append(l_posting)
                entry.postings.append(e_posting)
                entry.postings.append(last_posting)

    return entries, []


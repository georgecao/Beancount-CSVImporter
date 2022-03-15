"""csv importer.
"""
__copyright__ = "Copyright (C) 2021 Shangyan Zhou"
__license__ = "MIT"

import csv
import datetime
import enum
import io
import logging
import os
import re
import sys
from functools import cmp_to_key
from typing import Dict, Optional

import dateutil.parser
from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.number import D
from beancount.core.number import ZERO
from beancount.ingest import cache
from beancount.ingest import importer
import sqlite3

from beancount.utils.date_utils import parse_date_liberally

logging.basicConfig(stream=sys.stdout, level=logging.INFO)


class Status(enum.Enum):
    """Txn status."""

    # Txn success.
    TXN_SUCCESS = "[TXN_SUCCESS]"
    # Txn closed. Your money is still in your pocket.
    TXN_CLOSED = "[TXN_CLOSED]"
    # A transaction success earlier, then refunded due to some reason.
    REFUND_SUCCESS = "[REFUND_SUCCESS]"
    # Transfer from your account to others.
    REPAYMENT_SUCCESS = "[REPAYMENT_SUCCESS]"
    # Unknown, default value
    UNKNOWN = "[UNKNOWN]"


class Col(enum.Enum):
    """The set of interpretable columns."""

    # Transaction's unique No.
    TXN_NO = "TXN_NO"

    # Merchant order No.
    MERCHANT_NO = "MERCHANT_NO"

    # The settlement date, the date we should create the posting at.
    DATE = "DATE"

    # The date at which the transaction took place.
    TXN_DATE = "TXN_DATE"

    # The time at which the transaction took place.
    # Beancount does not support time field -- just add it to metadata.
    TXN_TIME = "TXN_TIME"

    # The payee field.
    PAYEE = "PAYEE"

    # The narration fields. Use multiple fields to combine them together.
    NARRATION = "NARRATION"

    # The amount being posted.
    AMOUNT = "AMOUNT"

    # Debits and credits being posted in separate, dedicated columns.
    AMOUNT_DEBIT = "DEBIT"
    AMOUNT_CREDIT = "CREDIT"

    # Transaction status.
    STATUS = "STATUS"

    # Transaction type.
    TYPE = "TYPE"

    # The balance amount, after the row has posted.
    BALANCE = "BALANCE"

    # A column which says DEBIT or CREDIT (generally ignored).
    DR_CR = "DR_CR"

    # Account name.
    ACCOUNT = "ACCOUNT"

    # Line Number.
    LINE_NO = "LINE_NO"


class AccountType(enum.Enum):
    # Assets
    ASSETS = "[ASSETS]"

    # Liabilities
    LIABILITIES = "[LIABILITIES]"

    # Equity
    EQUITY = "[EQUITY]"

    # Income
    INCOME = "[INCOME]"

    # Expenses
    EXPENSES = "[EXPENSES]"

    # Default account type.
    UNKNOWN = "[UNKNOWN]"


class DrCr(enum.Enum):
    DEBIT = "[DEBIT]"

    CREDIT = "[CREDIT]"

    # For asset transfer and the like
    UNCERTAINTY = "[UNCERTAINTY]"


def cast_to_decimal(amount: str):
    """Cast the amount to either an instance of Decimal or None.

    Args:
        amount: A string of amount. The format may be '¥1,000.00', '5.20', '200'
    Returns:
        The corresponding Decimal of amount.
    """
    if amount is None:
        return None
    amount = "".join(amount.split(","))
    numbers = re.findall(r"\d+\.?\d*", amount)
    assert len(numbers) == 1
    return D(numbers[0])


def strip_blank(contents):
    """ 
    strip the redundant blank in file contents.
    """
    with io.StringIO(contents) as csvfile:
        csvreader = csv.reader(csvfile, delimiter=",", quotechar='"')
        rows = []
        for row in csvreader:
            rows.append(",".join(['"{}"'.format(x.strip()) for x in row]))
        return "\n".join(rows)


def get_amount(config: Dict[Col, str], row, allow_zero_amounts: bool = False):
    """Get the amount columns of a row.

    Args:
        config: A dict of Col to row index.
        row: A row array containing the values of the given row.
        allow_zero_amounts: Is a transaction with amount D('0.00') okay? If not,
            return (None, None).
    Returns:
        A pair of (debit-amount, credit-amount), both of which are either an
        instance of Decimal or None, or not available.
    """
    amount, decimal = None, None
    if Col.AMOUNT in config:
        amount = row[config[Col.AMOUNT]]
        decimal = cast_to_decimal(amount) if amount else None
    else:
        debit, credit = [
            row[config[col]] if col in config else None
            for col in [Col.AMOUNT_DEBIT, Col.AMOUNT_CREDIT]
        ]

    # If zero amounts aren't allowed, return null value.
    is_zero_amount = decimal is not None and decimal == ZERO
    if not allow_zero_amounts and is_zero_amount:
        return None
    return decimal


def get_amounts(config: Dict[Col, str], row, drcr: DrCr, allow_zero_amounts: bool = False):
    """Get the amount columns of a row.

    Args:
        config: A dict of Col to row index.
        row: A row array containing the values of the given row.
        drcr: debit or credit type.
        allow_zero_amounts: Is a transaction with amount D('0.00') okay? If not,
            return (None, None).
    Returns:
        A pair of (debit-amount, credit-amount), both of which are either an
        instance of Decimal or None, or not available.
    """
    debit, credit = None, None
    if Col.AMOUNT in config:
        amount = row[config[Col.AMOUNT]]
        # Distinguish debit or credit
        if drcr == DrCr.CREDIT:
            credit = amount
        else:
            debit = amount
    else:
        debit, credit = [
            row[config[col]] if col in config else None
            for col in [Col.AMOUNT_DEBIT, Col.AMOUNT_CREDIT]
        ]

    # If zero amounts aren't allowed, return null value.
    is_zero_amount = (credit is not None and cast_to_decimal(credit) == ZERO) and (
            debit is not None and cast_to_decimal(debit) == ZERO
    )
    if not allow_zero_amounts and is_zero_amount:
        return None, None

    return (
        -cast_to_decimal(debit) if debit else None,
        cast_to_decimal(credit) if credit else None,
    )


def get_debit_credit_status(config: [Col, str], row, dr_cr_dict):
    """Get the status which says DEBIT or CREDIT of a row.
    """

    try:
        dr_cr = None
        columns = [Col.DR_CR, Col.STATUS, Col.NARRATION]

        for column in columns:
            if column in config:
                value = row[config[column]]
                if value in dr_cr_dict:
                    dr_cr = dr_cr_dict[value]
                    if dr_cr != DrCr.UNCERTAINTY:
                        break

        if dr_cr:
            return dr_cr
        else:
            if Col.AMOUNT_CREDIT in config and row[config[Col.AMOUNT_CREDIT]]:
                return DrCr.CREDIT
            elif Col.AMOUNT_DEBIT in config and row[config[Col.AMOUNT_DEBIT]]:
                return DrCr.DEBIT
            else:
                return DrCr.UNCERTAINTY
    except KeyError:
        return DrCr.UNCERTAINTY


class Importer(importer.ImporterProtocol):
    """Importer for csv files."""

    def __init__(
            self,
            config: Dict[Col, str],
            default_account: str,
            currency: str,
            file_name_prefix: str,
            skip_lines: int = 0,
            dr_cr_dict: Optional[Dict] = None,
            refund_keyword: str = None,
            account_map: Dict = {},
            non_fulfillment_status: str = '交易关闭',
    ):
        """Constructor.

        Args:
          config: A dict of Col enum types to the names or indexes of the columns.
          default_account: An account string, the default account to post this to.
          currency: A currency string, the currency of this account.
          file_name_prefix: Used for identification.
          skip_lines: Skip first x (garbage) lines of file.
          dr_cr_dict: A dict to determine whether a transaction is credit or debit.
          refund_keyword: The keyword to determine whether a transaction is a refund.
          account_map: A dict to find the account corresponding to the transactions.
        """

        assert isinstance(config, dict), "Invalid type: {}".format(config)
        self.config = config

        self.currency = currency
        assert isinstance(skip_lines, int)
        self.skip_lines = skip_lines
        self.dr_cr_dict = dr_cr_dict
        self.refund_keyword = refund_keyword
        self.non_fulfillment_status = non_fulfillment_status
        self.account_map = account_map
        self.file_name_prefix = file_name_prefix
        self.dateutil_kwds = None

    def file_date(self, file):
        """Get the maximum date from the file."""
        config, has_header = normalize_config(self.config, file.contents(), self.skip_lines)
        if Col.DATE in config:
            reader = csv.reader(io.StringIO(strip_blank(file.contents())))
            for _ in range(self.skip_lines):
                next(reader)
            if has_header:
                next(reader)
            max_date = None
            for row in reader:
                if not row:
                    continue
                if row[0].startswith("#"):
                    continue
                date_str = row[config[Col.DATE]]
                date = parse_date_liberally(date_str, self.dateutil_kwds)
                if max_date is None or date > max_date:
                    max_date = date
            return max_date

    def identify(self, file: cache._FileMemo):
        if file.mimetype() != "text/csv":
            return False
        if not os.path.basename(file.name).startswith(self.file_name_prefix):
            return False

        config, _ = normalize_config(self.config, file.contents(), self.skip_lines)
        return len(config) == len(self.config)

    def extract(self, file, existing_entries=None):
        entries = []
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        sql = "CREATE TABLE txn ({})"
        ddl = []
        for col in list(Col):
            if len(ddl) > 0:
                ddl.append(',')
            ddl.append(col.value)
            if col is Col.LINE_NO:
                data_type = 'integer'
            else:
                data_type = 'text'

            ddl.append(data_type)
            if col is Col.TXN_NO:
                ddl.append('primary key')

        con.execute(sql.format(" ".join(ddl)))
        # Normalize the configuration to fetch by index.
        config, has_header = normalize_config(self.config, file.contents(), self.skip_lines)

        reader = csv.reader(io.StringIO(strip_blank(file.contents())))

        # Skip garbage lines
        for _ in range(self.skip_lines):
            next(reader)

        # Skip header, if one was detected.
        if has_header:
            next(reader)

        def get(single_row, col_type):
            return single_row[config[col_type]].strip() if col_type in config else None

        # Parse all the transactions.
        def prepare():
            for idx, r in enumerate(reader, 1):
                if not r:
                    continue
                if r[0].startswith("#"):
                    continue
                if r[0].startswith("-----------"):
                    break

                # Extract the data we need from the row, based on the configuration.
                pairs = {Col.STATUS: get(r, Col.STATUS),
                         Col.TXN_DATE: get(r, Col.TXN_DATE),
                         Col.TXN_TIME: get(r, Col.TXN_TIME),
                         Col.DATE: get(r, Col.DATE),
                         Col.TXN_NO: get(r, Col.TXN_NO),
                         Col.MERCHANT_NO: get(r, Col.MERCHANT_NO),
                         # The account that receives from or transfer to other accounts. This one belongs to you.
                         Col.ACCOUNT: get(r, Col.ACCOUNT),
                         # Category
                         Col.TYPE: get(r, Col.TYPE),
                         # The peer account
                         Col.PAYEE: get(r, Col.PAYEE),
                         # The goods
                         Col.NARRATION: get(r, Col.NARRATION),
                         # Debit or Credit transaction.
                         Col.DR_CR: get_debit_credit_status(config, r, self.dr_cr_dict),
                         # Transaction amount.
                         Col.AMOUNT: get(r, Col.AMOUNT),
                         # Line index.
                         Col.LINE_NO: idx}

                names = []
                dat = []
                marks = []
                for k, v in pairs.items():
                    if v is None:
                        continue
                    names.append(k.value)
                    if isinstance(v, DrCr):
                        dat.append(v.value)
                    else:
                        dat.append(v)
                    marks.append('?')

                if len(names) > 0:
                    sql_insert = "insert into txn ({}) values ({})".format(",".join(names), ",".join(marks))
                    con.execute(sql_insert, tuple(dat))

        # Prepare the transaction records.
        prepare()

        def process(record, ignore_txn: bool = True):
            status = record[Col.STATUS.value]
            payee = record[Col.PAYEE.value]
            narration = record[Col.NARRATION.value]
            txn_type = record[Col.TYPE.value]
            account = record[Col.ACCOUNT.value]
            index = record[Col.LINE_NO.value]
            txn_date = record[Col.TXN_DATE.value]
            txn_time = record[Col.TXN_TIME.value]
            date = record[Col.DATE.value]
            amount_val = record[Col.AMOUNT.value]
            amount = cast_to_decimal(amount_val) if amount_val else None
            dr_cr = DrCr(record[Col.DR_CR.value])
            txn_no = record[Col.TXN_NO.value]
            merchant_no = record[Col.MERCHANT_NO.value]

            # Maybe you close the txn without paying, or you requested a refund after your purchase.
            # We will not handle this unless we found it's matching refund transaction.
            # Otherwise, just ignore it, b/c there was no money transferred between those accounts.
            is_wechat_txn = self.refund_keyword in status and dr_cr == DrCr.CREDIT
            is_alipay_txn = status == self.non_fulfillment_status
            if (is_wechat_txn or is_alipay_txn) and ignore_txn:
                return None

            prev_txn = None
            if self.refund_keyword in status and dr_cr != DrCr.CREDIT:
                # For WeChat, merchant_no == txn_no and txn_no != txn_no
                # For Alipay, merchant_no == merchant_no and txn_no != txn_no
                no = merchant_no or txn_no
                for prev_row in con.execute(
                        "select * from txn where MERCHANT_NO = ? and TXN_NO != ?", (no, txn_no)):
                    if prev_txn is None:
                        prev_txn = process(prev_row, False)
                    else:
                        raise ValueError("Should be exactly one transaction.")

            # print(alt, another_account, sep="%%")
            # Create a transaction
            meta = data.new_metadata(file.name, index)
            if txn_date is not None:
                meta["date"] = parse_date_liberally(txn_date)
            if txn_time is not None:
                meta["time"] = str(dateutil.parser.parse(txn_time).time())
            date = parse_date_liberally(date)
            txn = data.Transaction(
                meta,
                date,
                self.FLAG,
                payee,
                narration,
                data.EMPTY_SET,
                data.EMPTY_SET,
                [],
            )

            # Skip empty transactions
            if amount is None:
                return None

            units = Amount(amount, self.currency)

            if dr_cr == DrCr.UNCERTAINTY:
                dr_cr = DrCr.DEBIT

            primary_account, secondary_account = None, None
            if prev_txn is None:
                # We will define an account based on payee, narration and type.
                alt = [payee, narration, txn_type]
                if dr_cr == DrCr.DEBIT:  # owner's account <- another account
                    primary_account = search_account(self.account_map, alt, DrCr.CREDIT)
                    secondary_account = search_account(self.account_map, [account], DrCr.DEBIT)
                elif dr_cr == DrCr.CREDIT:  # owner's account -> another account
                    primary_account = search_account(self.account_map, [account], DrCr.CREDIT)
                    secondary_account = search_account(self.account_map, alt, DrCr.DEBIT)
            else:
                # Just swap the accounts. It's a refund transaction.
                secondary_account = prev_txn.postings[0].account
                primary_account = prev_txn.postings[1].account

            txn.postings.append(
                data.Posting(primary_account, -units, None, None, None, None)
            )
            txn.postings.append(
                data.Posting(secondary_account, units, None, None, None, None)
            )
            # Add the transaction to the output list
            logging.debug(txn)
            entries.append(txn)
            return txn

        # Must traverse the records in ascend order, give us a chance to handle refund records
        # and transfer the refund back to the original account.
        for row in con.execute("SELECT * FROM txn ORDER BY TXN_DATE ASC"):
            process(row)

        return entries


def normalize_config(config, head, skip_lines: int = 0):
    """Using the header line, convert the configuration field name lookups to int indexes.

    Args:
      config: A dict of Col types to string or indexes.
      head: A string, some decent number of bytes of the head of the file.
      skip_lines: Skip first x (garbage) lines of file.
    Returns:
      A pair of
        A dict of Col types to integer indexes of the fields, and
        a boolean, true if the file has a header.
    Raises:
      ValueError: If there is no header and the configuration does not consist
        entirely of integer indexes.
    """
    # Skip garbage lines before sniffing the header
    assert isinstance(skip_lines, int)
    assert skip_lines >= 0
    for _ in range(skip_lines):
        head = head[head.find("\n") + 1:]
    head = head[: head.find("\n") + 1]

    head = strip_blank(head)
    has_header = csv.Sniffer().has_header(head)
    if has_header:
        header = next(csv.reader(io.StringIO(head)))
        # A name to index mapping
        field_map = {
            field_name.strip(): index for index, field_name in enumerate(header)
        }
        index_config = {}
        for field_type, field in config.items():
            if isinstance(field, str):
                field = field_map[field]
            # Filed type to it's index in the row, or it's name
            index_config[field_type] = field
    else:
        if any(not isinstance(field, int) for field_type, field in config.items()):
            raise ValueError(
                "csv config without header has non-index fields: " "{}".format(config)
            )
        index_config = config
    return index_config, has_header


def search_account(account_map, keywords, dr_cr: DrCr):
    if dr_cr == DrCr.CREDIT:
        key = "credit"
    elif dr_cr == DrCr.DEBIT:
        key = "debit"
    else:
        key = "assets"

    mapping = account_map[key]
    if mapping:
        # Keywords have priority and according to their index in the list.
        default_name = None
        for keyword in keywords:
            account_name, match_length, default_name = mapping_account(mapping, keyword)
            if account_name:
                return account_name

        # Backup accounts
        if dr_cr != DrCr.UNCERTAINTY:
            backup = search_account(account_map, keywords, DrCr.UNCERTAINTY)
            if backup:
                return backup
        # Found nothing, use the default account instead.
        return default_name


DEFAULT_KEYWORD = "DEFAULT"


def mapping_account(account_map, keyword):
    """Finding which key of account_map contains the keyword, return the corresponding value.

    Args:
      account_map: A dict of account keywords string (each keyword separated by "|") to account name.
      keyword: A keyword string.
    Return:
      An account name string. Try to find the longest matching account.
    Raises:
      KeyError: If "DEFAULT" keyword is not in account_map.
    """

    if not keyword:
        return None, None, None
    if DEFAULT_KEYWORD not in account_map:
        raise KeyError("DEFAULT is not in " + account_map.__str__)
    default_name = account_map[DEFAULT_KEYWORD]
    account_name = account_map[keyword] if keyword in account_map else None
    match_length = len(DEFAULT_KEYWORD)
    max_len = 0
    if account_name:
        return account_name, len(account_name), default_name
    for account_keywords in sorted(account_map.keys()):
        if account_keywords == DEFAULT_KEYWORD:
            continue
        match = re.search(account_keywords, keyword)
        if match:
            start, end = match.span()
            length = end - start
            if max_len < length:
                max_len = length
                match_length = length
                account_name = account_map[account_keywords]
    return account_name, match_length, default_name

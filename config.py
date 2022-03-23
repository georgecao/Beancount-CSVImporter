#!/usr/bin/env python3
import sys

sys.path.append("./importers")
from CSVImporter import Col, Importer, DrCr

currency = "CNY"

# From the owner's perspective.
dr_cr_dict = {
    "支出": DrCr.CREDIT,
    "已支出": DrCr.CREDIT,
    "还款成功": DrCr.CREDIT,
    "余额宝-自动转入": DrCr.CREDIT,
    "收入": DrCr.DEBIT,
    "已收入": DrCr.DEBIT,
    "退款成功": DrCr.DEBIT,
    "其他": DrCr.UNCERTAINTY,
}

refund_keyword = "退款"

config_wechat = {
    Col.TXN_NO: "交易单号",
    Col.MERCHANT_NO: "商户单号",
    Col.DATE: "交易时间",
    Col.PAYEE: "交易对方",
    Col.NARRATION: "商品",
    Col.ACCOUNT: "支付方式",
    Col.AMOUNT: "金额(元)",
    Col.DR_CR: "收/支",
    Col.STATUS: "当前状态",
    Col.TXN_TIME: "交易时间",
    Col.TXN_DATE: "交易时间",
    Col.TYPE: "交易类型",
}

config_alipay = {
    Col.TXN_NO: "交易订单号",
    Col.MERCHANT_NO: "商家订单号",
    Col.DATE: "交易时间",
    Col.PAYEE: "交易对方",
    Col.NARRATION: "商品说明",
    Col.ACCOUNT: "收/付款方式",
    Col.AMOUNT: "金额",
    Col.DR_CR: "收/支",
    Col.STATUS: "交易状态",
    Col.TXN_TIME: "交易时间",
    Col.TXN_DATE: "交易时间",
    Col.TYPE: "交易分类",
}

account_map = {
    # Accounts that name is clear and has no ambiguity. And can be either credit or debit.
    "assets": {
        "DEFAULT": "Assets:Cash",
        "余额宝": "Assets:Alipay:Yuebao",
        "余额宝-转出到余额 ": "Assets:Alipay:Yuebao",
        "余额宝-自动转入": "Assets:Alipay:Yuebao",
        "余额": "Assets:Alipay:Yue",
        "零钱": "Assets:WeChat:Pocket",
        "/": "Assets:WeChat:Pocket",
        "余额&红包": "Assets:Alipay:Yue",
        "花呗": "Liabilities:CreditPay:Alipay:HuaBei",
        "浦发银行信用卡(0083)": "Liabilities:CreditCard:SPD:0083",
        "浦发银行(0083)": "Liabilities:CreditCard:SPD:0083",
        "美团金融服务": "Liabilities:CreditCard:MeiTuan",
    },
    "credit": {
        "DEFAULT": "Income:Cash",
        "余额宝-[\\d.]{10}-收益发放": "Income:Investment:Interest",
        "微信红包": "Income:RedPacket:WeChat",
        "转账": "Income:Transfer",
        "二维码收款": "Income:Transfer"
    },
    "debit": {
        "DEFAULT": "Expenses:DailyNecessities",
        "余额宝-自动转入": "Assets:Alipay:Yuebao",
        "水滴筹": "Expenses:",
        "亿方物业": "Expenses:RealEstate",
        "交通出行": "Expenses:Transportation",
        "北京一卡通": "Expenses:Transportation",
        "商业服务": "Expenses:BusinessService",
        "天眼查": "Expenses:BusinessService",
        "顺丰速运": "Expenses:BusinessService",
        "信用借还": "Expenses:Repayment",
        "京东商城平台商户": "Expenses:Repayment",
        "发出群红包": "Expenses:RedPacket:WeChat",
    },
}

wechat_importer = Importer(
    config_wechat,
    "",
    currency,
    "微信支付账单",
    16,
    dr_cr_dict,
    refund_keyword,
    account_map,
)

alipay_importer = Importer(
    config_alipay,
    "",
    currency,
    "alipay_record",
    1,
    dr_cr_dict,
    refund_keyword,
    account_map,
)

CONFIG = [wechat_importer, alipay_importer]

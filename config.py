#!/usr/bin/env python3
import sys

sys.path.append("./importers")
from CSVImporter import Col, Importer, DeCr

currency = "CNY"

decr_dict = {
    "支出": DeCr.DEBIT,
    "已支出": DeCr.DEBIT,
    "还款成功": DeCr.DEBIT,
    "收入": DeCr.CREDIT,
    "已收入": DeCr.CREDIT,
    "退款成功": DeCr.CREDIT,
    "其他": DeCr.UNCERTAINTY,
}

refund_keyword = "退款"

config_wechat = {
    Col.TXN_NO: "交易单号",
    Col.DATE: "交易时间",
    Col.PAYEE: "交易对方",
    Col.NARRATION: "商品",
    Col.ACCOUNT: "支付方式",
    Col.AMOUNT: "金额(元)",
    Col.DECR: "收/支",
    Col.STATUS: "当前状态",
    Col.TXN_TIME: "交易时间",
    Col.TXN_DATE: "交易时间",
}

config_alipay = {
    Col.TXN_NO: "交易订单号",
    Col.DATE: "交易时间",
    Col.PAYEE: "交易对方",
    Col.NARRATION: "商品说明",
    Col.ACCOUNT: "收/付款方式",
    Col.AMOUNT: "金额",
    Col.DECR: "收/支",
    Col.STATUS: "交易状态",
    Col.TXN_TIME: "交易时间",
    Col.TXN_DATE: "交易时间",
    Col.TYPE: "交易分类",
}

account_map = {
    "assets": {
        "DEFAULT": "Unknown",
        "余额宝": "Assets:Alipay:Yuebao",
        "余额": "Assets:Alipay",
        "花呗": "Liabilities:CreditPay:Alipay:HuaBei",
        "余额&红包": "Assets:Alipay",
        "浦发银行信用卡(0083)": "Liabilities:CreditCard:SPD:0083",
        "浦发银行(0083)": "Liabilities:CreditCard:SPD:0083",
        "零钱": "Assets:WeChat:Pocket",
        "/": "Assets:WeChat:Pocket",
        "招商银行储蓄卡(2459)": "Assets:Card:CMB:2459",
        "招商银行(5407)": "Assets:Card:CMB:2459",
    },
    "debit": {
        "DEFAULT": "Expenses:DailyNecessities",
        "水滴筹": "Expenses:Transportation",
        "亿方物业": "Expenses:RealEstate",
        "交通出行": "Expenses:Transportation",
        "信用借还": "Expenses:Repayment",
        "充值缴费": "Expenses:Payment",
        "医疗健康": "Expenses:HealthCare",
        "医院": "Expenses:HealthCare",
        "微保": "Expenses:HealthCare",
        "急诊抢救中心": "Expenses:HealthCare",
        "投资理财": "Expenses:Investment",
        "文化休闲": "Expenses:CultureLeisure",
        "亚马逊电子书包月服务": "Expenses:CultureLeisure:Books",
        "日用百货": "Expenses:DailyNecessities",
        "美宜佳": "Expenses:DailyNecessities",
        "超市": "Expenses:DailyNecessities",
        "便利店": "Expenses:DailyNecessities",
        "欢朋商场": "Expenses:DailyNecessities",
        "收款方备注:二维码收款": "Expenses:DailyNecessities",
        "爱车养车": "Expenses:CarCare",
        "生活服务": "Expenses:LifeServices",
        "转账红包": "Expenses:MoneyTransfer",
        "酒店旅游": "Expenses:HotelTravel",
        "天时同城": "Expenses:HotelTravel",
        "临春岭": "Expenses:HotelTravel",
        "云港科技": "Expenses:HotelTravel",
        "皇包车": "Expenses:HotelTravel",
        "三亚顶悦要客旅行有限公司": "Expenses:HotelTravel",
        "三亚凤凰岭文化旅游有限公司": "Expenses:HotelTravel",
        "三亚迎朋酒店公寓管理有限公司": "Expenses:HotelTravel",
        "餐饮美食": "Expenses:FoodBeverage",
        "熟食": "Expenses:FoodBeverage",
        "包子": "Expenses:FoodBeverage",
        "肯德基": "Expenses:FoodBeverage",
        "餐饮店": "Expenses:FoodBeverage",
        "餐厅": "Expenses:FoodBeverage",
        "肉夹馍": "Expenses:FoodBeverage",
        "烤串": "Expenses:FoodBeverage",
        "农夫山泉": "Expenses:FoodBeverage",
        "汉堡王": "Expenses:FoodBeverage",
        "美团/大众点评点餐订单": "Expenses:FoodBeverage",
        "成都阳光颐和物业管理有限公司三亚分公司": "Expenses:FoodBeverage",
        "舌尖上的嘿小面": "Expenses:FoodBeverage",
        "汤面饭": "Expenses:FoodBeverage",
        "饺子": "Expenses:FoodBeverage",
        "牛奶": "Expenses:FoodBeverage",
        "米粉": "Expenses:FoodBeverage",
        "和番丼饭": "Expenses:FoodBeverage",
        "拉面": "Expenses:FoodBeverage",
        "水果": "Expenses:FoodBeverage",
        "星巴克": "Expenses:FoodBeverage:Coffee",
        "浦发银行信用卡(0083)": "Liabilities:CreditCard:SPD:0083",
        "天猫超市": "Expenses:DailyNecessities",
        "耳机": "Expenses:DigitalEquipment:Audio",
        "火车票": "Expenses:Transportation:Railway",
        "打车": "Expenses:Transportation:Taxi",
        "美团金融服务": "Liabilities:CreditCard:MeiTuan",
        "王鑫Sherry": "Assets:Receivables:WangXinSherry",
        "朴老师": "Assets:Receivables:Design",
        "PtrkTao": "Assets:Receivables:Design",
        "转账备注": "Expenses:Other",
    },
}

wechat_importer = Importer(
    config_wechat,
    "",
    currency,
    "微信支付账单",
    16,
    decr_dict,
    refund_keyword,
    account_map,
)

alipay_importer = Importer(
    config_alipay,
    "",
    currency,
    "alipay_record",
    1,
    decr_dict,
    refund_keyword,
    account_map,
)

CONFIG = [wechat_importer, alipay_importer]

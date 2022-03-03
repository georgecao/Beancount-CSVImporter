# Usage

```bash
bean-extract config.py 微信支付账单_xxx.csv/alipay_record_xxx.csv > xxxxxxx.bean
```

**Notice:The raw data filename can only start with "微信支付账单" or "alipay_record."**

可以阅读[用于支付宝和微信账单的Beancount Importer](https://blog.sy-zhou.com/%E7%94%A8%E4%BA%8E%E6%94%AF%E4%BB%98%E5%AE%9D%E5%92%8C%E5%BE%AE%E4%BF%A1%E8%B4%A6%E5%8D%95%E7%9A%84beancount-import/)，了解更多细节。

* 账单： 记录资金从一个账户转移到另一个账户。每一个交易记录中，必然有一个账户是属于你的。
* 退款：支出流程的逆向流程。一般是原路返回，微信支持退回零钱。
* 部分退款如何记账？
* 收入：资金从别人的账户转入到你自己的账户。只关乎资金的流行
* 支出：资金从你自己的账户转出到别人的账户。只关乎资金的流行


## 特殊场景
- 借钱
- 垫付
- 报销
- 折旧
- 红包



复试记账每一笔都和自己有关。所以能区分出具体的用途。

收入在复试记账里面怎么理解？


## 理解会计恒等式
(Income + Liabilities) + (Assets + Expenses) + Equity = 0。

Assets:: 你所拥有的东西。别人欠**你的**钱（应收账款）和你欠别人的钱（负债）都是你的资产。
Liabilities: 你欠了别人的钱。所以别人的钱现在是在你的兜里，所以也是你的资产。
Expenses：你花出去的钱，不会在回来的的。
Equity：你的
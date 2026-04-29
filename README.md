# Personal Fund Trade Recorder

一个可本地运行的基金交易记录工具，用于记录场外基金买入/卖出并在净值曲线上标注当前仍持有份额的买入节点。

## Features

- 基金信息管理：基金代码、名称、当前净值，支持手动更新净值
- 交易记录：
  - 买入：日期、价格、份额，金额自动计算（价格 x 份额）
  - 卖出：日期、价格、份额
  - 卖出严格遵循 FIFO（先进先出），且不能超过当前持仓份额
- 图表展示：
  - 显示净值日期曲线
  - 仅标注“当前仍持有份额”的买入点（红点）
  - 已完全卖出的买入点不再显示
  - 不显示卖出点
- 本地持久化：数据保存至 `data/store.json`，重启后数据不丢失

## Tech Stack

- Python
- Streamlit
- Plotly
- JSON local storage

## Run Locally

1. 创建并激活虚拟环境（可选）:

   - Windows PowerShell:
     - `python -m venv .venv`
     - `.venv\Scripts\Activate.ps1`

2. 安装依赖:

   - `pip install -r requirements.txt`

3. 启动应用:

   - `streamlit run app.py`

4. 浏览器访问:
   - [http://localhost:8501](http://localhost:8501)

## Tests

- 运行测试:
  - `python -m pytest -q`

测试覆盖关键逻辑：

- 买入金额自动计算
- 卖出份额不能超过持仓
- FIFO 份额抵扣与剩余买入点计算


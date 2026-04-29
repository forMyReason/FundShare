# Personal Fund Trade Recorder

可本地运行的场外基金买卖记录工具：FIFO 抵扣份额、净值曲线、持仓与组合级收益总览，数据保存在本机 JSON（含轮转备份）。

## 面向使用者（快速上手）

1. 安装依赖：`pip install -r requirements.txt`
2. 启动：`streamlit run app.py`，浏览器打开提示的地址（常见为 `http://localhost:8501`）。
3. 顶部可看到**组合总成本 / 总市值 / 浮动盈亏 / 收益率 / 累计买卖金额 / 已实现盈亏**。
4. 四个标签页：
   - **组合总览**：组合 KPI、多基金持仓表、收益率排行、导出组合 CSV。
   - **基金管理**：仅展示当前持仓基金（基础信息、业绩曲线、买入节点、lot 分布、最近交易摘要）。
   - **交易与净值**：选基金后记录买入/卖出；卖出支持 **FIFO 自动** 与 **指定买入批次（lot）** 两种模式；支持日期筛选、导入导出与净值图。
   - **维护**：基金新增、净值更新、删除基金、删除交易记录。

**大额/清仓卖出**（≥50% 持仓或清仓）需在表单内二次勾选确认。

## Features（摘要）

- 6 位数字基金代码校验；重复代码会提示勿重复添加。
- 买入/卖出区分申请日与确认日；分析口径可在「按确认日 / 按申请日」间切换（影响排序、FIFO 展示与图上买点日期）。
- 卖出支持 FIFO 与手动 lot 指定；手动模式可选择某笔买入并输入要抵扣份额。
- 每笔卖出可记录 allocations（分摊到 buy_tx_id + shares），支持追溯每次卖出来源买入。
- 净值曲线 + 买入节点；节点 tooltip 展示原始份额 / 已卖份额 / 剩余份额。
- 数据文件：`data/store.json`；同目录 `store.json.bak` 与 `data/backups/` 下保留最近若干份轮转备份（详见 `.gitignore`，勿把本地数据提交到仓库）。

## Tech Stack

Python · Streamlit · Plotly · Pandas · Requests · pytest / pytest-cov

## Run Locally

- Windows PowerShell：`python -m venv .venv` → `.venv\Scripts\Activate.ps1`
- `pip install -r requirements.txt`
- `streamlit run app.py`

## 批量导入 JSON 格式

根对象需包含 `fund_code`（6 位）与 `transactions` 数组。每条交易：

- `tx_type`: `buy` 或 `sell`
- `apply_date` / `confirm_date`: `YYYY-MM-DD`
- `price` / `shares`: 数字
- 卖出交易可选 `allocations`（数组），元素结构：`{"buy_tx_id": 1, "shares": 5.0}`

可在「交易与图表」中下载当前基金示例 JSON。

CSV 导入可选列 `allocations_json`（JSON 字符串）；CSV 导出会包含该列。

## Tests

```bash
python -m pytest -q
python -m pytest --cov=fundshare --cov-report=term-missing -q
```

## FAQ

- **自动净值与当日不一致？** 数据源按「不晚于所选日的最近净值」取值，与部分平台展示可能差一日，可自行改为手动填写。
- **数据丢了？** 优先查看 `data/backups/` 下时间戳文件或 `store.json.bak`；主文件损坏时会尝试从 `.bak` 自动恢复。
- **端口占用？** Streamlit 可能使用 8502 等备用端口，以终端输出为准。

## 发布前自检

仓库提供 `scripts/verify.ps1`（运行测试 + 覆盖率），详见该脚本说明。

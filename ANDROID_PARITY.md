# Streamlit（桌面）与 Android 客户端功能对照

| 能力 | 网页版 `app.py` | Android `feature/android-local`（当前） |
|------|-----------------|----------------------------------------|
| 数据存储 `JsonStorage` | `data/store.json` 或 `DATA_DIR` | 已实现：`DATA_DIR` = 应用 `HOME` |
| `PortfolioService` 组合/基金/交易 | 全量 | 预研：仅状态字符串，未做表单与图表 |
| 净值抓取 `FundApiClient` | 有 | 依赖 `requests`（Chaquopy 已 pip），UI 未接 |
| Plotly / pandas 图表 | 有 | 未移植（需 Compose 图表或 WebView + 本地服务） |
| CSV 导入导出 | 有 | 未移植 |

## 建议里程碑

1. **MVP**：基金列表、新增基金、买入/卖出表单（调用现有 Service）。
2. **图表**：持仓与净值曲线（Compose 图表库或内嵌 WebView + 生成 HTML）。
3. **对齐桌面**：导入导出、维护页危险操作、与 `pytest` 持续对齐业务层。

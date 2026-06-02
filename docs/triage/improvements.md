## 前端

- position-trades面板下，每个trade如果edit notes之后，notes显示的位置不对。

- position创建的时候，first trade下的每个格子说明位置不好。

- position创建的时候可以自动derive一些参数

- position里添加trade尤其是iron condor可以考虑预填一些参数

- instrument的种类/显示方式还有待调整

## 后端 / 逻辑（bug）

- **position 的 `opened_at` 不会重算（和 `closed_at` 不对称）。** `closed_at` 在平仓时按「非归档 trade 的 MAX(executed_at)」重算，但 `opened_at` 只在创建时由前端取「第一笔 trade 的 executed_at」定一次，之后归档/修改那笔 trade 时**不会跟着重算**。后果：如果第一笔 trade 日期填错（比如默认成"现在"）没发现，等后面交易都补录完、再回头归档那笔错的，`opened_at` 会卡在错误值上，可能晚于 `closed_at` → days held 变负。目前只能改数据库修。
  - 已实际发生过一次：2026-06-02 的 INTC wheel position，手动改 `data/app.db` 修复（`opened_at` = 非归档 MIN(executed_at)，并删掉那笔归档的孤儿 trade；`pnl_realized` 本来就对，因为归档 trade 已被排除）。
  - 修复方向（任选）：(a) 后端在 trade 增/改/归档后，把 `opened_at` 一并按「非归档 MIN(executed_at)」重算，与 `closed_at` 对称；(b) 前端允许对已关闭 position 的首笔 trade 纠错。
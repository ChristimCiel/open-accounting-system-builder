# 標準結構權責損益草案與經營儀表板

目標是讓同一份已過帳資料同時產生「可追溯、待適切覆核的標準結構權責損益草案」與「老闆 30 秒能看懂的經營視圖」，不建立第二套帳，也不暗示已有專業人士背書。

## 先問老闆要做什麼決策

當 O6 或管理報表自訂功能啟用時，只問 3 個會改變報表的問題：

1. 每月看完後要做什麼決策：控成本、招人、定價、追欠款、開新店、縮減產品，還是掌握現金？
2. 最想拆哪個維度：產品、專案、門市、通路、客群、部門或不需要？
3. 要比較上月、去年同期、正式預算或預測？沒有可追溯預算時，不得預設為零。

以 `management-dashboard-config.json` 顯示 O6 子功能多選。預設推薦 `O6-DASH`、`O6-PROFIT`、`O6-COST`、`O6-TRUST` 與 `O6-CLOSE`；只在已知資料觸發時推薦現金預測、待收待付、維度獲利、趨勢、預算、稅款預留或情境。AI 推薦不等於老闆已選。

將三個問題逐題保存為 `owner_questions[]`，每題至少有 `question_id`、`question`、`answer`、`source_locator` 與 `status: ANSWERED`。O6 關帳驗證不得只憑預設值跳過老闆回答。

## 單一資料流

```text
POSTED journal
→ COA 損益分類與有效政策
→ 標準結構權責損益草案
→ 明示管理重分類／分攤／調整
→ 管理損益與成本／維度視圖
→ 老闆儀表板
```

現金視圖另由已確認的 payment / settlement 事件建立。不得把現金收支合計命名為「淨利」，也不得把開票、收款或銀行餘額直接當收入、損益或可用現金。

## 標準結構損益樹

`management-report-definition.json` 是受限的報表定義，只可使用 `ACCOUNT_SUM`、`ACCOUNT_SUM_SIGNED`、`SUM_LINES`、`SUBTRACT_LINES` 與 `ADD_SUBTRACT_LINES`；不允許任意程式、公式字串或常數金額。

基準行次：

1. 營業收入
2. 退款、折讓與收入減項
3. 營業收入淨額
4. 營業成本
5. 營業毛利／損失
6. 營業費用
7. 營業利益／損失
8. 營業外收益與費損
9. 稅前淨利／損失
10. 所得稅費用／利益
11. 繼續營業單位損益
12. 停業單位損益
13. 本期淨利／損失

若營業成本與營業費用無法依已確認政策可靠區分，不產生看似精確的毛利率。可產生「成本／費用待分類」草案，但必須顯示未分類金額與影響。OCI 與綜合損益另行呈現，不混入管理 EBITDA、貢獻利潤或營業利益。

## 成本不只分一種

科目與分錄至少可按下列獨立軸度追蹤：

- 損益功能：營業成本、銷售、管理、研發或其他已確認功能。
- 性質：薪資、租金、平台費、折舊、材料等。
- 可追溯性：`DIRECT / INDIRECT / UNCLASSIFIED`。
- 習性：`FIXED / VARIABLE / MIXED / UNCLASSIFIED`。
- 成本標的：產品、專案、門市、通路或客群。
- 責任中心：部門或負責人。

不得因科目名稱看起來像成本就自動完成全部分類。`chart-of-accounts.csv` 的 `pnl_category`、`pnl_line_id`、`cost_nature`、`cost_behavior`、`allocation_policy_id` 與 `dimension_required` 都需明確狀態。

## 分攤與管理調整

- 直接可追溯項目使用 `DIRECT` attribution。
- 共同成本只能依已確認 policy 的 driver 分攤，例如工時、面積、訂單量或明確用量。
- driver 為零、缺資料或政策未確認時放入 `UNALLOCATED`，不猜比例。
- 每個 journal line 在每一已啟用維度的 attribution 比例合計必須為 100%；不可重複分給多個標的。
- 重分類調整在公司總額必須為零。非 GAAP/管理排除可為非零，但要逐項顯示理由、policy、核准、對淨利影響與是否回轉，不回寫 journal。
- 每筆管理調整的 `period_start/period_end` 必須與報表完全一致，並指向原始 P&L `account_code`；成本明細的管理調整逐科目調節到這些核准列，不能只讓總數碰巧相等。
- 影響收入、營業成本／費用界線、存貨、折舊、稅務、股東、關係人、跨境或法定財報的政策必須列專業覆核。

v1.3 會驗證每個核准比例介於 0–1、逐列金額等於來源金額乘比例、同一來源合計 100%，並核對 policy 的成本池、目標維度、有效期間與版本；它尚不會從 driver 原始數量重新計算比例。若需要驗證工時、面積或訂單量的原始 driver，必須新增 driver ledger 與對應 validator，否則只能說「核准比例的數學與適用性已檢查」。

## 老闆首屏

首屏只先回答：

1. 這個月有沒有賺錢？
2. 現在真正能用的錢有多少？
3. 錢卡在客戶、平台、存貨還是待付款？
4. 哪些數字尚未對帳、含暫估、缺憑證或待專業確認？

首屏順序：

1. 報表期間、截至日、口徑、幣別、狀態與對帳進度。
2. 本期收入、毛利／率、營業利益、淨利、可用現金。
3. 「每 100 元收入最後留下多少」損益瀑布。
4. 前五大成本水平長條，分開直接成本與營運費用。
5. 最重要的 3–5 個待辦，依阻擋月結、逾期、現金風險、金額與缺漏排序。
6. 首屏以下才放現金安全線、待收待付、維度獲利、趨勢與完整明細。

損益主視覺使用瀑布圖；成本使用由大到小的水平長條；趨勢使用折線；實際與目標使用差異或 bullet-style 視覺。不使用 3D 圖、過多圖例或難以比較成本變化的裝飾性圓餅圖。

## 白話與正式名稱並列

老闆主標籤使用白話，次要文字顯示正式名稱：

| 老闆標籤 | 正式名稱 |
|---|---|
| 本月已完成生意的收入 | 營業收入淨額 |
| 歸屬本期收入的營業成本 | 營業成本 |
| 賣出後先留下的錢 | 營業毛利 |
| 每 100 元先留下多少 | 毛利率 |
| 維持公司運作花的錢 | 營業費用 |
| 本業經營賺或賠 | 營業利益／損失 |
| 本期最後賺或賠 | 本期淨利／損失 |
| 客戶還欠公司的錢 | 應收帳款 |
| 公司已欠、還沒付的錢 | 應付帳款 |
| 平台已代收、還沒匯入 | 金流平台應收／代收款 |
| 客戶已付、我們還沒做完 | 預收收入／合約負債 |

## 資料信心不用神秘分數

不顯示 AI 自創的「82% 信心」。每個重要數字顯示：

- 資料截至日與最後匯入時間。
- 期間、幣別、含稅／未稅或待確認。
- 口徑：權責、現金、稅務、預算、預測或管理調整。
- 狀態：`DRAFT / CONTROL_CHECKED / OWNER_APPROVED_MANAGEMENT / PROFESSIONAL_REVIEW_REQUIRED / PROFESSIONALLY_REVIEWED`。
- 銀行、信用卡、現金與平台對帳狀態。
- 暫估、缺憑證、未處理、矛盾、未分類、未分攤與待專業確認的筆數和金額。金額未知時顯示「影響金額未知」，不當零。

## 必備產物與視覺降級

- `management-report-definition.json`：受限的標準結構權責損益草案定義與圖表參照。
- `management-dashboard-config.json`：老闆已確認的模組、比較與維度。
- `management-report.json`：機器可重算的權責損益草案金額、管理調整、成本、維度、調節、缺口與圖表來源。
- `dimensions.csv`、`management-attribution.csv`、`management-adjustments.csv`：維度、分攤與非過帳管理調整。
- `allocation-policy-register.json`：結構化分攤政策，包含成本池、目標維度、driver、來源、分母、零分母處理、四捨五入、殘差、頻率、有效日、版本與核准。
- `budgets.csv`：選配但可追溯的已核准預算。報表宣稱有預算時，當期公司總額的八個基礎行次要逐一明列；明確的零與沒有預算不同。
- `management-dashboard.md`：任何 AI 都可產生的白話降級版。

`management-report.json.lines[]` 每列至少含 `line_id`、`financial_amount`、`management_adjustment`、`management_amount`、`budget_amount`、`variance_amount`、`currency`、`source_entry_count` 與 `data_status`。儀表板必須並列「帳載權責金額」、「管理調整」與「管理口徑金額」；只要顯示 `management_amount`，標籤就不得只寫「權責損益」。沒有預算時兩個預算欄位為 null；有預算時 `variance_amount = management_amount - budget_amount`，正負只表示實際減預算，不可未經定義直接標成有利／不利。

啟用維度獲利時，`dimension_summary[]` 每個項目含 `dimension_type`、`dimension_id`、`dimension_name`、涵蓋全部損益行次的 `financial_amounts`、`management_adjustments`、`management_amounts` 與 `data_status`；同一 dimension type 的三組金額都必須調節回公司總額。`UNASSIGNED/UNALLOCATED` 是可見的維度，不是可略過的差異。

`cash_summary` 是與權責損益分開的物件。未啟用現金模組時使用 `status: NOT_ENABLED` 與 null 金額；啟用時從 COA 的現金分類與截至日以前的 `POSTED` journal 重算 `available_cash` 與 `restricted_cash`，口徑固定為 `LEDGER_BALANCE_AS_OF`。這是依已確認帳載分類的可動用現金，不等於扣除未來應付與預留後的自由現金。`trust_summary[]` 至少覆蓋憑證缺口、未決事項、未過帳交易、未分類成本及報表調節，並從來源重算筆數，不產生 AI 信心分數；`action_items[]` 保存優先順序、行動、原因、負責人、期限、來源與狀態，所有未結 open item 都要用 `open_item_id` 出現在 action item。

報表的 `source_checksums` 同時固定 company profile、COA、會計政策、損益定義、儀表板設定、維度、分攤、管理調整、分攤政策、預算、憑證索引、未決事項與 renderer 版本。任一來源改變，都必須重新產生報表與新版儀表板。`management-dashboard.md` 使用 `render_management_dashboard.py` 固定生成；validator 逐字比對，所以手改首屏數字會失敗。

只有報表狀態為 `PROFESSIONALLY_REVIEWED` 且 `professional_review` 同時具備 reviewer ID、資格／角色、結構化 scope、書面結論位置與覆核時間，才可顯示專業覆核；老闆核准管理報表只能使用 `OWNER_APPROVED_MANAGEMENT`。scope 必須精確綁定 `report_id`、`revision`、`period_start`、`period_end`、`ledger_sha256` 與 `covered_areas`。全域 `PROFESSIONALLY_REVIEWED` 要求 `covered_areas` 完整覆蓋帳載權責損益草案、管理調整、成本明細、信任與待辦，以及所有已啟用的現金、維度與預算區域；只覆核局部時不得使用全域狀態。儀表板首頁必須顯示 reviewer、`reviewed_at` 與 `covered_areas`。

v1.3 可在 close 驗證 DASH、PROFIT、COST、TRUST、CLOSE、CASH、DIMENSION 與 BUDGET。`O6-MONEY`、`O6-TREND`、`O6-TAX-RESERVE`、`O6-SCENARIO` 可留在需求草案，但在對應機器可讀輸出與驗證規則擴充前不得標為 ENABLED 並通過 close。

v1.3 的報表幣別必須等於功能幣別；它會驗證交易外幣到功能幣別的換算，但尚未實作把整份損益再換成另一個報導幣別。需要不同報導幣別、合併或換算差額時，保留為草案並擴充資料契約，不可直接替換 currency 標籤。

專業覆核的機械檢查只接受 company profile 中已確認、具驗證來源與有效日期的 active advisor；reviewer 必須與 preparer 分離、同時是報表 approver。結論文件必須位於 company pack 內，validator 會讀取實際 bytes 重算 SHA-256，並要求結論日期不早於報表期末、不晚於 `reviewed_at`，`reviewed_at` 也不得早於期末或晚於 `generated_at`。v1.3 不會根據無法取得 bytes 的外部連結自動宣告專業覆核。這仍不能替代人工確認資格真實性與結論內容。

若環境可建立電子表格，另產生 `management-dashboard.xlsx`，至少含 `Dashboard`、`P&L`、`Cost Analysis`、`Dimension Profit`、`Data & Lineage` 與 `Checks` 工作表。所有派生數值用可審閱公式，圖表只引用可見資料區，不嵌入硬編數字。建立後要掃描公式錯誤、檢視關鍵範圍並視覺驗收。

若無電子表格或 BI 能力，使用 `management-dashboard.md` 與機器可讀檔案；不宣稱已產生互動圖表。

## 驗證不變量

1. 只使用報表期間內的 `POSTED` journal line，並記錄 journal checksum 與行數。
2. 每個損益科目都有唯一有效 `pnl_category`；資產負債科目不進損益。
3. `functional_amount` 固定為本幣借方減貸方；每筆 entry 的 functional 借貸平衡。收入以 functional credit 減 debit；成本與費用以 functional debit 減 credit；同幣別需與原幣借貸一致，外幣需可由原幣乘正匯率重算且保留來源。
4. 毛利＝淨營收－營業成本；營業利益＝毛利－營業費用；稅前損益＝營業利益＋營業外收益－營業外費損；淨利＝稅前損益－所得稅＋停業單位損益。
5. 財務淨利與 ledger 重算淨利差異在容差內；管理金額＝財務金額＋明示調整。
6. 成本明細合計＝營業成本＋營業費用。負毛利保留負值並警示，不取絕對值或隱藏。
7. 每個啟用維度中，所有相關 journal line attribution 總比例為 100%；各維度加 `UNASSIGNED/UNALLOCATED` 必須回到公司總額。
8. 分攤引用已確認 policy；政策或 driver 缺漏不猜。
9. 沒有預算時，`budget_amount`、差異與預算圖表保留 null/不產生；不寫零。
10. 圖表只引用已存在的 line / cost / dimension ID；不允許 `values` 或 `data` 內嵌金額陣列。
11. 缺維度、科目分類、匯率、憑證或重大未對帳時進 `missing_data` 與 open items，不當零或排除。
12. 關帳期間重跑後 checksum、policy 或報表版本改變時產生新版，不靜默覆蓋。

這些是機械性與內部控制檢查，不把管理報表說成查核、簽證或可直接申報的法定財報。

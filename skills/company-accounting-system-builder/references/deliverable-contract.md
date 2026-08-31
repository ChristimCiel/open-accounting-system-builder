# Company Accounting Pack 交付契約

公司包與 Skill 分開存放。預設資料夾可命名為 `accounting-system/`，但要先確認使用者指定位置。

## 最小交付物

```text
accounting-system/
├── company-profile.json
├── feature-selection.json
├── interview-state.json
├── industry-accounting-map.md
├── applicable-framework.md
├── system-recommendation.md
├── accounting-policy-register.json
├── allocation-policy-register.json
├── chart-of-accounts.csv
├── transaction-intake.csv
├── journal.csv
├── dimensions.csv
├── management-attribution.csv
├── management-adjustments.csv
├── budgets.csv
├── management-report-definition.json
├── management-dashboard-config.json
├── management-report.json
├── management-dashboard.md
├── evidence-register.csv
├── open-items.csv
├── reconciliations.md
├── monthly-close-checklist.md
├── professional-review-pack.md
├── change-log.md
└── version-manifest.json
```

若會計軟體是正式 master，CSV 可作為中介/匯出格式，但 `system-recommendation.md` 與 manifest 必須明記正式來源、匯出日、匯出範圍與調節方式。

## 內容要求

### `company-profile.json`

僅收納建議所需的事實與匿名識別，包含地區、組織型態、業務、階段、會計期間、幣別、收入流、通路、銀行/卡片末四碼或匿名 ID、使用者角色、專業顧問狀態與資料分級。若要標示 `PROFESSIONALLY_REVIEWED`，顧問至少保存匿名 `advisor_id`、資格／角色、active 狀態、驗證來源與可解析的驗證日期。`company-profile.json` 必須納入報表來源 checksum，顧問名冊變更時既有報表即失效。

### `feature-selection.json`

保留所有已呈現功能的推薦狀態、是否啟用、優先順序、理由、相依功能與專業覆核需求。目錄功能使用 `source: catalog`，使用者新增的功能使用 `source: custom` 並記錄期望結果、輸入、輸出與頻率。AI 推薦不得自動成為 `OWNER_CONFIRMED`；已確認組合的每次變更都要進入 `change_history`。

### `accounting-policy-register.json`

每條政策使用 baseline controls 中的欄位。影響法定、稅務或財報者不得只有老闆確認狀態而沒有專業覆核標記。

### CSV 資料

- 所有金額、日期與布林值使用可機器讀取格式，不把單位字串塞在數值欄位。
- 原幣與本幣金額分欄，幣別使用 ISO code，日期使用 `YYYY-MM-DD`。
- `journal.csv` 的每個 `entry_id` 至少一借一貸且合計平衡。
- `journal.csv` 保留原幣借貸與 functional debit/credit；`functional_amount` 固定為本幣借方減貸方。外幣需有正匯率、來源，且本幣金額可由原幣乘匯率重算。損益報表只使用指定期間的 `POSTED` line。
- `chart-of-accounts.csv` 為損益科目指定唯一 `pnl_category`、`pnl_line_id` 與成本屬性；未知分類不猜。
- 維度分攤可回到 `entry_id + line_no`；每個啟用維度比例合計 100%，共同成本分攤必須引用已確認政策。
- `budgets.csv` 只保存有來源、期間、核准者與狀態的正式預算；沒有預算時保留空表，不製造零預算。
- `evidence-register.csv` 的 `content_sha256` 用於固定重要文件內容；專業覆核結論必須有完整證據列、合適 document type 與相同 checksum。
- 不在自由文字備註隱藏待補；同步放進 `open-items.csv`。

### 標準結構權責損益草案與老闆儀表板

- `management-report-definition.json` 只可使用白名單操作，不接受任意公式字串、程式或硬編金額。
- `management-dashboard-config.json` 保存 AI 推薦、老闆多選確認、決策問題、比較口徑與維度；推薦不可自動寫成已確認。
- `management-report.json` 保存期間、口徑、幣別、ledger checksum/行數、財務金額、管理調整、成本、維度、缺口、警示、調節與圖表參照。
- `management-dashboard.md` 必須以 `render_management_dashboard.py` 從 report 固定生成並逐字通過驗證，不得手工維護第二套數字；正式會計名與白話標籤並列。
- `allocation-policy-register.json` 保存成本池、目標維度、driver、driver 來源、分母、零分母、四捨五入、殘差、頻率、有效日、版本與核准；只有文字 policy ID 不足以通過分攤驗證。
- 啟用 O6 且到 `close` 時，財務損益必須調節到 journal 重算結果，成本明細回到營業成本＋營業費用，負毛利保留並警示。
- 權責、現金、稅務、預算、預測與管理調整分開；無預算時預算及差異為 null，不得當零。
- 圖表只引用已驗證 line/cost/dimension ID，不嵌入另一套數字陣列。
- 若執行環境可建立試算表，可另交付 `management-dashboard.xlsx`；其公式與圖表必須引用可見資料與 lineage，且完成公式錯誤與視覺驗收。無該能力時以 Markdown/JSON 降級，不宣稱有互動圖表。

### `professional-review-pack.md`

每題以可回答的形式提供：背景事實、原始來源位置、目前 AI 草案、可能影響、具體問題、需要的回答格式、建議截止日。

### `version-manifest.json`

記錄 Skill 版本、公司包版本、生成/更新時間、狀態、期間、正式 master、原始來源檔、輸出檔、檢查結果、未決項目數、前一版與修改摘要。

## 驗收

1. 找不到某家示範公司的統編、人名、客戶、供應商單據號、金額、帳號或實際交易。
2. 已確認事實、AI 建議、官方來源、待補與專業判斷可區分。
3. 功能組合可多選、可新增自訂功能、可停用並有歷史；AI 推薦與負責人確認可區分。O6 子功能亦可多選與自訂。
4. 正式 master 唯一且有版本；原始檔未被覆蓋。
5. 代表性交易試跑中，重複不入帳、衝突不猜、信用卡繳款不重複列費用、平台淨撥款可調節至總銷售/手續費。
6. 借貸平衡、必填欄位、重複鍵、憑證連結、open items、對帳差異與版本檢查有結果。
7. 啟用 O6 時，損益由 journal 重算、管理 bridge 可追溯、圖表無硬編數字、負毛利與缺資料不被隱藏。

使用 `scripts/validate_company_pack.py <公司包> --stage onboarding|draft|posting|close` 檢查結構、功能 revision、訪談狀態、gate、manifest、JSON、CSV 必填、重複鍵與借貸平衡。空白 scaffold 只可在 `onboarding` 階段通過並必須顯示尚不可入帳。`posting` 與 `close` 的固定控制不受功能開關影響：必須有當期官方來源、已確認功能 revision、完整證據與來源連結、已清除的查重/用途/完整性狀態、人工審批、交易與分錄串聯，且不能有尚未解決的專業判斷；`close` 再加對帳結果、無未勾選月結控制、關帳決定與無阻擋項目。驗證通過只代表該階段的機械性控制通過，不代表會計/稅務正確。

初始化參數必須有非空白授權參照與授權者。若既有 `interview-state.json` 的授權 metadata 無效，初始化腳本必須先失敗；人工檢視後才可用 `--repair-authorization` 明確補登，不得靜默保留或覆蓋。

## 從 Skill 1.1 升級

1.1 Company Pack 不包含功能選擇。升級時保留原包，在新版本新增 `feature-selection.json`，將 `interview-state.json` 與 manifest 的 `schema_version` 升為 `1.2`，補上 `planned_modes`、`feature_selection_revision` 與 `feature_selection_status`。然後以舊包中已有的產物當作 AI 預選來源，顯示 O1–O8 差異給負責人確認；不得因檔案已存在就自動寫成 `OWNER_CONFIRMED`。升級完成前只可繼續閱讀與草案工作，不通過 posting/close 驗證。

## 從 Skill 1.2 升級

保留原 Company Pack，新建九個管理報表 scaffold，補齊 COA 損益／成本欄位及 journal 功能幣別／維度欄位，並把 manifest schema 升為 `1.3`。若 O6 原本已啟用，只能把 dashboard 子功能建成 AI 預選草案；需由老闆確認後才把 config 改為 `OWNER_CONFIRMED`。舊報表不得直接標示已調節，必須從 `POSTED` journal 重跑 checksum、損益與成本驗證。

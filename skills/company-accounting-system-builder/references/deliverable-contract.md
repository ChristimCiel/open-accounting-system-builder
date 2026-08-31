# Company Accounting Pack 交付契約

公司包與 Skill 分開存放。預設資料夾可命名為 `accounting-system/`，但要先確認使用者指定位置。

## 最小交付物

```text
accounting-system/
├── company-profile.json
├── interview-state.json
├── industry-accounting-map.md
├── applicable-framework.md
├── system-recommendation.md
├── accounting-policy-register.json
├── chart-of-accounts.csv
├── transaction-intake.csv
├── journal.csv
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

僅收納建議所需的事實與匿名識別，包含地區、組織型態、業務、階段、會計期間、幣別、收入流、通路、銀行/卡片末四碼或匿名 ID、使用者角色、專業顧問狀態與資料分級。

### `accounting-policy-register.json`

每條政策使用 baseline controls 中的欄位。影響法定、稅務或財報者不得只有老闆確認狀態而沒有專業覆核標記。

### CSV 資料

- 所有金額、日期與布林值使用可機器讀取格式，不把單位字串塞在數值欄位。
- 原幣與本幣金額分欄，幣別使用 ISO code，日期使用 `YYYY-MM-DD`。
- `journal.csv` 的每個 `entry_id` 至少一借一貸且合計平衡。
- 不在自由文字備註隱藏待補；同步放進 `open-items.csv`。

### `professional-review-pack.md`

每題以可回答的形式提供：背景事實、原始來源位置、目前 AI 草案、可能影響、具體問題、需要的回答格式、建議截止日。

### `version-manifest.json`

記錄 Skill 版本、公司包版本、生成/更新時間、狀態、期間、正式 master、原始來源檔、輸出檔、檢查結果、未決項目數、前一版與修改摘要。

## 驗收

1. 找不到某家示範公司的統編、人名、客戶、供應商單據號、金額、帳號或實際交易。
2. 已確認事實、AI 建議、官方來源、待補與專業判斷可區分。
3. 正式 master 唯一且有版本；原始檔未被覆蓋。
4. 代表性交易試跑中，重複不入帳、衝突不猜、信用卡繳款不重複列費用、平台淨撥款可調節至總銷售/手續費。
5. 借貸平衡、必填欄位、重複鍵、憑證連結、open items、對帳差異與版本檢查有結果。

使用 `scripts/validate_company_pack.py <公司包> --stage onboarding|draft|posting|close` 檢查結構、訪談狀態、gate、manifest、JSON、CSV 必填、重複鍵與借貸平衡。空白 scaffold 只可在 `onboarding` 階段通過並必須顯示尚不可入帳；`posting` 或 `close` 階段還必須通過對應關卡與正式 master 檢查。驗證通過只代表該階段的機械性控制通過，不代表會計/稅務正確。

初始化參數必須有非空白授權參照與授權者。若既有 `interview-state.json` 的授權 metadata 無效，初始化腳本必須先失敗；人工檢視後才可用 `--repair-authorization` 明確補登，不得靜默保留或覆蓋。

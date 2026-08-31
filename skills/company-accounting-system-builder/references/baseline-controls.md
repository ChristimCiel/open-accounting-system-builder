# 可移植內帳控制基線

這些是預設控制，不是某家公司的科目表、稅務結論或固定檔案結構。將其套用到新公司前，先依商業模式、司法管轄地、既有系統與專業意見調整。

## 證據與事實

- 每筆正式交易必須可回到來源：發票、收據、合約、銀行/卡片/平台紀錄、付款通知、公司文件，或具日期的使用者明確陳述。
- 使用者陳述可以是事實來源，但要標示證據強度與待補文件；不假裝等同第三方憑證。
- 金額、日期、幣別、匯率、稅額、單據、付款方式或用途不明時不猜；留原值與 `needs_data`。
- 非交易事件如申請、核准、期限、備忘可追蹤，但沒有金額與經濟事件時不產生分錄。

## 查重

1. 強鍵：invoice / receipt / e-invoice / merchant order / platform transaction / bank transaction ID。
2. 次鍵：交易對象 + 日期 + 幣別 + 金額 + 付款媒介。
3. 關聯檢查：原始消費、卡費結算、卡費繳款、平台收款、平台撥款、銀行入帳是同一生命週期的不同事件，不是多筆收入/費用。

找到重複時，只補來源、狀態、金額差異或連結，不新增第二筆經濟事件。

## 帳務層

不用一個混合表取代所有觀點。最小可用結構是：

1. `transaction_intake`：來源收件與尚未正式入帳的事實。
2. `evidence_register`：憑證 ID、種類、來源、檔案/連結、日期、交易關聯、完整性與敏感度。
3. `journal`：正式的複式分錄，每個 entry ID 借貸平衡。
4. `chart_of_accounts`：科目代碼、名稱、類別、正常餘額、使用範圍、禁用/替代與審核狀態。
5. `open_items`：待收、待付、待撥款、待憑證、暫估、衝突、期限與專業覆核。
6. `reconciliations`：銀行、現金、信用卡、平台、應收、應付與總帳調節。
7. `management_reporting`：從帳務來源可重新產生的現金、權責、通路/專案/產品觀點。

## 單一事實帳，三種視圖

不建立互相矛盾的「內帳/外帳」。保留單一、依真實事項建立的複式總帳，再導出：

- 法定財務報導視圖。
- 稅務調整視圖，不回頭竄改事實帳。
- 管理會計視圖，例如產品、專案、通路與現金可用度。

## 政策狀態

每條公司政策至少包含：

```yaml
policy_id:
statement:
scope:
rationale:
evidence_or_source:
assumptions:
status: draft | owner_confirmed | professional_review_required | professionally_reviewed
decision_owner:
effective_from:
supersedes:
review_due:
```

暫定、老闆確認、需專業覆核與已專業覆核不可混用。

## 版本與交接

- Skill 版本與公司制度版本獨立。
- 已確認版本不覆蓋；新版記錄差異、原因、來源、修改/覆核者、生效日與追溯影響。
- 每次更新同步交易、分錄、憑證連結、open items、reconciliation 與交接摘要，不只更新報表數字。
- 調整與暫估要保留原因與回轉/替換條件。

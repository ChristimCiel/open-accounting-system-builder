---
name: company-accounting-system-builder
description: Interview company owners to understand their industry and business model, research the applicable current accounting framework, diagnose existing records, and build or review a traceable and reconcilable internal accounting system. 適用於新公司建帳、舊帳遷移、內帳制度設計、日常交易控管與月結。
metadata:
  version: "1.1.0"
  author: "Tim Chen"
  license: "Apache-2.0"
---

# Open Accounting System Builder

An open-source Company Accounting System Builder maintained by Tim Chen.

把「可分享的方法」與「單一公司的事實」分開：本 Skill 負責訪談、研究、設計、驗證與更新方法；每家公司的回答、科目、憑證、政策、待辦與覆核結果，必須儲存在獨立的 Company Accounting Pack，不要回寫到本 Skill。

以使用者的工作語言進行訪談與交付。引用法規或準則時保留官方原文名稱，並提供使用者語言的白話說明。台灣以外的公司不得套用台灣司法管轄地 reference，必須另查所在地官方來源。

## 先決定模式

依使用者目的選擇一個主模式，可在完成一階段後轉換：

- `setup`：從商業模式、適用架構與現況診斷開始，生成公司制度包。
- `migrate`：檢視現有帳本、欄位、公式、規則與憑證，先產生映射與差異報告，不覆蓋原始檔。
- `operate`：依已確認的 Company Accounting Pack 處理交易、對帳、待補、月結與管理報表。
- `review`：做控制、完整性、矛盾、公式、追溯與交接檢查；不把控制檢查等同審計或稅務簽證。

若未找到既有 Company Accounting Pack，且使用者沒有明確要求其他模式，預設為 `setup`。

## 漸進式協作

1. 不要一次丟出完整題庫。每輪聚焦一個主題，問 3–5 個會改變建議的決策點；一個編號內塞入多個獨立決策仍算多題。
2. 先用使用者的語言解釋商業事件與會計事件，再討論科目或分錄。
3. 每輪結束時回顧 `FACT`、`AI_PROPOSAL`、`OPEN_QUESTION`、`PROFESSIONAL_DECISION_REQUIRED`，請使用者修正誤解。
4. 已從文件或前文得知的事實不重問。中斷後先讀取 `interview-state.json` 與最新 manifest，說明上次停點。
5. 遇到金額、日期、幣別、單據或用途矛盾，只停住受影響的項目；保留衝突兩邊來源，不自行選一個。
6. G0 尚未確認儲存位置、資料範圍與最小必要權限時，只在對話中顯示預填摘要，不執行初始化腳本、不建立檔案，也不持久化公司事實。若外層工作指令已明確授權隔離目錄，必須把授權來源、範圍、授權者與時間寫入 state。

首次使用時，先讀 [references/onboarding-interview.md](references/onboarding-interview.md)。

## Setup 與 migrate 工作流

1. 確認司法管轄地、組織型態、營運階段、產業與交付目標。
2. 讀 [references/onboarding-interview.md](references/onboarding-interview.md) 進行分段訪談，先建立產業會計地圖，再設計科目。
3. 涉及現行法令、準則、稅務、申報或期限時，必須讀 [references/standards-research.md](references/standards-research.md) 並即時查核官方來源。司法管轄地為台灣時，再讀 [references/jurisdictions/taiwan.md](references/jurisdictions/taiwan.md)。
4. 讀 [references/system-selection.md](references/system-selection.md)，建議電子表格、會計軟體或混合流程。必須指定單一正式帳務來源，不能讓兩套帳同時成為 master。
5. 讀 [references/baseline-controls.md](references/baseline-controls.md) 與 [references/transaction-playbooks.md](references/transaction-playbooks.md)，建立公司專屬政策、科目、證據規則、交易流與月結。
6. 依 [references/deliverable-contract.md](references/deliverable-contract.md) 生成 Company Accounting Pack。使用 `assets/` 內的空白模板，不把示範公司的名稱、統編、人名、金額、帳號、卡號、客戶、單據號或實際交易寫進 Skill。使用者明確確認輸出位置與資料範圍後，可執行 `python scripts/init_company_pack.py <輸出資料夾> --authorization-reference <對話或指令中的授權位置>` 建立空白公司包；腳本不會覆蓋已存在的檔案。
7. 用代表性交易試跑，至少覆蓋收入、未收款或預收、一筆支出、一個支付/金流通路、一筆模糊或矛盾資料。
8. 對現有帳本先讀 [references/migration-controls.md](references/migration-controls.md)，只先產生欄位映射、差異、公式/控制風險與遷移預覽。未獲確認前不覆蓋原始檔。

## Operate 與 review 工作流

讀 [references/operating-workflow.md](references/operating-workflow.md)，完成「來源收件 → 公司用途/完整性 → 查重 → 暫定分類 → 人工確認 → 分錄 → 對帳 → 待補/例外 → 月結 → 報表 → 專業覆核」。

每次處理要：

- 先以 invoice、receipt、發票、merchant order、平台交易 ID，加上日期/金額/交易對象做查重。
- 分開「交易發生」、「客戶付款」、「平台代收」、「平台撥款」、「銀行入帳」與「手續費」。
- 分開現金流、權責損益、稅務處理與管理口徑；不得混成一個未標示的數字。
- 任何未知金額、幣別、匯率、稅額、付款狀態或公司用途都不得猜測後正式入帳。
- 正式交易使用複式分錄；每筆分錄借貸必須平衡。非交易事件留在備忘/待辦，不產生金額分錄。
- 信用卡消費與信用卡帳單繳款不得重複認列費用。
- 維持 open-items register，不讓待補憑證、應收、應付、暫估與待專業覆核事項消失在備註中。

## 結論狀態與專業邊界

重要結論必須標示下列其一：

- `FACT`：來自使用者或可追溯文件。
- `AI_PROPOSAL`：內部管理建議，可由負責人確認。
- `OFFICIAL_SOURCE`：已查核現行官方來源，附標題、URL 與查核日期。
- `PROFESSIONAL_DECISION_REQUIRED`：需記帳士、會計師、稅務或法律專業人士判斷。

只能由具合適權限的人類將政策狀態改為 `professionally_reviewed`。使用者確認只能代表 `owner_confirmed`，不等於符合會計、稅務或法律規範。

下列項目必須列入專業覆核包：公司成立前交易、股本/股東/關係人、稅額與可扣抵性、收入認列與跨期、預收、平台總額/淨額、退款/折讓/反佣、跨境與外幣、員工/承攬/薪資、存貨、固定資產與資本化、多司法管轄地，以及任何重大矛盾或缺乏關鍵憑證的情形。

## 權限、隱私與寫入關卡

- 讀取銀行、員工、客戶、股東或稅務資料前，先確認資料範圍與儲存位置。
- 身分證、完整帳號/卡號、員工與客戶名單預設不進入共享 Skill；必要時使用匿名 ID 或末四碼。
- 未獲明確授權，不得寄信、上傳、分享、連接外部帳號、修改雲端帳本、開立發票、申報或送出付款。
- 寫入正式帳本、批次匯入、覆蓋檔案或關帳前，顯示預覽、變更摘要、未決事項與回復方式。
- 保留原始檔、不覆蓋已確認版本。每次變更記錄修改前後、理由、來源、修改者/覆核者、生效日、取代版本與是否需追溯調整。

## 完成條件

- 交付物中的事實、假設、AI 建議、官方來源與專業覆核項目可區分。
- 所有正式交易可追溯、可查重，借貸平衡，並與銀行/信用卡/金流平台對帳或明確列出未對帳原因。
- 待補憑證、應收、應付、暫估、衝突、期限與專業覆核均有負責人與下一步。
- 系統建議說明為什麼適合目前公司，以及何種情況出現時應升級。
- 經過代表性交易試跑與驗收。
- 交付前依階段執行 `python scripts/validate_company_pack.py <公司包資料夾> --stage onboarding|draft|posting|close`。只有 `posting` 或 `close` 階段通過才表示對應的機械性關卡完成；任何階段通過都不代表會計、稅務或法律正確。
- 新建或重大更新 Skill 時，用 [references/acceptance-scenarios.md](references/acceptance-scenarios.md) 做獨立前向測試，不把預期答案先喂給測試者。
- 回報只能說「完成內部控制檢查」或「形成待覆核草案」；除非有對應專業人士的明確書面結論，不宣稱「法定帳已正確」、「已符合會計準則」或「可直接申報」。

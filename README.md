# Open Accounting System Builder

[繁體中文](README.md) | [English](README.en.md)

[![驗證狀態](https://github.com/ChristimCiel/open-accounting-system-builder/actions/workflows/validate.yml/badge.svg)](https://github.com/ChristimCiel/open-accounting-system-builder/actions/workflows/validate.yml)
[![授權條款](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

一個開源的 AI Skill，透過漸進式訪談協助公司負責人理解產業與商業模式背後的會計邏輯、查核所在地適用的現行規範，並建立公司專屬、可追溯、可對帳、可交接的內部會計制度。

由 **Tim Chen** 建立及維護。

> 本專案協助整理會計事實、內部控制、作業流程與專業覆核問題，不構成會計、記帳、稅務、法律、審計、簽證或申報意見。

## 為什麼需要這個專案？

許多剛成立或正在成長的公司，會先從一張混合用途的試算表開始：收款、支出、股東匯款、信用卡與備忘事項全放在一起；憑證散落各處，規則只存在某個人的記憶裡。

這個 Skill 讓 AI 不只是「幫忙分類交易」，而是先理解公司怎麼營運，再協助建立一套能持續使用的會計制度。它不會把某一家公司的做法假設成所有公司的答案。

專案採兩層架構：

1. **共享的開源 Skill**：保存訪談、研究、制度設計、驗證與更新方法。
2. **每家公司獨立的 Company Accounting Pack**：保存該公司的事實、政策、科目、交易、待辦與專業覆核結果。

公司名稱、交易、帳號、客戶、員工與憑證等敏感資料，應留在私密的 Company Accounting Pack，不應提交到這個公開 Repo。

## 主要功能

- 每輪只詢問少量、真正會影響制度設計的決策點。
- 先用白話拆解收款、履約、收入、成本、退款與平台撥款，再討論科目與分錄。
- 將結論區分為 `FACT`、`AI_PROPOSAL`、`OFFICIAL_SOURCE`、`OPEN_QUESTION` 與 `PROFESSIONAL_DECISION_REQUIRED`。
- 依公司的交易量、複雜度與管理需求，建議使用試算表、會計軟體或混合流程。
- 建立政策、科目表、交易收件匣、複式分錄、憑證索引、對帳、未決事項、月結與版本控制模板。
- 在寫入公司資料前要求明確的資料範圍、儲存位置與持久化授權。
- 驗證資料結構、必填欄位、重複鍵、借貸平衡、訪談關卡與正式入帳準備狀態。
- 讓法定財報、稅務調整與管理分析都能追溯到單一正式帳務來源。

## 用 Codex 自動安裝

把下面這段提示交給 Codex：

```text
請使用 $skill-installer，從 GitHub 安裝以下公開 Skill：

Repository：ChristimCiel/open-accounting-system-builder
Path：skills/company-accounting-system-builder
Ref：main

安裝前請先檢查 SKILL.md 與 scripts。
如果同名 Skill 已存在，請停止並告訴我，不要直接覆蓋。
安裝完成後請告訴我；我會在下一輪開始使用。
```

安裝完成後，在下一輪輸入：

```text
請使用 $company-accounting-system-builder。

先不要直接替我入帳。請逐步訪談我，了解公司的產業、商業模式、付款與履約流程，再建立：

1. 產業會計地圖
2. 適用會計與財務架構
3. 現況診斷
4. 最適合的帳務系統
5. 公司專屬 Company Accounting Pack

所有涉及收入認列、稅務、股東交易、跨境、薪資或法定申報的事項，都要標示是否需要會計師、記帳士、稅務或法律專業人士覆核。
```

Codex 的 Skill Installer 會把 Skill 放進使用者的 Skills 目錄。其他 AI 產品即使可以讀取公開 Repo，也不一定具備安裝或持久保存本機 Skill 的能力。

## 手動安裝

只需要把下面的資料夾複製到 Codex Skills 目錄：

```text
skills/company-accounting-system-builder
```

安裝後的資料夾名稱必須保持為：

```text
company-accounting-system-builder
```

如果安裝後沒有立即出現，請重新載入或重新啟動 AI 工作環境。

## 第一次使用會發生什麼？

Skill 會先進行漸進式訪談，不會一開始就要求使用者選擇會計科目。主要階段包括：

1. 確認公司所在地、組織型態、營運階段、目標、資料範圍與儲存位置。
2. 理解產品／服務、付款、履約、退款、平台、直接成本與管理需求。
3. 建立產業會計地圖並請公司負責人確認。
4. 查核所在地當期適用的官方規範、準則版本與生效日。
5. 診斷現況並建議正式帳務來源。
6. 建立公司專屬政策、科目、憑證、分錄、對帳與月結流程。
7. 使用代表性交易試跑，確認後才允許正式寫入。

涉及稅務、收入認列、股東／關係人、跨境、薪資、存貨、固定資產或其他高判斷事項時，Skill 會整理成專業覆核問題，不會自行宣稱已符合法規或準則。

## Repo 結構

```text
skills/company-accounting-system-builder/
├── SKILL.md
├── agents/openai.yaml
├── assets/templates/
├── references/
└── scripts/
```

Repo 根目錄只保存專案說明、授權、驗證、版本與貢獻文件，不包含任何真實公司的帳本。

## 驗證專案

在 Repo 根目錄執行：

```bash
python3 scripts/validate_repository.py
```

建立 Company Accounting Pack 並執行 onboarding 檢查：

```bash
python3 skills/company-accounting-system-builder/scripts/init_company_pack.py \
  /path/to/private/accounting-system \
  --authorization-reference "conversation:explicit-user-authorization" \
  --authorized-by "company-owner"

python3 skills/company-accounting-system-builder/scripts/validate_company_pack.py \
  /path/to/private/accounting-system \
  --stage onboarding
```

驗證通過只代表對應的結構與機械性控制通過，不代表會計、稅務、法律、審計或申報正確。

## 隱私與安全

不要把生成後的 Company Accounting Pack 或任何真實會計憑證提交到這個 Repo。回報漏洞或疑似資料外洩前，請先閱讀 [SECURITY.md](SECURITY.md)。

## 參與貢獻

歡迎提出 Issue 與 Pull Request。請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)，所有案例都必須使用合成或完整去識別化資料。

## 品牌與作者標示

**Open Accounting System Builder** 是專案名稱；Skill 的穩定技術 ID 是 `company-accounting-system-builder`。

本專案採 Apache-2.0 授權，允許使用、修改及散布。授權不代表 Tim Chen 為修改版本背書，也不授權他人用專案名稱包裝實質上不同的產品。詳見 [NOTICE](NOTICE) 與 [LICENSE](LICENSE)。

引用方式：

```text
Open Accounting System Builder, created by Tim Chen
https://github.com/ChristimCiel/open-accounting-system-builder
```

## 授權條款

Apache License 2.0。詳見 [LICENSE](LICENSE) 與 [NOTICE](NOTICE)。

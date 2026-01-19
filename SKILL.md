# FDA 510(k) 智能審查 SKILL 說明

本檔說明本系統在 510(k) 審查情境下可提供的「技能模組」，搭配 `agents.yaml` 中 31 個代理使用。  
所有描述以 **FDA/510(k) 審查實務** 為核心，協助審查員與業者快速完成高品質文件分析。

---

## 一、系統核心定位

- 面向對象：  
  - FDA / 衛生主管機關審查員  
  - 醫材廠 RA/QA 團隊  
  - 顧問與法規專家  
- 核心目標：  
  1. 加速 510(k) 提交資料的閱讀、重組與摘要。  
  2. 協助建立結構化的 **審查 checklist** 與 **審查報告**。  
  3. 針對風險、性能測試、指引遵循等關鍵面向，提供工具型 AI 分析。

---

## 二、主要技能區塊總覽

1. **510(k) 智能檢索與摘要**
   - 從公開 510(k) 摘要中抽取結構化資訊。
   - 為特定裝置建立「類審查報告」風格的 summary。

2. **提交資料整理與標準化 (Submission Structuring)**
   - 將原始 510(k) 提交材料（Word、PDF 轉文字等）  
     轉為清楚分段的 Markdown：裝置描述、適應症、Predicate、性能測試、風險等。

3. **Checklist 產生與整理**
   - 從 FDA 指引或內部 SOP 自動產生審查 checklist。
   - 將舊有 Excel/CSV checklist 轉為適合逐項勾選的 Markdown 版本。

4. **審查報告草稿生成**
   - 利用整理好的提交資料與 checklist，  
     自動生成 510(k) 審查報告草稿（含逐項審查結果與 traceability）。

5. **差異與變更分析**
   - 比較不同版本的提交文件或技術檔（舊版 vs 新版）。
   - 對技術或適應症變更進行「是否需新 510(k)」初步分析。

6. **性能測試與標準對應**
   - 從指引與提交內容中萃取性能測試需求，建立測試矩陣。  
   - 整理使用之共通標準 (e.g., IEC/ISO/AAMI) 與適用性。

7. **風險與 Benefit-Risk 評估**
   - 建立風險與緩解措施矩陣。  
   - 聚焦 Benefit-Risk 架構，形成審查重點摘要。

8. **軟體 / SaMD / Cybersecurity 專家代理**
   - 針對軟體生命週期、SaMD 特有考量、資安控制提供結構化檢視。

9. **使用者界面 / 人因工程 (Human Factors)**
   - 從提交資料中抽取 HF 重點，對照 FDA HF 指引進行審查。

10. **標示與 IFU (Labeling / IFU)**
    - 檢查標示與使用說明是否與適應症、風險控制一致，  
      並標記可能需補充/修改之處。

11. **教育訓練與案例教學支援**
    - 將實際 510(k) 個案轉為教學案例、練習題與知識小結。

12. **審查筆記管理 (Note Keeper)**
    - 將審查員手寫或零散筆記整理成 Markdown。  
    - 進一步透過 Formatting、Keywords、Entities、Summary、Magic 工具  
      形成具結構的「知識物件」。

---

## 三、與 `agents.yaml` 的關係

- `agents.yaml` 中每一個代理均對應一組「技能」與使用場景，例如：
  - `fda_search_agent`：對單一裝置/510(k) 案件產生高品質審查型摘要。
  - `pdf_to_markdown_agent`：將 PDF 轉為可用 Markdown。
  - `guidance_to_checklist_converter`：將 FDA 指引轉為審查 checklist。
  - `review_memo_builder`：將 checklist + Review 結果彙整為審查備忘錄。
  - `note_keeper_agent` & Magics：面向審查筆記整理、風險登錄、缺口分析等。

- 每個 agent 具備：
  - `system_prompt`：規範 AI 行為與角色（以繁體中文撰寫）。
  - `user_prompt_template`：給使用者的可客製化輸入模板。
  - `output_requirements`：期望的輸出結構（段落/表格/JSON 等）。
  - `validation_rules`：簡易檢查（是否有特定章節、是否產生表格等）。

---

## 四、典型使用情境示意

1. **建立案件全貌**
   - 使用 `fda_search_agent` 與 510(k) Summary Studio  
     擷取裝置背景、Predicate、性能測試概況。

2. **整理申請人的 510(k) 提交資料**
   - 將 Word/PDF 轉文字後，餵給 `submission_structurer` 類型代理，  
     生成結構化 Markdown，方便人工瀏覽與後續自動化分析。

3. **產生 Checklist 與 Review 報告**
   - 使用 `guidance_to_checklist_converter` 從 FDA 指引建立 checklist。
   - 在「510(k) Review Pipeline」tab 中：  
     - Step 1：提交材料 → Markdown  
     - Step 2：checklist → Markdown  
     - Step 3：Checklist 套用於提交資料 → Review 報告。

4. **風險 / 測試 / 缺口的深度檢視**
   - 使用 Risk、Performance、Gap 類代理，從結構化資料中萃取：
     - 高風險區塊
     - 測試缺口
     - 潛在指引遵循缺失

5. **個人審查筆記管理**
   - 審查員於實際閱讀過程中將想法寫為自由文字。  
   - 使用 Note Keeper：
     - Note → Markdown 結構化  
     - AI Formatting / Keywords / Entities / Summary  
     - AI Magics：風險與行動登錄、法規缺口偵測  
   - 最終形成可追蹤、可教學、可再利用的知識物件。

---

## 五、模型選擇建議 (Model Strategy)

- **快速整理與大量文件切分**
  - 建議：`gemini-2.5-flash`, `gpt-4o-mini`
- **較深度的 510(k) 審查推理 / 法規缺口分析**
  - 建議：`gemini-3-flash-preview`, `gemini-3-pro-preview`
- **偏向對話與互動問答**
  - 建議：`gemini-3-flash-preview`, `gpt-4o-mini`

---

## 六、使用注意事項

1. AI 為輔助工具，**不得替代** 實際法規判斷與主管機關裁量。  
2. 請避免將未匿名的個資與機密資料曝露於非授權環境。  
3. 對於 AI 產出的內容，審查員應進行理性檢核與專業判讀。  
4. 若發現模型有明顯錯誤或不合理推論，建議在內部簡報或報告中註明  
   該部分為「AI 產出草稿，仍需人工確認」。

---

## 七、未來可擴充方向

- 加入更多針對特定科別 (e.g., 心血管、骨科、影像) 的專門代理。  
- 增加對 eSTAR 格式的解析與檢核工具。  
- 連結內部 QMS/Change Control 系統，做跨系統 traceability。

本 `SKILL.md` 可搭配 `agents.yaml` 與本 Streamlit 應用程式使用，  
亦可作為建立內部 SOP 或教育訓練教材的基礎文件。
```

---

## 3. 進階版 `agents.yaml`（31 個繁中代理）

> 檔名：`agents.yaml`  
> 格式：最上層 key 為 `agents`，其下 key 即為程式中使用的 `agent_id`（如 `fda_search_agent`）。  
> 每個代理皆為繁體中文描述，並盡量與 FDA/510(k) 實務對應。  
> 範例中使用的模型皆從 `AGENT_MODEL_CHOICES` 中選擇（`gemini-2.5-flash`, `gemini-3-flash-preview`, `gemini-3-pro-preview`, `gpt-4o-mini`, `gpt-5-mini`）。

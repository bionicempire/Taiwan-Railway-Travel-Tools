> [!NOTE]
> 敝人**空有想法，毫無能力**，所以此工具之重要程式皆由AI生成。由[Claude](https://claude.ai/new), [Gemini](https://gemini.google.com/app), [ChatGPT](https://chatgpt.com/)輔助完成，再經本人檢核正確性。

目前台灣鐵路相關之路徑查詢工具，多半僅支援「至多一次轉乘」之查詢模式；當查詢條件涉及支線路段時，系統亦可能無法提供可行車次。本程式針對上述限制加以改進，能處理包含支線之複雜運輸路徑，並提供完整之轉乘資訊，包括各段之車種、車次、轉乘對應關係、行駛里程、票價，以及票價之分段計算方式。
> [!IMPORTANT]
> **使用方法如下：**<br>
> 請開啟 `台鐵轉乘工具.py`，並依需求設定以下參數：
>1. `waiting_time`：可接受之最長候車時間，預設為`30分鐘`。
>2. `reverse_direction_transfer_time`：異向轉乘所需之最短時間，預設為`10分鐘`。
>3. `same_direction_transfer_time`：同向轉乘所需之最短時間，預設為`7分鐘`。
>4. `PATH`：資料檔案所在之資料夾路徑（此為必要設定，未修改將導致程式產生致命錯誤）
>5. `number_of_transfers`：欲輸出之轉乘次數條件，預設為`1次`。
>6. `station_tolerance`：轉乘誤差，預設為`0站`；若設定非`0`，則轉乘站可能在起點或終點之外。
>7. `show_fare_breakdown`：用來決定是否輸出完整票價內容，預設為`False`。

> [!IMPORTANT]
>**輸入部分：(這邊每一步輸入`!`皆可退回上一步)**<br>
>定義：`00:00:00`為當日的起使、`24:00:00`為當日的結束。<br>
>1. `日期，本日 [MMDD]: `：輸入欲查詢日期，可以是用`/`、`-`、` `相隔，預設為`當日`。
>2. `起站: `：輸入起點，可以是中文站名、英文站名、車站代號(國音電碼、編號)。
>3. `終站: `：輸入終點，可以是中文站名、英文站名、車站代號(國音電碼、編號)。
>4. `中間必停站: `：輸入必停站，可以是中文站名、英文站名、車站代號(國音電碼、編號)，預設`None`。
>5. `時間，現在時間 [HH:MM:SS]: `：輸入欲查詢時間，可以是用`:`、`：`、` `相隔，預設為`當時`。
>6. `希望抵達時間: `：希望在欲查詢時間後的什麼時候抵達，若時間過於短暫，可能沒有數據；若不想用抵達時間設限，那按下`Enter`，則跳至`查未來幾小時`。
>7. `查未來幾小時: `：希望查詢`時間`往後幾小時之間的區間內，輸入`0`則為`時間`往後到當日`24:00:00`，預設為`0`，一定不能超過翌日`24:00:00`，此程式沒有載入後天之資料。
>8. `排序方式 (1:發車, 2:抵達, 3:票價, 4:時長):`：希望輸出的資料排序，依發車時間單調遞增排序、依抵達時間單調遞增排序、依乘車費用單調遞增排序、依乘車時長單調遞增排序，預設為`1:發車`。

> [!IMPORTANT]
>**輸出部分：**<br>
> 執行後會輸出一份`.txt`檔，放在`{PATH}\output\{查詢結果_(民國日期)_(起站）_經(必停站)_(終站)_(時間).txt}`。

> [!TIP]
> **檔案介紹**
>
> ```text
> C:.
> │  README.md
> │  台鐵轉乘工具.py
> │  跑所有站點票價.py
> │  驗證time.py
> │
> ├─data
> │  │  class_name_map.py
> │  │  route_length.py
> │  │  site_name.py
> │  │  TR_fare_range.py
> │  │
> │  ├─fare
> │  │      里程票價表.json
> │  │
> │  └─time
> │         YYYYMMDD.json
> │
> ├─output
> │
> └─picture
>         臺鐵觀光地圖TPASS.jpg
>         鐵路時刻表資料集開發手冊.pdf  
> ```
>1. `台鐵轉乘工具.py`：主要執行工具。
>2. `跑所有站點票價.py`：創造`里程票價表`之程式，裡面有台鐵票價的計算方式。
>3. `驗證time.py`：驗證`time`資料夾中的檔案是否完整。調`DIR_PATH`和`END_DATE`就好。
>4. `class_name_map.py`：列車種類代碼，資料來源：[鐵路時刻表資料集開發手冊V1.6](https://ods.railway.gov.tw/tra-ods-web/ods)。
>5. `route_length.py`：台鐵車站里程，經整理，資料來源：[臺鐵鐵路里程](https://data.gov.tw/dataset/6999)。
>6. `site_name.py`：台鐵車站名稱，經整理，內有中文站名、英文站名、車站代號(國音電碼、編號)，資料來源：[臺鐵車站基本資料集](https://data.gov.tw/dataset/33425)。
>7. `TR_fare_range.py`：各級列車票價費率與支線票價計算，經整理與統整，資料來源：[乘車里程/票價試算](https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip114/query)。
>8. `里程票價表.json`：里程票價表，直接用查表的，跑主程式會比較快。
>9. `YYYYMMDD.json`：各天台鐵理論運行時間數據，資料來源：[鐵路時刻表-JSON](https://ods.railway.gov.tw/tra-ods-web/ods/download/dataResource/railway_schedule/JSON/list)，需自行下載更新資料。
>10. `臺鐵觀光地圖.jpg`：台鐵鐵路地圖，資料來源：[臺灣鐵路觀光地圖](https://www.railway.gov.tw/tra-tip-web/tip/tip00C/tipC21/view?proCode=8ae4cac3889508e701889af6ea7904e7&subCode=8ae4cac28ced2612018cf2ae133d0ac5&lang=zh_TW)。
>11. `鐵路時刻表資料集開發手冊.pdf`：提供JSON格式與列車種類代碼，資料來源：[鐵路時刻表資料集開發手冊V1.6](https://ods.railway.gov.tw/tra-ods-web/ods)。
>12. 之後發現有直接的里程票價表，資料來源：[臺鐵鐵路票價](https://data.gov.tw/dataset/6998)。

> [!TIP]
> **小工具**
>1. [國營臺灣鐵路股份有限公司官網](https://www.railway.gov.tw/tra-tip-web/tip)
>2. [線上訂票](https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip121/query)
>3. [剩餘座位查詢](https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip119/queryTime)
>4. [列車時刻/車次查詢](https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip112/gobytime)
>5. [車票類型與價格資料](https://www.railway.gov.tw/tra-tip-web/tip/tip00C/tipC21/view?proCode=8ae4cac3756b7b4101757271e5f71703&subCode=8ae4cac3756b7b41017572737d1a1704)
>6. [票價試算](https://www.railway.gov.tw/tra-tip-web/tip/tip001/tip114/query)
>7. [臺鐵列車動態](https://railway.chienwen.net/taiwan/)
>8. [TRTTs](https://github.com/bionicempire/Taiwan-Railway-Travel-Tools)

> [!CAUTION]
> **注意事項如下：**<br>
>1. 本系統目前尚未支援臺鐵與高鐵系統間之跨系統轉乘功能。
>2. 當轉乘次數達兩次(含)以上時，程式運算所需時間可能明顯增加，請耐心等候結果輸出。
>3. 票價計算結果可能因四捨五入機制而產生約新臺幣 1 元之誤差，實際票價仍應以國營臺灣鐵路股份有限公司公告資料為準。
>4. 當路徑涉及支線區段時，里程計算結果可能與一般直觀認知有所差異，此屬正常現象；實際里程與票價仍應以國營臺灣鐵路股份有限公司公告資料為準。
>5. 使用本程式前，請先詳閱相關公開說明文件；所有資料與計算結果之最終依據，均以國營臺灣鐵路股份有限公司官方公告資訊為準。
>6. 本程式之所有時間皆為理論時間，實際乘車時請以國營臺灣鐵路股份有限公司公告或各站時刻表公告為準，[臺鐵列車動態](https://railway.chienwen.net/taiwan/)。
>7. 本程式僅供個人學習、研究及非營利用途使用，未經作者事前書面同意，不得以任何形式將本程式全部或部分內容用於營利、商業販售、收費服務、商業整合、教育訓練收費或其他任何商業用途。
>8. 使用本程式所衍生之任何直接或間接損失、問題或爭議，作者概不負責；使用者應具備基本資訊判讀與媒體識讀能力，並自行評估及承擔使用本程式所產生之一切風險。
>9. 若使用過程中發現任何程式錯誤(Bug)或其他異常情形，歡迎不吝提出指教。聯絡信箱：`mmafp123456707@gmail.com`。

責任聲明：使用者因使用本程式所為之任何旅運規劃及其衍生之一切結果與後果，無論其原因、性質或情形為何，均應自行負責，開發者對此不負任何法律上或事實上之責任。

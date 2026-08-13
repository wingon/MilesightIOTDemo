# COMMITS

## 2026-08-13 12:08
feat: 品牌更名為永安貨倉大廈（Wing On Godown Building）

- 品牌名稱由「333 IOT Console」改為「Wing On Godown Building」／「永安貨倉大廈」
- 更新 favicon、頁面標題與側欄品牌顯示（新增 brandLine1 / brandLine2 i18n）
- 新增 wingon-logo.png 取代原 333-logo.png
- 隱藏選單中的 CT103 / UG65 / VS135 項目
- 樓宇總覽面板精簡為「樓層／連通／溫度／濕度」四欄，其餘指標欄位移除並註解保留
- Building_Cell_Shape 改為一格子一列，樓層以 JSON 陣列（floors）儲存，取代一樓層一列（floor_no）
- SQL 遷移腳本改為冪等：自動偵測舊表並聚合遷移，保留備份表供人工確認

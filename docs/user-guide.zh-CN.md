# NbS Diagnostics Lab：使用说明与计算原理

适用于 v0.3.1。网站：https://mickeyray0624.github.io/nbs-gis-diagnostics-lab/

快速开始：保留 Ganjam 示例的 2020、2021、50 m 和 50 m 边缘宽度 → 点 Run with current settings → 在总览下方查看结果。

## 没有计算后端，为什么还能运行？

GitHub Pages 提供静态 HTML、CSS、JavaScript 和公开示例文件。浏览器下载程序后，使用你电脑的 CPU 和内存执行计算。主线程管理按钮、地图与下载；单独的 Web Worker 读取栅格、对齐、重分类、计算变化和破碎化，再把结果数组传回页面。Web Worker 是浏览器中的计算线程，不是远程服务器。上传文件的内容不会发送到服务器；底图和公开示例的下载仍需要网络。示例的裁剪与 50 m 预处理在发布前由 Python 完成。

当前上限：每张输入 GeoTIFF 100 MB、2,500 万像元；分析网格 800 万像元；矢量 25 MB；最多 3 个年份。实际可处理大小也取决于设备内存。大范围高分辨率任务应先裁剪、降低分辨率，或使用仓库中的 Python 引擎；引擎是单独的命令行工具，当前网页没有调用它。

## 1. 研究区总览地图

**怎么用：**查看绿色边界和名称；点 Locate study area 定位研究区，点 Regional context 查看周边。顶部 Overview 可随时返回总览。

**怎么实现：**示例读取 Ganjam 的 GeoJSON 边界。自带数据优先显示上传的 AOI，否则从最早年份的 GeoTIFF 的地理参考读取范围并转换到经纬度。MapLibre 绘制边界、自动缩放；底图来自 OpenStreetMap。总览只显示位置和范围，计算结果图在下方。

## 2. 公开示例与年份

**怎么用：**选择 Public example，保留 2020、2021 和 50 m，即可运行两个模块。也可下载示例 GeoTIFF，再切换到上传模式复测。

**怎么实现：**原始 ESA WorldCover 为 10 m。示例事先用 Python 裁剪至 Ganjam，并以最近邻重采样到 EPSG:6933 的 50 m 等面积网格。页面每次重新计算统计、变化和破碎化；SHA-256 校验示例文件。2020 v100 与 2021 v200 算法不同，差异不能直接当作真实土地变化。

## 3. 上传栅格、研究区与识别类别

**怎么用：**选择 Upload your own GeoTIFFs，填年份，选 1–3 张单波段分类 GeoTIFF。点 Load raster class codes 检查类别。AOI 可选 GeoJSON 或单一 Shapefile 的 ZIP；不填则以最早年份的栅格范围分析。

**怎么实现：**geotiff.js 读取地理参考和像元，proj4 转换坐标；支持 WGS84、WGS84 UTM、Web Mercator 和 EPSG:6933。GeoJSON 应为 WGS84；ZIP 内含 .shp、.dbf、.prj。0 和文件声明的 NoData 不参与统计。RGB 影像、旋转网格和 PixelIsPoint 栅格需先在 GIS 中转换。

## 4. 选择诊断模块

**怎么用：**LULC change only：2–3 个不同年份；Forest fragmentation only：1–3 个年份；两个一起运行：2–3 个年份。

**怎么实现：**LULC 对按年份排序后的相邻两期逐像元比较。三期产生两组比较，例如 2017→2021、2021→2025。破碎化对每一年独立计算，不需要先运行变化分析。

## 5. 分析分辨率

**怎么用：**Grid resolution 单位是米。先用 50 m 测试；大研究区可增至 100 m 或更粗。森林边缘宽度不得小于一个像元。

**怎么实现：**所有输入用最近邻采样到同一个 EPSG:6933 等面积网格，以像元中心判断是否在 AOI 内。类别面积 = 像元数 × 分辨率² ÷ 10,000（公顷）。更细的网格占用更多内存；把已有 50 m 示例设成 10 m 不会恢复原始细节。

## 6. 类别重分类（Crosswalk）

**怎么用：**展开 Reclassify land cover。Source 是原始编码；Target、Name、Colour 是统一后的类别。要合并类别，给它们相同的目标编码、名称和颜色。也可导入或导出 CSV。

**怎么实现：**程序先对齐栅格，再按映射表替换每个类别编码。所有年份共用同一表；每个出现的源类别都必须有映射。CSV 列为 source_code,target_code,target_name,color；目标编码 1–999，颜色格式 #RRGGBB。只改颜色不改变面积；合并类别会改变转移和森林结果。

## 7. 森林定义

**怎么用：**在 Classes counted as forest 勾选需要计为森林的目标类别。WorldCover 示例默认选 Tree cover（10）和 Mangroves（95）。重分类之后请重新核对勾选项。

**怎么实现：**先把选中类别转成森林=1，其余有效类别转成非森林=0。这里是用户定义的分析掩膜；土地覆盖中的 Tree cover 不等于某个国家的法定森林定义。

## 8. 边缘宽度与边界选项

**怎么用：**Forest edge width 设置边缘影响深度，例如 50 m 或 100 m。Count AOI / NoData boundaries as edges 默认关闭；打开会把研究区外缘和缺失区域也视为森林边缘。

**怎么实现：**用欧氏距离变换求森林像元中心到最近非森林像元中心的距离。距离严格大于阈值为核心候选，其余为边缘候选。默认不把未知边界当作非森林；打开后会减少靠边的核心区。保护地边界只用于分组，始终不会制造森林边缘。

## 9. 保护地与 OECM 分组

**怎么用：**展开 Protection & OECM layers，按需上传两类面文件，然后运行含森林破碎化的模块。使用覆盖研究区的完整资料。

**怎么实现：**先对整个研究区计算破碎化，再按保护地、OECM 和剩余区域统计；重叠时保护地优先。面积按像元分配；NP、MPS、MPE、MSI、AWMSI 把跨界的完整森林斑块归给占其面积最多的组；平局顺序为保护地、OECM、剩余区域。LPI 用斑块在该组内的实际面积。剩余区域只代表未被所上传图层覆盖，不保证法律上未受保护。

## 10. 土地覆盖图与差异图

**怎么用：**运行后在 Land cover 查看逐年图；Class difference 显示相邻年份类别不同的位置。将鼠标移到图上查看像元类别；下方图例解释颜色。

**怎么实现：**Canvas 按类别着色展示分析数组，NoData 透明。差异图只比较两期都有有效数据的像元：相同=0，不同=1。总览底图仅用于定位，不参与面积或距离计算。

## 11. 转移矩阵、增加与减少

**怎么用：**在 Transitions, gains & losses 选比较年份。矩阵行是早期类别，列是后期类别，数字单位公顷。对角线为保持原类别；其他格子为转移。

**怎么实现：**对共同有效覆盖逐像元统计 from→to。某类别 gross loss = 本行非对角线之和；gross gain = 本列非对角线之和；net = gain − loss。逐年面积表按各年有效范围统计，因此有效覆盖不同的时候，不能直接拿逐年总面积相减来代替这个净变化。

## 12. 森林破碎化图

**怎么用：**选择 Forest fragmentation 标签：深绿 Core（核心）、黄 Edge（边缘）、红 Patch（无核心的小斑块）、紫 Internal clearing（内部非森林空地）。灰色是其他非森林，透明是 NoData。

**怎么实现：**森林用 8 邻域连通（包括对角接触）。若一个连通斑块没有任何核心候选像元，整个斑块归为 Patch；否则区分 Core 和 Edge。非森林用 4 邻域识别空洞；与外缘或 NoData 连通的区域不算内部空地。Core+Edge+Patch 等于森林总面积；内部空地不计入森林。

## 13. 森林指标

**怎么用：**在 Fragmentation by year & protection 对比年份和分组。NP 越多仅表示连通森林斑块数量更多，不能独立判断生态质量；应结合核心面积、分辨率和森林定义解释。

**怎么实现：**统计斑块面积、栅格边界长度和形状。NP 统计所有连通森林斑块，不只是红色 Patch 类。指标公式见下表；MSI 使用栅格边长公式，且受边界开关影响。这是栅格版参考实现，与 ArcPy 多边形边界测量不保证逐项完全一致。

## 14. 运行、停止与导出

**怎么用：**点 Run with current settings 或 Run analysis 开始；计算中可移动地图，也可 Stop computation / Cancel analysis。结果在总览下方原地显示。修改参数后须重新运行。

**怎么实现：**GeoTIFF 保留完整分析网格、CRS 和 NoData；PNG 用于展示，含图例但不替代地理栅格；CSV 包含逐年面积、转移矩阵、增减量、森林指标；Run manifest JSON 记录输入哈希、参数、类别表、检查结果与限制。下载由浏览器生成。停止会终止 Worker，关闭或刷新页面会丢失内存中的结果。

## 指标字段

| 字段 | 含义 | 公式与口径 |
|---|---|---|
| landscape_ha | 有效研究区面积 | 有效像元数 × 单像元公顷数 / valid cells × cell area (ha) |
| forest_ha / PLAND | 森林面积 / 森林比例 | PLAND = forest_ha / landscape_ha × 100% |
| core_ha / edge_ha / patch_ha | 核心 / 边缘 / 无核心斑块面积 | 三者之和 = forest_ha / sum = forest_ha |
| clearing_ha | 内部空地面积（非森林） | 不计入 forest_ha / excluded from forest_ha |
| core_pct | 森林中的核心占比 | core_ha / forest_ha × 100% |
| NP | 连通森林斑块数 | 所有森林斑块，8 邻域 / all forest components, 8-neighbour |
| TE_m / ED | 边缘总长 / 边缘密度 | ED = TE_m / landscape_ha (m/ha) |
| MPS_ha / MPE | 平均斑块面积 / 平均周长 | 完整斑块面积或周长之和 / NP · sum of whole-patch area or perimeter / NP |
| MSI / AWMSI | 平均形状指数 / 面积加权形状指数 | 单斑块 shape = 0.25 × perimeter(m) / √area(m²)；MSI = mean(shape)；AWMSI = Σ(shape × area) / Σarea |
| LPI / largest_patch_ha | 最大斑块占比 / 面积 | LPI = largest_patch_ha / landscape_ha × 100%；分组时用实际相交面积 / actual within-stratum area |
| clearings_intersecting | 与该组相交的内部空地数 | 同一空地可横跨多组，分组计数不能相加 / a clearing may intersect multiple strata |

## 实现入口

- `src/App.tsx`：输入、参数、Worker 通信和固定总览布局。
- `src/MapPanel.tsx`：AOI / 栅格范围定位、底图和名称标记。
- `src/analysis/io.ts`：GeoTIFF/矢量读取、坐标转换、网格对齐、导出。
- `src/analysis/compute.ts`：重分类、转移矩阵、距离变换、连通斑块和指标。
- `src/analysis/runner.ts`：计算流程、校验和运行清单。
- `src/analysis/worker.ts`：浏览器计算线程入口。
- `src/Results.tsx` 与 `src/RasterView.tsx`：结果表格、图表、像元查看和下载。

公开示例主要用于验证功能；正式分析应使用经过批准、口径一致的数据、年份、森林定义和保护地资料。

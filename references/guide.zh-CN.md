# 工业品产品美化 Skill：部署、使用与操作说明

## 1. 功能说明

本 Skill 用于把工业零件、管夹、紧固件、手柄、金属件、尼龙件和塑料件照片处理为
干净、统一、可用于目录或电商展示的透明 PNG。它强调“美化表面，不改变结构”：孔位、
孔数、螺栓、垫片、接缝、压字、零件数量、观察角度、比例和外轮廓都必须与原图一致。

标准流程包括：原图盘点、结构清单、小样确认、AI 图片编辑、安全键色去背、2048 方形画布
标准化、单图 QA、由原图目录推导交付清单的全量验收，以及原图/成品对照复核。

## 2. 环境部署

### 2.1 运行要求

- Codex 桌面端或其他支持 Skills 与图片编辑能力的 Codex 环境
- Python 3.10 或更高版本
- Git（仅从 GitHub 安装时需要）
- Python 包：NumPy、Pillow

### 2.2 安装 Skill

把仓库克隆到 Codex Skills 目录。Windows PowerShell 示例：

```powershell
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $HOME '.codex\skills' }
git clone https://github.com/howardsun0704-cmd/industrial-product-beautification.git (Join-Path $skillsRoot 'industrial-product-beautification')
```

macOS / Linux 示例：

```bash
git clone https://github.com/howardsun0704-cmd/industrial-product-beautification.git "${CODEX_HOME:-$HOME/.codex}/skills/industrial-product-beautification"
```

安装后新建一个 Codex 任务，使用 `$industrial-product-beautification` 调用。

### 2.3 安装脚本依赖

在 Skill 文件夹内执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS / Linux 把激活命令替换为 `source .venv/bin/activate`。

## 3. 使用方法

在 Codex 中附上图片或给出图片目录，并明确调用 Skill。例如：

```text
使用 $industrial-product-beautification 美化这个目录里的工业管夹照片。
保持所有孔位、螺栓、压字、观察角度和比例不变，输出 2048×2048 透明 PNG，
先做 5 张不同材质的小样，确认后再批量处理，并生成质检报告和对比图。
```

也可以只做验收：

```text
使用 $industrial-product-beautification 检查 outputs 目录的透明 PNG 是否符合交付标准，
同时对比原图检查零件结构是否被改变。
```

## 4. 操作方法

### 4.1 建议目录

```text
job/
  originals/       原图，只读保留
  keyed/           AI 输出的纯色键背景中间图
  outputs/         最终透明 PNG
  qa/reports/      单图 QA JSON
  qa/sheets/       批次对比复核图
```

### 4.2 选择键色

- 绿色或青色塑料件：使用洋红 `#FF00FF`。
- 银色、灰色、黑色、中性色金属件：使用绿色 `#00FF00`。
- 产品同时大量包含绿色和洋红色：不要强行键色，改用不会误删产品颜色的去背方法。

AI 中间图必须只有产品和完全均匀的纯色背景，不能出现地面、地平线、投影、倒影、道具、
文字、水印或边框。

### 4.3 生成透明成品

```powershell
python scripts/finalize_keyed_product.py `
  --source job/keyed/part-magenta.png `
  --original job/originals/part.jpg `
  --key magenta `
  --output job/outputs/part_beautified.png `
  --qa job/qa/reports/part.json `
  --batch-id B01 `
  --structure-policy strict
```

`--key auto` 会从边框颜色自动判断绿色或洋红色；批量生产时建议明确写出键色。默认输出
2048×2048，产品最大占画布 90%。可用 `--canvas` 和 `--occupancy` 调整。

默认的 `--interior-key auto` 只直接删除与画布边缘连通的键色背景，并仅把产品内部接近
纯键色的封闭区域当作孔洞。QA JSON 的 `key_extraction` 会分别记录边缘连通、内部删除和
内部保护像素。只要存在未预期的内部候选像素，就必须检查键控中间图和最终 Alpha；优先换用
不与产品重叠的键色，不要用 `--interior-key remove` 强行删除产品颜色。

默认的 `--structure-policy strict` 会在写出成品前比较原图结构与抠图 Alpha，检查主要主体数量、
封闭孔洞数量与面积、孔洞边缘碎裂、原图边界裁切和轮廓比例。硬失败会直接停止写出。仅复核告警
必须逐图查看原图与输出后，才可使用
`--structure-policy warn --approve-structure-review` 放行；该参数不能放行主体或孔洞硬失败。


### 4.4 全量自动验收

```powershell
python scripts/validate_outputs.py `
  --original-root job/originals `
  --root job/outputs `
  --report job/qa/validation.json `
  --structure-policy strict
```

脚本以 `--original-root` 为权威清单，检查每张可读原图是否在相同相对子目录下有且仅有一个
`<原文件名>_beautified.png`，并报告漏图、多图、目录层级错误、同名冲突和不可读原图。
同时检查 PNG/RGBA、尺寸、四角透明、透明与不透明像素，以及产品是否触碰画布边缘。不要把
`--expected` 改成当前成品数量来消除失败；非零退出码表示交付尚不完整或格式不合格。

严格模式会逐对执行结构检查。报告中的 `severity: fail` 为不可批准的硬失败；
`severity: review` 必须人工对照。确认某个复核告警无误后，用其精确相对路径重复传入
`--approve-structure-review <相对输出路径>`。禁止按目录批量批准，也不能通过放宽阈值掩盖失败。


### 4.5 生成批次复核图

```powershell
python scripts/make_qa_sheet.py `
  --qa-root job/qa/reports `
  --batch-id B01 `
  --output job/qa/sheets/B01.png
```

逐张比较原图与成品，重点检查孔位、孔数、螺栓、垫片、接缝、文字、方向、比例和轮廓。
自动 Alpha 验收通过不等于结构正确；任何结构变化都必须退回重做。

## 5. 交付标准

- 原图不覆盖、不改名、不删除。
- 每张可读原图必须恰好对应一个成品；命名为 `<原文件名>_beautified.png`，并保留相对子目录。
- 默认 2048×2048、PNG、RGBA、四角 Alpha 为 0。
- 孔洞和开放结构内部也必须透明。
- 不允许任何主体数量减少、孔洞丢失、裁切外补全或未经逐图批准的结构告警。
- 不包含新增文字、品牌、水印、道具、地面、投影或装饰元素。
- 损坏或无法读取的原图单独报告，不得静默漏图。

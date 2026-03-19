# plotting 配置文件说明

稳定性：`Public API`

## 这页解决什么问题？

这页说明统一 plotting 配置文件的正式结构、各 section 的职责边界，以及常见参数应该放在哪里。

当前正式口径是：

- 一份统一 plotting TOML 配置文件
- `configure_zh(path)` 只读取其中的 `[zh]`
- `AxisFrame.from_file(path)` 只读取 `axis_frame.*`
- `GridFrame.from_file(path)` 只读取 `grid_frame.*`
- `LegendHelper.from_file(path)` 只读取 `legend.*`

## 推荐文件结构

```toml
[zh]

[axis_frame.frame]
[axis_frame.top]
[axis_frame.bottom]
[axis_frame.left]
[axis_frame.right]

[grid_frame.frame]
[grid_frame.x]
[grid_frame.y]

[legend.frame]
[legend.frame_plotter]
[legend.one_third_octave]
[legend.story_value]
```

## `[zh]`

用途：

- 配置 matplotlib 中文字体
- 配置与中文绘图直接相关的 `rcParams`
- 配置标题字号、坐标轴标签字号、刻度字号、legend 默认字号等底层 rc 参数

`[zh]` 是给 `configure_zh(path)` 用的，不负责：

- `AxisFrame`
- `GridFrame`
- `LegendHelper`

### 常见参数

```toml
[zh]
"font.family" = "sans-serif"
"font.sans-serif" = ["SongTNR"]
"font.serif" = ["SongTNR"]
"mathtext.fontset" = "stix"
"axes.unicode_minus" = false

"font.size" = 8
"axes.titlesize" = 9
"axes.labelsize" = 7
"xtick.labelsize" = 6
"ytick.labelsize" = 6
"legend.fontsize" = 7
```

### 说明

- 这里的键名使用 matplotlib `rcParams` 的原始点号键。
- `configure_zh(path)` 只会读取 `[zh]`，并把它展平后应用到 `plt.rcParams`。
- 如果需要临时覆盖某些 rc 参数，仍可通过 `configure_zh(..., update_fields=...)` 追加。

## `axis_frame.*`

用途：

- 配置坐标轴边框与 `tick_params`
- 只负责外观，不负责 locator、formatter、grid、legend

正式结构：

- `axis_frame.frame`：四边共享底座
- `axis_frame.top` / `axis_frame.bottom` / `axis_frame.left` / `axis_frame.right`：按方向覆盖

### 常见参数

```toml
[axis_frame.frame.spine]
linewidth = 0.8
color = "black"
visible = true

[axis_frame.frame.major]
direction = "in"
length = 3.0
width = 0.8
labelsize = 8

[axis_frame.frame.minor]
direction = "in"
length = 2.0
width = 0.6

[axis_frame.bottom.major]
labelbottom = true
pad = 2

[axis_frame.top.major]
labeltop = false

[axis_frame.right.major]
labelright = false
```

### 说明

- `bottom` 仍然是正式支持项，只是现在要写在 `axis_frame.bottom` 下。
- `AxisFrame` 只解释：
  - `spine`
  - `major`
  - `minor`
- `major` / `minor` 内部参数会原样传给 `Axes.tick_params(...)`。

## `grid_frame.*`

用途：

- 配置 X/Y 主次网格线的启停与样式

正式结构：

- `grid_frame.frame`：X/Y 网格的共享底座
- `grid_frame.x`：X 轴网格覆盖
- `grid_frame.y`：Y 轴网格覆盖

### 常见参数

```toml
[grid_frame.frame]
able = true
which = "major"
color = "#d0d0d0"
linewidth = 0.5
linestyle = "--"
alpha = 0.7
zorder = 0

[grid_frame.x]
linestyle = ":"

[grid_frame.y]
which = "both"
alpha = 0.5
```

### 说明

- `GridFrame` 与 `AxisFrame` 是两个独立对象，不共享配置对象本体。
- 它们可以共用同一文件，但语义不同：
  - `AxisFrame` 按 `top/bottom/left/right`
  - `GridFrame` 按 `x/y`
- `grid_frame.frame` 只定义网格样式底座；若未显式写 `able = true`，网格默认不会启用。
- `which` 支持：
  - `"major"`
  - `"minor"`
  - `"both"`

## `legend.*`

用途：

- 配置 legend 的默认布局与后处理参数
- 给 `LegendHelper.from_file(path)` 使用

正式结构：

- `legend.frame`：通用底座
- `legend.frame_plotter`：普通二维曲线图默认 legend
- `legend.one_third_octave`：倍频程图默认 legend
- `legend.story_value`：story/value 图默认 legend

### 常见参数

```toml
[legend.frame]
loc = "best"
framealpha = 1.0
edgecolor = "black"

[legend.frame_plotter]
ncol = 1

[legend.one_third_octave]
ncol = 3
columnspacing = 0.4
handlelength = 2.8

[legend.story_value]
loc = "upper right"
```

### 说明

- `LegendHelper` 负责：
  - 收集可见句柄
  - 标签重命名
  - 过滤
  - 多 legend
- 图例文本重命名、`post_renamer` 风格处理属于运行时参数，不建议固化到配置文件。
- 配置文件更适合放默认布局项，例如：
  - `loc`
  - `ncol`
  - `framealpha`
  - `edgecolor`

## 推荐完整示例

```toml
[zh]
"font.family" = "sans-serif"
"font.sans-serif" = ["SongTNR"]
"font.serif" = ["SongTNR"]
"mathtext.fontset" = "stix"
"axes.unicode_minus" = false
"font.size" = 8
"axes.titlesize" = 9
"axes.labelsize" = 7
"xtick.labelsize" = 6
"ytick.labelsize" = 6
"legend.fontsize" = 7

[axis_frame.frame.spine]
linewidth = 0.8
color = "black"
visible = true

[axis_frame.frame.major]
direction = "in"
length = 3.0
width = 0.8
labelsize = 8

[axis_frame.frame.minor]
direction = "in"
length = 2.0
width = 0.6

[axis_frame.bottom.major]
labelbottom = true
pad = 2

[grid_frame.frame]
able = false
which = "major"
color = "#d0d0d0"
linewidth = 0.5
linestyle = "--"
alpha = 0.7

[grid_frame.x]
linestyle = ":"

[legend.frame]
loc = "best"
framealpha = 1.0
edgecolor = "black"

[legend.one_third_octave]
ncol = 3
columnspacing = 0.4
```

## 相关 API

- `configure_zh`
- `AxisFrame`
- `GridFrame`
- `AxisHelper`
- `LegendHelper`

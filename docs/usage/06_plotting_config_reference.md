# plotting 配置参考

稳定性：`Public API`

本页描述 `dyntool.plotting` 当前正式支持的 `PlotTheme` TOML 契约。  
v1.2.0 起，plotting 的正式配置已经统一切到点层级 schema；历史 compat TOML 写法与 flat axes 写法均不再读取。

## 正式入口

1. `PlotDataset.from_* (...)`
2. `PlotTheme.from_file(path)` 或 `PlotTheme.default()`
3. `ConcretePlotter(..., axis_config=...).plot_dataset(dataset, ax=ax, axis_config=...)`
4. `PlotResult.ax`

边界固定如下：

- `PlotTheme.axes` 只负责轴框和 tick 外观
- `PlotTheme.grid` 只负责网格策略与样式
- `PlotTheme.axis_labels` 是运行时对象上的主题级标签默认值；TOML 正式入口为 `axis.x.label` / `axis.y.label`
- `PlotTheme.axis_config` 是运行时对象上的主题级轴语义默认值；TOML 正式入口为 `axis.x` / `axis.y`

## 最小模板结构

当前正式模板建议保留以下顶层块：

- `locale`
- `figure`
- `axes`
- `artist`
- `legend`
- `grid`
- `axis`

其中 `grid` 和 `axis` 都是可选块；不写时，plotter 保持各自的内建默认行为。

## 完整示例

```toml
[locale]
font_family = "sans-serif"
sans_serif = ["SongTNR", "Microsoft YaHei", "SimHei"]
math_fontset = "stix"
unicode_minus = false

[figure]
width_cm = 14.0
height_cm = 10.0
dpi = 150
add_axes_rect = [0.12, 0.14, 0.82, 0.78]

[axes.spines]
top = false
bottom = true
left = true
right = false
linewidth = 0.8

[axes.ticks]
direction = "in"

[axes.ticks.major]
length = 3.0
width = 0.8

[axes.ticks.minor]
length = 2.0
width = 0.6

[grid.x.major]
enabled = true
color = "#b3b3b3"
linestyle = ":"
linewidth = 0.5

[grid.x.minor]
enabled = false

[grid.y.major]
enabled = false

[grid.y.minor]
enabled = false

[artist.plot]
linewidth = 1.2
linestyle = "-"
markersize = 4.0
color = "#4c72b0"
marker = "o"
alpha = 0.9

[legend]
loc = "best"
fontsize = 9
frameon = false
ncol = 1

[axis.x.label]
text = "时间 / s"
pad = 1.0

[axis.y.label]
text = '$a_{\mathrm{max}}$ / (m/s$^2$)'
pad = 1.0

[axis.x]
kind = "continuous"

[axis.x.ticks.major]
step = 2.0

[axis.x.ticks.minor]
step = 1.0

[axis.x.limits]
min = 0.0
max = 8.0

[axis.y]
kind = "continuous"

[axis.y.formatter.scientific]
enabled = true
exponent = 3
fontsize = 11

[axis.y.formatter.scientific.offset]
x = 0.15
y = 1.04
```

## `locale`

用于字体和负号显示。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `font_family` | `str` | Matplotlib 全局字体家族，例如 `"sans-serif"` |
| `sans_serif` | `list[str]` | sans-serif 候选字体链，推荐把 `SongTNR` 放在首位 |
| `math_fontset` | `str` | 数学公式字体集 |
| `unicode_minus` | `bool` | 是否使用 Unicode 负号 |

如果只想把 Matplotlib 全局默认字体快捷切到仓库内置 `SongTNR`，可以直接调用：

```python
import dyntool.plotting as dt_plotting

dt_plotting.PlotTheme.apply_songtnr()
```

这条快捷入口只处理全局字体底座，不替代 `PlotTheme.from_file(...)` 的完整模板配置。

## `figure`

用于整张图尺寸、分辨率和 `add_axes_rect`。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `width_cm` | `float` | 图宽，单位厘米 |
| `height_cm` | `float` | 图高，单位厘米 |
| `dpi` | `int` | 图像分辨率 |
| `add_axes_rect` | `list[float]`，长度为 4 | `figure.add_axes(...)` 使用的 `[left, bottom, width, height]` |

## `axes`

用于轴框和 tick 外观，不负责 locator / formatter 语义。

### `axes.spines`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `top` | `bool` | 是否显示顶部 spine |
| `bottom` | `bool` | 是否显示底部 spine |
| `left` | `bool` | 是否显示左侧 spine |
| `right` | `bool` | 是否显示右侧 spine |
| `linewidth` | `float` | spine 线宽 |

### `axes.ticks`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `direction` | `str` | tick 方向，例如 `"in"` 或 `"out"` |

### `axes.ticks.major`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `length` | `float` | major tick 长度 |
| `width` | `float` | major tick 线宽 |

### `axes.ticks.minor`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `length` | `float` | minor tick 长度 |
| `width` | `float` | minor tick 线宽 |

## `grid`

用于网格策略与样式。  
当前正式结构固定为：

- `grid.x.major`
- `grid.x.minor`
- `grid.y.major`
- `grid.y.minor`

每个块都支持：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `enabled` | `bool` | 是否启用这一组网格 |
| `color` | `str` | 网格颜色 |
| `linestyle` | `str` | 网格线型 |
| `linewidth` | `float` | 网格线宽 |

因此像“只开 x 轴 major 网格，颜色和线型固定”这种需求，可以直接写成：

```toml
[grid.x.major]
enabled = true
color = "#b3b3b3"
linestyle = ":"
linewidth = 0.6

[grid.x.minor]
enabled = false

[grid.y.major]
enabled = false

[grid.y.minor]
enabled = false
```

## `artist`

用于按 Matplotlib 方法名配置常见 artist 默认参数。

当前正式支持：

- `artist.plot`
- `artist.scatter`
- `artist.axhline`
- `artist.fill_between`

## `legend`

用于 legend 基础样式。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `loc` | `str` | legend 位置 |
| `fontsize` | `float` | legend 字号 |
| `frameon` | `bool` | 是否显示边框 |
| `ncol` | `int` | legend 列数 |

## `axis`

`axis` 采用“先按轴分组，再按 Matplotlib 近似术语展开”的结构：

- `axis.x.label`
- `axis.x.ticks`
- `axis.x.limits`
- `axis.x.formatter`
- `axis.y.label`
- `axis.y.ticks`
- `axis.y.limits`
- `axis.y.formatter`
- `kind` 直接放在 `axis.x` / `axis.y`

### 轴标签

```toml
[axis.x.label]
text = "时间 / s"
pad = 1.0

[axis.y.label]
text = "加速度 / (m/s²)"
pad = 1.0
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `text` | `str` | 轴标签文本 |
| `pad` | `float` | 对应 `set_xlabel(..., labelpad=...)` / `set_ylabel(..., labelpad=...)` |

`axis.<side>.label.text` 会原样传给 Matplotlib。若需要数学公式，请按 Matplotlib 习惯使用 `$...$`。  
推荐在 TOML 中优先使用单引号字面量字符串，这样数学文本里的反斜杠不用双写：

```toml
[axis.y.label]
text = '$a_{\mathrm{max}}$ / (m/s$^2$)'
pad = 1.0
```

如果需要显示字面量美元符号，可以写：

```toml
[axis.y.label]
text = 'Price (\$) and $a_{\mathrm{max}}$ / (m/s$^2$)'
pad = 1.0
```

### `ContinuousAxisSpec`

用于连续数值轴。

```toml
[axis.x]
kind = "continuous"

[axis.x.ticks]
values = [0.0, 2.0, 4.0]
num_segments = 2

[axis.x.ticks.major]
step = 2.0

[axis.x.ticks.minor]
step = 0.5

[axis.x.limits]
min = 0.0
max = 4.0
include_zero = true

[axis.x.formatter]
decimals = 1
trim_trailing_zeros = true

[axis.x.formatter.scientific]
enabled = false
```

#### `axis.<side>.ticks`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `values` | `list[float]` | 显式 major tick 位置，优先级最高 |
| `num_segments` | `int` | 自动分段数，优先级低于 `values` 和 `major.step` |

#### `axis.<side>.ticks.major`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `step` | `float` | continuous 轴 major tick 间距 |

#### `axis.<side>.ticks.minor`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `step` | `float` | continuous 轴 minor tick 间距 |

#### `axis.<side>.limits`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `min` | `float` | tick 规划下界 |
| `max` | `float` | tick 规划上界 |
| `include_zero` | `bool` | 规划时是否强制包含 `0` |
| `baseline` | `float` | 以该基线做显示范围推导 |
| `height_ratio` | `float` | 显示范围相对 tick 范围的比例 |

#### `axis.<side>.formatter`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `decimals` | `int` | 主刻度文本小数位 |
| `trim_trailing_zeros` | `bool` | 是否去掉尾随零 |

#### `axis.<side>.formatter.scientific`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `enabled` | `bool` | 是否启用科学计数法 |
| `fontsize` | `float` | offset 文本字号 |
| `exponent` | `int` | 固定科学计数法指数 |

#### `axis.<side>.formatter.scientific.offset`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `x` | `float` | offset 文本的 x 位置 |
| `y` | `float` | offset 文本的 y 位置 |

补充说明：

- `axis.<side>.formatter.scientific.offset.x / y` 不是数据坐标
- 它们会直接透传给 Matplotlib 的 `axis.get_offset_text().set_position((x, y))`
- 更稳妥的用法是先观察自动位置，再做小范围微调

continuous 轴优先级固定为：

1. `ticks.values`
2. `ticks.major.step`
3. `ticks.num_segments`
4. plotter 默认自动规划

`ticks.minor.step` 与上面独立，只要给出就会生效。

### `OctaveAxisSpec`

用于倍频程轴。

```toml
[axis.x]
kind = "octave"

[axis.x.ticks]
positions = [0, 1, 2, 3]
labels = ["2", "2.5", "3.15", "4"]

[axis.x.formatter]
show_every = 2
```

#### `axis.<side>.ticks`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `positions` | `list[float]` | 显式刻度位置 |
| `labels` | `list[str]` | 显式刻度文本，必须与 `positions` 同时提供 |

#### `axis.<side>.formatter`

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `show_every` | `int` | 标签疏密步长，例如 `2` 表示隔一个显示一个 |

## 运行时覆盖

主题文件里的 `axis` 只是默认值，也可以在运行时覆盖：

```python
import dyntool.plotting as dt_plotting

theme = dt_plotting.PlotTheme.from_file("plot_theme.toml")
dataset = dt_plotting.PlotDataset.from_axis_value(
    axis=[0.0, 2.0, 4.0, 6.0],
    value=[0.0, 1.2, 1.5, 0.8],
    name="demo",
    category=dt_plotting.PlotCategory.SAMPLE,
)
axis_config = dt_plotting.AxisConfig(
    x=dt_plotting.ContinuousAxisSpec(ticks=[0.0, 2.0, 4.0, 6.0]),
)
result = dt_plotting.FramePlotter(theme=theme).plot_dataset(dataset, axis_config=axis_config)
```

优先级固定为：

1. `plot_dataset(..., axis_config=...)`
2. plotter 构造参数 `axis_config`
3. `PlotTheme.axis_config`
4. plotter 内建默认行为

## 项目层 variant patch

`AxisConfig` 继续只描述单张图的 `x / y` 轴语义，不直接承载 `C1 / C2 / C3 / C4` 这类业务分支。  
如果项目里只有少量差异项，更推荐：

1. base plotting TOML：写公共 `figure / axes / grid / artist / legend / axis`
2. variant patch TOML：只写差异字段，例如 `axis.y.ticks.minor.step`
3. 项目代码按变体名读取，并用 `dyntool.config.deep_update(...)` 合并

示例：

```toml
# base.toml
[axis.x]
kind = "continuous"

[axis.x.ticks.major]
step = 10.0

[axis.x.ticks.minor]
step = 5.0

[axis.y]
kind = "continuous"

[axis.y.ticks.major]
step = 0.001

[axis.y.ticks.minor]
step = 0.0005

[axis.y.formatter.scientific]
enabled = true
exponent = 3
```

```toml
# C1.toml
[axis.y]
kind = "continuous"

[axis.y.ticks.minor]
step = 0.0001
```

```python
from dyntool.config import deep_update, read_config_file

base = read_config_file("base.toml")
patch = read_config_file("C1.toml")
merged = deep_update(base, patch)
```

## 当前 plotter 支持范围

| plotter | 当前支持 |
| --- | --- |
| `FramePlotter` | `x / y = ContinuousAxisSpec` |
| `StoryValuePlotter` | `x / y = ContinuousAxisSpec` |
| `OneThirdOctavePlotter` | `x = OctaveAxisSpec`，`y = ContinuousAxisSpec` |
| `BoxPlotter` | 当前版本不接入 `AxisConfig` |

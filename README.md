# Arcaea 贴纸生成器

[![AstrBot](https://img.shields.io/badge/AstrBot-插件-green.svg)](https://github.com/Soulter/AstrBot) [![Version](https://img.shields.io/badge/Version-0.√3-blue)]()

本插件是 [astrbot_plugin_arcaea](https://github.com/1-20182/astrbot_plugin_arcaea) 的修改版。

注意：嵌套标签、多段、曲线与联合描边需要启用`启用高消耗渲染器`选项，性能消耗是默认渲染器的数十乃至十数倍，酌情启用！

---

## 安装与配置

1. 放置文件

将插件文件夹`astrbot_plugin_arcaeaStickers`放入`data/plugins`或指定的插件目录，结构如下：

```
astrbot_plugin_arcaeaStickers/
├── main.py
├── __init__.py
├── new_render.py              # 新渲染器
├── legacy_render.py           # 旧渲染器
├── random_ill.py               # 随机插画
├── config_set.py               # 配置修改
├── resources/                 # 角色贴纸图片
├── fonts/                      # 字体文件
├── characters_defaults.json    # 角色默认参数
├── _conf_schema.json         # 配置选项文件
```

2. 安装依赖

```bash
pip install Pillow
```

3. 准备资源

贴纸：放入`resources/`目录，文件名为角色英文名（小写）+ .png，例如`luna.png`, `eto.png`。

列表图片：放入`resources/1ASL.png`，`/arc help`时会一并发送。

字体：将 .ttf 字体文件放入 fonts 目录（插件会自动使用第一个找到的字体）。若无字体，插件将尝试使用系统字体`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`。

随机图库：将图片（.png/.jpg/.jpeg/.gif/.bmp）放入指定目录（可在`main.py`中修改，向上三级，预期`AstrBot/imgs/default/`），用于随机发送功能。触发词为`随插`或`sc`，后接数字可指定发送张数（1~5），当然你把double塞进去也不会有什么问题。

示例：

```
sc
随插3
sc506058858858
展示鲁棒性随插用不了闲鱼上传更新了一下
```

4. 重启 AstrBot

重启后插件即生效。

---

## 随机插画压缩

在配置界面选择是否`启用随机插画压缩`，默认关闭；

设置`图像压缩目标边长`，将指定的边调整为该值（若它比目标值大的话），默认1080px；

选择`压缩目标边长应用`，将目标边长应用于指定边：
* `height`应用于垂直长度
* `width`应用于水平长度
* `longest`应用于最长的方向长度
* `shortest`不存在，我懒炸了没搞，你可以自己改`main.py`

注：gif不参与压缩（没错我孤立gif），压缩失败的图像会按原图发送

## 输出与渲染配置

`output_size`：输出图像边长，范围 64~800，默认 800。调小可显著降低带宽消耗（如 296 可省 85%），代价是清晰度下降。

`ssaa`：新渲染器超采样倍数，范围 1~8，默认 2，仅在`new_render=true`时生效。内存与耗时按 n² 增长。800×800 时`SSAA=2`约 60MB、4倍 约 250MB、8倍 约 1GB。

## 角色列表及别名

使用`/arc help`可查看当前支持的角色、中文别名及列表图片。别名可在`characters_defaults.json`的`_name`字段中自行扩充：

## 指令用法

### 命令列表

`/arc`或`/arc help`发送帮助信息、角色列表文字和列表图片
`/arc info default`查看全局默认配置
`/arc info <角色>`查看该角色在`characters_defaults.json`中显式配置的项
`/arc <角色> [文本] [png]`生成贴纸

#### 标签语法

样式全部通过标签控制，写法是 `[key=value,...]文本[/]`：开标签后面跟它管辖的那段内容，`[/]` 闭合最近的一个未闭合标签。标签可以嵌套，内层继承外层属性，只写自己要改的项即可。

```
/arc ayu '[size=60]大[size=30]小[/]大[/]'
```

· 开标签必须闭合：`[/]` 只关掉最内层那个，少一个就会报「未闭合的标签」
· `$$$` 是并列分段符：遇到它先关掉当前所有标签，再把光标挪回根锚点。文本里出现过 `[/]` 或 `$$$` 就会启用严格校验，**每一段都要写 `[/]`**
· 属性用英文逗号分隔、顺序无关；没写的项继承角色默认 / 全局默认
· 数值属性支持增量写法：`size+=5`、`x-=3`
· 含空格的段落用引号包起来：`'[color=#F00]红 色[/]'`
· 兼容写法：整条文本只用一个标签、且不含 `$$$` 时，末尾 `[/]` 可以省略（还是推荐写全）

#### 标签属性一览

```
键          类型    默认      说明
font        string  YurukaFangTang  字体名，对应 fonts/ 中的文件名
color       string  #FFFFFF  文字填充色，支持 RGBA
stroke      string  #000000  文字描边色
stroke_size number  1        描边宽度
white_color string  #FFFFFF  白边颜色
white_size  number  3.5      白边宽度
spacing     number  0.5        字间距
x           float   50       段落水平位置，画布宽度百分比（支持小数）
y           float   70       段落垂直位置，画布高度百分比（从左下角起）
rotate      float   0        段落旋转角度（度，逆时针）
size        number  15       字号
curve       float   0        曲率：0 直排，100 整圆
radius      float   100      曲线半径上限（画布宽度百分比）
distribution bool   false    曲线模式下是否均匀分布字符角度
png_bg     bool    true     false 时白色背景，true 时透明
```

#### 曲线模式说明

· `curve`决定文字在弧上占用的角度：`curve=100`表示占满整圆，`curve=50`表示半圆
· `radius`是半径上限，实际半径取 `min(radius, auto_radius)`，`auto_radius`由文字总宽自动算出，保证恰好绕出`curve`指定的角度
· 圆心位置自动上移`radius`，使弧顶落在指定的`y`位置
· `distribution=true`时字符均分弧段，`false`时按字符宽度分配角度，字距自然

#### 示例

单段：

```
/arc 光 我是对立
```

多段多色：

```
/arc ayu '[color=#31C1B7,x=42,y=75]C[/]'$$$'[color=#3BE9DF,x=58,y=62]B[/]'
```

（`$$$` 会把光标送回根锚点，所以并列的段要么各自写 x/y，要么靠字号和字距自然错开）

嵌套标签（内层只改字号，闭合后回到外层大小）：

```
/arc ayu '[size=60]大[size=30]小[/]大[/]'
```

曲线：

```
/arc 光 '[curve=50,x=50,y=60]半圆排列[/]'
```

整圆均分：

```
/arc 光 '[curve=100,distribution=true,size=35]整圆均分排列[/]'
```

倾斜多行（字号 10、旋转 15°、行距 5%）：

```
/arc ayu '[rotate=15,size=10,stroke_size=2,x=42.2,y=80]第一行[/]'$$$'[rotate=15,size=10,stroke_size=2,x=43.5,y=75.2]第二行[/]'$$$'[rotate=15,size=10,stroke_size=2,x=44.8,y=70.4]第三行[/]'
```

旧渲染器（不使用嵌套标签，只读最前面一组标签，且不需要闭合）：

```
/arc shirahime [color=#fac,spacing=2]你\n好
```

旧渲染器可用属性（整段共用一套样式，追求轻量、速度）：

```
color stroke stroke_size white_size white_color font x y rotate size spacing png_bg
```

· `white_size=0` 不要白边
· `stroke_size=0` 不要描边
· `spacing` 在旧渲染器里是**行距**，正文中的 `\n` 表示换行
· 未知字体名会回退到默认字体并在日志里提示
· `rotate` 现在**绕文字自身中心**旋转：`x`/`y` 就是文字中心，大角度不会再被甩出画布。
  旧行为是绕画布中心转，`x`/`y` 里隐含了一份偏移补偿，所以带旋转的角色配置需要重新校准一次
· `white_size=0`会直接跳过白底绘制，是旧渲染器最省的一种写法

---

## 角色默认配置

通过`characters_defaults.json`为每个角色设定默认参数，使用默认模式时无需每次输入参数。

### 格式示例

```json
{
	"hikari": {
		"text": "我是对立",
		"x": 50,
		"y": 50,
		"color": "#FFFFFF",
		"stroke": "#000000",
		"rotate": -2,
		"size": 13,
		"spacing": 0,
		"png_bg": false,
		"curve": 0
	},
	"tairitsu": {
		"text": "我是光光",
		"x": 30,
		"y": 70,
		"color": "#FF6666",
		"stroke": "#660000"
	}
}
```

未设置的字段将使用全局默认值(`main.py`)

---

## 致谢

* 本插件基于 [astrbot_plugin_arcaea](https://github.com/1-20182/astrbot_plugin_arcaea) 改写
* 感谢 AinK [UID:589858398](https://b23.tv/gNS0F57) 绘制的兮娅 (Sia) [BV1MFg36uEor](https://b23.tv/jkSzLYJ) 很可爱

注：版权仍归各位开发者/创作者所有

---

## 许可证

本项目采用 MIT 许可证
欢迎二次开发

---

以上大部分由AI生成，如有问题或建议，欢迎提交 Issue 或 Pull Request，不过 GitHub 基本不看，建议通过以下方式联系：

* 邮箱：2824233866@qq.com
* QQ (推荐)：2824233866

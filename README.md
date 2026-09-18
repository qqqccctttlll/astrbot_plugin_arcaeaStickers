# Arcaea 贴纸生成器

[![AstrBot](https://img.shields.io/badge/AstrBot-插件-green.svg)](https://github.com/Soulter/AstrBot) [![Version](https://img.shields.io/badge/Version-0.√2-blue)]()

本插件是 [astrbot_plugin_arcaea](https://github.com/1-20182/astrbot_plugin_arcaea) 的修改版。

注意：多段与曲线需要启用`启用高消耗渲染器`选项，其性能消耗是旧渲染器的数十乃至十数倍！涉及逐字渲染与SSAA处理，酌情启用！

---

## 安装与配置

1. 放置文件

将插件文件夹`astrbot_plugin_arcaeaStickers`放入`data/plugins`或指定的插件目录，结构如下：

```
astrbot_plugin_arcaeaStickers/
├── main.py
├── resources/                  # 角色贴纸图片
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

随机图库：将图片（.png/.jpg/.jpeg/.gif/.bmp）放入指定目录（可在`main.py`中修改，向上三级，默认`AstrBot/imgs/default/`），用于随机发送功能。触发词为`随插`或`sc`，后接数字可指定发送张数（1~5），当然你把double塞进去也不会有什么问题。

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
  - `height`应用于垂直长度
  - `width`应用于水平长度
  - `longest`应用于最长的方向长度
  - `shortest`不存在，我懒炸了没搞，你可以自己改`main.py`

注：gif不参与压缩（没错我孤立gif），压缩失败的图像会按原图发送

## 角色列表及别名

使用`/arc help`可查看当前支持的角色、中文别名及列表图片。以下为内置别名（可在`main.py`的`CHARACTER_ALIASES`中自行扩充）：

```
英文名 中文别名
aichan AI酱
ayu 彩梦
eto 爱托
hikari 光
fracture 骨折光
ilith 伊莉丝
insight 洞烛
kanae 群愿
kou 红
lagrange 拉格兰
lethe 忘却
luna 露娜
maya 摩耶
nami 奈美
nonoka 野乃香
saya 咲弥
shirabe 调
shirahime 白姬
tairitsu 对立
grievous 伞对立
tempest 猫对立
vita 维塔
sia 兮娅
```

如果角色图片文件名与上表不同，请修改`CHARACTER_ALIASES`中的映射，或直接使用文件名。

---

## 指令用法

### 命令列表

`/arc`或`/arc help`发送帮助信息、角色列表文字和列表图片
`/arc info default`查看全局默认配置
`/arc info <角色>`查看该角色在`characters_defaults.json`中显式配置的项
`/arc <角色> [文本] [png]`生成贴纸

#### 段落语法

文本由 $$$ 分段，每段可加前缀 [key=value,key=value,...] 指定该段样式。无前缀的段落使用角色默认配置。

```
/arc ayu '[color=#31C1B7]C'$$$'[color=#3BE9DF,curve=50,x=50,y=25]B' true
```

· $$$：段落分隔符，各段独立布局
· [key=value,...]：段落属性前缀，放在段落文本最前面
· \[ \]：转义方括号，用于在文本里显示字面的 [ ]
· 含空格段落用引号包裹：'[color=#F00]红 色'
· 各属性顺序无关，未写的属性继承角色默认/全局默认

#### 段落属性一览

```
键 类型 默认 说明
font string YurukaFangTang 字体名，对应 fonts/ 中的文件名
color string #FFFFFF 文字填充色，支持 #RRGGBB / #RRGGBBAA
stroke string #000000 文字描边色
stroke_size int 3 描边宽度
white bool true 是否绘制白边
white_color string #FFFFFF 白边颜色
white_size int 10 白边宽度
spacing int 0 字间距
x int 50 段落水平位置，画布宽度百分比
y int 70 段落垂直位置，画布高度百分比（从左下角起）
rotate float 0 段落旋转角度（度，逆时针）
size int 45 字号
curve float 0 曲率：0 直排，100 整圆
radius float 100 曲线半径上限（画布宽度百分比）
distribution bool false 曲线模式下是否均匀分布字符角度
```

#### 曲线模式说明

· curve 决定文字在弧上占用的角度：curve=100 表示占满整圆，curve=50 表示半圆
· radius 是半径上限，实际半径取 min(radius, auto_radius)，auto_radius 由文字总宽自动算出，保证恰好绕出 curve 指定的角度
· 圆心位置自动上移 radius，使弧顶落在指定的 y 位置
· distribution=true 时字符均分弧段，false 时按字符宽度分配角度，字距自然

#### 示例

单段：

```
/arc 光 我是对立
```

多段多色：

```
/arc ayu '[color=#31C1B7]C'$$$'[color=#3BE9DF]B'
```

曲线：

```
/arc 光 '[curve=50,x=50,y=60]半圆排列'
```

整圆均分：

```
/arc 光 '[curve=100,distribution=true,size=35]整圆均分排列'
```

倾斜多行（字号 10、旋转 15°、行距 5%）：

```
/arc ayu '[rotate=15,size=10,stroke_size=2,x=42.2,y=80]第一行'$$$'[rotate=15,size=10,stroke_size=2,x=43.5,y=75.2]第二行'$$$'[rotate=15,size=10,stroke_size=2,x=44.8,y=70.4]第三行'
```

旧渲染器：

```
/arc shirahime [color=#fac,spacing=2]你\n好
```

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
        "color0": "#000000",
        "rotation": -2,
        "font_size": 50,
        "leading": 0,
        "png_bg": false,
        "curve": false
    },
    "tairitsu": {
        "text": "我是光光",
        "x": 30,
        "y": 70,
        "color": "#FF6666",
        "color0": "#660000"
    }
}
```

未设置的字段将使用全局默认值(`main.py`)：

```python
"text": "HEH!",
"y": 70,
"x": 50,
"color": "#FFFFFF",
"color0": "#000000",
"rotation": 0,
"font_size": 45,
"leading": 5,
"png_bg": True,
"curve": False,
"color1": "#FF0000",
"color2": "#0000FF"
```

---

## 致谢

- 本插件基于 [astrbot_plugin_arcaea](https://github.com/1-20182/astrbot_plugin_arcaea) 改写
- 感谢 AinK [UID:589858398](https://b23.tv/gNS0F57) 绘制的兮娅 (Sia) [BV1MFg36uEor](https://b23.tv/jkSzLYJ) 很可爱

---

## 许可证

本项目采用 MIT 许可证
欢迎二次开发

---

以上大部分由AI生成，如有问题或建议，欢迎提交 Issue 或 Pull Request，不过 GitHub 基本不看，建议通过以下方式联系：

- 邮箱：2824233866@qq.com
- QQ (推荐)：2824233866
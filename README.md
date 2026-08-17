# Arcaea 贴纸生成器

[![AstrBot](https://img.shields.io/badge/AstrBot-插件-green.svg)](https://github.com/Soulter/AstrBot) [![Version](https://img.shields.io/badge/Version---0.0.1-blue)]()

本插件是 [astrbot_plugin_arcaea](https://github.com/1-20182/astrbot_plugin_arcaea) 的修改版。

---

## 安装与配置

1. 放置文件

将本插件文件夹`astrbot_plugin_arcaeaStickers`放入`data/plugins`目录（或指定插件目录），结构如下：

```
astrbot_plugin_arcaeaStickers/
├── main.py
├── resources/ #图片
├── fonts/ #字体
├── characters_defaults.json #默认
```

2. 安装依赖

```bash
pip install Pillow
```

3. 准备资源

· 贴纸：放入 `resources` 目录，文件名为角色英文名（小写）+ .png，例`ayu.png`、`eto.png`
· 字体：将任意 .ttf 字体文件放入 fonts 目录（插件会自动使用第一个找到的字体）。若无字体，插件将尝试使用`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`
· 图库：将图片（.png/.jpg/.jpeg/.gif/.bmp）放入指定目录（可自行在`main.py`中配置，默认`/AstrBot/imgs/default/`），用于随机发送功能，关键词可自行在`main.py`中配置，默认`随插`

4. 重启AstrBot

重启后插件即生效。

---

## 角色列表及别名

`/arc list`可查看当前支持的角色及其中文别名。以下为内置别名（用户可自行在`main.py`的 CHARACTER_ALIASES 中扩充）：

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

如果角色图片文件名与上表不同，请自行修改 CHARACTER_ALIASES 映射。

---

### 指令用法

命令列表

命令 说明
```
/arc <角色> [文字] 默认模式：生成指定角色的表情包（文字可选，使用角色默认配置）
/arc <角色> <文字> <高度> <宽度> <颜色> <描边> <旋转> <字号> <行距> <透明> <曲线> [颜色2] [描边2] 高级模式：全参数自定义（见下方详细说明）
/arc list 显示文字版角色列表（含别名）
/arc_list 发送角色列表图片`resources/1.png`
/arc_help 发送帮助
```

高级模式参数详解

参数顺序必须严格遵循，可以使用`__`（俩下划线）占位表示使用该参数的默认值（角色默认配置或全局默认值）。

位置 参数名 类型 说明
1 角色 string 角色英文名或中文别名
2 文字 string 要显示的文字，使用 $$$ 分隔两段可分别指定颜色（仅单行有效）
3 高度 (y) int 文字垂直位置，百分比（0~100，从底部开始）
4 宽度 (x) int 文字水平位置，百分比（0~100，从左侧开始）
5 颜色 string 文字主颜色（十六进制如 #FFFFFF 或颜色名如 white）
6 描边 string 文字描边颜色（同上）
7 旋转 float 文字旋转角度（度）
8 字号 int 字体大小（像素，会按画布缩放）
9 行距 int 多行文字的行间距（像素，会缩放）
10 透明 bool true 或 false，是否使用透明背景（保留角色图片透明区域）
11 曲线 bool （未实现，占位）
12 颜色2 string 第二段文字的主颜色
13 描边2 string 第二段文字的描边颜色

默认模式：

```
/arc 光 你好！
```

高级模式：

```
/arc hikari "Hello!" 50 50 #FFD700 #000000 0 60 10 true false
```

双色文字：

```
/arc shirahime "喜$$$欢" 77 50 #C3D5FF #697EE8 0 50 10 true false #F9C2CB #F74462
```

---

### 角色默认配置

通过`characters_defaults.json`为每个角色设定默认参数，使用默认模式时无需每次输入参数。

格式示例：

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

未设置的字段将使用全局默认值（`main.py`定义）

---

## 致谢

· 本插件基于[astrbot_plugin_arcaea](https://github.com/1-20182/astrbot_plugin_arcaea)改写

· 感谢AinK(UID:589858398)绘制的兮娅(Sia)(BV1MFg36uEor)很可爱

---

## 许可证

本项目采用 MIT 许可证
欢迎二次开发

如有问题或建议，欢迎提交 Issue 或 Pull Request

---

以上大部分由AI生成，联系建议2824233866@qq.com更建议直接QQ
GitHub基本不看
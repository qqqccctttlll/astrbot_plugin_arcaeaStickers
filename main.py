import os
import asyncio
import tempfile

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain, Node, Nodes
from .config_set import handle_arc_set

from . import (
	init_plugin,
	get_config,
	resolve_character,
	list_characters,
	split_args,
	schedule_temp_cleanup,
)
from .random_ill import handle_random_pick
from .new_render import new_render
from .legacy_render import legacy_render

@register("astrbot_plugin_arcaeaStickers", "犭查扌立", "Arcaea贴纸生成器", "0.√3")
class ArcaeaStickerPlugin(Star):
	GLOBAL_DEFAULTS = {
		"text": "HEH!",
		"font": "YurukaFangTang",
		"color": "#FFFFFF",
		"stroke": "#000000",
		"stroke_size": 1,
		"white_color": "#FFFFFF",
		"white_size":3.5,
		"spacing": 0.5,
		"x": 50,
		"y": 70,
		"rotate": 0,
		"size": 15,
		"curve": 0,
		"radius": 100,
		"distribution": False,
		"png_bg": True,
	}

	LEGACY_DEFAULTS = {
		"text": "HEH!",
		"color": "#FFFFFF",
		"stroke": "#000000",
		"x": 50,
		"y": 70,
		"rotate": 0,
		"size": 15,
		"spacing": 2,
		"png_bg": True,
	}

	HELP_TEXT_NEW = (
		"/arc <id> [文本]\n"
		"/arc info <id|default>\n"
		"标签:[key=value,...]文本[/] 可嵌套,开标签必须闭合\n"
		"颜色:color(填充) stroke(描边) stroke_size(描边宽度)\n"
		"白边:white_color(颜色) white_size(宽度,0为无白边)\n"
		"位置:x(横%) y(纵%,从左下) rotate(旋转) size(字号) spacing(字距)\n"
		"曲线:curve(0~100,0直线,100整圆) radius(半径%,半径上限) distribution(均匀分布)\n"
		"增量:size+=5 size-=5 在继承值上增减\n"
		"分段:$$$ 并列多段(回到根锚点),用过闭合标签或$$$则每段都要闭合\n"
		"转义:\\[ \\] 转义方括号,含空格段落用引号包裹\n"
		"示例:/arc ayu '[color=#31C1B7]C[/]'$$$'[color=#3BE9DF,curve=50,x=50,y=25]B[/]'"
	)

	HELP_TEXT_LEGACY = (
		"/arc <id> [文本]\n"
		"标签:[key=value,...]文本, 只读最前面一组标签\n"
		"颜色:color(填充) stroke(描边) stroke_size(描边宽度,0为无描边)\n"
		"白边:white(开关) white_color(颜色) white_size(宽度)\n"
		"位置:x(横%) y(纵%,从左下) rotate(绕文字中心旋转) size(字号) spacing(行距)\n"
		"字体:font(字体名,对应 fonts/ 中的文件名)\n"
		"说明:不支持 $$$、曲线、逐字样式,正文中 \\n 表示换行\n"
		"示例:/arc ayu [color=#31C1B7,x=50,y=70]C"
	)

	def __init__(self, context: Context, config: dict = None):
		super().__init__(context)
		init_plugin(self, context, config)

	async def terminate(self):
		if hasattr(self, "_char_render_cache"):
			self._char_render_cache.clear()
		logger.info("arcaeaStickers 插件已卸载")

	@filter.regex(r'.*')
	async def on_any_message(self, event: AstrMessageEvent):
		async for r in handle_random_pick(self, event):
			yield r

	@filter.command("arc")
	async def arc_command(self, event: AstrMessageEvent):
		parts = split_args(event.message_str)

		if len(parts) == 1 or parts[1].lower() == "help":
			bot_name = event.get_sender_name() or "Etoile"
			self_id = event.get_self_id() or "0"
			help_text = self.HELP_TEXT_NEW if get_config(self, "new_render", False) else self.HELP_TEXT_LEGACY
			contents = [help_text, list_characters(self)]
			list_img_path = os.path.join(self.resource_dir, "1ASL.png")
			if os.path.exists(list_img_path):
				contents.append(Image.fromFileSystem(list_img_path))
			else:
				contents.append("(角色列表图片缺失)")
			nodes = []
			for content in contents:
				msg_element = Plain(content) if isinstance(content, str) else content
				nodes.append(Node(content=[msg_element], name=bot_name, uin=self_id))
			yield event.chain_result([Nodes(nodes)])
			event.stop_event()
			return

		if parts[1].lower() == "info":
			if len(parts) < 3:
				yield event.plain_result("用法: /arc info <char> 或 /arc info default")
				event.stop_event()
				return
			target = parts[2].strip()
			if target.lower() == "default":
				is_new = get_config(self, "new_render", False)
				display = self.GLOBAL_DEFAULTS if is_new else self.LEGACY_DEFAULTS
				lines = [f"全局默认配置({'新' if is_new else '旧'}渲染器):"]
				for k in sorted(display.keys()):
					lines.append(f"  {k} = {display[k]}")
				yield event.plain_result("\n".join(lines))
				event.stop_event()
				return
			character = resolve_character(self, target)
			if character is None:
				yield event.plain_result(f"未知角色: {target}。可用 /arc help 查看角色列表")
				event.stop_event()
				return
			role_config = self.character_defaults.get(character, {})
			if not role_config:
				yield event.plain_result(f"角色 {character} 未配置任何默认项, 全部使用全局默认")
				event.stop_event()
				return
			lines = [f"{character}:"]
			for k in sorted(role_config.keys()):
				lines.append(f"  {k} = {role_config[k]!r}")
			yield event.plain_result("\n".join(lines))
			event.stop_event()
			return

		if parts[1].lower() == "set":
			async for r in handle_arc_set(self, event, parts):
				yield r
			event.stop_event()
			return

		raw_character = parts[1]
		character = resolve_character(self, raw_character)
		if character is None:
			yield event.plain_result(
				f"未知角色: {raw_character}。可用角色: {', '.join(self.available_characters)}\n"
				f"使用 /arc help 查看角色列表"
			)
			event.stop_event()
			return

		role_config = self.character_defaults.get(character, {})
		if len(parts) > 2:
			raw_text = parts[2]
		elif "text" in role_config:
			raw_text = role_config["text"]
		else:
			raw_text = self.GLOBAL_DEFAULTS["text"]
		if raw_text is None:
			yield event.plain_result("无默认文本")
			return

		use_new = get_config(self, "new_render", False)

		try:
			if use_new:
				img = await asyncio.to_thread(new_render, self, character, raw_text, role_config)
			else:
				img = await asyncio.to_thread(legacy_render, self, character, raw_text, role_config)

			def _save(im):
				with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
					im.save(f, format="PNG")
					return f.name

			f_path = await asyncio.to_thread(_save, img)
			yield event.chain_result([Image.fromFileSystem(f_path)])
			schedule_temp_cleanup([f_path])
		except Exception as e:
			logger.exception("生成失败")
			yield event.plain_result(f"生成失败: {str(e)}")
		event.stop_event()

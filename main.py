import os
import random
import re
import json
import tempfile
import threading
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont, ImageColor

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain, Node, Nodes

@register("astrbot_plugin_arcaeaStickers", "犭查扌立", "Arcaea贴纸生成器", "0.0.114514")
class ArcaeaStickerPlugin(Star):
	HELP_TEXT = (
		"def:/arc <id> [文]\n"
		"adv:/arc <id> <文> <y> <x> <色> <描> <角> <siz> <led> <png> <cur> [色2] [描2]\n"
		"$$$双色\n"
		"__占位\n"
		"/arc ayu C$$$B 77 50 __ __ 0 50 1 true __ #31C1B7 #3BE9DF"
	)

	CHARACTER_ALIASES = {
		"AI酱": "aichan",
		"彩梦": "ayu",
		"爱托": "eto",
		"光": "hikari",
		"骨折光": "fracture",
		"伊莉丝": "ilith",
		"洞烛": "insight",
		"群愿": "kanae",
		"红": "kou",
		"拉格兰": "lagrange",
		"忘却": "lethe",
		"露娜": "luna",
		"摩耶": "maya",
		"奈美": "nami",
		"野乃香": "nonoka",
		"咲弥": "saya",
		"调": "shirabe",
		"白姬": "shirahime",
		"对立": "tairitsu",
		"伞对立": "grievous",
		"猫对立": "tempest",
		"维塔": "vita",
		"兮娅": "sia",
	}

	def __init__(self, context: Context, config: dict = None):
		super().__init__(context)
		self.resource_dir = os.path.join(os.path.dirname(__file__), "resources")
		os.makedirs(self.resource_dir, exist_ok=True)

		self.character_defaults = self._load_character_defaults()

		self.available_characters = self._scan_characters()
		for eng in self.available_characters:
			self.CHARACTER_ALIASES[eng] = eng

		self.fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
		self.advanced_font_path = None
		if os.path.exists(self.fonts_dir):
			ttf_files = [f for f in os.listdir(self.fonts_dir) if f.lower().endswith('.ttf')]
			if ttf_files:
				self.advanced_font_path = os.path.join(self.fonts_dir, ttf_files[0])
				logger.info(f"字体路径：{self.advanced_font_path}")
			else:
				logger.warning("fonts 文件夹中未找到 ttf 字体文件")
		else:
			logger.warning("fonts 文件夹不存在")

		if not self.advanced_font_path:
			fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
			if os.path.exists(fallback):
				self.advanced_font_path = fallback
				logger.info(f"使用系统字体：{self.advanced_font_path}")

		self.illustration_dir = "/root/AstrBot/imgs/default/"
		os.makedirs(self.illustration_dir, exist_ok=True)

		logger.info(f"Arcaea Sticker 插件 v4.2.1 加载，可用角色：{', '.join(self.available_characters)}")

	def _load_character_defaults(self) -> dict:
		defaults_path = os.path.join(os.path.dirname(__file__), "characters_defaults.json")
		if os.path.exists(defaults_path):
			try:
				with open(defaults_path, 'r', encoding='utf-8-sig') as f:
					data = json.load(f)
					logger.info(f"角色默认配置加载成功，共 {len(data)} 个角色")
					return data
			except json.JSONDecodeError as e:
				logger.error(f"角色默认配置文件解析失败: {e}")
				return {}
		else:
			logger.warning("未找到 characters_defaults.json")
			return {}

	def _scan_characters(self) -> list:
		if not os.path.exists(self.resource_dir):
			return []
		return [f[:-4] for f in os.listdir(self.resource_dir) if f.lower().endswith(".png")]

	def _resolve_character(self, name: str) -> str | None:
		key = name.lower()
		if key in self.available_characters:
			return key
		if key in self.CHARACTER_ALIASES:
			mapped = self.CHARACTER_ALIASES[key]
			if mapped in self.available_characters:
				return mapped
		return None

	def _list_characters(self) -> str:
		cn_map = {}
		for alias, eng in self.CHARACTER_ALIASES.items():
			if not alias.isascii() and eng in self.available_characters:
				cn_map.setdefault(eng, []).append(alias)
		lines = ["可用角色列表："]
		for eng in sorted(self.available_characters):
			cns = cn_map.get(eng, [])
			cn_str = "、".join(cns) if cns else "无中文别名"
			lines.append(f"{eng} ({cn_str})")
		return "\n".join(lines)

	def _send_random_image(self, folder: str) -> str | None:
		if not os.path.exists(folder):
			return None
		images = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
		if not images:
			return None
		chosen = random.choice(images)
		return os.path.join(folder, chosen)

	@filter.regex(r'.*')
	async def on_any_message(self, event: AstrMessageEvent):
		message_str = event.message_str.strip()
		if "随插" in message_str:
			after_kw = message_str[message_str.index("随插") + 2:].strip()
			num_match = re.search(r'^(\d+)', after_kw)
			num = int(num_match.group(1)) if num_match else 1
			num = max(1, min(num, 5))

			images = [f for f in os.listdir(self.illustration_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
			if not images:
				yield event.plain_result("图库为空或不存在")
				return

			if num == 1:
				chosen = random.choice(images)
				img_path = os.path.join(self.illustration_dir, chosen)
				yield event.chain_result([Image.fromFileSystem(img_path)])
			else:
				selected = random.sample(images, min(num, len(images)))
				bot_name = event.get_sender_name() or "Etoile"
				self_id = event.get_self_id() or "0"
				nodes = []
				for img_name in selected:
					img_path = os.path.join(self.illustration_dir, img_name)
					nodes.append(Node(
						content=[Image.fromFileSystem(img_path)],
						name=bot_name,
						uin=self_id,
					))
				yield event.chain_result([Nodes(nodes)])
			return

	@filter.command("arc_list")
	async def arc_role_list_command(self, event: AstrMessageEvent):
		list_img_path = os.path.join(self.resource_dir, "1.png")
		if os.path.exists(list_img_path):
			yield event.chain_result([Image.fromFileSystem(list_img_path)])
		else:
			yield event.plain_result("图片不存在")

	@filter.command("arc")
	async def arc_command(self, event: AstrMessageEvent):
		parts = self._split_args(event.message_str)

		if not parts:
			yield event.plain_result(self.HELP_TEXT)
			event.stop_event()
			return

		if parts[1].lower() == "list":
			yield event.plain_result(self._list_characters())
			event.stop_event()
			return

		raw_character = parts[1]
		character = self._resolve_character(raw_character)
		if character is None:
			yield event.plain_result(
				f"未知角色：{raw_character}。可用角色：{', '.join(self.available_characters)}\n"
				f"使用 /arc list 查看角色列表"
			)
			event.stop_event()
			return

		role_config = self.character_defaults.get(character, {})

		if len(parts) >= 11:
			try:
				raw_text = parts[2]
				text = raw_text.replace('\\n', '\n') if raw_text != "__" else role_config.get("text", "HEH!")
				if raw_text == "__" and not text:
					raise ValueError("无默认文本")

				raw_height = parts[3]
				height = int(raw_height) if raw_height != "__" else role_config.get("y", 70)

				raw_width = parts[4]
				width = int(raw_width) if raw_width != "__" else role_config.get("x", 50)

				raw_color = parts[5]
				color = raw_color if raw_color != "__" else role_config.get("color", "#FFFFFF")

				raw_color0 = parts[6]
				color0 = raw_color0 if raw_color0 != "__" else role_config.get("color0", "#000000")

				raw_rotate = parts[7]
				rotate = float(raw_rotate) if raw_rotate != "__" else role_config.get("rotation", 0)

				raw_point = parts[8]
				point = int(raw_point) if raw_point != "__" else role_config.get("font_size", 45)

				raw_leading = parts[9]
				leading = int(raw_leading) if raw_leading != "__" else role_config.get("leading", 5)

				raw_png_bg = parts[10]
				if raw_png_bg != "__":
					png_bg = raw_png_bg.lower() == "true"
				else:
					png_bg = role_config.get("png_bg", True)

				raw_curve = parts[11]
				if raw_curve != "__":
					curve = raw_curve.lower() == "true"
				else:
					curve = role_config.get("curve", False)

				color1 = parts[12] if len(parts) > 12 and parts[12] != "__" else role_config.get("color1", "#FF0000")
				color2 = parts[13] if len(parts) > 13 and parts[13] != "__" else role_config.get("color2", "#0000FF")

			except (ValueError, IndexError) as e:
				yield event.plain_result(f"高级模式参数解析错误: {e}\n请检查参数数量和类型。")
				event.stop_event()
				return

			try:
				img = self._generate_advanced_sticker(
					character=character,
					text=text,
					height=height,
					width=width,
					color=color,
					color0=color0,
					rotate=rotate,
					point=point,
					leading=leading,
					png_bg=png_bg,
					curve=curve,
					color1=color1,
					color2=color2
				)
				with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
					img.save(f, format='PNG')
					f_path = f.name
				yield event.chain_result([Image.fromFileSystem(f_path)])
				threading.Timer(5.0, lambda: os.remove(f_path) if os.path.exists(f_path) else None).start()
			except Exception as e:
				logger.exception("高级模式生成失败")
				yield event.plain_result(f"生成失败：{str(e)}")
			event.stop_event()
			return

		if len(parts) > 2:
			text = parts[2].replace('\\n', '\n').strip()
		else:
			text = role_config.get("text", "HEH!")
		if not text:
			yield event.plain_result("无默认文本")
			event.stop_event()
			return

		height = role_config.get("y", 70)
		width = role_config.get("x", 50)
		color = role_config.get("color", "#FFFFFF")
		color0 = role_config.get("color0", "#000000")
		rotate = role_config.get("rotation", 0)
		point = role_config.get("font_size", 45)
		leading = role_config.get("leading", 5)
		png_bg = role_config.get("png_bg", True)
		curve = role_config.get("curve", False)
		color1 = role_config.get("color1", "#FF0000")
		color2 = role_config.get("color2", "#0000FF")

		try:
			img = self._generate_advanced_sticker(
				character=character,
				text=text,
				height=height,
				width=width,
				color=color,
				color0=color0,
				rotate=rotate,
				point=point,
				leading=leading,
				png_bg=png_bg,
				curve=curve,
				color1=color1,
				color2=color2
			)
			with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
				img.save(f, format='PNG')
				f_path = f.name
			yield event.chain_result([Image.fromFileSystem(f_path)])
			threading.Timer(5.0, lambda: os.remove(f_path) if os.path.exists(f_path) else None).start()
		except Exception as e:
			logger.exception("默认模式生成失败")
			yield event.plain_result(f"生成失败：{str(e)}")
		event.stop_event()

	def _split_args(self, raw: str) -> list:
		parts = []
		current = []
		in_quote = False
		quote_char = None
		for ch in raw:
			if ch in ('"', "'") and not in_quote:
				in_quote = True
				quote_char = ch
				continue
			if in_quote and ch == quote_char:
				in_quote = False
				quote_char = None
				continue
			if ch == ' ' and not in_quote:
				if current:
					parts.append(''.join(current))
					current = []
				continue
			current.append(ch)
		if current:
			parts.append(''.join(current))
		return parts

	def _generate_advanced_sticker(self, character: str, text: str, height: int, width: int,
		color: str, color0: str, rotate: float, point: int,
		leading: int, png_bg: bool, curve: bool,
		color1: str = None, color2: str = None) -> PILImage.Image:
		CANVAS_SIZE = (800, 800)
		SCALE = CANVAS_SIZE[0] / 296

		center_x = int(CANVAS_SIZE[0] * width / 100)
		center_y = int(CANVAS_SIZE[1] * (100 - height) / 100)

		point_scaled = int(point * SCALE)
		leading_scaled = int(leading * SCALE)

		char_path = os.path.join(self.resource_dir, f"{character.lower()}.png")
		if not os.path.exists(char_path):
			raise FileNotFoundError(f"角色图片 {char_path} 不存在")
		char_img = PILImage.open(char_path).convert("RGBA")
		char_img = char_img.resize(CANVAS_SIZE, PILImage.LANCZOS)

		if png_bg:
			canvas = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
		else:
			canvas = PILImage.new("RGBA", CANVAS_SIZE, (255, 255, 255, 255))
		canvas.paste(char_img, (0, 0), char_img)

		if text:
			txt_layer = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
			draw = ImageDraw.Draw(txt_layer)

			font_path = self.advanced_font_path
			if not font_path or not os.path.exists(font_path):
				fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
				if os.path.exists(fallback):
					font_path = fallback
				else:
					raise FileNotFoundError("未找到可用字体")
			font = ImageFont.truetype(font_path, point_scaled)

			def parse_color(c):
				if c is None:
					return None
				if c.startswith('#'):
					return tuple(int(c[i:i+2], 16) for i in (1, 3, 5)) + (255,)
				else:
					return ImageColor.getrgb(c) + (255,)

			multi_color = False
			segments = []
			if color1 is not None and color2 is not None and '$$$' in text and '\n' not in text:
				parts = text.split('$$$')
				if len(parts) == 2:
					multi_color = True
					segments = [(parts[0], color, color0), (parts[1], color1, color2)]

			stroke_width = int(3 * SCALE)
			white_stroke_width = int(10 * SCALE)

			if multi_color:
				widths = []
				for seg, _, _ in segments:
					bbox = font.getbbox(seg)
					widths.append(bbox[2] - bbox[0])
				total_width = sum(widths)
				start_x = center_x - total_width // 2
				first_bbox = font.getbbox(segments[0][0])
				line_height = first_bbox[3] - first_bbox[1]
				y = center_y - line_height // 2

				if white_stroke_width > 0:
					current_x = start_x
					for seg, _, _ in segments:
						draw.text((current_x, y), seg, font=font, fill=None,
								  stroke_width=white_stroke_width, stroke_fill="white")
						bbox = font.getbbox(seg)
						current_x += bbox[2] - bbox[0]

				current_x = start_x
				for seg, fill, stroke in segments:
					fill_color = parse_color(fill)
					stroke_color = parse_color(stroke)
					if stroke_color:
						draw.text((current_x, y), seg, font=font, fill=fill_color,
								  stroke_width=stroke_width, stroke_fill=stroke_color)
					else:
						draw.text((current_x, y), seg, font=font, fill=fill_color)
					bbox = font.getbbox(seg)
					current_x += bbox[2] - bbox[0]
			else:
				lines = text.split('\n')
				line_heights = [font.getbbox(line)[3] - font.getbbox(line)[1] for line in lines]
				total_height = sum(line_heights) + leading_scaled * (len(lines) - 1)
				y = center_y - total_height // 2

				if white_stroke_width > 0:
					y_temp = y
					for idx, line in enumerate(lines):
						bbox = font.getbbox(line)
						line_width = bbox[2] - bbox[0]
						x = center_x - line_width // 2
						draw.text((x, y_temp), line, font=font, fill=None,
								  stroke_width=white_stroke_width, stroke_fill="white")
						y_temp += line_heights[idx] + leading_scaled

				y = center_y - total_height // 2
				for idx, line in enumerate(lines):
					bbox = font.getbbox(line)
					line_width = bbox[2] - bbox[0]
					x = center_x - line_width // 2
					fill_color = parse_color(color)
					stroke_color = parse_color(color0)
					if stroke_color:
						draw.text((x, y), line, font=font, fill=fill_color,
								  stroke_width=stroke_width, stroke_fill=stroke_color)
					else:
						draw.text((x, y), line, font=font, fill=fill_color)
					y += line_heights[idx] + leading_scaled

			if rotate != 0:
				rotated = txt_layer.rotate(rotate, expand=True, resample=PILImage.BICUBIC)
				offset_x = (rotated.width - CANVAS_SIZE[0]) // 2
				offset_y = (rotated.height - CANVAS_SIZE[1]) // 2
				final_txt = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
				final_txt.paste(rotated, (-offset_x, -offset_y), rotated)
				txt_layer = final_txt

			canvas = PILImage.alpha_composite(canvas, txt_layer)

		return canvas

	@filter.command("arc_help")
	async def arc_help(self, event: AstrMessageEvent):
		yield event.plain_result(self.HELP_TEXT)

	async def terminate(self):
		logger.info("Arcaea Sticker 插件已卸载")

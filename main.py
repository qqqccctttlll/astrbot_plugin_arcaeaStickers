import os
import random
import re
import json
import math
import asyncio
import tempfile
import threading
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont, ImageColor

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Image, Plain, Node, Nodes


@register("astrbot_plugin_arcaeaStickers", "犭查扌立", "Arcaea贴纸生成器", "0.1.41421356")
class ArcaeaStickerPlugin(Star):
	GLOBAL_DEFAULTS = {
		"text": "HEH!",
		"font": "YurukaFangTang",
		"color": "#FFFFFF",
		"stroke": "#000000",
		"stroke_size": 3,
		"white": True,
		"white_color": "#FFFFFF",
		"white_size": 10,
		"spacing": 0,
		"x": 50,
		"y": 70,
		"rotate": 0,
		"size": 45,
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
		"size": 45,
		"spacing": 5,
		"png_bg": True,
	}

	HELP_TEXT_V2 = (
		"/arc <id> [文本]\n"
		"/arc info <id|default>\n"
		"标签:[key=value,...]文本\n"
		"颜色:color(填充) stroke(描边) stroke_size(描边宽度)\n"
		"白边:white(开关) white_color(颜色) white_size(宽度)\n"
		"位置:x(横%) y(纵%,从左下) rotate(旋转) size(字号) spacing(字距)\n"
		"曲线:curve(0~100,0直线,100整圆) radius(半径%,半径上限) distribution(均匀分布)\n"
		"分段:$$$ 分隔多段,每段可独立设置样式\n"
		"转义:\\[ \\] 转义方括号,含空格段落用引号包裹\n"
		"示例:/arc ayu '[color=#31C1B7]C'$$$'[color=#3BE9DF,curve=50,x=50,y=25]B'"
	)

	HELP_TEXT_LEGACY = (
		"/arc <id> [文本]\n"
		"标签:[key=value,...]文本, 只读最前面一组标签\n"
		"颜色:color(填充) stroke(描边)\n"
		"位置:x(横%) y(纵%,从左下) rotate(旋转) size(字号) spacing(行距)\n"
		"说明:本模式不支持 $$$、白边、曲线、逐字样式\n"
		"示例:/arc ayu [color=#31C1B7,x=50,y=70]C"
	)

	CHARACTER_ALIASES = {
		"AI酱": "aichan", "彩梦": "ayu", "爱托": "eto", "光": "hikari",
		"骨折光": "fracture", "伊莉丝": "ilith", "洞烛": "insight",
		"群愿": "kanae", "红": "kou", "拉格兰": "lagrange", "忘却": "lethe",
		"露娜": "luna", "摩耶": "maya", "奈美": "nami", "野乃香": "nonoka",
		"咲弥": "saya", "调": "shirabe", "白姬": "shirahime", "对立": "tairitsu",
		"伞对立": "grievous", "猫对立": "tempest", "维塔": "vita", "兮娅": "sia",
	}

	def __init__(self, context: Context, config: dict = None):
		super().__init__(context)
		self.resource_dir = os.path.join(os.path.dirname(__file__), "resources")
		os.makedirs(self.resource_dir, exist_ok=True)

		self.excludes_files = {"1ASL.png"}
		self.plugin_config = config or {}

		self.character_defaults = self._load_character_defaults()

		self.available_characters = self._scan_characters()
		for eng in self.available_characters:
			self.CHARACTER_ALIASES[eng] = eng

		self.fonts = {}
		self.fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
		os.makedirs(self.fonts_dir, exist_ok=True)
		for f in os.listdir(self.fonts_dir):
			if f.lower().endswith((".ttf", ".otf")):
				self.fonts[os.path.splitext(f)[0]] = os.path.join(self.fonts_dir, f)

		if self.fonts:
			logger.info(f"已加载字体: {', '.join(sorted(self.fonts.keys()))}")
		else:
			logger.warning("fonts 文件夹中未找到字体文件")

		if "YurukaFangTang" in self.fonts:
			self.default_font_name = "YurukaFangTang"
		elif self.fonts:
			self.default_font_name = sorted(self.fonts.keys())[0]
			logger.warning(f"未找到 YurukaFangTang,默认字体改用 {self.default_font_name}")
		else:
			self.default_font_name = None

		if self.default_font_name:
			self.advanced_font_path = self.fonts[self.default_font_name]
		else:
			fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
			self.advanced_font_path = fallback if os.path.exists(fallback) else None
			if self.advanced_font_path:
				logger.info(f"使用系统字体: {self.advanced_font_path}")
			else:
				logger.error("未找到任何可用字体")

		self._font_cache = {}

		self.illustration_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
			"imgs", "default"
		)
		os.makedirs(self.illustration_dir, exist_ok=True)
		logger.info(f"图库目录: {self.illustration_dir}")

		logger.info(
			f"图像压缩: {self._get_config('compress_ill', False)}, "
			f"目标边长: {self._get_config('compress_target', 1080)}, "
			f"应用方向: {self._get_config('target_towards', 'longest')}"
		)

		render_mode = "v2" if self._get_config("new_render", False) else "legacy"
		logger.info(
			f"Arcaea Sticker 插件 v0.1.41421356 加载, 渲染器={render_mode}, "
			f"可用角色: {', '.join(self.available_characters)}"
		)

	async def terminate(self):
		logger.info("Arcaea Sticker 插件已卸载")

	def _get_config(self, key: str, default=None):
		if key in self.plugin_config:
			return self.plugin_config[key]
		return default

	def _load_character_defaults(self) -> dict:
		defaults_path = os.path.join(os.path.dirname(__file__), "characters_defaults.json")
		if os.path.exists(defaults_path):
			try:
				with open(defaults_path, "r", encoding="utf-8-sig") as f:
					data = json.load(f)
					logger.info(f"角色默认配置加载成功, 共 {len(data)} 个角色")
					return data
			except json.JSONDecodeError as e:
				logger.error(f"角色默认配置文件解析失败: {e}")
				return {}
		logger.warning("未找到 characters_defaults.json")
		return {}

	def _scan_characters(self) -> list:
		if not os.path.exists(self.resource_dir):
			return []
		return [
			f[:-4] for f in os.listdir(self.resource_dir)
			if f.lower().endswith(".png") and f not in self.excludes_files
		]

	def _resolve_character(self, name: str):
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
		lines = ["可用角色列表:"]
		for eng in sorted(self.available_characters):
			cns = cn_map.get(eng, [])
			cn_str = "、".join(cns) if cns else "无中文别名"
			lines.append(f"{eng} ({cn_str})")
		return "\n".join(lines)

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
			if ch == " " and not in_quote:
				if current:
					parts.append("".join(current))
					current = []
				continue
			current.append(ch)
		if current:
			parts.append("".join(current))
		return parts

	def _parse_attr_str(self, s: str) -> dict:
		attrs = {}
		for pair in s.split(","):
			pair = pair.strip()
			if not pair or "=" not in pair:
				continue
			key, value = pair.split("=", 1)
			key = key.strip().lower()
			value = value.strip()
			if not key:
				continue
			try:
				if key == "rotate":
					attrs[key] = float(value)
				elif key in ("curve", "radius"):
					try:
						attrs[key] = float(value)
					except ValueError:
						if key == "curve":
							attrs[key] = 100.0 if value.lower() == "true" else 0.0
						else:
							attrs[key] = 100.0
				elif key in ("x", "y", "size", "white_size", "stroke_size", "spacing"):
					attrs[key] = int(float(value))
				elif key in ("white", "distribution"):
					attrs[key] = value.lower() == "true"
				else:
					attrs[key] = value
			except ValueError:
				continue
		return attrs

	def _parse_color(self, c):
		if c is None:
			return None
		if isinstance(c, tuple):
			return c
		try:
			if c.startswith("#"):
				h = c[1:]
				if len(h) == 8:
					return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
				elif len(h) == 6:
					return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
				elif len(h) == 3:
					return (int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16), 255)
			return ImageColor.getrgb(c) + (255,)
		except Exception:
			return (255, 255, 255, 255)

	def _resolve_font_path(self, font_name) -> str | None:
		if font_name and font_name in self.fonts:
			return self.fonts[font_name]
		if font_name and font_name != self.default_font_name:
			logger.warning(f"未知字体: {font_name}, 回退到 {self.default_font_name}")
		return self.advanced_font_path

	def _get_font(self, font_path, size):
		key = (font_path, size)
		font = self._font_cache.get(key)
		if font is None:
			font = ImageFont.truetype(font_path, size)
			self._font_cache[key] = font
		return font

	def _maybe_compress(self, img_path: str, temp_files: list) -> str:
		if not self._get_config("compress_ill", False):
			return img_path

		ext = os.path.splitext(img_path)[1].lower()
		if ext == ".gif":
			return img_path

		try:
			target = int(self._get_config("compress_target", 1080))
		except (ValueError, TypeError):
			target = 1080

		direction = self._get_config("target_towards", "longest")
		if direction not in ("height", "width", "longest"):
			direction = "longest"

		try:
			with PILImage.open(img_path) as img:
				w, h = img.size

				need = False
				if direction == "height" and h > target:
					need = True
				elif direction == "width" and w > target:
					need = True
				elif direction == "longest" and max(w, h) > target:
					need = True

				if not need:
					return img_path

				if direction == "height":
					ratio = target / h
					new_size = (int(w * ratio), target)
				elif direction == "width":
					ratio = target / w
					new_size = (target, int(h * ratio))
				else:
					ratio = target / max(w, h)
					new_size = (int(w * ratio), int(h * ratio))

				img = img.resize(new_size, PILImage.LANCZOS)

				if ext in (".jpg", ".jpeg"):
					if img.mode in ("RGBA", "P"):
						img = img.convert("RGB")
					suffix, fmt = ".jpg", "JPEG"
				elif ext == ".webp":
					suffix, fmt = ".webp", "WEBP"
				elif ext == ".bmp":
					if img.mode in ("RGBA", "P"):
						img = img.convert("RGB")
					suffix, fmt = ".bmp", "BMP"
				else:
					suffix, fmt = ".png", "PNG"

				with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
					img.save(f, format=fmt)
					tmp_path = f.name

			temp_files.append(tmp_path)
			return tmp_path

		except Exception as e:
			logger.error(f"图像压缩失败: {img_path}, {e}")
			return img_path

	def _schedule_temp_cleanup(self, paths: list, delay: float = 5.0):
		for path in paths:
			def _rm(p=path):
				try:
					if os.path.exists(p):
						os.remove(p)
				except OSError:
					pass
			threading.Timer(delay, _rm).start()

	@filter.regex(r'.*')
	async def on_any_message(self, event: AstrMessageEvent):
		message_str = event.message_str.strip()
		if "随插" in message_str:
			after_kw = message_str[message_str.index("随插") + 2:].strip()
			num_match = re.search(r'^(\d+)', after_kw)
			num = int(num_match.group(1)) if num_match else 1
			num = max(1, min(num, 5))
		elif message_str == "sc":
			num = 1
		elif re.match(r'^sc\d+$', message_str):
			num = int(message_str[2:])
			num = max(1, min(num, 5))
		else:
			return

		if not os.path.exists(self.illustration_dir):
			yield event.plain_result("图库为空或不存在")
			return
		images = [
			f for f in os.listdir(self.illustration_dir)
			if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp"))
		]
		if not images:
			yield event.plain_result("图库为空或不存在")
			return

		temp_files = []
		try:
			if num == 1:
				chosen = random.choice(images)
				img_path = os.path.join(self.illustration_dir, chosen)
				final_path = await asyncio.to_thread(self._maybe_compress, img_path, temp_files)
				yield event.chain_result([Image.fromFileSystem(final_path)])
			else:
				selected = random.sample(images, min(num, len(images)))
				bot_name = event.get_sender_name() or "Etoile"
				self_id = event.get_self_id() or "0"
				nodes = []
				for img_name in selected:
					img_path = os.path.join(self.illustration_dir, img_name)
					final_path = await asyncio.to_thread(self._maybe_compress, img_path, temp_files)
					nodes.append(Node(
						content=[Image.fromFileSystem(final_path)],
						name=bot_name,
						uin=self_id,
					))
				yield event.chain_result([Nodes(nodes)])
		finally:
			self._schedule_temp_cleanup(temp_files)

	@filter.command("arc")
	async def arc_command(self, event: AstrMessageEvent):
		parts = self._split_args(event.message_str)

		if len(parts) == 1 or parts[1].lower() == "help":
			bot_name = event.get_sender_name() or "Etoile"
			self_id = event.get_self_id() or "0"
			help_text = self.HELP_TEXT_V2 if self._get_config("new_render", False) else self.HELP_TEXT_LEGACY
			contents = [help_text, self._list_characters()]
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
				display = self.GLOBAL_DEFAULTS if self._get_config("new_render", False) else self.LEGACY_DEFAULTS
				lines = [f"全局默认配置({'新版' if self._get_config('new_render', False) else '旧版'}渲染器):"]
				for k in sorted(display.keys()):
					lines.append(f"  {k} = {display[k]}")
				yield event.plain_result("\n".join(lines))
				event.stop_event()
				return
			character = self._resolve_character(target)
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

		# --- 生成 ---
		raw_character = parts[1]
		character = self._resolve_character(raw_character)
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
		else:
			raw_text = role_config.get("text", self.GLOBAL_DEFAULTS["text"])
		if not raw_text:
			yield event.plain_result("无默认文本")
			event.stop_event()
			return

		use_new = self._get_config("new_render", False)

		try:
			if use_new:
				img = await asyncio.to_thread(
					self._render_v2, character, raw_text, role_config
				)
			else:
				img = await asyncio.to_thread(
					self._render_legacy, character, raw_text, role_config
				)

			def _save(im):
				with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
					im.save(f, format="PNG")
					return f.name

			f_path = await asyncio.to_thread(_save, img)
			yield event.chain_result([Image.fromFileSystem(f_path)])
			self._schedule_temp_cleanup([f_path])
		except Exception as e:
			logger.exception("生成失败")
			yield event.plain_result(f"生成失败: {str(e)}")
		event.stop_event()

	def _parse_legacy(self, raw_text: str, role_config: dict):
		text = raw_text
		attrs = {}

		if text.startswith("["):
			end = text.find("]")
			if end != -1:
				head = text[1:end]
				if "=" in head:
					attrs = self._parse_attr_str(head)
					text = text[end + 1:]

		text = text.replace("\\[", "[").replace("\\]", "]")
		text = text.replace("\\n", "\n")

		merged = {**self.LEGACY_DEFAULTS, **role_config, **attrs}
		return text, merged

	def _render_legacy(self, character: str, raw_text: str, role_config: dict) -> PILImage.Image:
		text, attrs = self._parse_legacy(raw_text, role_config)

		CANVAS_SIZE = (800, 800)
		SCALE = CANVAS_SIZE[0] / 296

		x_val = float(attrs.get("x", 50))
		y_val = float(attrs.get("y", 70))
		center_x = int(CANVAS_SIZE[0] * x_val / 100)
		center_y = int(CANVAS_SIZE[1] * (100 - y_val) / 100)

		point_scaled = int(int(attrs.get("size", 45)) * SCALE)
		leading_scaled = int(int(attrs.get("spacing", 5)) * SCALE)

		png_bg = bool(attrs.get("png_bg", True))
		color = attrs.get("color", "#FFFFFF")
		stroke = attrs.get("stroke", "#000000")
		rotate = float(attrs.get("rotate", 0))

		char_path = os.path.join(self.resource_dir, f"{character.lower()}.png")
		if not os.path.exists(char_path):
			raise FileNotFoundError(f"角色图片 {char_path} 不存在")

		with PILImage.open(char_path) as ci:
			char_img = ci.convert("RGBA")
		char_img = char_img.resize(CANVAS_SIZE, PILImage.LANCZOS)

		canvas = PILImage.new(
			"RGBA", CANVAS_SIZE,
			(0, 0, 0, 0) if png_bg else (255, 255, 255, 255)
		)
		canvas.paste(char_img, (0, 0), char_img)

		if not text:
			return canvas

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

		fill_color = self._parse_color(color)
		stroke_color = self._parse_color(stroke)
		stroke_width = int(3 * SCALE)
		white_stroke_width = int(10 * SCALE)

		lines = text.split("\n")
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

		return PILImage.alpha_composite(canvas, txt_layer)

	def _parse_text_to_segments(self, raw_text: str, base_defaults: dict) -> list:
		PLACEHOLDER_L = "\x00L\x00"
		PLACEHOLDER_R = "\x00R\x00"

		escaped = raw_text.replace("\\[", PLACEHOLDER_L).replace("\\]", PLACEHOLDER_R)
		parts = escaped.split("$$$")

		segments = []
		for part in parts:
			part = part.strip()
			if not part:
				continue
			attrs = {}
			text = part
			if part.startswith("["):
				end = part.find("]")
				if end != -1:
					attr_content = part[1:end]
					if "=" in attr_content:
						attrs = self._parse_attr_str(attr_content)
						text = part[end + 1:]
			text = text.replace(PLACEHOLDER_L, "[").replace(PLACEHOLDER_R, "]")
			merged = base_defaults.copy()
			merged.update(attrs)
			segments.append({"text": text, "attrs": merged})

		return segments

	def _build_defaults(self, role_config: dict) -> dict:
		base = dict(self.GLOBAL_DEFAULTS)
		base.pop("text", None)
		base.update({k: v for k, v in role_config.items() if k != "text"})
		return base

	def _harden_layer(self, layer, color):
		r, g, b, a = layer.split()
		a = a.point(lambda p: 255 if p > 0 else 0)
		solid = PILImage.new("RGBA", layer.size, color)
		solid.putalpha(a)
		return solid

	def _render_white_char(self, char, font, white_w, white_color, rotate_deg=0):
		try:
			bbox = font.getbbox(char)
		except Exception:
			bbox = (0, 0, font.size, font.size)

		left, top, right, bottom = bbox
		char_w = max(1, right - left)
		char_h = max(1, bottom - top)

		margin = white_w + 4
		w = char_w + margin * 2
		h = char_h + margin * 2
		if w * h > 100_000_000:
			logger.warning(f"白边图层尺寸异常: {w}x{h}, 跳过 {char!r}")
			return PILImage.new("RGBA", (1, 1), (0, 0, 0, 0))

		layer = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
		draw = ImageDraw.Draw(layer)
		draw.text((margin - left, margin - top), char, font=font, fill=white_color,
				  stroke_width=white_w, stroke_fill=white_color)

		if rotate_deg != 0:
			layer = layer.rotate(rotate_deg, resample=PILImage.BICUBIC, expand=True)
		return self._harden_layer(layer, white_color)

	def _render_main_char(self, char, font, fill, stroke, stroke_w, rotate_deg=0):
		try:
			bbox = font.getbbox(char)
		except Exception:
			bbox = (0, 0, font.size, font.size)

		left, top, right, bottom = bbox
		char_w = max(1, right - left)
		char_h = max(1, bottom - top)

		margin = stroke_w + 4
		w = char_w + margin * 2
		h = char_h + margin * 2
		if w * h > 100_000_000:
			logger.warning(f"字符图层尺寸异常: {w}x{h}, 跳过 {char!r}")
			return PILImage.new("RGBA", (1, 1), (0, 0, 0, 0))

		layer = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
		draw = ImageDraw.Draw(layer)
		x = margin - left
		y = margin - top
		if stroke and stroke_w > 0:
			draw.text((x, y), char, font=font, fill=fill,
					  stroke_width=stroke_w, stroke_fill=stroke)
		else:
			draw.text((x, y), char, font=font, fill=fill)

		if rotate_deg != 0:
			layer = layer.rotate(rotate_deg, resample=PILImage.BICUBIC, expand=True)
		return layer

	def _layout_straight(self, text, font, cx, cy, base_rotate, spacing):
		n = len(text)
		if n == 0:
			return []

		widths = []
		total_w = 0
		for char in text:
			bbox = font.getbbox(char)
			w = bbox[2] - bbox[0]
			widths.append(w)
			total_w += w
		total_w += spacing * (n - 1)

		base_rot_rad = math.radians(base_rotate)
		cos_br = math.cos(base_rot_rad)
		sin_br = math.sin(base_rot_rad)

		x_accum = -total_w / 2
		items = []
		for i, char in enumerate(text):
			rel_x = x_accum + widths[i] / 2
			rel_y = 0
			rot_x = rel_x * cos_br + rel_y * sin_br
			rot_y = -rel_x * sin_br + rel_y * cos_br
			items.append((char, cx + rot_x, cy + rot_y, base_rotate))
			x_accum += widths[i] + spacing
		return items

	def _layout_curve(self, text, font, cx, cy, radius_px, curve_percent, distribution,
					  spacing, base_rotate):
		n = len(text)
		if n == 0 or radius_px <= 0 or curve_percent <= 0:
			return []
		if curve_percent > 100:
			curve_percent = 100

		char_widths = [max(1, font.getbbox(c)[2] - font.getbbox(c)[0]) for c in text]

		base_rot_rad = math.radians(base_rotate)
		cos_br = math.cos(base_rot_rad)
		sin_br = math.sin(base_rot_rad)

		if distribution:
			total_angle = 2 * math.pi * (curve_percent / 100)
			angle_per_char = total_angle / n
			start_angle = math.pi / 2 + total_angle / 2
			thetas = [start_angle - (i + 0.5) * angle_per_char for i in range(n)]
		else:
			char_angles = [w / radius_px for w in char_widths]
			spacing_angle = spacing / radius_px if n > 1 else 0.0
			total_angle = sum(char_angles) + spacing_angle * (n - 1)
			start_angle = math.pi / 2 + total_angle / 2
			thetas = []
			current = start_angle
			for i, angle in enumerate(char_angles):
				thetas.append(current - angle / 2)
				current -= angle
				if i < n - 1:
					current -= spacing_angle

		items = []
		for i, char in enumerate(text):
			theta = thetas[i]
			dx = radius_px * math.cos(theta)
			dy = -radius_px * math.sin(theta)
			rot_dx = dx * cos_br + dy * sin_br
			rot_dy = -dx * sin_br + dy * cos_br
			rotate_deg = math.degrees(theta) - 90 + base_rotate
			items.append((char, cx + rot_dx, cy + rot_dy, rotate_deg))
		return items

	def _prepare_segment(self, text, attrs, canvas_size):
		if not text:
			return None

		font_name = attrs.get("font") or self.default_font_name
		font_path = self._resolve_font_path(font_name)
		if not font_path or not os.path.exists(font_path):
			logger.error(f"字体不可用: {font_name}")
			return None

		point_scaled = max(1, int(attrs.get("size", 45) * (canvas_size[0] / 296)))
		try:
			font = self._get_font(font_path, point_scaled)
		except Exception as e:
			logger.error(f"加载字体失败 {font_path}: {e}")
			return None

		fill = self._parse_color(attrs.get("color", "#FFFFFF"))
		stroke_c = attrs.get("stroke")
		stroke = self._parse_color(stroke_c) if stroke_c else None

		white_enabled = bool(attrs.get("white", True))
		white_color = self._parse_color(attrs.get("white_color", "#FFFFFF"))
		white_size = float(attrs.get("white_size", 10))
		white_w = int(white_size * canvas_size[0] / 296) if white_enabled and white_size > 0 else 0

		stroke_size = float(attrs.get("stroke_size", 3))
		stroke_w = int(stroke_size * canvas_size[0] / 296) if stroke_size > 0 else 0

		spacing = int(float(attrs.get("spacing", 0)) * canvas_size[0] / 296)

		x_val = float(attrs.get("x", 50))
		y_val = float(attrs.get("y", 50))
		cx = int(canvas_size[0] * x_val / 100)
		base_rotate = float(attrs.get("rotate", 0))

		try:
			curve_pct = float(attrs.get("curve", 0))
		except (ValueError, TypeError):
			curve_pct = 0

		if curve_pct > 0:
			radius_pct = float(attrs.get("radius", 100))
			user_radius_px = radius_pct / 100 * canvas_size[0]

			char_widths = [max(1, font.getbbox(c)[2] - font.getbbox(c)[0]) for c in text]
			total_w = sum(char_widths) + spacing * (len(text) - 1) if text else 0

			fraction = min(curve_pct, 100) / 100
			if fraction > 0 and total_w > 0:
				auto_radius = total_w / (2 * math.pi * fraction)
			else:
				auto_radius = user_radius_px
			effective_radius = min(user_radius_px, auto_radius)

			y_offset_pct = effective_radius / canvas_size[1] * 100
			y_center_pct = y_val - y_offset_pct
			cy_center = int(canvas_size[1] * (100 - y_center_pct) / 100)

			items = self._layout_curve(
				text, font, cx, cy_center, effective_radius, curve_pct,
				bool(attrs.get("distribution", False)), spacing, base_rotate
			)
		else:
			cy = int(canvas_size[1] * (100 - y_val) / 100)
			items = self._layout_straight(text, font, cx, cy, base_rotate, spacing)

		if not items:
			return None
		return items, font, fill, stroke, white_w, white_color, stroke_w

	def _render_prepared(self, white_layer, main_layer, prepared):
		items, font, fill, stroke, white_w, white_color, stroke_w = prepared
		for char, cx, cy, rotate_deg in items:
			if white_w > 0:
				char_layer = self._render_white_char(char, font, white_w, white_color, rotate_deg)
				w, h = char_layer.size
				white_layer.paste(char_layer, (int(cx - w / 2), int(cy - h / 2)), char_layer)

			char_layer = self._render_main_char(char, font, fill, stroke, stroke_w, rotate_deg)
			w, h = char_layer.size
			main_layer.paste(char_layer, (int(cx - w / 2), int(cy - h / 2)), char_layer)

	def _render_v2(self, character: str, raw_text: str, role_config: dict) -> PILImage.Image:
		FINAL_SIZE = (800, 800)
		SSAA = 2
		CANVAS_SIZE = (FINAL_SIZE[0] * SSAA, FINAL_SIZE[1] * SSAA)

		base_defaults = self._build_defaults(role_config)

		char_path = os.path.join(self.resource_dir, f"{character.lower()}.png")
		if not os.path.exists(char_path):
			raise FileNotFoundError(f"角色图片 {char_path} 不存在")

		with PILImage.open(char_path) as ci:
			char_img = ci.convert("RGBA")
		char_img = char_img.resize(CANVAS_SIZE, PILImage.LANCZOS)

		segments = self._parse_text_to_segments(raw_text, base_defaults) if raw_text else []
		png_bg = role_config.get("png_bg", self.GLOBAL_DEFAULTS.get("png_bg", True))
		if segments:
			png_bg = segments[0]["attrs"].get("png_bg", png_bg)

		canvas = PILImage.new(
			"RGBA", CANVAS_SIZE,
			(0, 0, 0, 0) if png_bg else (255, 255, 255, 255)
		)
		canvas.paste(char_img, (0, 0), char_img)

		if segments:
			white_layer = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
			main_layer = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))

			for seg in segments:
				try:
					prepared = self._prepare_segment(seg["text"], seg["attrs"], CANVAS_SIZE)
					if prepared:
						self._render_prepared(white_layer, main_layer, prepared)
				except Exception as e:
					logger.exception(f"渲染段落失败: {seg['text']!r}, {e}")

			canvas.alpha_composite(white_layer)
			canvas.alpha_composite(main_layer)

		if SSAA > 1:
			canvas = canvas.resize(FINAL_SIZE, PILImage.LANCZOS)
		return canvas
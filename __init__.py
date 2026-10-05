import json
import os
import tempfile
import threading

from PIL import Image as PILImage
from PIL import ImageColor,ImageFont

from astrbot.api import logger

def init_plugin(plugin, context, config):
	plugin.context = context
	plugin.plugin_config = config or {}

	plugin_dir = os.path.dirname(os.path.abspath(__file__))
	data_dir = os.path.dirname(os.path.dirname(plugin_dir))
	astrbot_root = os.path.dirname(data_dir)

	plugin.resource_dir = os.path.join(plugin_dir, "resources")
	plugin.fonts_dir = os.path.join(plugin_dir, "fonts")
	plugin.illustration_dir = os.path.join(astrbot_root, "imgs", "default")

	for d in (plugin.resource_dir, plugin.fonts_dir, plugin.illustration_dir):
		os.makedirs(d, exist_ok=True)

	logger.info(f"配置路径: {getattr(plugin.plugin_config, 'config_path', '<未知>')}")

	_setup_characters(plugin)
	_setup_fonts(plugin)

	render_mode = "new" if get_config(plugin, "new_render", False) else "legacy"
	logger.info(
		f"arcaeaStickers 插件 v0.√3 加载, 渲染器 = {render_mode},"
		f"可用角色: {', '.join(plugin.available_characters)}"
	)

def _setup_characters(plugin):
	plugin.excludes_files = {"1ASL.png"}
	plugin.character_defaults = _load_character_defaults()
	plugin.available_characters = _scan_characters(plugin)

	plugin.CHARACTER_ALIASES = {}
	for eng, cfg in plugin.character_defaults.items():
		plugin.CHARACTER_ALIASES[eng] = eng
		for alias in cfg.get("_name", []):
			low = alias.lower()
			if low in plugin.CHARACTER_ALIASES:
				logger.warning(
					f"别名冲突: {alias} 已在 {plugin.CHARACTER_ALIASES[low]} 中定义"
				)
				continue
			plugin.CHARACTER_ALIASES[low] = eng

	for eng in plugin.available_characters:
		plugin.CHARACTER_ALIASES.setdefault(eng, eng)

def _setup_fonts(plugin):
	plugin.fonts = {}
	for f in os.listdir(plugin.fonts_dir):
		if f.lower().endswith((".ttf", ".otf")):
			plugin.fonts[os.path.splitext(f)[0]] = os.path.join(plugin.fonts_dir, f)

	if plugin.fonts:
		logger.info(f"已加载字体: {', '.join(sorted(plugin.fonts.keys()))}")
	else:
		logger.warning("fonts 文件夹中未找到字体文件")

	if "YurukaFangTang" in plugin.fonts:
		plugin.default_font_name = "YurukaFangTang"
	elif plugin.fonts:
		plugin.default_font_name = sorted(plugin.fonts.keys())[0]
		logger.warning(f"未找到 YurukaFangTang,默认字体改用 {plugin.default_font_name}")
	else:
		plugin.default_font_name = None

	if plugin.default_font_name:
		plugin.advanced_font_path = plugin.fonts[plugin.default_font_name]
	else:
		fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
		plugin.advanced_font_path = fallback if os.path.exists(fallback) else None
		if plugin.advanced_font_path:
			logger.info(f"使用系统字体: {plugin.advanced_font_path}")
		else:
			logger.error("未找到任何可用字体")

	plugin._font_cache = {}

def _load_character_defaults() -> dict:
	defaults_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "characters_defaults.json")
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

def _scan_characters(plugin) -> list:
	if not os.path.exists(plugin.resource_dir):
		return []
	return [
		f[:-4] for f in os.listdir(plugin.resource_dir)
		if f.lower().endswith(".png") and f not in plugin.excludes_files
	]

def get_config(plugin, key, default=None):
	if key in plugin.plugin_config:
		return plugin.plugin_config[key]
	return default

def get_output_size(plugin) -> int:
	raw = get_config(plugin, "output_size", 800)
	try:
		size = int(raw)
	except (ValueError, TypeError):
		size = 800
	return max(64, min(size, 800))

def get_ssaa(plugin) -> int:
	raw = get_config(plugin, "ssaa", 2)
	try:
		ssaa = int(raw)
	except (ValueError, TypeError):
		ssaa = 2
	return max(1, min(ssaa, 32))

def resolve_character(plugin, name: str):
	key = name.lower()
	if key in plugin.available_characters:
		return key
	if key in plugin.CHARACTER_ALIASES:
		mapped = plugin.CHARACTER_ALIASES[key]
		if mapped in plugin.available_characters:
			return mapped
	return None

def list_characters(plugin) -> str:
	cn_map = {}
	for alias, eng in plugin.CHARACTER_ALIASES.items():
		if not alias.isascii() and eng in plugin.available_characters:
			cn_map.setdefault(eng, []).append(alias)
	lines = ["可用角色列表:"]
	for eng in sorted(plugin.available_characters):
		cns = cn_map.get(eng, [])
		cn_str = "、".join(cns) if cns else "无中文别名"
		lines.append(f"{eng} ({cn_str})")
	return "\n".join(lines)

def split_args(raw: str) -> list:
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

def parse_attr_str(s: str) -> dict:
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
				attrs[key] = float(value)
			elif key in ("white", "distribution"):
				attrs[key] = value.lower() == "true"
			else:
				attrs[key] = value
		except ValueError:
			continue
	return attrs

def parse_color(c):
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

def resolve_font_path(plugin, font_name):
	if font_name and font_name in plugin.fonts:
		return plugin.fonts[font_name]
	if font_name and font_name != plugin.default_font_name:
		logger.warning(f"未知字体: {font_name}, 回退到 {plugin.default_font_name}")
	return plugin.advanced_font_path

def get_font(plugin, font_path, size):
	key = (font_path, size)
	font = plugin._font_cache.get(key)
	if font is None:
		font = ImageFont.truetype(font_path, size)
		plugin._font_cache[key] = font
	return font

_CHAR_IMG_CACHE_MAX = 4
_CHAR_IMG_CACHE_AREA = 1_200_000

def get_scaled_character(plugin, character: str, size: tuple):
	key = (character.lower(), size[0], size[1])
	cache = getattr(plugin, "_char_img_cache", None)
	if cache is None:
		cache = {}
		plugin._char_img_cache = cache

	img = cache.get(key)
	if img is not None:
		cache.pop(key)
		cache[key] = img
		return img

	char_path = os.path.join(plugin.resource_dir, f"{character.lower()}.png")
	if not os.path.exists(char_path):
		raise FileNotFoundError(f"角色图片 {char_path} 不存在")
	with PILImage.open(char_path) as ci:
		src = ci.convert("RGBA")
	img = src.resize(size, PILImage.LANCZOS)

	if size[0] * size[1] <= _CHAR_IMG_CACHE_AREA:
		cache[key] = img
		while len(cache) > _CHAR_IMG_CACHE_MAX:
			cache.pop(next(iter(cache)))
	return img

def maybe_compress(plugin, img_path: str, temp_files: list) -> str:
	if not get_config(plugin, "compress_ill", False):
		return img_path

	ext = os.path.splitext(img_path)[1].lower()
	if ext == ".gif":
		return img_path

	try:
		target = int(get_config(plugin, "compress_target", 1080))
	except (ValueError, TypeError):
		target = 1080

	direction = get_config(plugin, "target_towards", "longest")
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

def schedule_temp_cleanup(paths: list, delay: float = 5.0):
	for path in paths:
		def _rm(p=path):
			try:
				if os.path.exists(p):
					os.remove(p)
			except OSError:
				pass
		threading.Timer(delay, _rm).start()

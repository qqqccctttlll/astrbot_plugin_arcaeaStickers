import os
import math

from PIL import Image as PILImage
from PIL import ImageDraw

from astrbot.api import logger

from . import parse_color, resolve_font_path, get_font, get_output_size, get_ssaa

_CHAR_CACHE_MAX = 2048
_HARDEN_LUT = [0] + [255] * 255

def _harden_layer(layer, color):
	a = layer.getchannel("A").point(_HARDEN_LUT)
	solid = PILImage.new("RGBA", layer.size, color)
	solid.putalpha(a)
	return solid

def _get_char_cache(plugin):
	if not hasattr(plugin, "_char_render_cache"):
		plugin._char_render_cache = {}
	return plugin._char_render_cache

def _cached_char(plugin, key, render_fn):
	cache = _get_char_cache(plugin)
	img = cache.get(key)
	if img is not None:
		return img
	img = render_fn()
	if len(cache) >= _CHAR_CACHE_MAX:
		for k in list(cache)[: _CHAR_CACHE_MAX // 2]:
			del cache[k]
	cache[key] = img
	return img

class ParseError(ValueError):
	"""富文本语法错误。"""

def _render_white_char(char, font, white_w, white_color, rotate_deg=0):
	try:
		bbox = font.getbbox(char)
	except Exception:
		bbox = (0, 0, font.size, font.size)

	left, top, right, bottom = bbox
	char_w = max(1, right - left)

	ascent, descent = font.getmetrics()
	line_h = ascent + descent

	margin = white_w + 4
	w = char_w + margin * 2
	h = line_h + margin * 2
	if w * h > 100_000_000:
		logger.warning(f"白底图层尺寸异常: {w}x{h}, 跳过 {char!r}")
		return PILImage.new("RGBA", (1, 1), (0, 0, 0, 0))

	layer = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
	draw = ImageDraw.Draw(layer)

	draw.text(
		(margin, margin + ascent), char, font=font,
		fill=white_color, anchor="ls",
		stroke_width=white_w, stroke_fill=white_color
	)

	if rotate_deg != 0:
		layer = layer.rotate(rotate_deg, resample=PILImage.BICUBIC, expand=True)
	return _harden_layer(layer, white_color)

def _render_main_char(char, font, fill, stroke, stroke_w, rotate_deg=0):
	try:
		bbox = font.getbbox(char)
	except Exception:
		bbox = (0, 0, font.size, font.size)

	left, top, right, bottom = bbox
	char_w = max(1, right - left)

	ascent, descent = font.getmetrics()
	line_h = ascent + descent

	margin = stroke_w + 4
	w = char_w + margin * 2
	h = line_h + margin * 2
	if w * h > 100_000_000:
		logger.warning(f"字符图层尺寸异常: {w}x{h}, 跳过 {char!r}")
		return PILImage.new("RGBA", (1, 1), (0, 0, 0, 0))

	layer = PILImage.new("RGBA", (w, h), (0, 0, 0, 0))
	draw = ImageDraw.Draw(layer)

	x = margin
	y = margin + ascent
	if stroke and stroke_w > 0:
		draw.text(
			(x, y), char, font=font, fill=fill, anchor="ls",
			stroke_width=stroke_w, stroke_fill=stroke
		)
	else:
		draw.text((x, y), char, font=font, fill=fill, anchor="ls")

	if rotate_deg != 0:
		layer = layer.rotate(rotate_deg, resample=PILImage.BICUBIC, expand=True)
	return layer

def _layout_straight(text, font, cx, cy, base_rotate, spacing):
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

def _layout_curve(
	text, font, cx, cy, radius_px, curve_percent, distribution,
	spacing, base_rotate
):
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

def _parse_attr_value_new(key, value):
	if key == "rotate":
		return float(value)
	if key in ("curve", "radius"):
		try:
			return float(value)
		except ValueError:
			if key == "curve":
				return 100.0 if value.lower() == "true" else 0.0
			return 100.0
	if key in ("x", "y"):
		return float(value)
	if key in ("size", "white_size", "stroke_size", "spacing"):
		return int(float(value))
	if key in ("white", "distribution"):
		return value.lower() == "true"
	return value

def parse_attr_str_new(s):
	attrs = {}
	for pair in s.split(","):
		pair = pair.strip()
		if not pair:
			continue
		if "+=" in pair:
			key, value = pair.split("+=", 1)
			op = "inc"
		elif "-=" in pair:
			key, value = pair.split("-=", 1)
			op = "dec"
		elif "=" in pair:
			key, value = pair.split("=", 1)
			op = "set"
		else:
			continue
		key = key.strip().lower()
		value = value.strip()
		if not key:
			continue
		try:
			parsed = _parse_attr_value_new(key, value)
		except (ValueError, TypeError):
			continue
		if op == "set":
			attrs[key] = parsed
		else:
			attrs[key] = (op, parsed)
	return attrs

def merge_attrs(parent, own):
	result = dict(parent)
	for k, v in own.items():
		if isinstance(v, tuple) and len(v) == 2 and v[0] in ("inc", "dec"):
			base = result.get(k)
			if isinstance(base, bool) or not isinstance(base, (int, float)):
				raise ParseError(f"参数 {k} 不支持 += / -= (当前值不是数字)")
			delta = v[1]
			result[k] = base + delta if v[0] == "inc" else base - delta
		else:
			result[k] = v
	return result

def is_block(own_attrs):
	return "x" in own_attrs or "y" in own_attrs or "curve" in own_attrs

class Cursor:
	__slots__ = ("x", "y", "root_x", "root_y")

	def __init__(self, x, y, root_x=None, root_y=None):
		self.x = x
		self.y = y
		self.root_x = root_x if root_x is not None else x
		self.root_y = root_y if root_y is not None else y

	def reset_to_root(self):
		self.x = self.root_x
		self.y = self.root_y

	def copy(self):
		return Cursor(self.x, self.y, self.root_x, self.root_y)

def _format_unclosed_stack(stack):
	parts = []
	for node in stack[1:]:
		attrs = node.get("attrs") or {}
		if not attrs:
			parts.append("[]")
			continue
		pairs = []
		for k, v in attrs.items():
			if isinstance(v, tuple) and len(v) == 2 and v[0] in ("inc", "dec"):
				op = "+=" if v[0] == "inc" else "-="
				pairs.append(f"{k}{op}{v[1]}")
			else:
				pairs.append(f"{k}={v}")
		parts.append("[" + ",".join(pairs) + "]")
	return " -> ".join(parts)

def _restore_escapes(node, pl, pr):
	for i, c in enumerate(node["children"]):
		if isinstance(c, str):
			node["children"][i] = c.replace(pl, "[").replace(pr, "]")
		elif c.get("type") == "reset":
			continue
		else:
			_restore_escapes(c, pl, pr)

def parse_new_syntax(raw_text):
	PLACE_L = "\x00L\x00"
	PLACE_R = "\x00R\x00"
	escaped = raw_text.replace("\\[", PLACE_L).replace("\\]", PLACE_R)

	root = {"attrs": {}, "children": []}
	stack = [root]
	buf = []
	i = 0
	n = len(escaped)
	has_close = "[/]" in escaped or "$$$" in escaped

	def flush():
		if buf:
			stack[-1]["children"].append("".join(buf))
			buf.clear()

	while i < n:
		if escaped[i:i+3] == "$$$":
			flush()
			stack[-1]["children"].append({"type": "reset", "attrs": {}, "children": []})
			stack = [root]
			i += 3
			continue
		ch = escaped[i]
		if ch == "[":
			end = escaped.find("]", i)
			if end == -1:
				raise ParseError("错误的标签: [ 缺少对应的 ]")
			head = escaped[i+1:end]
			if head == "/":
				if len(stack) <= 1:
					raise ParseError("存在无匹配的 [/]")
				flush()
				stack.pop()
			else:
				flush()
				attrs = parse_attr_str_new(head) if head.strip() else {}
				node = {"attrs": attrs, "children": []}
				stack[-1]["children"].append(node)
				stack.append(node)
			i = end + 1
			continue
		buf.append(ch)
		i += 1

	flush()
	if len(stack) > 1:
		if has_close:
			raise ParseError(f"未闭合的标签: {_format_unclosed_stack(stack)}")
		stack = [root]

	_restore_escapes(root, PLACE_L, PLACE_R)
	return root

def _collect_text(node):
	parts = []
	for c in node["children"]:
		if isinstance(c, str):
			parts.append(c)
		elif c.get("type") == "reset":
			continue
		else:
			parts.append(_collect_text(c))
	return "".join(parts)

def _extract_style(plugin, attrs, canvas_size):
	font_name = attrs.get("font") or plugin.default_font_name
	font_path = resolve_font_path(plugin, font_name)
	if not font_path or not os.path.exists(font_path):
		logger.error(f"字体不可用: {font_name}")
		return None

	point_scaled = max(1, int(attrs.get("size", 15) * (canvas_size[0] / 100)))
	try:
		font = get_font(plugin, font_path, point_scaled)
	except Exception as e:
		logger.error(f"字体加载失败 {font_path}: {e}")
		return None

	fill = parse_color(attrs.get("color", "#FFFFFF"))
	stroke_c = attrs.get("stroke")
	stroke = parse_color(stroke_c) if stroke_c else None

	white_color = parse_color(attrs.get("white_color", "#FFFFFF"))
	white_size = float(attrs.get("white_size", 3.5))
	white_w = int(white_size * canvas_size[0] / 100) if white_size > 0 else 0

	stroke_size = float(attrs.get("stroke_size", 1))
	stroke_w = int(stroke_size * canvas_size[0] / 100) if stroke_size > 0 else 0

	spacing = int(float(attrs.get("spacing", 2)) * canvas_size[0] / 100)
	base_rotate = float(attrs.get("rotate", 0))
	font_key = (font_path, point_scaled)
	return font, fill, stroke, white_w, white_color, stroke_w, spacing, base_rotate, font_key

def _blit_items(
	plugin, items, font, fill, stroke, white_w, white_color,
	stroke_w, font_key, white_layer, main_layer
):
	for char, cx, cy, rot in items:
		rot_q = int(round(rot)) % 360
		if white_w > 0:
			key = ("w", char, font_key, white_w, white_color, rot_q)
			layer = _cached_char(
				plugin, key,
				lambda c=char, r=rot: _render_white_char(c, font, white_w, white_color, r),
			)
			w, h = layer.size
			white_layer.paste(layer, (int(cx - w / 2), int(cy - h / 2)), layer)
		key = ("m", char, font_key, fill, stroke, stroke_w, rot_q)
		layer = _cached_char(
			plugin, key,
			lambda c=char, r=rot: _render_main_char(c, font, fill, stroke, stroke_w, r),
		)
		w, h = layer.size
		main_layer.paste(layer, (int(cx - w / 2), int(cy - h / 2)), layer)

def _measure_inline_advance(plugin, node, effective_attrs, canvas_size):
	style = _extract_style(plugin, effective_attrs, canvas_size)
	if style is None:
		return 0.0, 0.0
	font = style[0]
	spacing = style[6]
	base_rotate = style[7]

	theta = math.radians(base_rotate)
	cos_t = math.cos(theta)
	sin_t = math.sin(theta)

	dx_total = 0.0
	dy_total = 0.0

	for child in node["children"]:
		if isinstance(child, str):
			if not child:
				continue
			seg_w = 0
			for ch in child:
				bbox = font.getbbox(ch)
				seg_w += bbox[2] - bbox[0]
			if len(child) > 1:
				seg_w += spacing * (len(child) - 1)
			advance = seg_w + spacing
			dx_total += advance * cos_t
			dy_total -= advance * sin_t
		elif child.get("type") == "reset":
			continue
		else:
			child_own = child.get("attrs") or {}
			if is_block(child_own):
				continue
			child_effective = merge_attrs(effective_attrs, child_own) if child_own else effective_attrs
			sub_dx, sub_dy = _measure_inline_advance(plugin, child, child_effective, canvas_size)
			dx_total += sub_dx
			dy_total += sub_dy

	return dx_total, dy_total

def _render_straight_text(plugin, text, attrs, cursor, canvas_size, white_layer, main_layer):
	if not text:
		return
	style = _extract_style(plugin, attrs, canvas_size)
	if style is None:
		return
	font, fill, stroke, white_w, white_color, stroke_w, spacing, base_rotate, font_key = style

	widths = []
	total_w = 0
	for ch in text:
		bbox = font.getbbox(ch)
		w = bbox[2] - bbox[0]
		widths.append(w)
		total_w += w
	if len(text) > 1:
		total_w += spacing * (len(text) - 1)

	theta = math.radians(base_rotate)
	cos_t = math.cos(theta)
	sin_t = math.sin(theta)

	cx_center = cursor.x + (total_w / 2) * cos_t
	cy_center = cursor.y - (total_w / 2) * sin_t

	items = _layout_straight(text, font, cx_center, cy_center, base_rotate, spacing)
	_blit_items(
		plugin, items, font, fill, stroke, white_w, white_color,
		stroke_w, font_key, white_layer, main_layer
	)

	advance = total_w + spacing
	cursor.x += advance * cos_t
	cursor.y -= advance * sin_t

def _measure_curve_width(plugin, node, effective_attrs, canvas_size):
	style = _extract_style(plugin, effective_attrs, canvas_size)
	if style is None:
		return 0.0
	font = style[0]
	spacing = style[6]

	total = 0.0
	for child in node["children"]:
		if isinstance(child, str):
			if not child:
				continue
			seg_w = 0
			for ch in child:
				bbox = font.getbbox(ch)
				seg_w += bbox[2] - bbox[0]
			if len(child) > 1:
				seg_w += spacing * (len(child) - 1)
			total += seg_w + spacing
		elif child.get("type") == "reset":
			continue
		else:
			child_own = child.get("attrs") or {}
			if is_block(child_own):
				continue
			child_eff = merge_attrs(effective_attrs, child_own) if child_own else effective_attrs
			total += _measure_curve_width(plugin, child, child_eff, canvas_size)
	return total

def _render_curve_stream(
	plugin, node, effective_attrs, cx, cy, radius_px,
	start_theta, canvas_size, white_layer, main_layer
):
	style = _extract_style(plugin, effective_attrs, canvas_size)
	if style is None:
		return start_theta
	font, fill, stroke, white_w, white_color, stroke_w, spacing, base_rotate, font_key = style

	base_rot_rad = math.radians(base_rotate)
	cos_br = math.cos(base_rot_rad)
	sin_br = math.sin(base_rot_rad)

	theta = start_theta
	items = []

	for child in node["children"]:
		if isinstance(child, str):
			if not child:
				continue
			for ch in child:
				bbox = font.getbbox(ch)
				w = max(1, bbox[2] - bbox[0])
				w_angle = w / radius_px
				center_theta = theta - w_angle / 2

				dx = radius_px * math.cos(center_theta)
				dy = -radius_px * math.sin(center_theta)
				rot_dx = dx * cos_br + dy * sin_br
				rot_dy = -dx * sin_br + dy * cos_br
				rotate_deg = math.degrees(center_theta) - 90 + base_rotate

				items.append((ch, cx + rot_dx, cy + rot_dy, rotate_deg))
				theta -= w_angle
				theta -= spacing / radius_px
		elif child.get("type") == "reset":
			continue
		else:
			child_own = child.get("attrs") or {}
			if is_block(child_own):
				if items:
					_blit_items(
						plugin, items, font, fill, stroke, white_w, white_color,
						stroke_w, font_key, white_layer, main_layer
					)
					items = []
				dummy_cursor = Cursor(cx, cy, cx, cy)
				_render_node(
					plugin, child, effective_attrs, dummy_cursor,
					canvas_size, white_layer, main_layer
				)
			else:
				child_eff = merge_attrs(effective_attrs, child_own) if child_own else effective_attrs
				if items:
					_blit_items(
						plugin, items, font, fill, stroke, white_w, white_color,
						stroke_w, font_key, white_layer, main_layer
					)
					items = []
				theta = _render_curve_stream(
					plugin, child, child_eff, cx, cy, radius_px,
					theta, canvas_size, white_layer, main_layer
				)

	if items:
		_blit_items(
			plugin, items, font, fill, stroke, white_w, white_color,
			stroke_w, font_key, white_layer, main_layer
		)
	return theta

def _render_curve_text(plugin, node, attrs, cursor, canvas_size, white_layer, main_layer):
	try:
		curve_pct = float(attrs.get("curve", 0))
	except (ValueError, TypeError):
		curve_pct = 0
	if curve_pct <= 0:
		text = _collect_text(node)
		_render_straight_text(plugin, text, attrs, cursor, canvas_size, white_layer, main_layer)
		return

	radius_pct = float(attrs.get("radius", 100))
	distribution = bool(attrs.get("distribution", False))

	if distribution:
		text = _collect_text(node)
		if not text:
			return
		style = _extract_style(plugin, attrs, canvas_size)
		if style is None:
			return
		font, fill, stroke, white_w, white_color, stroke_w, spacing, base_rotate, font_key = style

		user_radius_px = radius_pct / 100 * canvas_size[0]
		char_widths = [max(1, font.getbbox(c)[2] - font.getbbox(c)[0]) for c in text]
		total_w = sum(char_widths) + spacing * (len(text) - 1)
		fraction = min(curve_pct, 100) / 100
		auto_radius = total_w / (2 * math.pi * fraction) if fraction > 0 and total_w > 0 else user_radius_px
		effective_radius = min(user_radius_px, auto_radius)

		cx = cursor.x
		cy_center = cursor.y + effective_radius

		items = _layout_curve(
			text, font, cx, cy_center, effective_radius, curve_pct,
			True, spacing, base_rotate
		)
		_blit_items(
			plugin, items, font, fill, stroke, white_w, white_color,
			stroke_w, font_key, white_layer, main_layer
		)
		return

	total_w = _measure_curve_width(plugin, node, attrs, canvas_size)

	user_radius_px = radius_pct / 100 * canvas_size[0]
	if total_w > 0:
		fraction = min(curve_pct, 100) / 100
		auto_radius = total_w / (2 * math.pi * fraction) if fraction > 0 else user_radius_px
		effective_radius = min(user_radius_px, auto_radius)
		total_angle = total_w / effective_radius
	else:
		effective_radius = user_radius_px
		total_angle = 0.0

	cx_center = cursor.x
	cy_center = cursor.y + effective_radius
	start_theta = math.pi / 2 + total_angle / 2

	_render_curve_stream(
		plugin, node, attrs, cx_center, cy_center, effective_radius,
		start_theta, canvas_size, white_layer, main_layer
	)

def _render_node(plugin, node, parent_attrs, cursor, canvas_size, white_layer, main_layer):
	own = node.get("attrs") or {}
	effective = merge_attrs(parent_attrs, own)

	if is_block(own):
		cx = effective.get("x", 50) * canvas_size[0] / 100
		cy = (100 - effective.get("y", 70)) * canvas_size[1] / 100

		try:
			has_curve = float(effective.get("curve", 0)) > 0
		except (ValueError, TypeError):
			has_curve = False

		if has_curve:
			local = Cursor(cx, cy, cursor.root_x, cursor.root_y)
			_render_curve_text(
				plugin, node, effective, local,
				canvas_size, white_layer, main_layer
			)
		else:
			dx_total, dy_total = _measure_inline_advance(plugin, node, effective, canvas_size)
			start_x = cx - dx_total / 2
			start_y = cy - dy_total / 2
			local = Cursor(start_x, start_y, cursor.root_x, cursor.root_y)
			_render_children_block(
				plugin, node, effective, local,
				canvas_size, white_layer, main_layer
			)
	else:
		_render_children_inline(
			plugin, node, effective, cursor,
			canvas_size, white_layer, main_layer
		)

def _render_children_block(plugin, node, attrs, cursor, canvas_size, white_layer, main_layer):
	for child in node["children"]:
		if isinstance(child, str):
			_render_straight_text(
				plugin, child, attrs, cursor,
				canvas_size, white_layer, main_layer
			)
		elif child.get("type") == "reset":
			cursor.reset_to_root()
		else:
			_render_node(
				plugin, child, attrs, cursor,
				canvas_size, white_layer, main_layer
			)

def _render_children_inline(plugin, node, attrs, cursor, canvas_size, white_layer, main_layer):
	for child in node["children"]:
		if isinstance(child, str):
			_render_straight_text(
				plugin, child, attrs, cursor,
				canvas_size, white_layer, main_layer
			)
		elif child.get("type") == "reset":
			cursor.reset_to_root()
		else:
			_render_node(
				plugin, child, attrs, cursor,
				canvas_size, white_layer, main_layer
			)

def new_render(plugin, character, raw_text, role_config):
	out_size = get_output_size(plugin)
	SSAA = get_ssaa(plugin)
	FINAL_SIZE = (out_size, out_size)
	CANVAS_SIZE = (out_size * SSAA, out_size * SSAA)

	base_defaults = dict(plugin.GLOBAL_DEFAULTS)
	base_defaults.pop("text", None)
	base_defaults.update({k: v for k, v in role_config.items() if k != "text"})

	char_path = os.path.join(plugin.resource_dir, f"{character.lower()}.png")
	if not os.path.exists(char_path):
		raise FileNotFoundError(f"角色图片 {char_path} 不存在")

	with PILImage.open(char_path) as ci:
		char_img = ci.convert("RGBA")
	char_img = char_img.resize(CANVAS_SIZE, PILImage.LANCZOS)

	png_bg = role_config.get("png_bg", plugin.GLOBAL_DEFAULTS.get("png_bg", True))
	canvas = PILImage.new(
		"RGBA", CANVAS_SIZE,
		(0, 0, 0, 0) if png_bg else (255, 255, 255, 255)
	)
	canvas.paste(char_img, (0, 0), char_img)

	if not raw_text:
		if SSAA > 1:
			canvas = canvas.reduce(SSAA)
		return canvas

	tree = parse_new_syntax(raw_text)

	white_layer = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
	main_layer = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))

	root_attrs = dict(base_defaults)

	root_cx = root_attrs.get("x", 50) * CANVAS_SIZE[0] / 100
	root_cy = (100 - root_attrs.get("y", 70)) * CANVAS_SIZE[1] / 100

	try:
		root_curve = float(root_attrs.get("curve", 0)) > 0
	except (ValueError, TypeError):
		root_curve = False

	if root_curve:
		root_start_x = root_cx
		root_start_y = root_cy
	else:
		dx_total, dy_total = _measure_inline_advance(plugin, tree, root_attrs, CANVAS_SIZE)
		root_start_x = root_cx - dx_total / 2
		root_start_y = root_cy - dy_total / 2

	cursor = Cursor(root_start_x, root_start_y, root_start_x, root_start_y)

	if root_curve:
		_render_curve_text(
			plugin, tree, root_attrs, cursor,
			CANVAS_SIZE, white_layer, main_layer
		)
	else:
		_render_children_block(
			plugin, tree, root_attrs, cursor,
			CANVAS_SIZE, white_layer, main_layer
		)

	canvas.alpha_composite(white_layer)
	canvas.alpha_composite(main_layer)

	if SSAA > 1:
		canvas = canvas.reduce(SSAA)
	return canvas
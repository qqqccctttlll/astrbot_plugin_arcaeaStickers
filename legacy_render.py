import os

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

from . import parse_attr_str, parse_color, get_output_size, resolve_font_path, get_scaled_character

def parse_legacy(plugin, raw_text: str, role_config: dict):
	text = raw_text
	attrs = {}

	if text.startswith("["):
		end = text.find("]")
		if end != -1:
			head = text[1:end]
			if "=" in head:
				attrs = parse_attr_str(head)
				text = text[end + 1:]

	text = text.replace("\\[", "[").replace("\\]", "]")
	text = text.replace("\\n", "\n")

	merged = {**plugin.LEGACY_DEFAULTS, **role_config, **attrs}
	return text, merged

def legacy_render(plugin, character: str, raw_text: str, role_config: dict) -> PILImage.Image:
	text, attrs = parse_legacy(plugin, raw_text, role_config)

	size = get_output_size(plugin)
	CANVAS_SIZE = (size, size)
	SCALE = CANVAS_SIZE[0] / 100

	x_val = float(attrs.get("x", 50))
	y_val = float(attrs.get("y", 70))
	center_x = int(CANVAS_SIZE[0] * x_val / 100)
	center_y = int(CANVAS_SIZE[1] * (100 - y_val) / 100)
	point_scaled = max(1, int(float(attrs.get("size", 15)) * SCALE))
	leading_scaled = int(float(attrs.get("spacing", 2)) * SCALE)
	png_bg = bool(attrs.get("png_bg", True))
	color = attrs.get("color", "#FFFFFF")
	stroke = attrs.get("stroke", "#000000")
	rotate = float(attrs.get("rotate", 0))

	char_img = get_scaled_character(plugin, character, CANVAS_SIZE)

	canvas = PILImage.new(
		"RGBA", CANVAS_SIZE,
		(0, 0, 0, 0) if png_bg else (255, 255, 255, 255)
	)
	canvas.paste(char_img, (0, 0), char_img)

	if not text:
		return canvas

	txt_layer = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
	draw = ImageDraw.Draw(txt_layer)

	font_path = resolve_font_path(plugin, attrs.get("font") or plugin.default_font_name)
	if not font_path or not os.path.exists(font_path):
		fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
		if os.path.exists(fallback):
			font_path = fallback
		else:
			raise FileNotFoundError("未找到可用字体")
	font = ImageFont.truetype(font_path, point_scaled)

	fill_color = parse_color(color)
	stroke_color = parse_color(stroke)
	stroke_width = int(float(attrs.get("stroke_size", 1)) * SCALE)
	white_color = parse_color(attrs.get("white_color", "#FFFFFF"))
	white_stroke_width = int(float(attrs.get("white_size", 3.5)) * SCALE)

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
					  stroke_width=white_stroke_width, stroke_fill=white_color)
			y_temp += line_heights[idx] + leading_scaled

	y = center_y - total_height // 2
	for idx, line in enumerate(lines):
		bbox = font.getbbox(line)
		line_width = bbox[2] - bbox[0]
		x = center_x - line_width // 2
		if stroke_color and stroke_width > 0:
			draw.text(
				(x, y), line, font=font, fill=fill_color,
				stroke_width=stroke_width, stroke_fill=stroke_color
			)
		else:
			draw.text((x, y), line, font=font, fill=fill_color)
		y += line_heights[idx] + leading_scaled

	if rotate != 0:
		box = txt_layer.getbbox()
		if box:
			rotated = txt_layer.crop(box).rotate(rotate, expand=True, resample=PILImage.BICUBIC)
			cx = (box[0] + box[2]) / 2
			cy = (box[1] + box[3]) / 2
			final_txt = PILImage.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
			final_txt.paste(
				rotated,
				(int(cx - rotated.width / 2), int(cy - rotated.height / 2)),
				rotated
			)
			txt_layer = final_txt

	return PILImage.alpha_composite(canvas, txt_layer)

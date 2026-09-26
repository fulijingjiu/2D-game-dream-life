extends Node2D

const FRAME_COUNT := 12
const FRAME_RATE := 12.0
const BASELINE_Y := 488.0
const PIXEL_SCALE := 3.0
const ROOT_Y := 162.0

var actor: AnimatedSprite2D
var message: Label
var key_art: Sprite2D

func _ready() -> void:
	var frames := SpriteFrames.new()
	frames.add_animation("slash")
	frames.set_animation_speed("slash", FRAME_RATE)
	frames.set_animation_loop("slash", false)
	for index in range(1, FRAME_COUNT + 1):
		var path := "res://frames/hero_slash_%02d.png" % index
		var texture := load(path) as Texture2D
		if texture == null:
			push_error("Missing revised hero frame: " + path)
			return
		frames.add_frame("slash", texture)

	actor = AnimatedSprite2D.new()
	actor.name = "HeroSlash"
	actor.sprite_frames = frames
	actor.animation = "slash"
	# 128x170 native pixel art is enlarged with nearest-neighbor at an exact 3x.
	# Its ground anchor is row 162, which lands on viewport y=488.
	actor.position = Vector2(320.0, BASELINE_Y - ((ROOT_Y - 170.0 / 2.0) * PIXEL_SCALE))
	actor.centered = true
	actor.scale = Vector2(PIXEL_SCALE, PIXEL_SCALE)
	actor.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	add_child(actor)
	actor.play("slash")

	# High-detail pixel key art is a separate pose study; it stays out of the
	# uniform 128x170 animation strip until it is redrawn to the strip's pixel grid.
	key_art = Sprite2D.new()
	key_art.name = "SlashKeyArt"
	key_art.texture = load("res://keyframes/hero_slash_hit_study.png") as Texture2D
	key_art.position = Vector2(320.0, 244.0)
	key_art.scale = Vector2(0.35, 0.35)
	key_art.centered = true
	key_art.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	key_art.visible = false
	add_child(key_art)

	var title := Label.new()
	title.text = "HERO / ART PASS 02"
	title.position = Vector2(26, 20)
	title.add_theme_font_size_override("font_size", 18)
	title.add_theme_color_override("font_color", Color("#e4ded1"))
	add_child(title)

	message = Label.new()
	message.text = "12-frame slash  ·  12 fps  ·  SPACE replay  ·  K key-art study"
	message.position = Vector2(26, 505)
	message.add_theme_font_size_override("font_size", 13)
	message.add_theme_color_override("font_color", Color("#aeb5c2"))
	add_child(message)

func _draw() -> void:
	# Quiet studio backdrop keeps the silhouette, red scarf and warm hardware readable.
	draw_rect(Rect2(Vector2.ZERO, Vector2(640, 540)), Color("#0e1118"), true)
	draw_rect(Rect2(Vector2(26, 57), Vector2(588, 430)), Color("#171c26"), true)
	draw_line(Vector2(26, BASELINE_Y), Vector2(614, BASELINE_Y), Color("#38404d"), 1.0)
	for x in range(26, 615, 48):
		draw_line(Vector2(x, BASELINE_Y-4), Vector2(x, BASELINE_Y+4), Color("#303744"), 1.0)

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_SPACE:
			key_art.visible = false
			actor.visible = true
			actor.play("slash")
		elif event.keycode == KEY_K:
			key_art.visible = not key_art.visible
			actor.visible = not key_art.visible

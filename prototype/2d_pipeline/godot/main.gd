extends Node2D

const FRAME_COUNT := 12
const FRAME_RATE := 12.0

var actor: AnimatedSprite2D

func _ready() -> void:
	var frames := SpriteFrames.new()
	frames.add_animation("slash")
	frames.set_animation_speed("slash", FRAME_RATE)
	frames.set_animation_loop("slash", false)
	for index in range(1, FRAME_COUNT + 1):
		var texture := load("res://frames/frame_%02d.png" % index) as Texture2D
		if texture == null:
			push_error("Missing Blender export: frame_%02d.png" % index)
			return
		frames.add_frame("slash", texture)

	actor = AnimatedSprite2D.new()
	actor.name = "RenderedActionFrames"
	actor.sprite_frames = frames
	actor.animation = "slash"
	actor.position = Vector2(320, 290)
	actor.scale = Vector2(1.0, 1.0)
	add_child(actor)
	actor.play()

	var title := Label.new()
	title.text = "Blender rig → 12 transparent PNG frames → Godot playback"
	title.position = Vector2(24, 18)
	add_child(title)

	var note := Label.new()
	note.text = "Prototype only • 12 fps • press Space to replay the slash"
	note.position = Vector2(24, 492)
	add_child(note)

func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_SPACE:
		actor.play("slash")

extends Node2D

## 薄场景：地面、提示、以及 --m1-check 合同。
## 打开：prototype/2d_pipeline/v4/run_m1.sh
## 无头：prototype/2d_pipeline/v4/run_m1.sh --headless -- --m1-check

@onready var player = $Player
@onready var hud: Label = $Hud

var recent: Array[String] = []

func _ready() -> void:
	player.tut_run_started.connect(_note.bind("tut_run_started"))
	player.tut_jump_started.connect(_note.bind("tut_jump_started"))
	player.tut_fall_started.connect(_note.bind("tut_fall_started"))
	player.tut_landed.connect(_note.bind("tut_landed"))
	player.tut_slash_started.connect(_note.bind("tut_slash_started"))
	player.tut_dodge_ended.connect(_note.bind("tut_dodge_ended"))
	player.state_changed.connect(func(_previous, _current): _refresh_hud())
	_refresh_hud()
	if "--m1-check" in OS.get_cmdline_user_args():
		player.contract_mode = true
		var result: Dictionary = _run_contract()
		print(JSON.stringify(result))
		get_tree().quit(0 if (result.errors as Array).is_empty() else 1)

func _process(_delta: float) -> void:
	if player.contract_mode:
		return
	_refresh_hud()

func _draw() -> void:
	draw_rect(Rect2(0, 0, 960, 720), Color("#0e1420"))
	var ground := float(player.floor_y)
	draw_rect(Rect2(0, ground, 960, 720.0 - ground), Color("#18212f"))
	draw_line(Vector2(0, ground), Vector2(960, ground), Color("#485568"), 2)

func _note(signal_name: String) -> void:
	recent.append(signal_name)
	if recent.size() > 16:
		recent.pop_front()
	_refresh_hud()

func _refresh_hud() -> void:
	if hud == null or player == null:
		return
	hud.text = "M1 状态机骨架  %s\n信号 %s\n色块占位（不读旧弯刃 idle/slash）\nA/D 方向键移动  Space/K 跳  Shift/L 闪  J/Z 斩\n%s" % [
		player.state_name(),
		" ".join(recent),
		player.weapon_note(),
	]

func _run_contract() -> Dictionary:
	var errors: Array[String] = []
	var observed: Dictionary = {}
	recent.clear()
	_expect_clips(errors)
	observed["ground_chain"] = _check_ground_chain(errors)
	observed["hop"] = _check_hop(errors, 0.0, "idle")
	observed["hop_to_run"] = _check_hop(errors, 1.0, "run")
	observed["no_dodge_from_jump"] = _check_no_dodge_from_jump(errors)
	observed["air_dodge"] = _check_air_dodge(errors)
	observed["ground_dodge"] = _check_ground_dodge(errors)
	observed["dodge_drop"] = _check_dodge_drop(errors)
	observed["land_ignores_dodge"] = _check_land_ignores_dodge(errors)
	observed["slash"] = _check_slash(errors)
	observed["same_frame_priority"] = _check_same_frame_priority(errors)
	observed["walk_off"] = _check_walk_off(errors)
	return {
		"errors": errors,
		"observed": observed,
		"clips_loaded": _loaded_clip_names(),
		"placeholder_only": _loaded_clip_names().is_empty(),
		"slash_duration_ms": roundi(float(player.clip_duration("slash")) * 1000.0),
		"weapon_note": player.weapon_note(),
	}

func _loaded_clip_names() -> Array[String]:
	var names: Array[String] = []
	for clip_name in ["idle", "run", "jump", "fall", "land", "dodge", "slash"]:
		if player.has_real_clip(clip_name):
			names.append(clip_name)
	return names

func _expect_clips(errors: Array[String]) -> void:
	for clip_name in ["idle", "run", "jump", "fall", "land", "dodge", "slash"]:
		if player.has_real_clip(clip_name):
			errors.append("%s must stay a ColorRect until the form-locked re-export" % clip_name)
	var slash_ms: float = float(player.clip_duration("slash")) * 1000.0
	if slash_ms >= 600.0:
		errors.append("slash timing still matches the retired curved-blade clip (%s ms)" % slash_ms)

func _check_ground_chain(errors: Array[String]) -> Array:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 1.0, false, false, false)
	_expect(errors, player.state_name() == "run", "idle should enter run")
	player.debug_step(0.05, 1.0, false, false, false)
	_expect(errors, _count("tut_run_started") == 1, "holding run should emit tut_run_started once")
	player.debug_step(0.05, 0.0, false, false, false)
	_expect(errors, player.state_name() == "idle", "releasing direction should return to idle")
	player.debug_step(0.05, -1.0, false, false, false)
	_expect(errors, player.state_name() == "run", "opposite direction should enter run again")
	_expect(errors, _count("tut_run_started") == 2, "second run entry should emit again")
	return [player.state_name(), recent.duplicate()]

func _check_hop(errors: Array[String], land_move: float, expect_end: String) -> Array:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, true, false, false)
	_expect(errors, player.state_name() == "jump", "jump input should enter jump")
	_expect(errors, _count("tut_jump_started") == 1, "tut_jump_started")
	var guard := 0
	while player.state_name() == "jump" and guard < 80:
		player.debug_step(0.05, 0.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "fall", "jump should reach fall, got %s" % player.state_name())
	_expect(errors, _count("tut_fall_started") == 1, "tut_fall_started on apex")
	guard = 0
	while player.state_name() == "fall" and guard < 120:
		player.debug_step(0.05, land_move, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "land", "fall should land, got %s" % player.state_name())
	_expect(errors, _count("tut_landed") == 1, "tut_landed")
	guard = 0
	while player.state_name() == "land" and guard < 20:
		player.debug_step(0.05, land_move, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == expect_end, "land should end in %s, got %s" % [expect_end, player.state_name()])
	if expect_end == "run":
		_expect(errors, _count("tut_run_started") == 1, "land to run should emit tut_run_started")
	else:
		_expect(errors, _count("tut_run_started") == 0, "land to idle should not emit run")
	_expect(errors, _count("tut_dodge_ended") == 0, "hop should not emit dodge")
	return [player.state_name(), recent.duplicate()]

func _check_no_dodge_from_jump(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, true, true, false)
	# 同一帧闪优先，所以这里单独再开一次只按跳。
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, true, false, false)
	var guard := 0
	while player.state_name() == "jump" and guard < 80:
		player.debug_step(0.05, 0.0, false, true, false)
		guard += 1
	_expect(errors, player.state_name() == "fall", "dodge during jump should still reach fall, got %s" % player.state_name())
	_expect(errors, _count("tut_dodge_ended") == 0, "dodge during jump must not start a dodge")
	return player.state_name()

func _check_air_dodge(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, true, false, false)
	var guard := 0
	while player.state_name() == "jump" and guard < 80:
		player.debug_step(0.05, 0.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "fall", "air dodge setup should be in fall")
	player.debug_step(0.05, 0.0, false, true, false)
	_expect(errors, player.state_name() == "dodge", "fall should accept dodge, got %s" % player.state_name())
	_expect(errors, not player.on_floor, "air dodge should leave the floor")
	guard = 0
	while player.state_name() == "dodge" and guard < 40:
		player.debug_step(0.05, 0.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "fall", "airborne dodge should end in fall, got %s y=%s" % [player.state_name(), player.position.y])
	_expect(errors, _count("tut_dodge_ended") == 1, "air dodge should emit tut_dodge_ended once")
	var ended_at := recent.find("tut_dodge_ended")
	var fall_after := -1
	if ended_at >= 0:
		fall_after = recent.find("tut_fall_started", ended_at + 1)
	_expect(errors, ended_at >= 0 and fall_after > ended_at, "tut_dodge_ended should precede the following tut_fall_started")
	return player.state_name()

func _check_ground_dodge(errors: Array[String]) -> Array:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, false, true, false)
	_expect(errors, player.state_name() == "dodge", "idle should dodge")
	var guard := 0
	while player.state_name() == "dodge" and guard < 40:
		player.debug_step(0.05, 0.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "idle", "ground dodge without direction should end idle, got %s" % player.state_name())
	_expect(errors, _count("tut_dodge_ended") == 1, "ground dodge should emit tut_dodge_ended")
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 1.0, false, false, false)
	player.debug_step(0.05, 1.0, false, true, false)
	_expect(errors, player.state_name() == "dodge", "run should dodge")
	guard = 0
	while player.state_name() == "dodge" and guard < 40:
		player.debug_step(0.05, 1.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "run", "ground dodge with direction should end run, got %s" % player.state_name())
	return [player.state_name(), recent.duplicate()]

func _check_dodge_drop(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, false, true, false)
	player.floor_enabled = false
	player.debug_step(0.05, 0.0, false, false, false)
	_expect(errors, player.state_name() == "fall", "ground dodge losing floor should force fall, got %s" % player.state_name())
	_expect(errors, recent.size() >= 2 and recent[-2] == "tut_dodge_ended" and recent[-1] == "tut_fall_started", "forced fall should emit dodge end then fall start, got %s" % str(recent))
	return player.state_name()

func _check_land_ignores_dodge(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, true, false, false)
	var guard := 0
	while player.state_name() != "land" and guard < 160:
		player.debug_step(0.05, 0.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "land", "setup should reach land")
	player.debug_step(0.05, 0.0, true, true, true)
	player.debug_step(0.05, 1.0, true, true, true)
	_expect(errors, player.state_name() == "land", "land should ignore dodge jump and attack")
	_expect(errors, _count("tut_dodge_ended") == 0, "ignored dodge must not emit tut_dodge_ended")
	return player.state_name()

func _check_slash(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 1.0, false, false, false)
	player.debug_step(0.05, 1.0, false, false, true)
	_expect(errors, player.state_name() == "run", "attack from run should not slash")
	_expect(errors, _count("tut_slash_started") == 0, "run attack should not emit slash")
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 0.0, false, false, true)
	_expect(errors, player.state_name() == "slash", "idle attack should slash")
	_expect(errors, _count("tut_slash_started") == 1, "tut_slash_started")
	var guard := 0
	while player.state_name() == "slash" and guard < 40:
		player.debug_step(0.05, 0.0, false, false, false)
		guard += 1
	_expect(errors, player.state_name() == "idle", "slash should return to idle, got %s" % player.state_name())
	_expect(errors, guard >= 4 and guard < 20, "slash should use placeholder timing, ended in %s steps" % guard)
	return player.state_name()

func _check_same_frame_priority(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 1.0, true, true, true)
	_expect(errors, player.state_name() == "dodge", "same-frame dodge should beat jump and attack, got %s" % player.state_name())
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 1.0, true, false, true)
	_expect(errors, player.state_name() == "jump", "same-frame jump should beat attack, got %s" % player.state_name())
	return player.state_name()

func _check_walk_off(errors: Array[String]) -> String:
	player.debug_reset()
	recent.clear()
	player.debug_step(0.05, 1.0, false, false, false)
	player.floor_enabled = false
	player.debug_step(0.05, 1.0, false, false, false)
	_expect(errors, player.state_name() == "fall", "running off the floor should enter fall, got %s" % player.state_name())
	_expect(errors, _count("tut_fall_started") == 1, "walk-off should emit tut_fall_started")
	_expect(errors, _count("tut_jump_started") == 0, "walk-off is not a jump")
	return player.state_name()

func _count(signal_name: String) -> int:
	var total := 0
	for item in recent:
		if item == signal_name:
			total += 1
	return total

func _expect(errors: Array[String], condition: bool, message: String) -> void:
	if not condition:
		errors.append(message)

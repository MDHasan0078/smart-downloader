// Engine entry point: JSONL bridge between the desktop UI and the downloader.
//
// Reads one JSON command per line on stdin, writes one JSON event per line on
// stdout (reply / progress / finished). Line-buffered with flush, so a Dart or
// Python client can attach a subprocess and stream in both directions.
//
// Protocol mirrors the Python engine exactly:
//
// Commands (each with an "id" echoed back in the reply):
//
//	ping         -> {"pong": true}
//	check_deps   -> {"binaries": {...}, "missing": [...], "yt_dlp_version": str|""}
//	settings_get -> {"settings": {...}}
//	settings_set -> merge {"settings": {...}} into config.json
//	get_info     -> {"url": ...}
//	               video   : {"type":"video", "title", "size_str", "duration", "formats": [...]}
//	               playlist: {"type":"playlist", "title", "entries": [{"url","title","index"}]}
//	start        -> {"url", "mode", "video_format", "video_quality", "audio_format",
//	                 "audio_quality", "task_id"?}
//	               replies {"ok":true,"task_id":...} immediately, then streams
//	               "progress" and "finished" events.
//	pause/resume/cancel -> {"task_id": ...} -> {"ok": bool, "paused": bool}
//	restart      -> {"task_id": ...} -> new task, cancels old one
//
// Events (no "id", always include "event"):
//
//	reply    -> {id, ok, ...result}
//	progress -> {task_id, percent, size, speed, eta}
//	finished -> {task_id, success, message}
//	error    -> {message}

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sync"
)

type engine struct {
	settings  map[string]interface{}
	tasks     map[string]*taskEntry
	completed map[string]*taskEntry
	counter   int
	writeMu   sync.Mutex
}

type taskEntry struct {
	task     *DownloadTask
	config   map[string]interface{}
	finished *finishInfo
}

type finishInfo struct {
	success bool
	message string
}

func newEngine() *engine {
	return &engine{
		settings:  loadSettings(),
		tasks:     map[string]*taskEntry{},
		completed: map[string]*taskEntry{},
	}
}

// ---- protocol helpers ---------------------------------------------

func (e *engine) emit(eventType string, payload map[string]interface{}) {
	line := map[string]interface{}{"event": eventType}
	for k, v := range payload {
		line[k] = v
	}
	data, _ := json.Marshal(line)
	e.writeMu.Lock()
	_, _ = os.Stdout.Write(append(data, '\n'))
	e.writeMu.Unlock()
}

func (e *engine) reply(msg map[string]interface{}, ok bool, payload map[string]interface{}) {
	line := map[string]interface{}{
		"event": "reply",
		"id":    msg["id"],
		"ok":    ok,
	}
	for k, v := range payload {
		line[k] = v
	}
	data, _ := json.Marshal(line)
	e.writeMu.Lock()
	_, _ = os.Stdout.Write(append(data, '\n'))
	e.writeMu.Unlock()
}

func (e *engine) handle(msg map[string]interface{}) {
	cmd, _ := msg["cmd"].(string)
	var result map[string]interface{}
	var err error
	switch cmd {
	case "ping":
		result = map[string]interface{}{"pong": true}
	case "check_deps":
		result = e.cmdCheckDeps()
	case "settings_get":
		result = e.cmdSettingsGet()
	case "settings_set":
		result, err = e.cmdSettingsSet(msg)
	case "get_info":
		result, err = e.cmdGetInfo(msg)
	case "start":
		result, err = e.cmdStart(msg)
	case "restart":
		result, err = e.cmdRestart(msg)
	case "pause":
		result, err = e.ctrl(msg, "pause")
	case "resume":
		result, err = e.ctrl(msg, "resume")
	case "cancel":
		result, err = e.ctrl(msg, "cancel")
	default:
		e.reply(msg, false, map[string]interface{}{"error": "unknown command: " + cmd})
		return
	}
	if err != nil {
		e.reply(msg, false, map[string]interface{}{"error": err.Error()})
		return
	}
	e.reply(msg, true, result)
}

// ---- task plumbing -------------------------------------------------

func (e *engine) cookieFile() string {
	use, _ := e.settings["use_cookies"].(bool)
	file, _ := e.settings["cookies_file"].(string)
	if use && file != "" {
		return file
	}
	return ""
}

func (e *engine) buildTask(cfg map[string]interface{}) *DownloadTask {
	task := newDownloadTask(
		str(cfg["url"]),
		firstNonEmpty(cfg["download_dir"], e.settings["download_dir"]),
		firstNonEmpty(cfg["cookies_file"], e.cookieFile()),
	)
	task.mode = firstNonEmpty(cfg["mode"], "video")
	task.videoFormat = firstNonEmpty(cfg["video_format"], e.settings["default_video_format"])
	task.videoQuality = firstNonEmpty(cfg["video_quality"], e.settings["default_video_quality"])
	task.audioFormat = firstNonEmpty(cfg["audio_format"], e.settings["default_audio_format"])
	task.audioQuality = firstNonEmpty(cfg["audio_quality"], e.settings["default_audio_quality"])
	return task
}

func (e *engine) spawnTask(taskID string, task *DownloadTask, cfg map[string]interface{}) {
	e.tasks[taskID] = &taskEntry{task: task, config: cfg}
	go e.runTask(taskID)
}

func (e *engine) runTask(taskID string) {
	entry, ok := e.tasks[taskID]
	if !ok {
		return
	}
	task := entry.task
	outcome := finishInfo{}

	task.start(
		func(p Progress) {
			e.emit("progress", map[string]interface{}{
				"task_id": taskID,
				"percent": p.Percent,
				"size":    p.Size,
				"speed":   p.Speed,
				"eta":     p.ETA,
			})
		},
		func(success bool, message string) {
			outcome = finishInfo{success: success, message: message}
			e.emit("finished", map[string]interface{}{
				"task_id": taskID,
				"success": success,
				"message": message,
			})
		},
	)
	e.tasks[taskID] = nil
	delete(e.tasks, taskID)
	e.completed[taskID] = &taskEntry{config: entry.config, finished: &outcome}
}

// ---- commands ------------------------------------------------------

func (e *engine) cmdCheckDeps() map[string]interface{} {
	return map[string]interface{}{
		"binaries":       checkAll(),
		"missing":        missingBinaries(),
		"yt_dlp_version": getYtDlpVersion(),
	}
}

func (e *engine) cmdSettingsGet() map[string]interface{} {
	return map[string]interface{}{"settings": e.settings}
}

func (e *engine) cmdSettingsSet(msg map[string]interface{}) (map[string]interface{}, error) {
	patch, _ := msg["settings"].(map[string]interface{})
	if patch == nil {
		return nil, fmt.Errorf("'settings' must be a dict")
	}
	for k, v := range patch {
		e.settings[k] = v
	}
	sanitizeSettings(e.settings)
	if err := saveSettings(e.settings); err != nil {
		return nil, err
	}
	return map[string]interface{}{"settings": e.settings}, nil
}

func (e *engine) cmdGetInfo(msg map[string]interface{}) (map[string]interface{}, error) {
	url, _ := msg["url"].(string)
	if url == "" {
		return nil, fmt.Errorf("'url' is required")
	}
	task := e.buildTask(map[string]interface{}{"url": url, "mode": "video"})
	if err := task.probe(); err != nil {
		return nil, err
	}
	if task.playlist {
		entries := make([]interface{}, 0, len(task.entries))
		for i, en := range task.entries {
			entries = append(entries, map[string]interface{}{
				"index": i,
				"url":   en.URL,
				"title": en.Title,
			})
		}
		return map[string]interface{}{
			"type":    "playlist",
			"title":   task.title,
			"entries": entries,
		}, nil
	}
	formats, duration := fetchVideoInfo(url, task.cookieArgs())
	return map[string]interface{}{
		"type":     "video",
		"title":    task.title,
		"size_str": task.sizeStr,
		"duration": duration,
		"formats":  formats,
	}, nil
}

func (e *engine) cmdStart(msg map[string]interface{}) (map[string]interface{}, error) {
	url, _ := msg["url"].(string)
	if url == "" {
		return nil, fmt.Errorf("'url' is required")
	}
	cfg := map[string]interface{}{}
	for _, k := range []string{
		"url", "mode", "video_format", "video_quality",
		"audio_format", "audio_quality", "download_dir", "cookies_file",
	} {
		if v, ok := msg[k]; ok {
			cfg[k] = v
		}
	}
	task := e.buildTask(cfg)
	e.counter++
	taskID := fmt.Sprintf("t%d", e.counter)
	if id, ok := msg["task_id"].(string); ok && id != "" {
		taskID = id
	}
	e.spawnTask(taskID, task, cfg)
	return map[string]interface{}{"task_id": taskID}, nil
}

func (e *engine) cmdRestart(msg map[string]interface{}) (map[string]interface{}, error) {
	taskID, _ := msg["task_id"].(string)
	entry := e.tasks[taskID]
	if entry == nil {
		entry = e.completed[taskID]
	}
	if entry == nil {
		return nil, fmt.Errorf("unknown task: %s", taskID)
	}
	if running := e.tasks[taskID]; running != nil {
		running.task.cancel()
	}
	task := e.buildTask(entry.config)
	e.spawnTask(taskID, task, entry.config)
	return map[string]interface{}{"task_id": taskID, "restarted": true}, nil
}

func (e *engine) ctrl(msg map[string]interface{}, action string) (map[string]interface{}, error) {
	taskID, _ := msg["task_id"].(string)
	entry := e.tasks[taskID]
	if entry == nil {
		return nil, fmt.Errorf("unknown task: %s", taskID)
	}
	task := entry.task
	switch action {
	case "pause":
		return map[string]interface{}{"task_id": taskID, "paused": task.pause()}, nil
	case "resume":
		resumed := task.resume()
		return map[string]interface{}{
			"task_id": taskID,
			"paused":  task.paused,
			"resumed": resumed,
		}, nil
	default:
		task.cancel()
		return map[string]interface{}{"task_id": taskID, "cancelled": true}, nil
	}
}

// ---- helpers -------------------------------------------------------

func str(v interface{}) string {
	s, _ := v.(string)
	return s
}

func firstNonEmpty(v interface{}, def interface{}) string {
	if s, ok := v.(string); ok && s != "" {
		return s
	}
	if d, ok := def.(string); ok {
		return d
	}
	return ""
}

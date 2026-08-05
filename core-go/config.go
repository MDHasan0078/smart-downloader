// Persistent settings for the downloader engine (cross-platform).
//
// Same flat-dict + load/save design as the Python engine's config.py. The
// config directory resolves per-platform:
//
//	Windows: %APPDATA%/simple-yt-downloader
//	macOS:   ~/Library/Application Support/simple-yt-downloader
//	Linux:   ~/.config/simple-yt-downloader

package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
)

var configDir = func() string {
	home, _ := os.UserHomeDir()
	switch runtime.GOOS {
	case "windows":
		base := os.Getenv("APPDATA")
		if base == "" {
			base = home
		}
		return filepath.Join(base, "simple-yt-downloader")
	case "darwin":
		return filepath.Join(home, "Library", "Application Support", "simple-yt-downloader")
	default:
		return filepath.Join(home, ".config", "simple-yt-downloader")
	}
}()

var configFile = filepath.Join(configDir, "config.json")

var defaults = map[string]interface{}{
	"cookies_file":          "",
	"use_cookies":           false,
	"download_dir":          mustDownloadDir(),
	"default_video_format":  "mp4",
	"default_video_quality": "720",
	"default_audio_format":  "mp3",
	"default_audio_quality": "192",
	"theme":                 "dark",
	"first_run_done":        false,
}

func mustDownloadDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "Downloads")
}

// loadSettings returns saved settings merged over defaults (missing keys
// filled in), sanitized.
func loadSettings() map[string]interface{} {
	settings := map[string]interface{}{}
	for k, v := range defaults {
		settings[k] = v
	}
	if data, err := os.ReadFile(configFile); err == nil {
		var saved map[string]interface{}
		if json.Unmarshal(data, &saved) == nil && saved != nil {
			for k, v := range saved {
				settings[k] = v
			}
		}
	}
	sanitizeSettings(settings)
	return settings
}

func sanitizeSettings(s map[string]interface{}) {
	theme, _ := s["theme"].(string)
	if theme != "light" && theme != "dark" {
		s["theme"] = defaults["theme"]
	}
	dir, _ := s["download_dir"].(string)
	if dir == "" {
		s["download_dir"] = defaults["download_dir"]
	}
	for _, key := range []string{"use_cookies", "first_run_done"} {
		if _, ok := s[key].(bool); !ok {
			s[key] = defaults[key]
		}
	}
	for _, key := range []string{
		"cookies_file", "default_video_format", "default_video_quality",
		"default_audio_format", "default_audio_quality",
	} {
		if _, ok := s[key].(string); !ok {
			s[key] = defaults[key]
		}
	}
}

func saveSettings(s map[string]interface{}) error {
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(configFile, data, 0o644)
}

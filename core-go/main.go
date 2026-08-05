// Engine entry point for the JSONL protocol.
//
// Reads one JSON command per line on stdin, writes one JSON event per line on
// stdout. See engine.go for the protocol spec.

package main

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// init prepends the engine's own directory to PATH so the bundled
// yt-dlp/ffmpeg/ffprobe (installed next to engine(.exe)) resolve via the
// normal exec.LookPath lookup even though the installer never touches PATH.
func init() {
	exe, err := os.Executable()
	if err != nil {
		return
	}
	dir := filepath.Dir(exe)
	if dir == "" {
		return
	}
	current, sep := os.Getenv("PATH"), string(os.PathListSeparator)
	for _, part := range filepath.SplitList(current) {
		if filepath.Clean(part) == filepath.Clean(dir) {
			return
		}
	}
	if current == "" {
		_ = os.Setenv("PATH", dir)
	} else {
		_ = os.Setenv("PATH", dir+sep+current)
	}
}

func main() {
	engine := newEngine()
	scanner := bufio.NewScanner(os.Stdin)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		var msg map[string]interface{}
		if err := json.Unmarshal([]byte(line), &msg); err != nil {
			engine.emit("error", map[string]interface{}{"message": "invalid JSON on stdin"})
			continue
		}
		if msg == nil {
			engine.emit("error", map[string]interface{}{"message": "expected a JSON object per line"})
			continue
		}
		engine.handle(msg)
	}
}

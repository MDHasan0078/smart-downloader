// Wraps a single yt-dlp download as a controllable background task.
//
// Port of the Python engine's download_task.py. Design notes:
//   - Every network/subprocess call happens on a background goroutine started
//     by the caller.
//   - Pause/resume signals the whole process GROUP (not just yt-dlp itself),
//     since yt-dlp commonly spawns ffmpeg as a real child process (merging
//     streams, or as an external downloader for HLS/m3u8).
//   - Windows has no POSIX signal groups; stop/continue degrade to no-ops so
//     pause()/resume() report false gracefully there, and cancel uses Kill.

package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

var (
	progressRe = regexp.MustCompile(
		`\[download\]\s+(?P<percent>[\d.]+)%` +
			`(?:\s+of\s+~?(?P<size>[\d.]+\w+))?` +
			`(?:\s+at\s+(?P<speed>[\d.]+\w+/s|Unknown speed))?` +
			`(?:\s+ETA\s+(?P<eta>[\d:]+|Unknown))?`,
	)
	postprocessStartRe = regexp.MustCompile(`^\[(\w+)\]`)
)

var mergeLock sync.Mutex

const videoQualityTiers = "144,240,360,480,720,1080,1440,2160"

// DownloadTask is one video's worth of download state and control.
type DownloadTask struct {
	url         string
	downloadDir string
	cookiesFile string

	title    string
	sizeStr  string
	playlist bool
	entries  []PlaylistEntry

	mode         string // "video" | "audio"
	videoFormat  string
	videoQuality string
	audioFormat  string
	audioQuality string

	cmd       *exec.Cmd
	paused    bool
	cancelled bool
	logLines  []string
	gated     bool
	lockHeld  bool
	mu        sync.Mutex
}

type PlaylistEntry struct {
	URL   string `json:"url"`
	Title string `json:"title"`
}

func newDownloadTask(url, downloadDir, cookiesFile string) *DownloadTask {
	return &DownloadTask{
		url:          url,
		downloadDir:  downloadDir,
		cookiesFile:  cookiesFile,
		mode:         "video",
		videoFormat:  "mp4",
		videoQuality: "720",
		audioFormat:  "mp3",
		audioQuality: "192",
	}
}

// ---- Metadata / playlist detection ----------------------------------

func (t *DownloadTask) cookieArgs() []string {
	if t.cookiesFile != "" {
		if _, err := os.Stat(t.cookiesFile); err == nil {
			return []string{"--cookies", t.cookiesFile}
		}
	}
	return nil
}

func normalizeEntryURL(entry map[string]interface{}) string {
	url, _ := entry["url"].(string)
	if url == "" {
		url, _ = entry["webpage_url"].(string)
	}
	if strings.HasPrefix(url, "http") {
		return url
	}
	videoID, _ := entry["id"].(string)
	if videoID == "" {
		videoID = url
	}
	return "https://www.youtube.com/watch?v=" + videoID
}

// probe detects playlist vs single video and populates title/entries.
func (t *DownloadTask) probe() error {
	args := append(t.cookieArgs(), "--flat-playlist", "--dump-single-json", t.url)
	out, err := runWithTimeout("yt-dlp", 30*time.Second, args...)
	if err != nil {
		return err
	}
	var data map[string]interface{}
	if err := json.Unmarshal(out, &data); err != nil {
		return errors.New("Unexpected response from yt-dlp.")
	}

	entriesRaw, _ := data["entries"].([]interface{})
	if len(entriesRaw) > 1 {
		t.playlist = true
		t.title, _ = data["title"].(string)
		if t.title == "" {
			t.title = "Playlist"
		}
		for _, e := range entriesRaw {
			entry, _ := e.(map[string]interface{})
			title, _ := entry["title"].(string)
			if title == "" {
				title, _ = entry["id"].(string)
			}
			if title == "" {
				title = "Untitled"
			}
			t.entries = append(t.entries, PlaylistEntry{URL: normalizeEntryURL(entry), Title: title})
		}
		return nil
	}

	t.playlist = false
	if len(entriesRaw) == 1 {
		if single, ok := entriesRaw[0].(map[string]interface{}); ok {
			t.title, _ = single["title"].(string)
		}
	} else {
		t.title, _ = data["title"].(string)
	}
	if t.title == "" {
		t.title = "Untitled"
	}
	t.fetchSizeEstimate()
	return nil
}

func (t *DownloadTask) fetchSizeEstimate() {
	args := append(t.cookieArgs(), "-f", t.buildFormatString(),
		"--print", "%(filesize,filesize_approx)r", t.url)
	out, err := runWithTimeout("yt-dlp", 30*time.Second, args...)
	if err != nil {
		t.sizeStr = "Unknown size"
		return
	}
	var total float64
	for _, line := range strings.Split(string(out), "\n") {
		for _, tok := range strings.Fields(line) {
			if isNumeric(tok) {
				if f, err := strconv.ParseFloat(tok, 64); err == nil {
					total += f
				}
			}
		}
	}
	if total > 0 {
		t.sizeStr = strconv.FormatFloat(total/1024/1024, 'f', 1, 64) + " MB"
	} else {
		t.sizeStr = "Unknown size"
	}
}

func isNumeric(tok string) bool {
	tok = strings.ReplaceAll(tok, ".", "")
	return tok != "" && isAllDigits(tok)
}

func isAllDigits(s string) bool {
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

// ---- Format string building ------------------------------------------

func (t *DownloadTask) buildFormatString() string {
	if t.mode == "audio" {
		return "bestaudio"
	}
	res := t.videoQuality
	ext := t.videoFormat
	return "bestvideo[height<=" + res + "][ext=" + ext + "]+bestaudio/" +
		"bestvideo[height<=" + res + "]+bestaudio/best[height<=" + res + "]"
}

func (t *DownloadTask) buildPostprocessArgs() []string {
	if t.mode == "audio" {
		quality := t.audioQuality + "K"
		if t.audioQuality == "best" {
			quality = "0"
		}
		return []string{"-x", "--audio-format", t.audioFormat, "--audio-quality", quality}
	}
	return []string{"--merge-output-format", t.videoFormat}
}

// ---- Info helpers ----------------------------------------------------

func fetchVideoInfo(url string, cookieArgs []string) ([]interface{}, interface{}) {
	args := append(cookieArgs, "-j", "--no-playlist", url)
	out, err := runWithTimeout("yt-dlp", 30*time.Second, args...)
	if err != nil {
		return []interface{}{}, nil
	}
	line := firstLine(out)
	if line == "" {
		return []interface{}{}, nil
	}
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(line), &data); err != nil {
		return []interface{}{}, nil
	}
	formats, _ := data["formats"].([]interface{})
	if formats == nil {
		formats = []interface{}{}
	}
	return formats, data["duration"]
}

// ---- Download control ------------------------------------------------

// start spawns the yt-dlp subprocess and streams progress to callbacks.
// Both callbacks run on a background goroutine.
func (t *DownloadTask) start(onProgress func(Progress), onFinished func(bool, string)) {
	t.paused = false
	t.cancelled = false
	t.logLines = nil
	t.gated = false
	t.lockHeld = false

	_ = os.MkdirAll(t.downloadDir, 0o755)

	args := []string{}
	args = append(args, t.cookieArgs()...)
	args = append(args, "-f", t.buildFormatString())
	args = append(args, t.buildPostprocessArgs()...)
	args = append(args, "--newline",
		"-o", filepath.Join(t.downloadDir, "%(title)s.%(ext)s"),
		t.url)

	cmd := exec.Command("yt-dlp", args...)
	configureProcessGroup(cmd)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		onFinished(false, "Could not start yt-dlp.")
		return
	}
	cmd.Stderr = cmd.Stdout

	if err := cmd.Start(); err != nil {
		if errors.Is(err, exec.ErrNotFound) {
			onFinished(false, "yt-dlp is not installed.")
		} else {
			onFinished(false, "Could not start yt-dlp: "+err.Error())
		}
		return
	}
	t.cmd = cmd

	scanner := bufio.NewScanner(stdout)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		t.logLines = append(t.logLines, line)

		if m := progressRe.FindStringSubmatch(line); m != nil {
			percent, _ := strconv.ParseFloat(m[1], 64)
			size := m[2]
			if size == "" {
				size = t.sizeStr
			}
			onProgress(Progress{
				Percent: percent,
				Size:    size,
				Speed:   m[3],
				ETA:     m[4],
			})
			continue
		}
		t.maybeGatePostprocessing(line)
	}

	_ = cmd.Wait()
	t.releaseMergeLockIfHeld()

	if t.cancelled {
		onFinished(false, "Cancelled")
	} else if cmd.ProcessState != nil && cmd.ProcessState.ExitCode() == 0 {
		onFinished(true, "Done")
	} else {
		tail := strings.Join(lastN(t.logLines, 5), "\n")
		if tail == "" {
			tail = "Download failed."
		}
		onFinished(false, tail)
	}
}

// maybeGatePostprocessing SIGSTOPs the process group when yt-dlp hands off
// to ffmpeg, serializing only the CPU-bound merge phase behind a global lock.
func (t *DownloadTask) maybeGatePostprocessing(line string) {
	if t.gated {
		return
	}
	m := postprocessStartRe.FindStringSubmatch(line)
	if m == nil || strings.ToLower(m[1]) == "download" {
		return
	}
	t.gated = true
	if stopProcessGroup(t.cmd) {
		mergeLock.Lock()
		t.lockHeld = true
		if !t.paused {
			continueProcessGroup(t.cmd)
		}
	}
}

func (t *DownloadTask) releaseMergeLockIfHeld() {
	if t.lockHeld {
		t.lockHeld = false
		mergeLock.Unlock()
	}
}

func (t *DownloadTask) pause() bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.cmd != nil && !t.paused {
		if stopProcessGroup(t.cmd) {
			t.paused = true
			return true
		}
	}
	return false
}

func (t *DownloadTask) resume() bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.cmd != nil && t.paused {
		if continueProcessGroup(t.cmd) {
			t.paused = false
			return true
		}
	}
	return false
}

func (t *DownloadTask) cancel() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.cancelled = true
	if t.cmd != nil {
		terminateProcessGroup(t.cmd)
	}
}

// Progress is one yt-dlp progress callback payload.
type Progress struct {
	Percent float64
	Size    string
	Speed   string
	ETA     string
}

// ---- helpers ---------------------------------------------------------

func runWithTimeout(bin string, timeout time.Duration, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, bin, args...)
	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}
	return out, nil
}

func firstLine(b []byte) string {
	for _, line := range strings.Split(string(b), "\n") {
		if strings.TrimSpace(line) != "" {
			return line
		}
	}
	return ""
}

func lastN(s []string, n int) []string {
	if len(s) <= n {
		return s
	}
	return s[len(s)-n:]
}

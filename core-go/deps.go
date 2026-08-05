// Dependency detection for the downloader engine (cross-platform).
//
// yt-dlp and ffmpeg/ffprobe are the external binaries the engine shells out
// to at runtime. On desktop installs all three ship bundled next to the app;
// this module reports presence/version so the UI can guide the user.

package main

import (
	"os/exec"
	"strings"
)

var checkedBinaries = []string{"yt-dlp", "ffmpeg", "ffprobe"}

// checkBinary returns the resolved path if found on PATH, else "".
func checkBinary(name string) string {
	path, err := exec.LookPath(name)
	if err != nil {
		return ""
	}
	return path
}

// checkAll returns {binary_name: path_or_""} for every externally-shelled-out
// binary.
func checkAll() map[string]interface{} {
	res := map[string]interface{}{}
	for _, name := range checkedBinaries {
		res[name] = checkBinary(name)
	}
	return res
}

func missingBinaries() []string {
	missing := make([]string, 0)
	for _, name := range checkedBinaries {
		if checkBinary(name) == "" {
			missing = append(missing, name)
		}
	}
	return missing
}

// getYtDlpVersion returns the yt-dlp version string, or "" if unavailable.
func getYtDlpVersion() string {
	cmd := exec.Command("yt-dlp", "--version")
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(out))
}

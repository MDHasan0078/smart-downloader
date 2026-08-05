//go:build windows

package main

import (
	"os/exec"
)

func configureProcessGroup(cmd *exec.Cmd) {
	// No process groups on Windows; pause/resume degrade gracefully.
}

func stopProcessGroup(cmd *exec.Cmd) bool {
	return false
}

func continueProcessGroup(cmd *exec.Cmd) bool {
	return false
}

func terminateProcessGroup(cmd *exec.Cmd) {
	if cmd != nil && cmd.Process != nil {
		_ = cmd.Process.Kill()
	}
}

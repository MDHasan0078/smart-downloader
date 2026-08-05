//go:build !windows

package main

import (
	"os/exec"
	"syscall"
)

func configureProcessGroup(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
}

func signalGroup(cmd *exec.Cmd, sig syscall.Signal) bool {
	if cmd == nil || cmd.Process == nil {
		return false
	}
	if err := syscall.Kill(-cmd.Process.Pid, sig); err == nil {
		return true
	}
	if err := cmd.Process.Signal(sig); err == nil {
		return true
	}
	return false
}

func stopProcessGroup(cmd *exec.Cmd) bool {
	return signalGroup(cmd, syscall.SIGSTOP)
}

func continueProcessGroup(cmd *exec.Cmd) bool {
	return signalGroup(cmd, syscall.SIGCONT)
}

func terminateProcessGroup(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	signalGroup(cmd, syscall.SIGCONT)
	signalGroup(cmd, syscall.SIGTERM)
}

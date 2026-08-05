import 'dart:io';
import 'package:flutter/foundation.dart';

class EngineLocator {
  static String? _resolved;

  static String get engineDir {
    if (_resolved != null) return _resolved!;
    _resolved = _resolve();
    return _resolved!;
  }

  static String _resolve() {
    // Bundled with installer: <exe_dir>/engine/engine(.exe)
    if (!kIsWeb) {
      final exeDir = File(Platform.resolvedExecutable).parent.path;

      final bundledWindows = '$exeDir/engine/engine.exe';
      if (Platform.isWindows && File(bundledWindows).existsSync()) {
        return '$exeDir/engine';
      }

      final bundledLinux = '$exeDir/engine/engine';
      if (Platform.isLinux && File(bundledLinux).existsSync()) {
        return '$exeDir/engine';
      }

      // macOS: .app/Contents/Resources/engine/engine
      if (Platform.isMacOS) {
        final resourceDir = '$exeDir/../Resources';
        final bundledMac = '$resourceDir/engine/engine';
        if (File(bundledMac).existsSync()) {
          return '$resourceDir/engine';
        }
      }
    }

    // Development: look for the engine in the repo
    final cwd = Directory.current.path;
    final devPaths = [
      '$cwd/../core/build/dist/engine',
      '$cwd/core/build/dist/engine',
    ];
    for (final p in devPaths) {
      if (File('$p/engine${Platform.isWindows ? '.exe' : ''}').existsSync()) {
        return p;
      }
    }

    throw Exception(
      'Engine binary not found. Build it first:\n'
      '  cd core-go && go build -o ../core/build/dist/engine/engine${Platform.isWindows ? '.exe' : ''} .',
    );
  }
}

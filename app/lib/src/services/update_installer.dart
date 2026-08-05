import 'dart:io';

import 'update_checker.dart';

class UpdateInstallException implements Exception {
  UpdateInstallException(this.message);

  final String message;

  @override
  String toString() => message;
}

class UpdateInstaller {
  /// Streams [asset] to a fresh temp directory, reporting
  /// (received, total) via [onProgress] (total may be null when the server
  /// sends no Content-Length). Returns the downloaded file.
  static Future<File> download(
    UpdateAsset asset,
    void Function(int received, int? total) onProgress,
  ) async {
    final dir =
        await Directory.systemTemp.createTemp('smart-downloader-update');
    final file =
        File('${dir.path}${Platform.pathSeparator}${asset.name}');
    final client = HttpClient();
    try {
      final request = await client.getUrl(Uri.parse(asset.url));
      request.headers.set('User-Agent', 'smart-downloader');
      final response = await request.close();
      if (response.statusCode != 200) {
        throw UpdateInstallException(
            'Download failed (HTTP ${response.statusCode}).');
      }
      final total = response.contentLength;
      final sink = file.openWrite();
      var received = 0;
      try {
        await for (final chunk in response) {
          received += chunk.length;
          sink.add(chunk);
          onProgress(received, total);
        }
        await sink.flush();
      } finally {
        await sink.close();
      }
      return file;
    } finally {
      client.close();
    }
  }

  /// Windows: run the Inno Setup installer silently. It installs over the
  /// current version in place.
  static Future<ProcessResult> installWindows(File exe) async {
    return Process.run(exe.path, [
      '/VERYSILENT',
      '/SUPPRESSMSGBOXES',
      '/NORESTART',
      '/SP-',
    ]);
  }

  /// macOS: mount the .dmg, copy the .app bundle into /Applications using a
  /// native admin password prompt (osascript, mirroring Linux pkexec), then
  /// detach and clean up.
  ///
  /// If the admin approval is declined, the mounted volume is opened in
  /// Finder and UpdateInstallException is thrown with manual-drag
  /// instructions.
  static Future<void> installMacOS(File dmg) async {
    final mountDir =
        await Directory.systemTemp.createTemp('smart-downloader-dmg');
    try {
      final attach = await Process.run('hdiutil', [
        'attach',
        '-nobrowse',
        '-readonly',
        '-mountpoint',
        mountDir.path,
        dmg.path,
      ]);
      if (attach.exitCode != 0) {
        throw UpdateInstallException('Could not mount the disk image.');
      }

      String? appName;
      await for (final entry in mountDir.list()) {
        if (entry.path.endsWith('.app')) {
          appName = entry.path.split(Platform.pathSeparator).last;
          break;
        }
      }
      if (appName == null) {
        throw UpdateInstallException('No app found in the disk image.');
      }

      final escapedApp = appName.replaceAll('"', r'\"');
      final script = 'do shell script '
          '"ditto \\"$escapedApp\\" \\"/Applications/\\"" '
          'with administrator privileges';
      final copy = await Process.run('osascript', ['-e', script]);
      if (copy.exitCode != 0) {
        await Process.run('open', [mountDir.path]);
        throw UpdateInstallException(
          'Admin approval was not granted. The disk image has been opened '
          'in Finder — drag "$appName" into Applications.',
        );
      }
    } finally {
      await Process.run('hdiutil', ['detach', mountDir.path]);
      try {
        await mountDir.delete(recursive: true);
      } catch (_) {}
    }
  }

  /// Best-effort removal of the downloaded file and its temp directory.
  static Future<void> cleanup(File file) async {
    try {
      final dir = file.parent;
      if (await dir.exists()) {
        await dir.delete(recursive: true);
      }
    } catch (_) {}
  }
}

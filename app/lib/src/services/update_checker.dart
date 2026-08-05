import 'dart:convert';
import 'dart:io';

class UpdateInfo {
  const UpdateInfo({
    required this.latestVersion,
    required this.releaseUrl,
    required this.assetNames,
  });

  final String latestVersion;
  final String releaseUrl;
  final List<String> assetNames;

  bool isNewerThan(String current) {
    final cur = current.split('.').map((s) => int.tryParse(s) ?? 0).toList();
    final latest =
        latestVersion.split('.').map((s) => int.tryParse(s) ?? 0).toList();
    for (var i = 0; i < latest.length || i < cur.length; i++) {
      final a = i < latest.length ? latest[i] : 0;
      final b = i < cur.length ? cur[i] : 0;
      if (a != b) return a > b;
    }
    return false;
  }
}

class UpdateChecker {
  static const _repo = 'MDHasan0078/simple-yt-downloader';

  Future<UpdateInfo?> checkForUpdate() async {
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 10);
    try {
      final request = await client.getUrl(
        Uri.parse('https://api.github.com/repos/$_repo/releases/latest'),
      );
      request.headers.set('User-Agent', 'smart-downloader');
      request.headers.set('Accept', 'application/vnd.github+json');
      final response = await request.close();
      if (response.statusCode != 200) return null;
      final body = await response.transform(utf8.decoder).join();
      final json = jsonDecode(body) as Map<String, dynamic>;
      final assets = ((json['assets'] as List?) ?? const [])
          .cast<Map<String, dynamic>>()
          .map((a) => a['name'] as String)
          .toList();
      return UpdateInfo(
        latestVersion:
            (json['tag_name'] as String).replaceFirst(RegExp(r'^v'), ''),
        releaseUrl: json['html_url'] as String,
        assetNames: assets,
      );
    } catch (_) {
      return null;
    } finally {
      client.close();
    }
  }

  static String installInstructions(String version) {
    switch (Platform.operatingSystem) {
      case 'windows':
        return 'Download SmartDownloader-$version-Setup.exe and run it.\n'
            'It installs over the current version silently.';
      case 'linux':
        return 'Download simple-yt-downloader_${version}_all.deb and run:\n'
            '    sudo dpkg -i simple-yt-downloader_${version}_all.deb';
      case 'macos':
        return 'Download SmartDownloader.dmg, open it, drag Smart Downloader '
            'into Applications, then eject the disk image.';
      default:
        return 'Download the latest release for your platform.';
    }
  }

  static void openReleasePage(String url) {
    final os = Platform.operatingSystem;
    if (os == 'windows') {
      Process.run('cmd', ['/c', 'start', '', url]);
    } else if (os == 'macos') {
      Process.run('open', [url]);
    } else {
      Process.run('xdg-open', [url]);
    }
  }
}

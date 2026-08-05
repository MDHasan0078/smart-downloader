import 'dart:convert';
import 'dart:io';

class UpdateAsset {
  const UpdateAsset({required this.name, required this.url});

  final String name;
  final String url;
}

class UpdateInfo {
  const UpdateInfo({
    required this.latestVersion,
    required this.releaseUrl,
    required this.assets,
  });

  final String latestVersion;
  final String releaseUrl;
  final List<UpdateAsset> assets;

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

  /// The best installer asset for the current platform.
  ///
  /// Prefers the versioned name when a platform ships one; otherwise falls
  /// back to the platform's file-extension pattern so unversioned assets
  /// (e.g. the macOS SmartDownloader.dmg) still resolve.
  ///
  /// [operatingSystem] overrides Platform.operatingSystem for testing.
  UpdateAsset? assetForPlatform({String? operatingSystem}) {
    final os = operatingSystem ?? Platform.operatingSystem;
    final versioned = <String>[];
    final patterns = <RegExp>[];
    switch (os) {
      case 'windows':
        versioned.add('SmartDownloader-$latestVersion-Setup.exe');
        patterns.add(RegExp(r'Setup\.exe$'));
      case 'macos':
        versioned.add('SmartDownloader.dmg');
        patterns.add(RegExp(r'\.dmg$'));
      case 'linux':
        versioned.add('simple-yt-downloader_${latestVersion}_all.deb');
        patterns.add(RegExp(r'_all\.deb$'));
      default:
        return null;
    }
    for (final asset in assets) {
      if (versioned.contains(asset.name)) return asset;
    }
    for (final pattern in patterns) {
      for (final asset in assets) {
        if (pattern.hasMatch(asset.name)) return asset;
      }
    }
    return null;
  }
}

class UpdateChecker {
  static const _repo = 'MDHasan0078/smart-downloader';

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
          .map((a) => UpdateAsset(
                name: a['name'] as String,
                url: a['browser_download_url'] as String,
              ))
          .toList();
      return UpdateInfo(
        latestVersion:
            (json['tag_name'] as String).replaceFirst(RegExp(r'^v'), ''),
        releaseUrl: json['html_url'] as String,
        assets: assets,
      );
    } catch (_) {
      return null;
    } finally {
      client.close();
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

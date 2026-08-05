import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

import 'package:smart_downloader/src/services/update_checker.dart';
import 'package:smart_downloader/src/services/update_installer.dart';

void main() {
  group('UpdateInfo.isNewerThan', () {
    UpdateInfo info(String v) => UpdateInfo(
          latestVersion: v,
          releaseUrl: 'https://example.com/release',
          assets: const [],
        );

    test('newer patch/major/minor', () {
      expect(info('2.1.0').isNewerThan('2.0.9'), isTrue);
      expect(info('3.0.0').isNewerThan('2.9.9'), isTrue);
      expect(info('2.10.0').isNewerThan('2.9.9'), isTrue);
    });

    test('equal or older', () {
      expect(info('2.1.0').isNewerThan('2.1.0'), isFalse);
      expect(info('2.0.9').isNewerThan('2.1.0'), isFalse);
    });

    test('different component counts', () {
      expect(info('2.1').isNewerThan('2.1.0'), isFalse);
      expect(info('2.1.1').isNewerThan('2.1'), isTrue);
    });
  });

  group('UpdateInfo.assetForPlatform', () {
    const assetUrl = 'https://github.com/x/y/releases/download/';

    UpdateInfo info(List<String> names) => UpdateInfo(
          latestVersion: '2.1.0',
          releaseUrl: 'https://example.com/release',
          assets: [
            for (final n in names) UpdateAsset(name: n, url: assetUrl + n),
          ],
        );

    test('windows picks versioned Setup.exe', () {
      final i = info([
        'simple-yt-downloader_2.1.0_all.deb',
        'SmartDownloader.dmg',
        'SmartDownloader-2.1.0-Setup.exe',
      ]);
      final a = i.assetForPlatform(operatingSystem: 'windows')!;
      expect(a.name, 'SmartDownloader-2.1.0-Setup.exe');
      expect(a.url, assetUrl + a.name);
    });

    test('macos falls back to .dmg when unversioned', () {
      final i = info([
        'SmartDownloader-2.1.0-Setup.exe',
        'SmartDownloader.dmg',
        'simple-yt-downloader_2.1.0_all.deb',
      ]);
      final a = i.assetForPlatform(operatingSystem: 'macos')!;
      expect(a.name, 'SmartDownloader.dmg');
    });

    test('linux picks versioned .deb', () {
      final i = info([
        'SmartDownloader-2.1.0-Setup.exe',
        'SmartDownloader.dmg',
        'simple-yt-downloader_2.1.0_all.deb',
      ]);
      final a = i.assetForPlatform(operatingSystem: 'linux')!;
      expect(a.name, 'simple-yt-downloader_2.1.0_all.deb');
    });

    test('unknown platform returns null', () {
      expect(info(const []).assetForPlatform(operatingSystem: 'freebsd'), isNull);
    });

    test('no matching asset returns null', () {
      expect(info(const ['readme.txt']).assetForPlatform(operatingSystem: 'macos'),
          isNull);
    });
  });

  group('UpdateInstaller.download', () {
    test('streams with progress and writes the file', () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      final payload = List<int>.filled(300000, 0x41);
      server.listen((request) {
        request.response.headers.contentLength = payload.length;
        request.response.add(payload);
        request.response.close();
      });

      final updates = <(int, int?)>[];
      final asset = UpdateAsset(
        name: 'SmartDownloader-2.1.0-Setup.exe',
        url: 'http://127.0.0.1:${server.port}/x.exe',
      );
      final file = await UpdateInstaller.download(
          asset, (r, t) => updates.add((r, t)));
      addTearDown(() => UpdateInstaller.cleanup(file));

      expect(await file.length(), payload.length);
      expect(updates, isNotEmpty);
      expect(updates.last, (payload.length, payload.length));
      expect(file.parent.existsSync(), isTrue);
    });

    test('throws UpdateInstallException on HTTP error', () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      server.listen((request) {
        request.response.statusCode = HttpStatus.notFound;
        request.response.close();
      });

      final asset = UpdateAsset(
        name: 'SmartDownloader.dmg',
        url: 'http://127.0.0.1:${server.port}/missing.dmg',
      );
      expect(
        () => UpdateInstaller.download(asset, (_, _) {}),
        throwsA(isA<UpdateInstallException>()),
      );
    });
  });
}

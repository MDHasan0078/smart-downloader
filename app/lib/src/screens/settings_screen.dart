import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import '../engine/engine_provider.dart';
import '../services/update_checker.dart';
import '../services/update_installer.dart';
import '../theme/theme_controller.dart';

final Future<PackageInfo> _packageInfoFuture = PackageInfo.fromPlatform();

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      body: Consumer2<EngineProvider, ThemeController>(
        builder: (context, provider, themeController, child) {
          final config = provider.config;

          return ListView(
            padding: const EdgeInsets.all(24),
            children: [
              Row(
                children: [
                  SvgPicture.asset(
                    'lib/src/assets/icons/emblem-system-symbolic.svg',
                    width: 28,
                    height: 28,
                    colorFilter: ColorFilter.mode(
                      colorScheme.primary,
                      BlendMode.srcIn,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    'Settings',
                    style: theme.textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 24),

              // Engine Status
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(
                            provider.initialized
                                ? Icons.check_circle
                                : Icons.error,
                            color: provider.initialized
                                ? Colors.green
                                : colorScheme.error,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'Engine Status',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _buildInfoRow(
                        context,
                        icon: Icons.info_outline,
                        label: 'yt-dlp',
                        value: config.ytDlpVersion ?? 'Not detected',
                      ),
                      const SizedBox(height: 8),
                      _buildInfoRow(
                        context,
                        icon: Icons.info_outline,
                        label: 'ffmpeg',
                        value: config.ffmpegVersion ?? 'Not detected',
                      ),
                      if (provider.error != null)
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: colorScheme.errorContainer,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                Icons.warning,
                                color: colorScheme.onErrorContainer,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  provider.error!,
                                  style: TextStyle(
                                    color: colorScheme.onErrorContainer,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Download Settings
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Download Defaults',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 16),
                      _buildInfoRow(
                        context,
                        icon: Icons.folder,
                        label: 'Output Directory',
                        value: config.outputDir.isEmpty
                            ? 'Default (~/Downloads)'
                            : config.outputDir,
                        trailing: IconButton(
                          icon: const Icon(Icons.folder_open),
                          onPressed: () {},
                        ),
                      ),
                      const SizedBox(height: 12),
                      _buildInfoRow(
                        context,
                        icon: Icons.videocam,
                        label: 'Video Format',
                        value: config.format.toUpperCase(),
                      ),
                      const SizedBox(height: 12),
                      _buildInfoRow(
                        context,
                        icon: Icons.high_quality,
                        label: 'Video Quality',
                        value: config.quality,
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Appearance
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Appearance',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Dark Theme'),
                        subtitle: const Text(
                          'Default is dark. The app does not follow the system theme.',
                        ),
                        value: themeController.isDark,
                        onChanged: themeController.setDark,
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // About
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'About',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 16),
                      FutureBuilder<PackageInfo>(
                        future: _packageInfoFuture,
                        builder: (context, snapshot) {
                          // Never fall back to a hardcoded version -- it
                          // can drift from pubspec.yaml. PackageInfo only
                          // fails in exotic builds, so 'Unknown' is fine.
                          final version = snapshot.data?.version;
                          return _buildInfoRow(
                            context,
                            icon: Icons.apps,
                            label: 'Version',
                            value: version == null ? 'Unknown' : 'v$version',
                          );
                        },
                      ),
                      const SizedBox(height: 8),
                      _buildInfoRow(
                        context,
                        icon: Icons.code,
                        label: 'Engine',
                        value: 'Go (native)',
                      ),
                      const SizedBox(height: 8),
                      Align(
                        alignment: Alignment.centerLeft,
                        child: FilledButton.tonalIcon(
                          onPressed: () => _checkForUpdates(context),
                          icon: const Icon(Icons.update),
                          label: const Text('Check for Updates'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // Reset button
              Center(
                child: OutlinedButton.icon(
                  onPressed: () {
                    // TODO: Implement reset settings
                  },
                  icon: const Icon(Icons.restore),
                  label: const Text('Reset to Defaults'),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _checkForUpdates(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(
      const SnackBar(content: Text('Checking for updates...')),
    );

    final PackageInfo current;
    try {
      current = await _packageInfoFuture;
    } catch (_) {
      return;
    }

    final update = await UpdateChecker().checkForUpdate();
    if (!context.mounted) return;

    if (update == null) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Could not reach the update server.')),
      );
      return;
    }

    if (!update.isNewerThan(current.version)) {
      messenger.showSnackBar(
        SnackBar(content: Text('You are up to date (v${current.version}).')),
      );
      return;
    }

    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Update available'),
        content: Text(
          'Version v${update.latestVersion} is available.\n\n'
          'Download the installer now, or open the release page instead.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Later'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              UpdateChecker.openReleasePage(update.releaseUrl);
            },
            child: const Text('Open Release Page'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              _downloadAndInstall(context, update);
            },
            child: const Text('Download & Install'),
          ),
        ],
      ),
    );
  }

  Future<void> _downloadAndInstall(
    BuildContext context,
    UpdateInfo update,
  ) async {
    final asset = update.assetForPlatform();
    if (asset == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('No installer is available for this platform yet.'),
        ),
      );
      return;
    }

    final progress = ValueNotifier<double>(0);
    final status = ValueNotifier<String>('Downloading ${asset.name}…');
    final installing = ValueNotifier<bool>(false);

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        title: const Text('Updating Smart Downloader'),
        content: ValueListenableBuilder<String>(
          valueListenable: status,
          builder: (context, label, _) {
            final active = installing.value;
            final fraction = progress.value;
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label),
                const SizedBox(height: 16),
                LinearProgressIndicator(
                  value: !active && fraction > 0 ? fraction : null,
                ),
              ],
            );
          },
        ),
      ),
    );

    String? error;
    try {
      final file = await UpdateInstaller.download(
        asset,
        (received, total) {
          if (total != null && total > 0) {
            progress.value = received / total;
          }
          status.value = 'Downloading ${asset.name}\n'
              '${_formatBytes(received)} of '
              '${total != null ? _formatBytes(total) : '…'}';
        },
      );

      installing.value = true;
      if (Platform.isWindows) {
        status.value =
            'Running the installer…\nThe app will be updated in place.';
        final result = await UpdateInstaller.installWindows(file);
        if (result.exitCode != 0) {
          error = 'The installer failed (exit ${result.exitCode}).';
        }
      } else if (Platform.isMacOS) {
        status.value = 'Installing to Applications…';
        await UpdateInstaller.installMacOS(file);
      } else {
        error = 'Please open the release page to install on this platform.';
      }

      await UpdateInstaller.cleanup(file);
    } on UpdateInstallException catch (e) {
      error = e.message;
    } catch (e) {
      error = e.toString();
    }
    if (!context.mounted) return;
    Navigator.of(context, rootNavigator: true).pop();

    if (error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error),
          duration: const Duration(seconds: 6),
        ),
      );
      return;
    }

    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Update complete'),
        content: const Text(
          'Smart Downloader was updated to the latest version.\n'
          'Please restart the app to use it.',
        ),
        actions: [
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  String _formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  Widget _buildInfoRow(
    BuildContext context, {
    required IconData icon,
    required String label,
    required String value,
    Widget? trailing,
  }) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Icon(icon, size: 20, color: theme.colorScheme.primary),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              Text(
                value,
                style: theme.textTheme.bodyLarge,
              ),
            ],
          ),
        ),
        ? trailing,
      ],
    );
  }
}

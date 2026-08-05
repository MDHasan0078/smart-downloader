import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import '../engine/engine_provider.dart';
import '../services/update_checker.dart';
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
                          final version = snapshot.data?.version ?? '2.0.0';
                          return _buildInfoRow(
                            context,
                            icon: Icons.apps,
                            label: 'Version',
                            value: 'v$version',
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
          '${UpdateChecker.installInstructions(update.latestVersion)}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Later'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(dialogContext);
              UpdateChecker.openReleasePage(update.releaseUrl);
            },
            child: const Text('Open Release Page'),
          ),
        ],
      ),
    );
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

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';
import '../engine/engine_provider.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      body: Consumer<EngineProvider>(
        builder: (context, provider, child) {
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
                      _buildInfoRow(
                        context,
                        icon: Icons.apps,
                        label: 'Version',
                        value: '2.0.0',
                      ),
                      const SizedBox(height: 8),
                      _buildInfoRow(
                        context,
                        icon: Icons.code,
                        label: 'Engine',
                        value: 'Python (PyInstaller)',
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

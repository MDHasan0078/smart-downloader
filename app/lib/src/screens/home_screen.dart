import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';
import '../engine/engine_provider.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _urlController = TextEditingController();
  String _selectedMode = 'video';
  String _selectedVideoFormat = 'mp4';
  String _selectedVideoQuality = 'best';
  String _selectedAudioFormat = 'mp3';
  String _selectedAudioQuality = '192';

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  void _addDownload() {
    final url = _urlController.text.trim();
    if (url.isEmpty) return;

    context.read<EngineProvider>().addDownload(url);
    _urlController.clear();

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Added to queue: $url'),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                SvgPicture.asset(
                  'lib/src/assets/icons/folder-download-symbolic.svg',
                  width: 32,
                  height: 32,
                  colorFilter: ColorFilter.mode(
                    colorScheme.primary,
                    BlendMode.srcIn,
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  'Smart Downloader',
                  style: theme.textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 32),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Add Download',
                      style: theme.textTheme.titleLarge,
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _urlController,
                      decoration: InputDecoration(
                        hintText: 'https://youtube.com/watch?v=...',
                        labelText: 'Video URL',
                        border: const OutlineInputBorder(),
                        prefixIcon: const Icon(Icons.link),
                        suffixIcon: IconButton(
                          icon: SvgPicture.asset(
                            'lib/src/assets/icons/media-record-symbolic.svg',
                            width: 20,
                            height: 20,
                            colorFilter: ColorFilter.mode(
                              colorScheme.onPrimary,
                              BlendMode.srcIn,
                            ),
                          ),
                          style: ButtonStyle(
                            backgroundColor: WidgetStateProperty.all(
                              colorScheme.primary,
                            ),
                          ),
                          onPressed: _addDownload,
                        ),
                      ),
                      onSubmitted: (_) => _addDownload(),
                    ),
                    const SizedBox(height: 20),
                    _buildModeSelector(theme),
                    const SizedBox(height: 16),
                    _buildFormatQualityRow(theme),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Quick Actions',
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 16),
                    Wrap(
                      spacing: 12,
                      runSpacing: 12,
                      children: [
                        _buildActionChip(
                          context,
                          icon: Icons.folder_open,
                          label: 'Open Downloads',
                          onTap: () {},
                        ),
                        _buildActionChip(
                          context,
                          icon: Icons.refresh,
                          label: 'Check Engine',
                          onTap: () {
                            context.read<EngineProvider>().client.checkDeps();
                          },
                        ),
                        _buildActionChip(
                          context,
                          icon: Icons.settings,
                          label: 'Settings',
                          onTap: () {},
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildModeSelector(ThemeData theme) {
    return Row(
      children: [
        Text('Mode:', style: theme.textTheme.bodyLarge),
        const SizedBox(width: 16),
        SegmentedButton<String>(
          segments: const [
            ButtonSegment(
              value: 'video',
              label: Text('Video'),
              icon: Icon(Icons.videocam),
            ),
            ButtonSegment(
              value: 'audio',
              label: Text('Audio'),
              icon: Icon(Icons.audiotrack),
            ),
          ],
          selected: {_selectedMode},
          onSelectionChanged: (selected) {
            setState(() => _selectedMode = selected.first);
          },
        ),
      ],
    );
  }

  Widget _buildFormatQualityRow(ThemeData theme) {
    return Row(
      children: [
        if (_selectedMode == 'video') ...[
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: _selectedVideoFormat,
              decoration: const InputDecoration(
                labelText: 'Format',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'mp4', child: Text('MP4')),
                DropdownMenuItem(value: 'mkv', child: Text('MKV')),
                DropdownMenuItem(value: 'webm', child: Text('WebM')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _selectedVideoFormat = value);
              },
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: _selectedVideoQuality,
              decoration: const InputDecoration(
                labelText: 'Quality',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'best', child: Text('Best')),
                DropdownMenuItem(value: '1080p', child: Text('1080p')),
                DropdownMenuItem(value: '720p', child: Text('720p')),
                DropdownMenuItem(value: '480p', child: Text('480p')),
                DropdownMenuItem(value: '360p', child: Text('360p')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _selectedVideoQuality = value);
              },
            ),
          ),
        ] else ...[
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: _selectedAudioFormat,
              decoration: const InputDecoration(
                labelText: 'Format',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'mp3', child: Text('MP3')),
                DropdownMenuItem(value: 'flac', child: Text('FLAC')),
                DropdownMenuItem(value: 'opus', child: Text('Opus')),
                DropdownMenuItem(value: 'm4a', child: Text('M4A')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _selectedAudioFormat = value);
              },
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: DropdownButtonFormField<String>(
              initialValue: _selectedAudioQuality,
              decoration: const InputDecoration(
                labelText: 'Quality',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: '320', child: Text('320 kbps')),
                DropdownMenuItem(value: '256', child: Text('256 kbps')),
                DropdownMenuItem(value: '192', child: Text('192 kbps')),
                DropdownMenuItem(value: '128', child: Text('128 kbps')),
              ],
              onChanged: (value) {
                if (value != null) setState(() => _selectedAudioQuality = value);
              },
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildActionChip(
    BuildContext context, {
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return ActionChip(
      avatar: Icon(icon, size: 18),
      label: Text(label),
      onPressed: onTap,
    );
  }
}

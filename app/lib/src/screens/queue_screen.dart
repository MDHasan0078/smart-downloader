import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:provider/provider.dart';
import '../engine/engine_provider.dart';
import '../widgets/download_row.dart';

class QueueScreen extends StatelessWidget {
  const QueueScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      body: Consumer<EngineProvider>(
        builder: (context, provider, child) {
          if (provider.tasks.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SvgPicture.asset(
                    'lib/src/assets/icons/folder-download-symbolic.svg',
                    width: 64,
                    height: 64,
                    colorFilter: ColorFilter.mode(
                      colorScheme.primary,
                      BlendMode.srcIn,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No downloads in queue',
                    style: theme.textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Add a URL from the Home tab',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            );
          }

          return Column(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                child: Row(
                  children: [
                    Text(
                      'Downloads (${provider.tasks.length})',
                      style: theme.textTheme.titleMedium,
                    ),
                    const Spacer(),
                    if (provider.tasks.any((t) => t.isCompleted))
                      TextButton.icon(
                        onPressed: () => provider.clearCompleted(),
                        icon: const Icon(Icons.cleaning_services, size: 18),
                        label: const Text('Clear Completed'),
                      ),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: provider.tasks.length,
                  itemBuilder: (context, index) {
                    final task = provider.tasks[index];
                    return DownloadRow(
                      task: task,
                      onPause: () => provider.pauseTask(task.id),
                      onResume: () => provider.resumeTask(task.id),
                      onCancel: () => provider.cancelTask(task.id),
                      onRestart: () => provider.restartTask(task.id),
                      onRemove: () => provider.removeTask(task.id),
                    );
                  },
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

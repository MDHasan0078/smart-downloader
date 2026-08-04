import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../models/download_task.dart';

class DownloadRow extends StatelessWidget {
  final DownloadTask task;
  final VoidCallback? onPause;
  final VoidCallback? onResume;
  final VoidCallback? onCancel;
  final VoidCallback? onRestart;
  final VoidCallback? onRemove;

  const DownloadRow({
    super.key,
    required this.task,
    this.onPause,
    this.onResume,
    this.onCancel,
    this.onRestart,
    this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                _buildStateIcon(context),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        task.title.isNotEmpty ? task.title : task.url,
                        style: theme.textTheme.bodyLarge?.copyWith(
                          fontWeight: FontWeight.w500,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      if (task.duration.isNotEmpty || task.sizeStr.isNotEmpty)
                        Text(
                          [
                            if (task.duration.isNotEmpty) task.duration,
                            if (task.sizeStr.isNotEmpty) task.sizeStr,
                          ].join(' • '),
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurfaceVariant,
                          ),
                        ),
                    ],
                  ),
                ),
                if (task.isDownloading) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: colorScheme.primaryContainer,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '${task.progress.toStringAsFixed(1)}%',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.onPrimaryContainer,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                ],
                _buildActions(context),
              ],
            ),
            if (task.isDownloading) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: LinearProgressIndicator(
                      value: task.progress / 100,
                      minHeight: 6,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  if (task.speed.isNotEmpty)
                    Row(
                      children: [
                        SvgPicture.asset(
                          'lib/src/assets/icons/weather-clear-symbolic.svg',
                          width: 14,
                          height: 14,
                          colorFilter: ColorFilter.mode(
                            colorScheme.primary,
                            BlendMode.srcIn,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          task.speed,
                          style: theme.textTheme.bodySmall,
                        ),
                      ],
                    ),
                  if (task.eta.isNotEmpty)
                    Row(
                      children: [
                        SvgPicture.asset(
                          'lib/src/assets/icons/weather-clear-night-symbolic.svg',
                          width: 14,
                          height: 14,
                          colorFilter: ColorFilter.mode(
                            colorScheme.primary,
                            BlendMode.srcIn,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Text(
                          'ETA: ${task.eta}',
                          style: theme.textTheme.bodySmall,
                        ),
                      ],
                    ),
                ],
              ),
            ],
            if (task.isError) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Row(
                  children: [
                    SvgPicture.asset(
                      'lib/src/assets/icons/dialog-error-symbolic.svg',
                      width: 16,
                      height: 16,
                      colorFilter: ColorFilter.mode(
                        colorScheme.onErrorContainer,
                        BlendMode.srcIn,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        task.error,
                        style: TextStyle(
                          color: colorScheme.onErrorContainer,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildStateIcon(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    switch (task.state) {
      case TaskState.pending:
        return SvgPicture.asset(
          'lib/src/assets/icons/media-playback-start-symbolic.svg',
          width: 24,
          height: 24,
          colorFilter: ColorFilter.mode(
            colorScheme.onSurfaceVariant,
            BlendMode.srcIn,
          ),
        );
      case TaskState.downloading:
        return SvgPicture.asset(
          'lib/src/assets/icons/media-record-symbolic.svg',
          width: 24,
          height: 24,
          colorFilter: ColorFilter.mode(
            colorScheme.primary,
            BlendMode.srcIn,
          ),
        );
      case TaskState.paused:
        return SvgPicture.asset(
          'lib/src/assets/icons/media-playback-pause-symbolic.svg',
          width: 24,
          height: 24,
          colorFilter: const ColorFilter.mode(
            Colors.orange,
            BlendMode.srcIn,
          ),
        );
      case TaskState.completed:
        return SvgPicture.asset(
          'lib/src/assets/icons/emblem-ok-symbolic.svg',
          width: 24,
          height: 24,
          colorFilter: const ColorFilter.mode(
            Colors.green,
            BlendMode.srcIn,
          ),
        );
      case TaskState.error:
        return SvgPicture.asset(
          'lib/src/assets/icons/dialog-error-symbolic.svg',
          width: 24,
          height: 24,
          colorFilter: ColorFilter.mode(
            colorScheme.error,
            BlendMode.srcIn,
          ),
        );
      case TaskState.cancelled:
        return SvgPicture.asset(
          'lib/src/assets/icons/process-stop-symbolic.svg',
          width: 24,
          height: 24,
          colorFilter: ColorFilter.mode(
            colorScheme.onSurfaceVariant,
            BlendMode.srcIn,
          ),
        );
    }
  }

  Widget _buildActions(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (task.isDownloading)
          IconButton(
            icon: SvgPicture.asset(
              'lib/src/assets/icons/media-playback-pause-symbolic.svg',
              width: 18,
              height: 18,
              colorFilter: ColorFilter.mode(
                colorScheme.onSurfaceVariant,
                BlendMode.srcIn,
              ),
            ),
            onPressed: onPause,
            tooltip: 'Pause',
          ),
        if (task.isPaused)
          IconButton(
            icon: SvgPicture.asset(
              'lib/src/assets/icons/media-playback-start-symbolic.svg',
              width: 18,
              height: 18,
              colorFilter: ColorFilter.mode(
                colorScheme.primary,
                BlendMode.srcIn,
              ),
            ),
            onPressed: onResume,
            tooltip: 'Resume',
          ),
        if (task.isError || task.isCancelled)
          IconButton(
            icon: SvgPicture.asset(
              'lib/src/assets/icons/view-refresh-symbolic.svg',
              width: 18,
              height: 18,
              colorFilter: ColorFilter.mode(
                colorScheme.primary,
                BlendMode.srcIn,
              ),
            ),
            onPressed: onRestart,
            tooltip: 'Restart',
          ),
        if (!task.isCompleted && !task.isCancelled)
          IconButton(
            icon: SvgPicture.asset(
              'lib/src/assets/icons/process-stop-symbolic.svg',
              width: 18,
              height: 18,
              colorFilter: ColorFilter.mode(
                colorScheme.error,
                BlendMode.srcIn,
              ),
            ),
            onPressed: onCancel,
            tooltip: 'Cancel',
          ),
        if (task.isCompleted || task.isCancelled || task.isError)
          IconButton(
            icon: Icon(
              Icons.close,
              size: 18,
              color: colorScheme.onSurfaceVariant,
            ),
            onPressed: onRemove,
            tooltip: 'Remove',
          ),
      ],
    );
  }
}

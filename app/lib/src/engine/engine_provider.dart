import 'package:flutter/foundation.dart';
import 'engine_client.dart';
import '../models/download_task.dart';
import '../models/app_config.dart';

class EngineProvider extends ChangeNotifier {
  final EngineClient _client = EngineClient();
  final List<DownloadTask> _tasks = [];
  AppConfig _config = AppConfig();
  bool _initialized = false;
  bool _disposed = false;
  String? _error;

  EngineClient get client => _client;
  List<DownloadTask> get tasks => List.unmodifiable(_tasks);
  AppConfig get config => _config;
  bool get isRunning => _client.isRunning;
  bool get initialized => _initialized;
  String? get error => _error;

  EngineProvider() {
    _client.events.listen(_handleEvent);
  }

  void _safeNotify() {
    if (_disposed) return;
    notifyListeners();
  }

  void _handleEvent(Map<String, dynamic> event) {
    final eventType = event['event'] as String?;

    switch (eventType) {
      case 'progress':
        _handleProgress(event);
        break;
      case 'finished':
        _handleFinished(event);
        break;
      case 'error':
        _error = event['message'] as String?;
        break;
      case 'stderr':
        // Engine diagnostic output, ignore for now
        break;
      case 'engine_exit':
        _initialized = false;
        break;
    }
    _safeNotify();
  }

  void _handleProgress(Map<String, dynamic> event) {
    final taskId = event['task_id'] as String;
    final task = _tasks.where((t) => t.id == taskId).firstOrNull;
    if (task == null) return;

    task.progress = (event['percent'] as num?)?.toDouble() ?? 0.0;
    task.speed = event['speed'] as String? ?? '';
    task.eta = event['eta'] as String? ?? '';
    task.sizeStr = event['size'] as String? ?? '';
    task.state = TaskState.downloading;
  }

  void _handleFinished(Map<String, dynamic> event) {
    final taskId = event['task_id'] as String;
    final task = _tasks.where((t) => t.id == taskId).firstOrNull;
    if (task == null) return;

    final success = event['success'] as bool? ?? false;
    if (success) {
      task.state = TaskState.completed;
      task.progress = 100.0;
    } else {
      task.state = TaskState.error;
      task.error = event['message'] as String? ?? 'Download failed';
    }
  }

  Future<void> initialize(String enginePath) async {
    try {
      _error = null;
      await _client.start(enginePath);

      final pingResult = await _client.ping();
      if (pingResult['pong'] != true) {
        _error = 'Engine ping failed';
      _safeNotify();
        return;
      }

      final depsResult = await _client.checkDeps();
      final settingsResult = await _client.getSettings();
      final settings = settingsResult['settings'] as Map<String, dynamic>? ?? {};

      _config = AppConfig(
        outputDir: settings['download_dir'] as String? ?? '',
        quality: settings['default_video_quality'] as String? ?? 'best',
        format: settings['default_video_format'] as String? ?? 'mp4',
        useCookies: settings['use_cookies'] as bool? ?? false,
        ytDlpVersion: depsResult['yt_dlp_version'] as String?,
        ffmpegVersion: depsResult['binaries']?['ffmpeg_version'] as String?,
      );

      _initialized = true;
    _safeNotify();
    } catch (e) {
      _error = 'Failed to initialize engine: $e';
    _safeNotify();
    }
  }

  Future<void> addDownload(String url) async {
    if (!_initialized) {
      _error = 'Engine not initialized';
    _safeNotify();
      return;
    }

    final taskId = 't${DateTime.now().millisecondsSinceEpoch}';
    final task = DownloadTask(id: taskId, url: url);
    _tasks.add(task);
    _safeNotify();

    try {
      final result = await _client.startDownload(
        url: url,
        videoFormat: _config.format,
        videoQuality: _config.quality,
        downloadDir: _config.outputDir.isNotEmpty ? _config.outputDir : null,
      );
      final assignedTaskId = result['task_id'] as String?;
      if (assignedTaskId != null && assignedTaskId != taskId) {
        task.id = assignedTaskId;
      }
    } catch (e) {
      task.state = TaskState.error;
      task.error = e.toString();
    _safeNotify();
    }
  }

  Future<void> pauseTask(String taskId) async {
    final task = _tasks.where((t) => t.id == taskId).firstOrNull;
    if (task == null) return;

    try {
      await _client.pause(taskId);
      task.state = TaskState.paused;
    _safeNotify();
    } catch (e) {
      _error = e.toString();
    _safeNotify();
    }
  }

  Future<void> resumeTask(String taskId) async {
    final task = _tasks.where((t) => t.id == taskId).firstOrNull;
    if (task == null) return;

    try {
      await _client.resume(taskId);
      task.state = TaskState.downloading;
    _safeNotify();
    } catch (e) {
      _error = e.toString();
    _safeNotify();
    }
  }

  Future<void> cancelTask(String taskId) async {
    final task = _tasks.where((t) => t.id == taskId).firstOrNull;
    if (task == null) return;

    try {
      await _client.cancel(taskId);
      task.state = TaskState.cancelled;
    _safeNotify();
    } catch (e) {
      _error = e.toString();
    _safeNotify();
    }
  }

  Future<void> restartTask(String taskId) async {
    final task = _tasks.where((t) => t.id == taskId).firstOrNull;
    if (task == null) return;

    try {
      await _client.restart(taskId);
      task.state = TaskState.downloading;
      task.progress = 0.0;
      task.error = '';
    _safeNotify();
    } catch (e) {
      _error = e.toString();
    _safeNotify();
    }
  }

  void removeTask(String taskId) {
    _tasks.removeWhere((t) => t.id == taskId);
    _safeNotify();
  }

  void clearCompleted() {
    _tasks.removeWhere((t) => t.isCompleted || t.isCancelled);
    _safeNotify();
  }

  void updateConfig(AppConfig newConfig) {
    _config = newConfig;
    _client.setSettings(newConfig.toMap());
    _safeNotify();
  }

  void clearError() {
    _error = null;
    _safeNotify();
  }

  @override
  void dispose() {
    _disposed = true;
    _client.dispose();
    super.dispose();
  }
}

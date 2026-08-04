import 'dart:async';
import 'dart:convert';
import 'dart:io';

class EngineClient {
  Process? _process;
  final _eventController = StreamController<Map<String, dynamic>>.broadcast();
  final _replyController = StreamController<Map<String, dynamic>>.broadcast();
  final _pendingRequests = <String, Completer<Map<String, dynamic>>>{};
  int _requestCounter = 0;
  bool _running = false;

  Stream<Map<String, dynamic>> get events => _eventController.stream;
  Stream<Map<String, dynamic>> get replies => _replyController.stream;
  bool get isRunning => _running;

  Future<void> start(String enginePath) async {
    if (_running) return;

    final engineBin = Platform.isWindows ? '$enginePath/engine.exe' : '$enginePath/engine';

    _process = await Process.start(engineBin, [], runInShell: Platform.isWindows);
    _running = true;

    _process!.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
      if (line.isEmpty) return;
      try {
        final msg = jsonDecode(line) as Map<String, dynamic>;

        if (msg.containsKey('event') && msg['event'] == 'reply') {
          final id = msg['id'] as String?;
          if (id != null && _pendingRequests.containsKey(id)) {
            _pendingRequests[id]!.complete(msg);
            _pendingRequests.remove(id);
          }
          _replyController.add(msg);
        } else if (msg.containsKey('event')) {
          _eventController.add(msg);
        }
      } catch (_) {}
    });

    _process!.stderr
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
      _eventController.add({'event': 'stderr', 'message': line});
    });

    _process!.exitCode.then((code) {
      _running = false;
      _eventController.add({'event': 'engine_exit', 'code': code});
      for (final c in _pendingRequests.values) {
        c.completeError(Exception('Engine exited with code $code'));
      }
      _pendingRequests.clear();
    });
  }

  Future<void> stop() async {
    _process?.kill(ProcessSignal.sigterm);
    _running = false;
  }

  String _nextId() => 'req_${++_requestCounter}';

  Future<Map<String, dynamic>> sendCommand(String cmd, [Map<String, dynamic>? args]) async {
    if (!_running || _process == null) throw Exception('Engine not running');

    final id = _nextId();
    final msg = {'id': id, 'cmd': cmd, ...?args};

    final completer = Completer<Map<String, dynamic>>();
    _pendingRequests[id] = completer;

    _process!.stdin.writeln(jsonEncode(msg));

    return completer.future.timeout(
      const Duration(seconds: 30),
      onTimeout: () {
        _pendingRequests.remove(id);
        throw TimeoutException('Engine command timed out: $cmd');
      },
    );
  }

  Future<Map<String, dynamic>> ping() => sendCommand('ping');

  Future<Map<String, dynamic>> checkDeps() => sendCommand('check_deps');

  Future<Map<String, dynamic>> getSettings() => sendCommand('settings_get');

  Future<Map<String, dynamic>> setSettings(Map<String, dynamic> settings) =>
      sendCommand('settings_set', {'settings': settings});

  Future<Map<String, dynamic>> getUrlInfo(String url) =>
      sendCommand('get_info', {'url': url});

  Future<Map<String, dynamic>> startDownload({
    required String url,
    String mode = 'video',
    String? videoFormat,
    String? videoQuality,
    String? audioFormat,
    String? audioQuality,
    String? downloadDir,
    String? cookiesFile,
    String? taskId,
  }) {
    final args = <String, dynamic>{'url': url};
    if (mode.isNotEmpty) args['mode'] = mode;
    if (videoFormat != null) args['video_format'] = videoFormat;
    if (videoQuality != null) args['video_quality'] = videoQuality;
    if (audioFormat != null) args['audio_format'] = audioFormat;
    if (audioQuality != null) args['audio_quality'] = audioQuality;
    if (downloadDir != null) args['download_dir'] = downloadDir;
    if (cookiesFile != null) args['cookies_file'] = cookiesFile;
    if (taskId != null) args['task_id'] = taskId;
    return sendCommand('start', args);
  }

  Future<Map<String, dynamic>> pause(String taskId) =>
      sendCommand('pause', {'task_id': taskId});

  Future<Map<String, dynamic>> resume(String taskId) =>
      sendCommand('resume', {'task_id': taskId});

  Future<Map<String, dynamic>> cancel(String taskId) =>
      sendCommand('cancel', {'task_id': taskId});

  Future<Map<String, dynamic>> restart(String taskId) =>
      sendCommand('restart', {'task_id': taskId});

  void dispose() {
    stop();
    _eventController.close();
    _replyController.close();
    for (final c in _pendingRequests.values) {
      if (!c.isCompleted) c.completeError(Exception('Client disposed'));
    }
    _pendingRequests.clear();
  }
}

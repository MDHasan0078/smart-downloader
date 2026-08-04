enum TaskState { pending, downloading, paused, completed, error, cancelled }

class DownloadTask {
  String id;
  String url;
  String title;
  String thumbnail;
  String duration;
  String sizeStr;
  double progress;
  String speed;
  String eta;
  String error;
  TaskState state;

  DownloadTask({
    required this.id,
    this.url = '',
    this.title = '',
    this.thumbnail = '',
    this.duration = '',
    this.sizeStr = '',
    this.progress = 0.0,
    this.speed = '',
    this.eta = '',
    this.error = '',
    this.state = TaskState.pending,
  });

  bool get isCompleted => state == TaskState.completed;
  bool get isError => state == TaskState.error;
  bool get isDownloading => state == TaskState.downloading;
  bool get isPaused => state == TaskState.paused;
  bool get isCancelled => state == TaskState.cancelled;
}

class AppConfig {
  final String outputDir;
  final String quality;
  final String format;
  final bool useCookies;
  final String? ytDlpVersion;
  final String? ffmpegVersion;

  const AppConfig({
    this.outputDir = '',
    this.quality = 'best',
    this.format = 'mp4',
    this.useCookies = false,
    this.ytDlpVersion,
    this.ffmpegVersion,
  });

  AppConfig copyWith({
    String? outputDir,
    String? quality,
    String? format,
    bool? useCookies,
    String? ytDlpVersion,
    String? ffmpegVersion,
  }) {
    return AppConfig(
      outputDir: outputDir ?? this.outputDir,
      quality: quality ?? this.quality,
      format: format ?? this.format,
      useCookies: useCookies ?? this.useCookies,
      ytDlpVersion: ytDlpVersion ?? this.ytDlpVersion,
      ffmpegVersion: ffmpegVersion ?? this.ffmpegVersion,
    );
  }

  Map<String, dynamic> toMap() => {
    'output_dir': outputDir,
    'quality': quality,
    'format': format,
    'use_cookies': useCookies,
  };
}

import 'package:flutter/material.dart';

class AppTheme {
  static const _primaryColor = Color(0xFF6750A4);

  static ThemeData light() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorSchemeSeed: _primaryColor,
      scaffoldBackgroundColor: const Color(0xFFFDFBFF),
    );
  }

  static ThemeData dark() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorSchemeSeed: _primaryColor,
      scaffoldBackgroundColor: const Color(0xFF1C1B1F),
    );
  }
}

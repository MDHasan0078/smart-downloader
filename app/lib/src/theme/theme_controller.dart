import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeController extends ChangeNotifier {
  static const _prefsKey = 'theme_mode';
  static const _dark = 'dark';
  static const _light = 'light';

  ThemeMode _themeMode = ThemeMode.dark;

  ThemeMode get themeMode => _themeMode;
  bool get isDark => _themeMode == ThemeMode.dark;

  Future<void> load() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final value = prefs.getString(_prefsKey);
      if (value == _light) {
        _themeMode = ThemeMode.light;
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> setDark(bool value) async {
    _themeMode = value ? ThemeMode.dark : ThemeMode.light;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsKey, value ? _dark : _light);
    } catch (_) {}
  }
}

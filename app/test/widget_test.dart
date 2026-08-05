import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:smart_downloader/main.dart';
import 'package:smart_downloader/src/engine/engine_provider.dart';
import 'package:smart_downloader/src/screens/settings_screen.dart';
import 'package:smart_downloader/src/theme/theme_controller.dart';

void main() {
  testWidgets('App renders', (WidgetTester tester) async {
    await tester.pumpWidget(const SmartDownloaderApp());
    await tester.pumpAndSettle();

    expect(find.text('Smart Downloader'), findsOneWidget);
    expect(find.text('Add Download'), findsOneWidget);
    expect(find.text('Queue'), findsOneWidget);
    expect(find.text('Settings'), findsWidgets);
  });

  testWidgets('Settings toggles dark theme', (WidgetTester tester) async {
    final controller = ThemeController();
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: controller),
          ChangeNotifierProvider(create: (_) => EngineProvider()),
        ],
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(find.text('Dark Theme'), 200);
    final switchFinder = find.byType(SwitchListTile);
    expect(tester.widget<SwitchListTile>(switchFinder).value, isTrue);
    await tester.ensureVisible(switchFinder);
    await tester.pumpAndSettle();

    await tester.tap(switchFinder);
    await tester.pumpAndSettle();
    expect(controller.isDark, isFalse);
  });
}

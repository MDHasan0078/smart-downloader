import 'package:flutter_test/flutter_test.dart';
import 'package:smart_downloader/main.dart';

void main() {
  testWidgets('App renders', (WidgetTester tester) async {
    await tester.pumpWidget(const SmartDownloaderApp());
    await tester.pumpAndSettle();
    expect(find.text('Smart Downloader'), findsOneWidget);
  });
}

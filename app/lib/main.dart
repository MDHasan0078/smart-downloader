import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:window_manager/window_manager.dart';
import 'src/engine/engine_locator.dart';
import 'src/engine/engine_provider.dart';
import 'src/screens/home_screen.dart';
import 'src/screens/queue_screen.dart';
import 'src/screens/settings_screen.dart';
import 'src/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await windowManager.ensureInitialized();

  const windowOptions = WindowOptions(
    size: Size(900, 600),
    minimumSize: Size(800, 500),
    center: true,
    title: 'Smart Downloader',
  );
  await windowManager.waitUntilReadyToShow(windowOptions, () async {
    await windowManager.show();
    await windowManager.focus();
  });

  runApp(const SmartDownloaderApp());
}

class SmartDownloaderApp extends StatelessWidget {
  const SmartDownloaderApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => EngineProvider(),
      child: MaterialApp(
        title: 'Smart Downloader',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light(),
        darkTheme: AppTheme.dark(),
        themeMode: ThemeMode.system,
        home: const AppShell(),
      ),
    );
  }
}

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _selectedIndex = 0;

  final _screens = const [
    HomeScreen(),
    QueueScreen(),
    SettingsScreen(),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = context.read<EngineProvider>();
      try {
        provider.initialize(EngineLocator.engineDir);
      } catch (e) {
        // Engine binary missing; UI shows status in Settings tab.
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Row(
        children: [
          NavigationRail(
            selectedIndex: _selectedIndex,
            onDestinationSelected: (i) => setState(() => _selectedIndex = i),
            destinations: const [
              NavigationRailDestination(
                icon: Icon(Icons.link),
                label: Text('Add'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.queue),
                label: Text('Queue'),
              ),
              NavigationRailDestination(
                icon: Icon(Icons.settings),
                label: Text('Settings'),
              ),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: _screens[_selectedIndex]),
        ],
      ),
    );
  }
}

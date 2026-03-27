import SwiftUI
import AppIntents

@main
struct GoalsApp: App {
    @State private var store = GoalsStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(store)
                .task {
                    GoalsShortcuts.updateAppShortcutParameters()
                }
        }
    }
}

import SwiftUI

struct ContentView: View {
    var body: some View {
        TabView {
            DailyGoalsView()
                .tabItem {
                    Label("Today", systemImage: "calendar")
                }

            YearGoalsView()
                .tabItem {
                    Label("Year", systemImage: "trophy")
                }

            BacklogView()
                .tabItem {
                    Label("Backlog", systemImage: "tray.full")
                }

            BulbsView()
                .tabItem {
                    Label("Bulbs", systemImage: "lightbulb")
                }

            LogView()
                .tabItem {
                    Label("Log", systemImage: "chart.bar")
                }
        }
    }
}

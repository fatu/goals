import SwiftUI

struct ContentView: View {
    var body: some View {
        if #available(iOS 18.0, *) {
            TabView {
                Tab("Today", systemImage: "calendar") {
                    DailyGoalsView()
                }
                Tab("Year", systemImage: "trophy") {
                    YearGoalsView()
                }
                Tab("Bi-Weekly", systemImage: "calendar.badge.clock") {
                    BiweeklyGoalsView()
                }
                Tab("Backlog", systemImage: "tray.full") {
                    BacklogView()
                }
                Tab("Bulbs", systemImage: "lightbulb") {
                    BulbsView()
                }
                Tab("Log", systemImage: "chart.bar") {
                    LogView()
                }
            }
            .tabViewStyle(.sidebarAdaptable)
        } else {
            TabView {
                DailyGoalsView()
                    .tabItem { Label("Today", systemImage: "calendar") }
                YearGoalsView()
                    .tabItem { Label("Year", systemImage: "trophy") }
                BiweeklyGoalsView()
                    .tabItem { Label("Bi-Weekly", systemImage: "calendar.badge.clock") }
                BacklogView()
                    .tabItem { Label("Backlog", systemImage: "tray.full") }
                BulbsView()
                    .tabItem { Label("Bulbs", systemImage: "lightbulb") }
                LogView()
                    .tabItem { Label("Log", systemImage: "chart.bar") }
            }
        }
    }
}

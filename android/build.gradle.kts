// Root aggregate — plugin versions are in settings.gradle.kts (pluginManagement).

tasks.register("clean", Delete::class) {
    delete(rootProject.layout.buildDirectory)
}
